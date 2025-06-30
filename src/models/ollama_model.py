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


class OllamaModel(FullLLMInterface):
    """
    Ollama 本地模型實作
    
    使用 Ollama API + 本地向量資料庫實現 RAG 功能
    支援 llama2, codellama, mistral 等本地模型
    """
    
    def __init__(self, base_url: str = "http://localhost:11434", model_name: str = "llama2"):
        self.base_url = base_url.rstrip('/')
        self.model_name = model_name
        self.knowledge_store = {}  # 本地知識庫
        self.embeddings_cache = {}  # 嵌入向量快取
    
    def get_provider(self) -> ModelProvider:
        return ModelProvider.OLLAMA
    
    def check_connection(self) -> Tuple[bool, Optional[str]]:
        """檢查 Ollama 連線和模型可用性"""
        try:
            # 檢查 Ollama 服務
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            if response.status_code != 200:
                return False, f"Ollama 服務不可用: {response.status_code}"
            
            # 檢查指定模型是否可用
            models = response.json().get('models', [])
            model_names = [model['name'] for model in models]
            
            if not any(self.model_name in name for name in model_names):
                return False, f"模型 {self.model_name} 不可用，可用模型：{model_names}"
            
            return True, None
            
        except Exception as e:
            return False, str(e)
    
    @retry_on_rate_limit(max_retries=3, base_delay=1.0)
    def chat_completion(self, messages: List[ChatMessage], **kwargs) -> Tuple[bool, Optional[ChatResponse], Optional[str]]:
        """Ollama Chat Completion"""
        try:
            # 轉換訊息格式
            ollama_messages = [
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ]
            
            json_body = {
                "model": kwargs.get('model', self.model_name),
                "messages": ollama_messages,
                "stream": False,
                "options": {
                    "temperature": kwargs.get('temperature', 0.1),
                    "num_predict": kwargs.get('max_tokens', 2000)
                }
            }
            
            is_successful, response, error_message = self._request('POST', '/api/chat', body=json_body)
            
            if not is_successful:
                return False, None, error_message
            
            content = response.get('message', {}).get('content', '')
            
            chat_response = ChatResponse(
                content=content,
                finish_reason=response.get('done_reason', 'stop'),
                metadata={
                    'model': response.get('model'),
                    'total_duration': response.get('total_duration'),
                    'load_duration': response.get('load_duration'),
                    'prompt_eval_count': response.get('prompt_eval_count'),
                    'eval_count': response.get('eval_count')
                }
            )
            
            return True, chat_response, None
            
        except Exception as e:
            return False, None, str(e)
    
    # === RAG 介面實作（使用本地向量搜尋） ===
    
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
            
            # 分塊
            chunks = self._chunk_text(content, chunk_size=kwargs.get('chunk_size', 800))
            
            # 生成嵌入向量（使用 Ollama 的 embedding 功能）
            chunk_embeddings = []
            for chunk in chunks:
                embedding = self._get_embedding(chunk['text'])
                if embedding:
                    chunk['embedding'] = embedding
                    chunk_embeddings.append(chunk)
            
            # 儲存到知識庫
            self.knowledge_store[file_id] = {
                'filename': filename,
                'content': content,
                'chunks': chunk_embeddings,
                'metadata': kwargs
            }
            
            file_info = FileInfo(
                file_id=file_id,
                filename=filename,
                size=len(content),
                status='processed',
                purpose='knowledge_base',
                metadata={'chunks': len(chunk_embeddings)}
            )
            
            return True, file_info, None
            
        except Exception as e:
            return False, None, str(e)
    
    def query_with_rag(self, query: str, thread_id: str = None, **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        """使用向量搜尋進行 RAG 查詢"""
        try:
            # 生成查詢的嵌入向量
            query_embedding = self._get_embedding(query)
            
            if not query_embedding:
                # 無法生成嵌入向量，使用一般聊天
                messages = [ChatMessage(role="user", content=query)]
                is_successful, response, error = self.chat_completion(messages, **kwargs)
                
                if not is_successful:
                    return False, None, error
                
                rag_response = RAGResponse(
                    answer=response.content,
                    sources=[],
                    metadata={'model': 'ollama', 'no_embedding': True}
                )
                return True, rag_response, None
            
            # 搜尋相關文檔片段
            relevant_chunks = self._vector_search(query_embedding, top_k=kwargs.get('top_k', 3))
            
            if not relevant_chunks:
                # 沒有相關文檔，使用一般聊天
                messages = [ChatMessage(role="user", content=query)]
                is_successful, response, error = self.chat_completion(messages, **kwargs)
                
                if not is_successful:
                    return False, None, error
                
                rag_response = RAGResponse(
                    answer=response.content,
                    sources=[],
                    metadata={'model': 'ollama', 'no_sources': True}
                )
                return True, rag_response, None
            
            # 建立包含上下文的提示
            context = "\\n\\n".join([chunk['text'] for chunk in relevant_chunks])
            
            enhanced_query = f"""根據以下上下文資訊回答問題：

上下文：
{context}

問題：{query}

請基於上下文資訊回答問題。如果上下文中沒有相關資訊，請明確說明。"""
            
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
                    'similarity': chunk.get('similarity', 0.0)
                }
                for chunk in relevant_chunks
            ]
            
            rag_response = RAGResponse(
                answer=response.content,
                sources=sources,
                metadata={
                    'model': 'ollama',
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
            file_id: data['filename'].replace('.txt', '').replace('.json', '')
            for file_id, data in self.knowledge_store.items()
        }
    
    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """使用 Ollama 生成嵌入向量"""
        try:
            # 檢查快取
            text_hash = hashlib.md5(text.encode()).hexdigest()
            if text_hash in self.embeddings_cache:
                return self.embeddings_cache[text_hash]
            
            # 使用 Ollama 的 embedding 功能
            json_body = {
                "model": self.model_name,
                "prompt": text
            }
            
            is_successful, response, error = self._request('POST', '/api/embeddings', body=json_body)
            
            if not is_successful:
                return None
            
            embedding = response.get('embedding')
            if embedding:
                # 快取結果
                self.embeddings_cache[text_hash] = embedding
                return embedding
            
            return None
            
        except Exception:
            return None
    
    def _chunk_text(self, text: str, chunk_size: int = 800, overlap: int = 100) -> List[Dict]:
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
    
    def _vector_search(self, query_embedding: List[float], top_k: int = 3) -> List[Dict]:
        """向量相似度搜尋"""
        try:
            scored_chunks = []
            
            for file_id, data in self.knowledge_store.items():
                for chunk in data['chunks']:
                    if 'embedding' not in chunk:
                        continue
                    
                    # 計算餘弦相似度
                    similarity = self._cosine_similarity(query_embedding, chunk['embedding'])
                    
                    if similarity > 0.1:  # 設定最低相似度閾值
                        scored_chunks.append({
                            'file_id': file_id,
                            'filename': data['filename'],
                            'text': chunk['text'],
                            'similarity': similarity
                        })
            
            # 按相似度排序並返回前 top_k 個
            scored_chunks.sort(key=lambda x: x['similarity'], reverse=True)
            return scored_chunks[:top_k]
            
        except Exception:
            return []
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """計算餘弦相似度"""
        try:
            dot_product = sum(a * b for a, b in zip(vec1, vec2))
            norm1 = sum(a * a for a in vec1) ** 0.5
            norm2 = sum(b * b for b in vec2) ** 0.5
            
            if norm1 == 0 or norm2 == 0:
                return 0
            
            return dot_product / (norm1 * norm2)
            
        except Exception:
            return 0
    
    def _request(self, method: str, endpoint: str, body=None, files=None):
        """發送 HTTP 請求到 Ollama API"""
        try:
            url = f'{self.base_url}{endpoint}'
            headers = {'Content-Type': 'application/json'}
            
            if method == 'POST':
                r = requests.post(url, headers=headers, json=body, timeout=60)
            elif method == 'GET':
                r = requests.get(url, headers=headers, timeout=30)
            else:
                return False, None, f"Unsupported method: {method}"
            
            # 檢查 HTTP 狀態碼
            if r.status_code >= 400:
                try:
                    error_data = r.json()
                    error_msg = error_data.get('error', f'HTTP {r.status_code}')
                    return False, None, error_msg
                except:
                    return False, None, f'HTTP {r.status_code}: {r.text[:200]}'
            
            response_data = r.json()
            return True, response_data, None
            
        except requests.exceptions.RequestException as e:
            return False, None, f'Ollama 連線錯誤: {str(e)}'
        except Exception as e:
            return False, None, f'Ollama API 錯誤: {str(e)}'
    
    # === 其他介面（部分實作） ===
    
    def create_thread(self) -> Tuple[bool, Optional[ThreadInfo], Optional[str]]:
        """建立簡單的對話串 ID"""
        import uuid
        thread_id = str(uuid.uuid4())
        thread_info = ThreadInfo(thread_id=thread_id)
        return True, thread_info, None
    
    def delete_thread(self, thread_id: str) -> Tuple[bool, Optional[str]]:
        """刪除對話串"""
        return True, None
    
    def add_message_to_thread(self, thread_id: str, message: ChatMessage) -> Tuple[bool, Optional[str]]:
        """添加訊息到對話串"""
        return True, None
    
    def run_assistant(self, thread_id: str, **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        """執行助理"""
        return False, None, "請使用 query_with_rag 方法"
    
    def transcribe_audio(self, audio_file_path: str, **kwargs) -> Tuple[bool, Optional[str], Optional[str]]:
        """音訊轉錄（Ollama 不支援）"""
        return False, None, "Ollama 不支援音訊轉錄"
    
    def generate_image(self, prompt: str, **kwargs) -> Tuple[bool, Optional[str], Optional[str]]:
        """圖片生成（Ollama 不支援）"""
        return False, None, "Ollama 不支援圖片生成"