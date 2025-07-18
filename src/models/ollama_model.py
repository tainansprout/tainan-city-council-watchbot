import requests
import json
import hashlib
import time
import uuid
from typing import List, Dict, Tuple, Optional, Any
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
import time

logger = get_logger(__name__)


class OllamaModel(FullLLMInterface):
    """
    Ollama 本地模型實作
    
    📋 架構職責分工：
    ✅ RESPONSIBILITIES (模型層職責):
      - 實作統一的 FullLLMInterface 接口
      - 提供 chat_with_user() 文字對話功能
      - 提供 transcribe_audio() 音訊轉錄功能
      - 管理對話歷史和上下文
      - 處理本地 Ollama 服務連線和重試邏輯

    🎯 模型特色：
    - 完全本地部署，保護隱私
    - 支援多種開源模型 (Llama2, Mistral, CodeLlama等)
    - 本地向量資料庫實現 RAG 功能
    - 無需網路連線運行

    ⚠️ 功能限制：
    - 音訊轉錄: 需本地安裝 Whisper (`pip install openai-whisper`)
    - 圖片生成: 目前不支援
    - 依賴本地 Ollama 服務運行狀態
    - 需要充足的硬體資源 (RAM/GPU)
    """
    
    def __init__(self, base_url: str = "http://localhost:11434", model_name: str = "llama3.1:8b", embedding_model: str = "nomic-embed-text", enable_mcp: bool = False):
        self.base_url = base_url.rstrip('/')
        self.model_name = model_name
        self.embedding_model = embedding_model  # 本地 embedding 模型
        
        # 本地知識庫和向量快取
        self.knowledge_store = {}  # 本地知識庫
        self.embeddings_cache = {}  # 嵌入向量快取
        
        # 本地快取配置（隱私保護）
        self.local_cache_enabled = True
        self.max_cache_size = 1000
        self.conversation_cache = {}  # 本地對話快取
        
        # 對話歷史管理
        self.conversation_manager = get_conversation_manager()
        
        # 本地 Whisper 支援
        self.whisper_model = None  # 需要額外設定

        # MCP 支援
        if enable_mcp:
            self.enable_mcp = True
        else:
            try:
                from ..core.config import get_value
                feature_enabled = get_value('features.enable_mcp', False)
                mcp_enabled = get_value('mcp.enabled', False)
                self.enable_mcp = feature_enabled and mcp_enabled
            except Exception as e:
                logger.warning(f"Error reading MCP config: {e}")
                self.enable_mcp = False
        
        self.mcp_service = None
        if self.enable_mcp:
            self._init_mcp_service()
    
    def get_provider(self) -> ModelProvider:
        return ModelProvider.OLLAMA

    def _init_mcp_service(self) -> None:
        """初始化 MCP 服務"""
        try:
            from ..services.mcp_service import get_mcp_service
            
            mcp_service = get_mcp_service()
            if mcp_service.is_enabled:
                self.mcp_service = mcp_service
                logger.info("Ollama Model: MCP service initialized successfully")
            else:
                logger.warning("Ollama Model: MCP service is not enabled")
                self.enable_mcp = False
        except Exception as e:
            logger.warning(f"Ollama Model: Failed to initialize MCP service: {e}")
            self.enable_mcp = False
            self.mcp_service = None
    
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
                    "temperature": kwargs.get('temperature', 0.01),
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
    
    def _process_inline_citations(self, text: str, retrieved_sources: List[Dict]) -> Tuple[str, List[Dict]]:
        """
        處理模型回應中的內文引用，將 [檔名] 替換為 [數字] 引用格式。
        """
        import re
        
        cited_filenames = set(re.findall(r'\[([^\]]+)\]', text))
        
        if not cited_filenames:
            return text, retrieved_sources

        final_sources = []
        citation_map = {}
        next_ref_num = 1

        for source in retrieved_sources:
            filename = source.get('filename')
            if filename in cited_filenames:
                if filename not in citation_map:
                    citation_map[filename] = next_ref_num
                    final_sources.append(source)
                    next_ref_num += 1
        
        for filename, ref_num in citation_map.items():
            text = text.replace(f'[{filename}]', f'[{ref_num}]')
            
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
                'model': 'ollama', 
                'no_sources': True,
                'local_processing': True,
                'context_messages_count': len(messages)
            }
        )
        return True, rag_response, None

    def query_with_rag(self, query: str, thread_id: str = None, **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        """使用本地向量搜尋進行 RAG 查詢（支援上下文和隱私模式）"""
        try:
            context_messages = kwargs.get('context_messages', [])
            local_only = kwargs.get('local_only', True)
            
            # 生成查詢的嵌入向量（本地處理）
            query_embedding = self._get_embedding(query)
            
            if not query_embedding:
                return self._fallback_chat_completion(query, context_messages, **kwargs)
            
            # 搜尋相關文檔片段
            relevant_chunks = self._vector_search(query_embedding, top_k=kwargs.get('top_k', 3))
            
            if not relevant_chunks:
                return self._fallback_chat_completion(query, context_messages, **kwargs)
            
            # 整合本地知識庫和對話上下文
            context = "\n\n".join([chunk['text'] for chunk in relevant_chunks])
            
            if context_messages:
                # 有上下文訊息，整合本地知識庫
                enhanced_system_prompt = f"""你是一個本地化的 AI 助理，具有以下本地知識庫資料：

{context}

請根據對話歷史和上述本地知識庫回答用戶的問題。所有處理都在本地進行，保護用戶隱私。
當引用知識庫時，請使用 [文檔名稱] 格式標註來源。"""
                
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
                # 傳統 RAG 方式
                enhanced_query = f"""根據以下本地知識庫資訊回答問題：

本地知識庫：
{context}

問題：{query}

請基於本地知識庫資訊回答問題。如果知識庫中沒有相關資訊，請明確說明。所有處理都在本地進行。"""
                messages = [ChatMessage(role="user", content=enhanced_query)]
            
            is_successful, response, error = self.chat_completion(messages, **kwargs)
            
            if not is_successful:
                return False, None, error
            
            # 準備來源資訊
            retrieved_sources = [
                {
                    'file_id': chunk['file_id'],
                    'filename': chunk['filename'],
                    'text': chunk['text'][:200] + "..." if len(chunk['text']) > 200 else chunk['text'],
                    'similarity': chunk.get('similarity', 0.0)
                }
                for chunk in relevant_chunks
            ]

            # 處理內文引用
            processed_answer, final_sources = self._process_inline_citations(response.content, retrieved_sources)
            
            rag_response = RAGResponse(
                answer=processed_answer,
                sources=final_sources,
                metadata={
                    'model': 'ollama',
                    'context_length': len(context),
                    'num_sources': len(final_sources),
                    'local_processing': local_only,
                    'context_messages_count': len(context_messages),
                    'embedding_model': self.embedding_model,
                    'privacy_protected': True
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
            if start >= len(text) or end >= len(text):
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
        """本地音訊轉錄（使用本地 Whisper）"""
        try:
            import whisper
        except ImportError:
            logger.error("本地 Whisper 套件未安裝，請執行 `pip install openai-whisper`")
            return False, None, "本地語音轉錄功能未啟用：Whisper 套件未安裝。"

        try:
            if self.whisper_model:
                return self._transcribe_with_local_whisper(audio_file_path, **kwargs)
            else:
                # 如果模型未載入，嘗試載入預設模型
                self.set_whisper_model()
                if self.whisper_model:
                    return self._transcribe_with_local_whisper(audio_file_path, **kwargs)
                else:
                    return False, None, "未配置本地 Whisper 模型，請先設定本地語音轉錄服務"
        except Exception as e:
            logger.error(f"Ollama audio transcription failed: {e}")
            return False, None, str(e)
    
    def generate_image(self, prompt: str, **kwargs) -> Tuple[bool, Optional[str], Optional[str]]:
        """圖片生成（Ollama 不支援）"""
        return False, None, "Ollama 目前不支援圖片生成"
    
    # === 🆕 新的用戶級對話管理接口 ===
    
    def chat_with_user(self, user_id: str, message: str, platform: str = 'line', **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        """
        主要對話接口：本地對話歷史 + 本地向量 RAG
        
        完全本地化，資料不出本地環境，保護用戶隱私
        
        Args:
            user_id: 用戶 ID (如 Line user ID)
            message: 用戶訊息
            platform: 平台識別 ('line', 'discord', 'telegram')
            **kwargs: 額外參數
                - conversation_limit: 對話歷史輪數，預設10（平衡效能和記憶）
                - use_local_cache: 是否使用本地快取，預設 True
                - privacy_mode: 隱私模式，預設 True（資料不儲存到外部資料庫）
                
        Returns:
            (is_successful, rag_response, error_message)
        """
        try:
            # 1. 隱私保護模式檢查
            privacy_mode = kwargs.get('privacy_mode', True)
            use_local_cache = kwargs.get('use_local_cache', True)
            
            # 2. 取得對話歷史（本地快取 + 資料庫）
            conversation_limit = kwargs.get('conversation_limit', 10)
            recent_conversations = self._get_recent_conversations(user_id, platform, limit=conversation_limit, use_cache=use_local_cache)
            
            # 3. 儲存用戶訊息到本地快取
            if use_local_cache:
                self._add_to_local_cache(user_id, 'user', message)
            
            # 4. 儲存到資料庫（如果不是隱私模式）
            if not privacy_mode:
                self.conversation_manager.add_message(user_id, 'ollama', 'user', message, platform)
            
            # 5. 建立包含對話歷史的上下文
            messages = self._build_local_conversation_context(recent_conversations, message)
            
            if self.enable_mcp and self.mcp_service:
                # MCP 需要 async，但目前在 sync 模式下禁用
                logger.warning("MCP is disabled in sync mode. Falling back to local RAG.")
                rag_kwargs = {**kwargs, 'context_messages': messages, 'local_only': True}
                is_successful, rag_response, error = self.query_with_rag(message, **rag_kwargs)
            else:
                rag_kwargs = {**kwargs, 'context_messages': messages, 'local_only': True}
                is_successful, rag_response, error = self.query_with_rag(message, **rag_kwargs)

            if not is_successful:
                return False, None, error
            
            # 7. 儲存助理回應
            if use_local_cache:
                self._add_to_local_cache(user_id, 'assistant', rag_response.answer)
            
            if not privacy_mode:
                self.conversation_manager.add_message(user_id, 'ollama', 'assistant', rag_response.answer, platform)
            
            # 8. 更新 metadata（強調本地化特性）
            rag_response.metadata.update({
                'conversation_turns': len(recent_conversations),
                'local_processing': True,
                'privacy_protected': privacy_mode,
                'cache_enabled': use_local_cache,
                'user_id': user_id,
                'model_provider': 'ollama',
                'embedding_model': self.embedding_model
            })
            
            logger.info(f"Completed local Ollama chat with user {user_id}, privacy_mode: {privacy_mode}, response length: {len(rag_response.answer)}")
            return True, rag_response, None
            
        except Exception as e:
            logger.error(f"Error in chat_with_user for user {user_id}: {e}")
            return False, None, str(e)

    async def chat_completion_with_mcp(self, messages: List[ChatMessage], **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        """
        支援 MCP function calling 的對話完成 (基於提示工程)
        """
        if not self.enable_mcp or not self.mcp_service:
            is_success, response, error = self.chat_completion(messages, **kwargs)
            if not is_success:
                return False, None, error
            return True, RAGResponse(answer=response.content, sources=[], metadata=response.metadata), None

        try:
            # 1. 建立包含工具定義的系統提示
            system_prompt = self._build_mcp_system_prompt()
            
            # 替換或插入系統提示
            final_messages = [msg for msg in messages if msg.role != 'system']
            final_messages.insert(0, ChatMessage(role="system", content=system_prompt))

            # 2. 第一次呼叫模型，判斷是否需要工具
            is_successful, response, error = self.chat_completion(final_messages, **kwargs)
            if not is_successful:
                return False, None, error

            # 3. 解析回應，檢查是否有工具調用
            tool_call_request = self._parse_for_tool_call(response.content)

            if not tool_call_request:
                # 沒有工具調用，直接返回結果
                return True, RAGResponse(answer=response.content, sources=[], metadata=response.metadata), None

            # 4. 執行工具調用
            tool_name = tool_call_request['tool_name']
            arguments = tool_call_request['arguments']
            
            logger.info(f"🔧 Ollama Model: Executing tool '{tool_name}' with args: {arguments}")
            tool_result = self.mcp_service.handle_function_call_sync(tool_name, arguments)
            
            # 5. 將工具結果加到對話歷史中
            final_messages.append(ChatMessage(role="assistant", content=response.content)) # 加入模型的工具請求
            final_messages.append(ChatMessage(
                role="function",
                content=json.dumps(tool_result, ensure_ascii=False),
                metadata={"function_name": tool_name}
            ))

            # 6. 再次呼叫模型，生成最終回覆
            logger.info("🔄 Ollama Model: Calling model again with tool result.")
            is_successful, final_response, error = self.chat_completion(final_messages, **kwargs)
            if not is_successful:
                return False, None, error

            # 7. 組合最終的 RAGResponse
            sources = tool_result.get('metadata', {}).get('sources', [])
            final_rag_response = RAGResponse(
                answer=final_response.content,
                sources=sources,
                metadata={
                    **final_response.metadata,
                    'mcp_enabled': True,
                    'tool_calls': [tool_call_request],
                    'tool_results': [tool_result]
                }
            )
            return True, final_rag_response, None

        except Exception as e:
            logger.error(f"Error in chat_completion_with_mcp for Ollama: {e}")
            return False, None, str(e)

    def _parse_for_tool_call(self, response_text: str) -> Optional[Dict[str, Any]]:
        """從模型回應中解析工具調用請求"""
        try:
            # 移除程式碼區塊標記
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            data = json.loads(response_text.strip())
            if isinstance(data, dict) and 'tool_name' in data and 'arguments' in data:
                logger.info(f"✅ Parsed tool call request: {data['tool_name']}")
                return data
            return None
        except (json.JSONDecodeError, TypeError):
            return None

    def _build_mcp_system_prompt(self) -> str:
        """建立包含 MCP 工具定義和指令的系統提示"""
        base_prompt = self._build_local_system_prompt()
        
        if not self.mcp_service:
            return base_prompt

        try:
            tools_description = []
            for func_str in self.mcp_service.get_function_schemas_for_anthropic().split('\n'):
                tools_description.append(f"- {func_str}")

            if not tools_description:
                return base_prompt

            mcp_prompt = f"""{base_prompt}

## 外部工具調用 (MCP)

除了你的內建能力，你還可以調用以下外部工具來獲取即時資訊或執行特定任務。

### 可用工具列表:
{chr(10).join(tools_description)}

### 調用指令:
當你判斷需要使用工具時，你的回覆**必須且只能**是一個 JSON 物件，格式如下，不包含任何其他文字或解釋:
```json
{{
  "tool_name": "工具名稱",
  "arguments": {{
    "參數1": "值1",
    "參數2": "值2"
  }}
}}
```
系統會執行此工具並將結果回傳給你，然後你再根據結果生成最終的自然語言回覆."""
            return mcp_prompt
        except Exception as e:
            logger.error(f"Failed to build MCP system prompt for Ollama: {e}")
            return base_prompt

    def clear_user_history(self, user_id: str, platform: str = 'line') -> Tuple[bool, Optional[str]]:
        """清除用戶對話歷史（本地快取 + 資料庫）"""
        try:
            # 清除本地快取
            if user_id in self.conversation_cache:
                del self.conversation_cache[user_id]
                logger.info(f"Cleared local cache for user {user_id}")
            
            # 清除資料庫歷史
            success = self.conversation_manager.clear_user_history(user_id, 'ollama', platform)
            if success:
                logger.info(f"Cleared database history for user {user_id}")
                return True, None
            else:
                return False, "Failed to clear database conversation history"
                
        except Exception as e:
            logger.error(f"Error clearing history for user {user_id}: {e}")
            return False, str(e)
    
    def _get_recent_conversations(self, user_id: str, platform: str = 'line', limit: int = 10, use_cache: bool = True) -> List[Dict]:
        """取得用戶最近的對話歷史（本地快取優先）"""
        try:
            conversations = []
            
            # 1. 優先使用本地快取
            if use_cache and user_id in self.conversation_cache:
                cached_conversations = self.conversation_cache[user_id].get('messages', [])
                conversations.extend(cached_conversations[-limit*2:])  # 取雙倍確保足夠
            
            # 2. 如果快取不足，從資料庫補充
            if len(conversations) < limit and hasattr(self, 'conversation_manager'):
                db_conversations = self.conversation_manager.get_recent_conversations(user_id, 'ollama', limit, platform)
                # 合併並去重
                existing_content = {conv.get('content', '') for conv in conversations}
                for conv in db_conversations:
                    if conv.get('content', '') not in existing_content:
                        conversations.append(conv)
            
            return conversations[-limit*2:] if conversations else []
            
        except Exception as e:
            logger.warning(f"Failed to get recent conversations for user {user_id}: {e}")
            return []
    
    def _add_to_local_cache(self, user_id: str, role: str, content: str):
        """新增訊息到本地快取（隱私保護）"""
        try:
            if not self.local_cache_enabled:
                return
            
            if user_id not in self.conversation_cache:
                self.conversation_cache[user_id] = {
                    'messages': [],
                    'created_at': time.time()
                }
            
            # 新增訊息
            self.conversation_cache[user_id]['messages'].append({
                'role': role,
                'content': content,
                'timestamp': time.time()
            })
            
            # 限制快取大小（隱私保護 + 效能考量）
            messages = self.conversation_cache[user_id]['messages']
            if len(messages) > self.max_cache_size:
                self.conversation_cache[user_id]['messages'] = messages[-self.max_cache_size//2:]
            
            logger.debug(f"Added message to local cache for user {user_id}")
            
        except Exception as e:
            logger.warning(f"Failed to add message to local cache: {e}")
    
    def _build_local_conversation_context(self, recent_conversations: List[Dict], current_message: str) -> List[ChatMessage]:
        """
        建立本地對話上下文（平衡效能和記憶）
        
        相比其他模型，Ollama 更注重本地效能優化
        """
        messages = []
        
        # 添加系統訊息（本地化優化）
        system_prompt = self._build_local_system_prompt()
        messages.append(ChatMessage(role='system', content=system_prompt))
        
        # 添加對話歷史（最多取最近 20 輪對話，平衡效能）
        max_history = min(len(recent_conversations), 20)
        for conv in recent_conversations[-max_history:]:
            messages.append(ChatMessage(
                role=conv.get('role', 'user'),
                content=conv.get('content', '')
            ))
        
        # 添加當前訊息
        messages.append(ChatMessage(role='user', content=current_message))
        
        logger.debug(f"Built local context with {len(messages)} messages")
        return messages
    
    def _build_local_system_prompt(self) -> str:
        """建立本地化系統提示詞（強調隱私和本地特性）"""
        return """你是一個完全本地化的 AI 助理，具有以下特質和能力：

## 核心理念
- 隱私保護：所有對話和資料處理完全在本地進行，不會傳送到外部服務
- 本地優化：針對本地運算資源進行優化，提供高效的回應
- 知識檢索：使用本地向量資料庫進行知識檢索和問答
- 持續學習：基於本地對話歷史提供個人化服務

## 回答原則
1. 充分利用本地知識庫和對話歷史
2. 當引用知識文檔時，使用 [文檔名稱] 格式標註來源
3. 對於敏感資訊，強調本地處理的隱私保護優勢
4. 如本地知識庫中無相關資訊，基於對話歷史提供建議
5. 保持友善、專業的語調，強調本地化服務的可靠性

## 回答格式
- 使用清晰的段落結構
- 重要資訊使用條列或編號
- 適當引用對話歷史（如："如我們之前討論的..."）
- 在回答末尾標註本地知識來源

請始終記住你是一個本地化、隱私保護的 AI 助理，為用戶提供安全可靠的服務。"""
    
    def _transcribe_with_local_whisper(self, audio_file_path: str, **kwargs) -> Tuple[bool, Optional[str], Optional[str]]:
        """使用本地 Whisper 進行語音轉錄（隱私保護）"""
        try:
            # 這裡需要整合本地 Whisper 模型
            # 例如使用 openai-whisper 或其他本地實作
            import whisper
            
            if not self.whisper_model:
                # 載入預設模型（第一次使用時）
                model_size = kwargs.get('whisper_model', 'base')
                self.whisper_model = whisper.load_model(model_size)
                logger.info(f"Loaded local Whisper model: {model_size}")
            
            # 本地轉錄（完全隱私）
            result = self.whisper_model.transcribe(audio_file_path)
            transcribed_text = result["text"].strip()
            
            logger.info(f"Local audio transcription completed, length: {len(transcribed_text)}")
            return True, transcribed_text, None
            
        except ImportError:
            return False, None, "本地 Whisper 未安裝，請執行：pip install openai-whisper"
        except Exception as e:
            return False, None, f"本地語音轉錄失敗: {str(e)}"
    
    def set_whisper_model(self, model_size: str = "base"):
        """設定本地 Whisper 模型"""
        try:
            import whisper
            self.whisper_model = whisper.load_model(model_size)
            logger.info(f"Local Whisper model set to: {model_size}")
        except ImportError:
            logger.error("Whisper not installed. Run: pip install openai-whisper")
        except Exception as e:
            logger.error(f"Failed to set Whisper model: {e}")
    
    def get_privacy_stats(self, user_id: str) -> Dict:
        """獲取隱私保護統計資訊"""
        try:
            stats = {
                'local_cache_messages': 0,
                'knowledge_chunks': 0,
                'embedding_cache_size': len(self.embeddings_cache),
                'privacy_protected': True,
                'local_only': True
            }
            
            if user_id in self.conversation_cache:
                stats['local_cache_messages'] = len(self.conversation_cache[user_id].get('messages', []))
            
            stats['knowledge_chunks'] = sum(
                len(store.get('chunks', [])) for store in self.knowledge_store.values()
            )
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get privacy stats: {e}")
            return {'error': str(e)}