import requests
import json
import time
import uuid
from typing import List, Dict, Tuple, Optional
from .base import (
    FullLLMInterface, 
    ModelProvider, 
    ChatMessage, 
    ChatResponse, 
    ThreadInfo, 
    FileInfo,
    KnowledgeBase,
    RAGResponse
)
from ..utils.retry import retry_on_rate_limit
from ..services.conversation import get_conversation_manager
from ..core.logger import get_logger

logger = get_logger(__name__)


class GeminiModel(FullLLMInterface):
    """
    Google Gemini 2024 模型實作
    
    📋 架構職責分工：
    ✅ RESPONSIBILITIES (模型層職責):
      - 實作統一的 FullLLMInterface 接口
      - 提供 chat_with_user() 文字對話功能
      - 提供 transcribe_audio() 音訊轉錄功能
      - 管理對話歷史和上下文
      - 處理 Google AI API 限流和重試邏輯

    🎯 模型特色：
    - Semantic Retrieval API: Google 的語義檢索服務
    - Multimodal RAG: 支援文字、圖片、影片的混合檢索
    - Long Context Window: Gemini Pro 1.5 支援百萬 token 上下文

    ⚠️ 功能限制：
    - 音訊轉錄: 使用多模態API (Beta階段，可能不穩定)
    - 圖片生成: 目前不支援 (返回 "Gemini 目前不支援圖片生成")
    - Vertex AI 整合: 企業級 AI 平台整合
    - Ranking API: 智慧重排序提升檢索品質
    """
    
    def __init__(self, api_key: str, model_name: str = "gemini-1.5-pro-latest", base_url: str = None, project_id: str = None):
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url or "https://generativelanguage.googleapis.com/v1beta"
        self.project_id = project_id  # Google Cloud 專案 ID，用於 Vertex AI
        
        # Semantic Retrieval API 支援 - 使用有界快取
        from ..core.bounded_cache import BoundedCache
        self.corpora = BoundedCache(max_size=50, ttl=7200)  # 50個語料庫，2小時TTL
        self.default_corpus_name = "chatbot-knowledge"
        
        # Multimodal 和長上下文支援
        self.max_context_tokens = 1000000  # Gemini 1.5 Pro 支援百萬 token
        self.supported_media_types = ['image', 'video', 'audio', 'text']
        
        # Vertex AI 客戶端（可選）
        self.vertex_ai_client = None
        
        # 第三方語音轉錄服務（Google Speech-to-Text）
        self.speech_service = None
        
        # 對話歷史管理
        self.conversation_manager = get_conversation_manager()
    
    def get_provider(self) -> ModelProvider:
        return ModelProvider.GEMINI
    
    def check_connection(self) -> Tuple[bool, Optional[str]]:
        """檢查 Gemini API 連線"""
        try:
            test_message = [ChatMessage(role="user", content="Hello")]
            is_successful, response, error = self.chat_completion(test_message)
            return is_successful, error
        except Exception as e:
            return False, str(e)
    
    @retry_on_rate_limit(max_retries=3, base_delay=1.0)
    def chat_completion(self, messages: List[ChatMessage], **kwargs) -> Tuple[bool, Optional[ChatResponse], Optional[str]]:
        """Gemini Chat Completion with Long Context and Multimodal Support"""
        try:
            # 轉換訊息格式
            gemini_contents = []
            system_instruction = None
            
            for msg in messages:
                if msg.role == "system":
                    system_instruction = msg.content
                else:
                    role = "user" if msg.role == "user" else "model"
                    
                    # 支持多模態內容
                    parts = []
                    if isinstance(msg.content, str):
                        parts.append({"text": msg.content})
                    elif isinstance(msg.content, list):
                        # 多模態內容（文字 + 圖片等）
                        for part in msg.content:
                            if isinstance(part, str):
                                parts.append({"text": part})
                            elif isinstance(part, dict) and 'type' in part:
                                if part['type'] == 'image':
                                    parts.append({
                                        "inline_data": {
                                            "mime_type": part.get('mime_type', 'image/jpeg'),
                                            "data": part['data']
                                        }
                                    })
                                elif part['type'] == 'video':
                                    parts.append({
                                        "file_data": {
                                            "mime_type": part.get('mime_type', 'video/mp4'),
                                            "file_uri": part['uri']
                                        }
                                    })
                    else:
                        parts.append({"text": str(msg.content)})
                    
                    gemini_contents.append({
                        "role": role,
                        "parts": parts
                    })
            
            json_body = {
                "contents": gemini_contents,
                "generationConfig": {
                    "temperature": kwargs.get('temperature', 0.01),
                    "maxOutputTokens": min(kwargs.get('max_tokens', 8192), 8192),  # Gemini Pro 限制
                    "topP": kwargs.get('top_p', 0.8),
                    "topK": kwargs.get('top_k', 40)
                }
            }
            
            # 系統指令支援
            if system_instruction:
                json_body["systemInstruction"] = {
                    "parts": [{"text": system_instruction}]
                }
            
            # 安全設定
            json_body["safetySettings"] = [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH", 
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                }
            ]
            
            endpoint = f'/models/{self.model_name}:generateContent'
            is_successful, response, error_message = self._request('POST', endpoint, body=json_body)
            
            if not is_successful:
                return False, None, error_message
            
            if 'candidates' not in response or not response['candidates']:
                return False, None, "No response generated"
            
            candidate = response['candidates'][0]
            if 'content' not in candidate or not candidate['content']['parts']:
                return False, None, "No content in response"
            
            content = candidate['content']['parts'][0]['text']
            finish_reason = candidate.get('finishReason', 'STOP')
            
            chat_response = ChatResponse(
                content=content,
                finish_reason=finish_reason,
                metadata={
                    'usage': response.get('usageMetadata', {}),
                    'model': response.get('modelVersion', self.model_name),
                    'safety_ratings': candidate.get('safetyRatings', []),
                    'context_tokens': response.get('usageMetadata', {}).get('promptTokenCount', 0)
                }
            )
            
            return True, chat_response, None
            
        except Exception as e:
            return False, None, str(e)
    
    # === RAG 介面實作（使用 Google Semantic Retrieval API） ===
    
    def upload_knowledge_file(self, file_path: str, **kwargs) -> Tuple[bool, Optional[FileInfo], Optional[str]]:
        """使用 Semantic Retrieval API 上傳檔案到知識庫"""
        try:
            import os
            import mimetypes
            
            filename = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            
            # 檢查檔案大小限制（Semantic Retrieval API 限制）
            if file_size > 20 * 1024 * 1024:  # 20MB 限制
                return False, None, f"檔案過大: {file_size / 1024 / 1024:.1f}MB，超過 20MB 限制"
            
            # 1. 確保語料庫存在
            corpus_name = kwargs.get('corpus_name', self.default_corpus_name)
            if self.corpora.get(corpus_name) is None:
                is_successful, corpus, error = self._create_corpus(corpus_name)
                if not is_successful:
                    return False, None, error
                self.corpora.set(corpus_name, corpus)
            
            # 2. 讀取檔案內容並檢測類型
            content_type, _ = mimetypes.guess_type(file_path)
            if not content_type:
                content_type = 'text/plain'
            
            # 支援多模態檔案類型
            is_multimodal = any(media_type in content_type for media_type in ['image', 'video', 'audio'])
            
            if is_multimodal:
                # 多模態檔案處理
                return self._upload_multimodal_file(file_path, corpus_name, **kwargs)
            else:
                # 文字檔案處理
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            
            # 3. 建立文檔
            document_data = {
                "displayName": filename,
                "customMetadata": [
                    {"key": "source_file", "stringValue": filename},
                    {"key": "file_type", "stringValue": content_type},
                    {"key": "upload_time", "stringValue": str(int(time.time()))},
                    {"key": "file_size", "numericValue": file_size}
                ]
            }
            
            corpus_data = self.corpora.get(corpus_name)
            if not corpus_data:
                return False, None, f"Corpus {corpus_name} not found"
            corpus_name_full = corpus_data['name']
            endpoint = f'{corpus_name_full}/documents'
            is_successful, document_response, error = self._request('POST', endpoint, body=document_data)
            
            if not is_successful:
                return False, None, error
            
            # 4. 智慧分塊並上傳
            chunks = self._intelligent_chunk_text(content, kwargs.get('chunk_size', 1000))
            document_name = document_response['name']
            
            successful_chunks = 0
            for i, chunk in enumerate(chunks):
                chunk_data = {
                    "data": {
                        "stringValue": chunk['text']
                    },
                    "customMetadata": [
                        {"key": "chunk_index", "numericValue": i},
                        {"key": "source_file", "stringValue": filename},
                        {"key": "chunk_tokens", "numericValue": chunk.get('tokens', 0)},
                        {"key": "semantic_section", "stringValue": chunk.get('section', 'general')}
                    ]
                }
                
                chunk_endpoint = f'{document_name}/chunks'
                is_successful, _, error = self._request('POST', chunk_endpoint, body=chunk_data)
                if is_successful:
                    successful_chunks += 1
                # 繼續處理其他塊，不因單個塊失敗而停止
            
            if successful_chunks == 0:
                return False, None, "所有文檔塊上傳失敗"
            
            file_info = FileInfo(
                file_id=document_response['name'].split('/')[-1],
                filename=filename,
                size=file_size,
                status='processed',
                purpose='knowledge_base',
                metadata={
                    'corpus': corpus_name,
                    'document_name': document_name,
                    'total_chunks': len(chunks),
                    'successful_chunks': successful_chunks,
                    'content_type': content_type,
                    'is_multimodal': is_multimodal,
                    'upload_time': time.time()
                }
            )
            
            return True, file_info, None
            
        except Exception as e:
            return False, None, str(e)

    def _process_inline_citations(self, text: str, retrieved_sources: List[Dict]) -> Tuple[str, List[Dict]]:
        """
        處理模型回應中的內文引用，將 [檔名] 替換為 [數字] 引用格式，並移除無效引用。
        """
        import re
        
        cited_filenames = set(re.findall(r'\[([^\]]+)\]', text))
        if not cited_filenames:
            # 如果模型回應中沒有引用，則來源列表也應該是空的
            return text, []

        final_sources = []
        citation_map = {}
        next_ref_num = 1
        
        # 從檢索到的來源中，建立有效檔案名的集合
        valid_source_filenames = {source['filename'] for source in retrieved_sources if 'filename' in source}

        # 建立有效引用的對應表
        for filename in sorted(list(cited_filenames)): # sort for consistent numbering
            if filename in valid_source_filenames:
                if filename not in citation_map:
                    citation_map[filename] = next_ref_num
                    next_ref_num += 1

        # 替換有效的引用
        for filename, ref_num in citation_map.items():
            text = text.replace(f'[{filename}]', f'[{ref_num}]')

        # 移除無效的引用
        invalid_filenames = cited_filenames - set(citation_map.keys())
        for filename in invalid_filenames:
            text = text.replace(f'[{filename}]', '')
        
        # 清理可能產生的多餘空格
        text = re.sub(r'\s\s+', ' ', text).strip()

        # 根據有效的引用，建立最終的 sources 列表
        # 使用檔案名來確保我們只為每個被引用的文件添加一次源
        added_filenames = set()
        for source in retrieved_sources:
            filename = source.get('filename')
            if filename in citation_map and filename not in added_filenames:
                final_sources.append(source)
                added_filenames.add(filename)
                
        return text, final_sources

    def _fallback_chat_completion(self, query: str, context_messages: List[ChatMessage], **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        """在 RAG 不可用時，執行標準的上下文聊天"""
        if context_messages:
            messages = context_messages
        else:
            messages = [ChatMessage(role="user", content=query)]
        
        is_successful, response, error = self.chat_completion(messages, **kwargs)
        
        if not is_successful:
            return False, None, error
        
        rag_response = RAGResponse(
            answer=response.content,
            sources=[],
            metadata={
                'model': 'gemini', 
                'no_sources': True,
                'context_messages_count': len(messages)
            }
        )
        return True, rag_response, None

    def query_with_rag(self, query: str, thread_id: str = None, **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        """使用 Google Semantic Retrieval 進行 RAG 查詢（支援長上下文）"""
        try:
            corpus_name = kwargs.get('corpus_name', self.default_corpus_name)
            context_messages = kwargs.get('context_messages', [])
            
            if self.corpora.get(corpus_name) is None:
                return self._fallback_chat_completion(query, context_messages, **kwargs)
            
            # 1. 使用 Semantic Retrieval 搜尋相關內容
            corpus_data = self.corpora.get(corpus_name)
            if not corpus_data:
                return False, None, f"Corpus {corpus_name} not found"
            corpus_name_full = corpus_data['name']
            query_corpus_endpoint = f'{corpus_name_full}:queryCorpus'
            
            query_data = {
                "query": query,
                "metadataFilters": [],
                "resultsCount": kwargs.get('top_k', 5)
            }
            
            is_successful, retrieval_response, error = self._request('POST', query_corpus_endpoint, body=query_data)
            
            if not is_successful:
                return False, None, error
            
            # 2. 提取檢索到的內容
            relevant_passages = retrieval_response.get('relevantChunks', [])
            
            if not relevant_passages:
                return self._fallback_chat_completion(query, context_messages, **kwargs)
            
            # 3. 建立包含上下文的提示
            context_parts = []
            retrieved_sources = []
            
            for passage in relevant_passages:
                chunk_data = passage.get('chunk', {}).get('data', {})
                text = chunk_data.get('stringValue', '')
                
                if text:
                    context_parts.append(text)
                    
                    # 提取來源資訊
                    metadata = passage.get('chunk', {}).get('customMetadata', [])
                    source_file = "Unknown"
                    for meta in metadata:
                        if meta.get('key') == 'source_file':
                            source_file = meta.get('stringValue', 'Unknown')
                            break
                    
                    retrieved_sources.append({
                        'file_id': passage.get('chunkRelevanceScore', 0),
                        'filename': source_file,
                        'text': text[:200] + "..." if len(text) > 200 else text,
                        'relevance_score': passage.get('chunkRelevanceScore', 0)
                    })
            
            context = "\n\n".join(context_parts)
            
            # 4. 整合檢索結果和長上下文
            if context_messages:
                # 有上下文訊息，整合檢索內容到對話中
                enhanced_system_prompt = f"""你是一個專業的 AI 助理，具有以下參考資料：

{context}

請根據對話歷史和上述參考資料回答用戶的問題。如果參考資料中沒有相關資訊，請基於對話歷史提供建議。
當引用參考資料時，請使用 [文檔名稱] 格式標註來源。"""
                
                # 更新系統提示詞
                messages = []
                for msg in context_messages:
                    if msg.role == "system":
                        # 替換系統提示詞
                        messages.append(ChatMessage(role="system", content=enhanced_system_prompt))
                    else:
                        messages.append(msg)
                
                # 如果沒有系統訊息，添加一個
                if not any(msg.role == "system" for msg in messages):
                    messages.insert(0, ChatMessage(role="system", content=enhanced_system_prompt))
            else:
                # 沒有上下文，使用傳統 RAG 方式
                enhanced_query = f"""請根據以下文檔內容回答問題：

參考資料：
{context}

問題：{query}

請基於上述參考資料回答問題。如果參考資料中沒有相關資訊，請明確說明。"""
                messages = [ChatMessage(role="user", content=enhanced_query)]
            
            is_successful, response, error = self.chat_completion(messages, **kwargs)
            
            if not is_successful:
                return False, None, error

            # 5. 處理內文引用
            processed_answer, final_sources = self._process_inline_citations(response.content, retrieved_sources)
            
            rag_response = RAGResponse(
                answer=processed_answer,
                sources=final_sources,
                metadata={
                    'model': 'gemini',
                    'corpus': corpus_name,
                    'num_sources': len(final_sources),
                    'context_length': len(context),
                    'context_messages_count': len(context_messages),
                    'long_context_enabled': len(context_messages) > 5
                }
            )
            
            return True, rag_response, None
            
        except Exception as e:
            return False, None, str(e)
    
    def get_knowledge_files(self) -> Tuple[bool, Optional[List[FileInfo]], Optional[str]]:
        """取得語料庫檔案列表"""
        try:
            files = []
            
            # 獲取所有語料庫數據
            if hasattr(self.corpora, 'cache'):
                # 直接從 BoundedCache 的內部 cache 獲取項目
                with self.corpora.lock:
                    corpora_items = list(self.corpora.cache.items())
            else:
                corpora_items = []
            
            for corpus_name, corpus_data in corpora_items:
                corpus_name_full = corpus_data['name']
                documents_endpoint = f'{corpus_name_full}/documents'
                
                is_successful, response, error = self._request('GET', documents_endpoint)
                if not is_successful:
                    continue
                
                for document in response.get('documents', []):
                    file_info = FileInfo(
                        file_id=document['name'].split('/')[-1],
                        filename=document.get('displayName', 'Unknown'),
                        status='processed',
                        purpose='knowledge_base',
                        metadata={
                            'corpus': corpus_name,
                            'document_name': document['name']
                        }
                    )
                    files.append(file_info)
            
            return True, files, None
            
        except Exception as e:
            return False, None, str(e)
    
    def get_file_references(self) -> Dict[str, str]:
        """取得檔案引用對應表"""
        try:
            is_successful, files, error = self.get_knowledge_files()
            if not is_successful:
                return {}
            
            return {
                file.file_id: file.filename.replace('.txt', '').replace('.json', '')
                for file in files
            }
        except Exception as e:
            return {}
    
    def _create_corpus(self, corpus_name: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """建立語料庫"""
        try:
            corpus_data = {
                "displayName": corpus_name,
            }
            
            endpoint = '/corpora'
            is_successful, response, error = self._request('POST', endpoint, body=corpus_data)
            
            return is_successful, response, error
            
        except Exception as e:
            return False, None, str(e)
    
    def _chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 100) -> List[Dict]:
        """將文本分塊"""
        chunks = []
        start = 0
        
        # 確保 overlap 不會大於 chunk_size 並且是合理的
        overlap = min(overlap, chunk_size // 2)
        
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk_text = text[start:end]
            
            chunks.append({
                'text': chunk_text,
                'start': start,
                'end': end
            })
            
            # 確保下一個位置總是向前移動
            next_start = end - overlap
            if next_start <= start:  # 防止無限循環
                next_start = start + max(1, chunk_size - overlap)
            
            start = next_start
            
            # 如果已經到達文本末尾，停止
            if end >= len(text):
                break
        
        return chunks
    
    def _intelligent_chunk_text(self, text: str, chunk_size: int = 1000) -> List[Dict]:
        """
        智慧分塊文本 - 針對 Gemini Semantic Retrieval 優化
        
        嘗試在語義邊界分塊，保持內容完整性
        """
        import re
        
        # 基本分塊
        basic_chunks = self._chunk_text(text, chunk_size, overlap=100)
        
        # 智慧處理：嘗試在段落邊界分塊
        intelligent_chunks = []
        for i, chunk in enumerate(basic_chunks):
            chunk_text = chunk['text']
            
            # 嘗試在句子邊界調整
            sentences = re.split(r'[.!?。！？]\s+', chunk_text)
            if len(sentences) > 1:
                # 重新組合句子，確保不超過 chunk_size
                optimized_text = ""
                for sentence in sentences:
                    if len(optimized_text + sentence) <= chunk_size:
                        optimized_text += sentence + "。"
                    else:
                        break
                
                if optimized_text:
                    chunk_text = optimized_text.strip()
            
            intelligent_chunks.append({
                'text': chunk_text,
                'start': chunk['start'],
                'end': chunk['end'],
                'tokens': len(chunk_text.split()),  # 估算 token 數量
                'section': f'chunk_{i}'  # 區段標識
            })
        
        return intelligent_chunks
    
    @retry_on_rate_limit(max_retries=3, base_delay=1.0)
    def _request(self, method: str, endpoint: str, body=None, files=None):
        """發送 HTTP 請求到 Gemini API"""
        
        # 處理 endpoint
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint
        
        url = f'{self.base_url}{endpoint}'
        if '?' in url:
            url += f'&key={self.api_key}'
        else:
            url += f'?key={self.api_key}'
        
        headers = {
            'Content-Type': 'application/json'
        }
        
        try:
            if method == 'POST':
                r = requests.post(url, headers=headers, json=body, timeout=30)
            elif method == 'GET':
                r = requests.get(url, headers=headers, timeout=30)
            else:
                return False, None, f"Unsupported method: {method}"
            
            # 檢查 HTTP 狀態碼
            if r.status_code == 429:
                raise requests.exceptions.RequestException(f"Rate limit exceeded: {r.status_code}")
            elif r.status_code >= 500:
                raise requests.exceptions.RequestException(f"Server error: {r.status_code}")
            elif r.status_code >= 400:
                try:
                    error_data = r.json()
                    error_msg = error_data.get('error', {}).get('message', f'HTTP {r.status_code}')
                    return False, None, error_msg
                except:
                    return False, None, f'HTTP {r.status_code}: {r.text[:200]}'
            
            response_data = r.json()
            return True, response_data, None
            
        except requests.exceptions.RequestException as e:
            raise e
        except Exception as e:
            return False, None, f'Gemini API 系統不穩定，請稍後再試: {str(e)}'
    
    # === 其他介面（部分實作） ===
    
    def create_thread(self) -> Tuple[bool, Optional[ThreadInfo], Optional[str]]:
        """建立簡單的對話串 ID"""
        import uuid
        thread_id = str(uuid.uuid4())
        thread_info = ThreadInfo(thread_id=thread_id)
        return True, thread_info, None
    
    def delete_thread(self, thread_id: str) -> Tuple[bool, Optional[str]]:
        """刪除對話串（Gemini 不支援，直接返回成功）"""
        return True, None
    
    def add_message_to_thread(self, thread_id: str, message: ChatMessage) -> Tuple[bool, Optional[str]]:
        """添加訊息到對話串（Gemini 不支援，直接返回成功）"""
        return True, None
    
    def run_assistant(self, thread_id: str, **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        """執行助理（使用 RAG 查詢）"""
        return False, None, "請使用 query_with_rag 方法"
    
    def transcribe_audio(self, audio_file_path: str, **kwargs) -> Tuple[bool, Optional[str], Optional[str]]:
        """使用 Gemini Pro 的多模態能力進行音訊轉錄"""
        try:
            import base64
            import mimetypes

            # 讀取音訊檔案並進行 Base64 編碼
            with open(audio_file_path, "rb") as f:
                audio_data = f.read()
            
            encoded_audio = base64.b64encode(audio_data).decode("utf-8")
            
            # 猜測 MIME 類型
            mime_type, _ = mimetypes.guess_type(audio_file_path)
            if not mime_type:
                mime_type = "audio/wav"  # 預設值
            if mime_type == "audio/x-wav":
                mime_type = "audio/wav" # 標準化 MIME 類型

            # 建立請求
            json_body = {
                "contents": [
                    {
                        "parts": [
                            {"text": "請將這段音訊轉錄成文字。"},
                            {
                                "inline_data": {
                                    "mime_type": mime_type,
                                    "data": encoded_audio
                                }
                            }
                        ]
                    }
                ]
            }
            
            endpoint = f'/models/{self.model_name}:generateContent'
            is_successful, response, error_message = self._request('POST', endpoint, body=json_body)

            if not is_successful:
                return False, None, error_message

            if 'candidates' not in response or not response['candidates']:
                return False, None, "No response generated from audio"

            candidate = response['candidates'][0]
            if 'content' not in candidate or not candidate['content']['parts']:
                return False, None, "No content in response from audio"

            transcribed_text = candidate['content']['parts'][0]['text']
            return True, transcribed_text.strip(), None

        except FileNotFoundError:
            return False, None, f"Audio file not found at: {audio_file_path}"
        except Exception as e:
            logger.error(f"Gemini audio transcription failed: {e}")
            return False, None, str(e)
    
    def generate_image(self, prompt: str, **kwargs) -> Tuple[bool, Optional[str], Optional[str]]:
        """圖片生成（Gemini 不支援）"""
        return False, None, "Gemini 目前不支援圖片生成"
    
    # === 🆕 新的用戶級對話管理接口 ===
    
    def chat_with_user(self, user_id: str, message: str, platform: str = 'line', **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        """
        主要對話接口：長上下文對話歷史 + Semantic Retrieval RAG
        
        利用 Gemini 1.5 Pro 的 1M token 上下文窗口優勢
        
        Args:
            user_id: 用戶 ID (如 Line user ID)
            message: 用戶訊息
            platform: 平台識別 ('line', 'discord', 'telegram')
            **kwargs: 額外參數
                - conversation_limit: 對話歷史輪數，預設20（利用長上下文）
                - corpus_name: 語料庫名稱
                
        Returns:
            (is_successful, rag_response, error_message)
        """
        try:
            # 1. 取得較長的對話歷史（利用 1M token 優勢）
            conversation_limit = kwargs.get('conversation_limit', 20)  # 比其他模型更多
            recent_conversations = self._get_recent_conversations(user_id, platform, limit=conversation_limit)
            
            # 2. 儲存用戶訊息
            self.conversation_manager.add_message(user_id, 'gemini', 'user', message, platform)
            
            # 3. 建立長上下文對話
            messages = self._build_long_conversation_context(recent_conversations, message)
            
            # 4. 使用 Semantic Retrieval API 進行 RAG 查詢（包含長上下文）
            rag_kwargs = {**kwargs, 'context_messages': messages}
            is_successful, rag_response, error = self.query_with_rag(message, **rag_kwargs)
            
            if not is_successful:
                return False, None, error
            
            # 5. 儲存助理回應
            self.conversation_manager.add_message(user_id, 'gemini', 'assistant', rag_response.answer, platform)
            
            # 6. 更新 metadata（加入長上下文資訊）
            rag_response.metadata.update({
                'conversation_turns': len(recent_conversations),
                'context_tokens_used': len(str(messages)),  # 估算值
                'long_context_enabled': len(recent_conversations) > 10,
                'user_id': user_id,
                'model_provider': 'gemini'
            })
            
            logger.info(f"Completed Gemini chat with user {user_id}, context turns: {len(recent_conversations)}, response length: {len(rag_response.answer)}")
            return True, rag_response, None
            
        except Exception as e:
            logger.error(f"Error in chat_with_user for user {user_id}: {e}")
            return False, None, str(e)
    
    def clear_user_history(self, user_id: str, platform: str = 'line') -> Tuple[bool, Optional[str]]:
        """清除用戶對話歷史"""
        try:
            success = self.conversation_manager.clear_user_history(user_id, 'gemini', platform)
            if success:
                logger.info(f"Cleared conversation history for user {user_id}")
                return True, None
            else:
                return False, "Failed to clear conversation history"
        except Exception as e:
            logger.error(f"Error clearing history for user {user_id}: {e}")
            return False, str(e)
    
    def _get_recent_conversations(self, user_id: str, platform: str = 'line', limit: int = 20) -> List[Dict]:
        """取得用戶最近的對話歷史（支援長上下文）"""
        try:
            return self.conversation_manager.get_recent_conversations(user_id, 'gemini', limit, platform)
        except Exception as e:
            logger.warning(f"Failed to get recent conversations for user {user_id}: {e}")
            return []
    
    def _build_long_conversation_context(self, recent_conversations: List[Dict], current_message: str) -> List[ChatMessage]:
        """
        建立長上下文對話（利用 Gemini 1M token 優勢）
        
        與其他模型不同，Gemini 可以包含更多歷史對話
        """
        messages = []
        
        # 添加系統訊息
        system_prompt = self._build_system_prompt_with_context()
        messages.append(ChatMessage(role='system', content=system_prompt))
        
        # 添加更多對話歷史（最多取最近 40 輪對話，受限於實際可用上下文）
        max_history = min(len(recent_conversations), 40)
        for conv in recent_conversations[-max_history:]:
            messages.append(ChatMessage(
                role=conv['role'],
                content=conv['content']
            ))
        
        # 添加當前訊息
        messages.append(ChatMessage(role='user', content=current_message))
        
        logger.debug(f"Built long context with {len(messages)} messages")
        return messages
    
    def _build_system_prompt_with_context(self) -> str:
        """建立包含語義檢索指導的系統提示詞"""
        return """你是一個專業的 AI 助理，具有以下能力和特質：

## 核心能力
- 長期對話記憶：可以記住並引用較長的對話歷史
- 語義檢索：基於 Google Semantic Retrieval API 的知識檢索
- 多模態理解：支援文字、圖片、影片等多種內容格式
- 上下文分析：充分利用 100萬 token 的長上下文窗口

## 回答原則
1. 充分利用提供的對話歷史，建立連貫的對話體驗
2. 當引用知識文檔時，請使用 [文檔名稱] 格式標註來源
3. 對於複雜問題，可以參考前面的對話內容提供更好的回答
4. 如文檔中無相關資訊，明確說明並提供基於對話歷史的建議
5. 保持專業但友善的語調，展現長期對話的連續性

## 回答格式
- 適當引用前面的對話內容（如："如我們之前討論的..."）
- 使用清晰的段落結構和條列式重點
- 重要資訊使用適當的格式突出
- 在回答末尾標註相關的知識文檔來源

請始終保持這個角色設定，充分發揮長上下文和語義檢索的優勢。"""

    def _upload_multimodal_file(self, file_path: str, corpus_name: str, **kwargs) -> Tuple[bool, Optional[FileInfo], Optional[str]]:
        """
        上傳多模態檔案到 Google Cloud Storage 並與 Semantic Retrieval 整合
        
        此功能為進階實作，需要完整的 Google Cloud Storage (GCS) 整合，目前尚未啟用。
        啟用此功能前，請確保：
        1. 已安裝 `google-cloud-storage` Python 套件。
        2. 應用程式執行環境已設定 GCS 服務帳號憑證。
        3. 已在 Google Cloud 專案中建立一個 GCS 儲存桶 (bucket)。
        """
        logger.warning("Multimodal file upload is not fully implemented and requires Google Cloud Storage integration.")
        return False, None, "多模態檔案上傳功能尚未完整實作，需要 Google Cloud Storage 整合。"
        
        # 完整實作流程範例：
        # try:
        #     from google.cloud import storage
        #     import os

        #     # 從設定或環境變數讀取 GCS bucket 名稱
        #     bucket_name = os.environ.get("GCS_BUCKET_NAME")
        #     if not bucket_name:
        #         logger.error("GCS_BUCKET_NAME environment variable is not set.")
        #         return False, None, "GCS bucket 未設定"

        #     storage_client = storage.Client()
        #     bucket = storage_client.bucket(bucket_name)
            
        #     destination_blob_name = f"multimodal_uploads/{os.path.basename(file_path)}"
        #     blob = bucket.blob(destination_blob_name)

        #     logger.info(f"Uploading {file_path} to GCS bucket {bucket_name}...")
        #     blob.upload_from_filename(file_path)
        #     gcs_uri = f"gs://{bucket_name}/{destination_blob_name}"
        #     logger.info(f"File uploaded to {gcs_uri}")

        #     # TODO: 後續需要調用 Google File API 或類似服務，
        #     # 將 GCS URI 與 Semantic Retrieval 的文檔進行關聯。
        #     # 這部分的 API 可能會隨 Google Cloud 的更新而變化。

        #     file_info = FileInfo(
        #         file_id=gcs_uri, # 暫時使用 GCS URI 作為 ID
        #         filename=os.path.basename(file_path),
        #         status='uploaded_to_gcs',
        #         purpose='multimodal_knowledge',
        #         metadata={'gcs_uri': gcs_uri, 'corpus': corpus_name}
        #     )
            
        #     return True, file_info, None

        # except ImportError:
        #     logger.error("google-cloud-storage is not installed. Please install it to use multimodal features.")
        #     return False, None, "缺少 google-cloud-storage 套件"
        # except Exception as e:
        #     logger.error(f"Failed to upload multimodal file to GCS: {e}")
        #     return False, None, f"多模態檔案上傳失敗: {e}"