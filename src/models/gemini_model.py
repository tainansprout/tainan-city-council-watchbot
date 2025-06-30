import requests
import json
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


class GeminiModel(FullLLMInterface):
    """
    Google Gemini 模型實作
    
    使用 Google AI Studio 和 Semantic Retrieval API 實現 RAG 功能
    """
    
    def __init__(self, api_key: str, model_name: str = "gemini-pro", base_url: str = None):
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url or "https://generativelanguage.googleapis.com/v1beta"
        self.corpora = {}  # 儲存語料庫資訊
    
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
        """Gemini Chat Completion"""
        try:
            # 轉換訊息格式
            gemini_contents = []
            
            for msg in messages:
                role = "user" if msg.role == "user" else "model"
                gemini_contents.append({
                    "role": role,
                    "parts": [{"text": msg.content}]
                })
            
            json_body = {
                "contents": gemini_contents,
                "generationConfig": {
                    "temperature": kwargs.get('temperature', 0.1),
                    "maxOutputTokens": kwargs.get('max_tokens', 4000)
                }
            }
            
            endpoint = f'/models/{self.model_name}:generateContent'
            is_successful, response, error_message = self._request('POST', endpoint, body=json_body)
            
            if not is_successful:
                return False, None, error_message
            
            if 'candidates' not in response or not response['candidates']:
                return False, None, "No response generated"
            
            content = response['candidates'][0]['content']['parts'][0]['text']
            finish_reason = response['candidates'][0].get('finishReason', 'STOP')
            
            chat_response = ChatResponse(
                content=content,
                finish_reason=finish_reason,
                metadata={'usage': response.get('usageMetadata', {})}
            )
            
            return True, chat_response, None
            
        except Exception as e:
            return False, None, str(e)
    
    # === RAG 介面實作（使用 Google Semantic Retrieval API） ===
    
    def upload_knowledge_file(self, file_path: str, **kwargs) -> Tuple[bool, Optional[FileInfo], Optional[str]]:
        """上傳檔案到 Google Semantic Retrieval"""
        try:
            import os
            
            filename = os.path.basename(file_path)
            
            # 1. 建立語料庫（如果不存在）
            corpus_name = kwargs.get('corpus_name', 'default-corpus')
            if corpus_name not in self.corpora:
                is_successful, corpus, error = self._create_corpus(corpus_name)
                if not is_successful:
                    return False, None, error
                self.corpora[corpus_name] = corpus
            
            # 2. 讀取檔案內容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 3. 建立文檔
            document_data = {
                "displayName": filename,
                "customMetadata": [
                    {"key": "source_file", "stringValue": filename}
                ]
            }
            
            corpus_name_full = self.corpora[corpus_name]['name']
            endpoint = f'{corpus_name_full}/documents'
            is_successful, document_response, error = self._request('POST', endpoint, body=document_data)
            
            if not is_successful:
                return False, None, error
            
            # 4. 分塊並上傳
            chunks = self._chunk_text(content, kwargs.get('chunk_size', 1000))
            document_name = document_response['name']
            
            for i, chunk in enumerate(chunks):
                chunk_data = {
                    "data": {
                        "stringValue": chunk['text']
                    },
                    "customMetadata": [
                        {"key": "chunk_index", "numericValue": i},
                        {"key": "source_file", "stringValue": filename}
                    ]
                }
                
                chunk_endpoint = f'{document_name}/chunks'
                is_successful, _, error = self._request('POST', chunk_endpoint, body=chunk_data)
                if not is_successful:
                    # 繼續處理其他塊，不因單個塊失敗而停止
                    continue
            
            file_info = FileInfo(
                file_id=document_response['name'].split('/')[-1],
                filename=filename,
                size=len(content),
                status='processed',
                purpose='knowledge_base',
                metadata={
                    'corpus': corpus_name,
                    'document_name': document_name,
                    'chunks': len(chunks)
                }
            )
            
            return True, file_info, None
            
        except Exception as e:
            return False, None, str(e)
    
    def query_with_rag(self, query: str, thread_id: str = None, **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        """使用 Google Semantic Retrieval 進行 RAG 查詢"""
        try:
            corpus_name = kwargs.get('corpus_name', 'default-corpus')
            
            if corpus_name not in self.corpora:
                # 沒有語料庫，使用一般聊天
                messages = [ChatMessage(role="user", content=query)]
                is_successful, response, error = self.chat_completion(messages, **kwargs)
                
                if not is_successful:
                    return False, None, error
                
                rag_response = RAGResponse(
                    answer=response.content,
                    sources=[],
                    metadata={'model': 'gemini', 'no_sources': True}
                )
                return True, rag_response, None
            
            # 1. 使用 Semantic Retrieval 搜尋相關內容
            corpus_name_full = self.corpora[corpus_name]['name']
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
                # 沒有相關內容，使用一般聊天
                messages = [ChatMessage(role="user", content=query)]
                is_successful, response, error = self.chat_completion(messages, **kwargs)
                
                if not is_successful:
                    return False, None, error
                
                rag_response = RAGResponse(
                    answer=response.content,
                    sources=[],
                    metadata={'model': 'gemini', 'no_retrieval': True}
                )
                return True, rag_response, None
            
            # 3. 建立包含上下文的提示
            context_parts = []
            sources = []
            
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
                    
                    sources.append({
                        'file_id': passage.get('chunkRelevanceScore', 0),
                        'filename': source_file,
                        'text': text[:200] + "..." if len(text) > 200 else text,
                        'relevance_score': passage.get('chunkRelevanceScore', 0)
                    })
            
            context = "\\n\\n".join(context_parts)
            
            enhanced_query = f"""請根據以下文檔內容回答問題：

參考資料：
{context}

問題：{query}

請基於上述參考資料回答問題。如果參考資料中沒有相關資訊，請明確說明。"""
            
            # 4. 使用 Gemini 生成回應
            messages = [ChatMessage(role="user", content=enhanced_query)]
            is_successful, response, error = self.chat_completion(messages, **kwargs)
            
            if not is_successful:
                return False, None, error
            
            rag_response = RAGResponse(
                answer=response.content,
                sources=sources,
                metadata={
                    'model': 'gemini',
                    'corpus': corpus_name,
                    'num_sources': len(sources),
                    'context_length': len(context)
                }
            )
            
            return True, rag_response, None
            
        except Exception as e:
            return False, None, str(e)
    
    def get_knowledge_files(self) -> Tuple[bool, Optional[List[FileInfo]], Optional[str]]:
        """取得語料庫檔案列表"""
        try:
            files = []
            
            for corpus_name, corpus_data in self.corpora.items():
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
        
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk_text = text[start:end]
            
            chunks.append({
                'text': chunk_text,
                'start': start,
                'end': end
            })
            
            start = end - overlap
            if start <= 0:
                break
        
        return chunks
    
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
        """音訊轉錄（Gemini 不支援）"""
        return False, None, "Gemini 目前不支援音訊轉錄"
    
    def generate_image(self, prompt: str, **kwargs) -> Tuple[bool, Optional[str], Optional[str]]:
        """圖片生成（Gemini 不支援）"""
        return False, None, "Gemini 目前不支援圖片生成"