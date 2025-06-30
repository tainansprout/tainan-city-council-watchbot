import requests
import json
import hashlib
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


class AnthropicModel(FullLLMInterface):
    """
    Anthropic Claude 模型實作
    
    Note: Anthropic 沒有內建的 RAG 服務，所以我們需要整合外部向量資料庫
    這裡提供一個基於檔案 embedding 的 RAG 實作範例
    """
    
    def __init__(self, api_key: str, model_name: str = "claude-3-sonnet-20240229", base_url: str = None):
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url or "https://api.anthropic.com/v1"
        self.knowledge_store = {}  # 簡單的記憶體知識庫（生產環境應使用向量資料庫）
        self.file_store = {}  # 檔案儲存
    
    def get_provider(self) -> ModelProvider:
        return ModelProvider.ANTHROPIC
    
    def check_connection(self) -> Tuple[bool, Optional[str]]:
        """檢查 Anthropic API 連線"""
        try:
            test_message = [ChatMessage(role="user", content="Hello")]
            is_successful, response, error = self.chat_completion(test_message, max_tokens=10)
            return is_successful, error
        except Exception as e:
            return False, str(e)
    
    @retry_on_rate_limit(max_retries=3, base_delay=1.0)
    def chat_completion(self, messages: List[ChatMessage], **kwargs) -> Tuple[bool, Optional[ChatResponse], Optional[str]]:
        """Anthropic Claude Chat Completion"""
        try:
            # 轉換訊息格式
            claude_messages = []
            system_message = None
            
            for msg in messages:
                if msg.role == "system":
                    system_message = msg.content
                else:
                    claude_messages.append({
                        "role": msg.role, 
                        "content": msg.content
                    })
            
            json_body = {
                "model": kwargs.get('model', self.model_name),
                "max_tokens": kwargs.get('max_tokens', 4000),
                "messages": claude_messages,
                "temperature": kwargs.get('temperature', 0)
            }
            
            if system_message:
                json_body["system"] = system_message
            
            is_successful, response, error_message = self._request('POST', '/messages', body=json_body)
            
            if not is_successful:
                return False, None, error_message
            
            content = response['content'][0]['text']
            finish_reason = response.get('stop_reason')
            
            chat_response = ChatResponse(
                content=content,
                finish_reason=finish_reason,
                metadata={'usage': response.get('usage')}
            )
            
            return True, chat_response, None
            
        except Exception as e:
            return False, None, str(e)
    
    # === RAG 介面實作（使用自建向量搜尋） ===
    
    def upload_knowledge_file(self, file_path: str, **kwargs) -> Tuple[bool, Optional[FileInfo], Optional[str]]:
        """上傳檔案到本地知識庫"""
        try:
            import os
            
            # 生成檔案 ID
            file_id = hashlib.md5(file_path.encode()).hexdigest()
            filename = os.path.basename(file_path)
            
            # 讀取檔案內容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 簡單的文本分塊（生產環境應使用更高級的分塊策略）
            chunks = self._chunk_text(content, chunk_size=kwargs.get('chunk_size', 1000))
            
            # 儲存到知識庫
            self.knowledge_store[file_id] = {
                'filename': filename,
                'content': content,
                'chunks': chunks,
                'metadata': kwargs
            }
            
            self.file_store[file_id] = filename
            
            file_info = FileInfo(
                file_id=file_id,
                filename=filename,
                size=len(content),
                status='processed',
                purpose='knowledge_base',
                metadata={'chunks': len(chunks)}
            )
            
            return True, file_info, None
            
        except Exception as e:
            return False, None, str(e)
    
    def query_with_rag(self, query: str, thread_id: str = None, **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        """使用 RAG 查詢（簡單的關鍵字搜尋 + Claude 生成）"""
        try:
            # 搜尋相關文檔片段
            relevant_chunks = self._search_knowledge(query, top_k=kwargs.get('top_k', 3))
            
            if not relevant_chunks:
                # 沒有相關文檔，使用一般聊天
                messages = [ChatMessage(role="user", content=query)]
                is_successful, response, error = self.chat_completion(messages, **kwargs)
                
                if not is_successful:
                    return False, None, error
                
                rag_response = RAGResponse(
                    answer=response.content,
                    sources=[],
                    metadata={'model': 'anthropic-claude', 'no_sources': True}
                )
                return True, rag_response, None
            
            # 建立包含上下文的提示
            context = "\\n\\n".join([chunk['text'] for chunk in relevant_chunks])
            
            enhanced_query = f"""請根據以下文檔內容回答問題：

<文檔內容>
{context}
</文檔內容>

問題：{query}

請基於上述文檔內容回答，如果文檔中沒有相關資訊，請明確說明。"""
            
            messages = [ChatMessage(role="user", content=enhanced_query)]
            is_successful, response, error = self.chat_completion(messages, **kwargs)
            
            if not is_successful:
                return False, None, error
            
            # 準備來源資訊
            sources = [
                {
                    'file_id': chunk['file_id'],
                    'filename': chunk['filename'],
                    'text': chunk['text'][:200] + "..." if len(chunk['text']) > 200 else chunk['text'],
                    'score': chunk.get('score', 0.0)
                }
                for chunk in relevant_chunks
            ]
            
            rag_response = RAGResponse(
                answer=response.content,
                sources=sources,
                metadata={
                    'model': 'anthropic-claude',
                    'context_length': len(context),
                    'num_sources': len(sources)
                }
            )
            
            return True, rag_response, None
            
        except Exception as e:
            return False, None, str(e)
    
    def get_knowledge_files(self) -> Tuple[bool, Optional[List[FileInfo]], Optional[str]]:
        """取得知識庫檔案列表"""
        try:
            files = []
            for file_id, data in self.knowledge_store.items():
                file_info = FileInfo(
                    file_id=file_id,
                    filename=data['filename'],
                    size=len(data['content']),
                    status='processed',
                    purpose='knowledge_base',
                    metadata=data.get('metadata', {})
                )
                files.append(file_info)
            
            return True, files, None
            
        except Exception as e:
            return False, None, str(e)
    
    def get_file_references(self) -> Dict[str, str]:
        """取得檔案引用對應表"""
        return {
            file_id: filename.replace('.txt', '').replace('.json', '')
            for file_id, filename in self.file_store.items()
        }
    
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
    
    def _search_knowledge(self, query: str, top_k: int = 3) -> List[Dict]:
        """簡單的關鍵字搜尋（生產環境應使用向量搜尋）"""
        query_words = set(query.lower().split())
        scored_chunks = []
        
        for file_id, data in self.knowledge_store.items():
            for chunk in data['chunks']:
                chunk_words = set(chunk['text'].lower().split())
                # 簡單的關鍵字匹配分數
                common_words = query_words.intersection(chunk_words)
                score = len(common_words) / len(query_words) if query_words else 0
                
                if score > 0:
                    scored_chunks.append({
                        'file_id': file_id,
                        'filename': data['filename'],
                        'text': chunk['text'],
                        'score': score
                    })
        
        # 按分數排序並返回前 top_k 個
        scored_chunks.sort(key=lambda x: x['score'], reverse=True)
        return scored_chunks[:top_k]
    
    @retry_on_rate_limit(max_retries=3, base_delay=1.0)
    def _request(self, method: str, endpoint: str, body=None, files=None):
        """發送 HTTP 請求到 Anthropic API"""
        headers = {
            'x-api-key': self.api_key,
            'Content-Type': 'application/json',
            'anthropic-version': '2023-06-01'
        }
        
        try:
            if method == 'POST':
                r = requests.post(f'{self.base_url}{endpoint}', headers=headers, json=body, timeout=30)
            else:
                r = requests.get(f'{self.base_url}{endpoint}', headers=headers, timeout=30)
            
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
            return False, None, f'Anthropic API 系統不穩定，請稍後再試: {str(e)}'
    
    # === 其他介面（暫未實作） ===
    
    def create_thread(self) -> Tuple[bool, Optional[ThreadInfo], Optional[str]]:
        """Anthropic 不支援對話串，使用簡單 ID"""
        import uuid
        thread_id = str(uuid.uuid4())
        thread_info = ThreadInfo(thread_id=thread_id)
        return True, thread_info, None
    
    def delete_thread(self, thread_id: str) -> Tuple[bool, Optional[str]]:
        """Anthropic 不支援對話串管理"""
        return True, None
    
    def add_message_to_thread(self, thread_id: str, message: ChatMessage) -> Tuple[bool, Optional[str]]:
        """Anthropic 不支援對話串，直接返回成功"""
        return True, None
    
    def run_assistant(self, thread_id: str, **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        """使用 RAG 查詢作為助理功能"""
        # 需要從對話串中取得最新訊息，這裡簡化處理
        return False, None, "請使用 query_with_rag 方法"
    
    def transcribe_audio(self, audio_file_path: str, **kwargs) -> Tuple[bool, Optional[str], Optional[str]]:
        """Anthropic 不支援音訊轉錄"""
        return False, None, "Anthropic 不支援音訊轉錄"
    
    def generate_image(self, prompt: str, **kwargs) -> Tuple[bool, Optional[str], Optional[str]]:
        """Anthropic 不支援圖片生成"""
        return False, None, "Anthropic 不支援圖片生成"