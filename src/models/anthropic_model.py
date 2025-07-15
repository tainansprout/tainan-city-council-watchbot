"""
Anthropic Claude Model 實作
使用 Anthropic Messages API 提供聊天功能

📋 架構職責分工：
✅ RESPONSIBILITIES (模型層職責):
  - 實作統一的 FullLLMInterface 接口
  - 提供 chat_with_user() 文字對話功能
  - 提供 transcribe_audio() 音訊轉錄功能 (透過外部服務)
  - 管理對話歷史和上下文
  - 處理 Anthropic API 限流和重試邏輯

❌ NEVER DO (絕對禁止):
  - 知道訊息來源平台 (LINE、Telegram 等)
  - 處理平台特定的訊息格式
  - 直接處理 webhook 或網路請求
  - 路由訊息或協調服務

🔄 統一接口：
  - chat_with_user(user_id, message, platform) -> (bool, str, str)
  - transcribe_audio(file_path) -> (bool, str, str)
  - clear_user_history(user_id, platform) -> (bool, str)
  - check_connection() -> (bool, str)

🎯 模型特色：
  - 使用 Claude 的 Messages API
  - 支援長對話和複雜推理
  - 優秀的程式碼和文字生成能力
  - 對話歷史儲存在資料庫

⚠️ 功能限制：
  - 音訊轉錄: 需配置外部服務 (Deepgram/AssemblyAI)
  - 圖片生成: 不支援 (返回 "Anthropic does not support image generation")
"""

import requests
import json
import time
import uuid
import re
from ..core.logger import get_logger
from typing import List, Dict, Tuple, Optional, Any
from .base import (
    FullLLMInterface, 
    ModelProvider, 
    ChatMessage, 
    ChatResponse, 
    ThreadInfo, 
    FileInfo,
    RAGResponse
)
from ..utils.retry import retry_on_rate_limit
from ..services.conversation import get_conversation_manager
from ..core.bounded_cache import FileCache

logger = get_logger(__name__)

class AnthropicModel(FullLLMInterface):
    """
    Anthropic Claude 2024 模型實作
    """
    
    def __init__(self, api_key: str, model_name: str = "claude-3-5-sonnet-20240620", base_url: str = None, enable_mcp: bool = False):
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url or "https://api.anthropic.com/v1"
        self.file_cache = FileCache(max_files=300, file_ttl=3600)
        self.speech_service = None
        self.conversation_manager = get_conversation_manager()
        
        # MCP 支援 - 預設關閉，可透過參數或設定檔啟用
        if enable_mcp:
            self.enable_mcp = True
        else:
            # 如果明確傳遞 False，則直接關閉，否則檢查設定檔
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
        
        # 根據 MCP 狀態建立 system prompt
        self.system_prompt = self._build_system_prompt()

    def get_provider(self) -> ModelProvider:
        return ModelProvider.ANTHROPIC
    
    def _init_mcp_service(self) -> None:
        """初始化 MCP 服務"""
        try:
            from ..services.mcp_service import get_mcp_service
            
            mcp_service = get_mcp_service()
            if mcp_service.is_enabled:
                self.mcp_service = mcp_service
                logger.info("Anthropic Model: MCP service initialized successfully")
            else:
                logger.warning("Anthropic Model: MCP service is not enabled")
                self.enable_mcp = False
        except Exception as e:
            logger.warning(f"Anthropic Model: Failed to initialize MCP service: {e}")
            self.enable_mcp = False
            self.mcp_service = None

    def check_connection(self) -> Tuple[bool, Optional[str]]:
        try:
            is_successful, _, error = self.chat_completion([ChatMessage(role="user", content="Hello")], max_tokens=10)
            return is_successful, error
        except Exception as e:
            logger.error(f"Anthropic connection check failed: {e}")
            return False, str(e)

    @retry_on_rate_limit(max_retries=3, base_delay=1.0)
    def chat_completion(self, messages: List[ChatMessage], **kwargs) -> Tuple[bool, Optional[ChatResponse], Optional[str]]:
        try:
            claude_messages = [{"role": msg.role, "content": msg.content} for msg in messages if msg.role != "system"]
            system_message = next((msg.content for msg in messages if msg.role == "system"), kwargs.get('system', self.system_prompt))

            json_body = {
                "model": kwargs.get('model', self.model_name),
                "max_tokens": kwargs.get('max_tokens', 4000),
                "messages": claude_messages,
                "temperature": kwargs.get('temperature', 0.01),
                "system": system_message
            }
            
            is_successful, response, error_message = self._request('POST', '/messages', body=json_body)
            
            if not is_successful:
                return False, None, error_message
            
            content = response['content'][0]['text']
            chat_response = ChatResponse(
                content=content,
                finish_reason=response.get('stop_reason'),
                metadata={'usage': response.get('usage'), 'model': response.get('model')}
            )
            return True, chat_response, None
        except Exception as e:
            logger.error(f"Anthropic chat completion failed: {e}")
            return False, None, str(e)

    def chat_with_user(self, user_id: str, message: str, platform: str = 'line', **kwargs: Any) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        try:
            self.conversation_manager.add_message(user_id, 'anthropic', 'user', message, platform)
            conversations = self._get_recent_conversations(user_id, platform, kwargs.get('conversation_limit', 10))
            messages = self._build_conversation_context(conversations, message)
            
            # 使用 MCP function calling 如果啟用
            if self.enable_mcp and self.mcp_service:
                import asyncio
                is_successful, response, error = asyncio.run(
                    self.query_with_rag_and_mcp(message, context_messages=messages, **kwargs)
                )
            else:
                is_successful, response, error = self.query_with_rag(message, context_messages=messages, **kwargs)
            
            if not is_successful:
                return False, None, error
            
            self.conversation_manager.add_message(user_id, 'anthropic', 'assistant', response.answer, platform)
            response.metadata.update({'user_id': user_id, 'model_provider': 'anthropic', 'mcp_enabled': self.enable_mcp})
            return True, response, None
        except Exception as e:
            logger.error(f"Error in chat_with_user for {user_id}: {e}")
            return False, None, str(e)
    
    async def query_with_rag_and_mcp(self, query: str, context_messages: List[ChatMessage] = None, **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        """支援 MCP function calling 的 RAG 查詢"""
        messages = context_messages if context_messages else [ChatMessage(role="user", content=query)]
        return await self._perform_rag_query_with_mcp(messages, **kwargs)

    async def _perform_rag_query_with_mcp(self, messages: List[ChatMessage], **kwargs: Any) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        """執行 RAG 查詢（支援 MCP function calling）"""
        try:
            system_prompt = self._build_files_context() if self.file_cache else self.system_prompt
            is_successful, response, error = await self.chat_completion_with_mcp(messages, system=system_prompt, **kwargs)
            
            if not is_successful:
                return False, None, error
            
            # 處理來源信息
            sources = []
            
            # 從回應中提取的傳統來源
            traditional_sources = self._extract_sources_from_response(response.content)
            sources.extend(traditional_sources)
            
            # 從 MCP function calls 中提取的來源
            if response.metadata and 'sources' in response.metadata:
                mcp_sources = response.metadata['sources']
                sources.extend(mcp_sources)
            
            # 創建 RAGResponse
            rag_response = RAGResponse(
                answer=response.content, 
                sources=sources, 
                metadata={
                    **response.metadata,
                    'mcp_enabled': True,
                    'sources_count': len(sources)
                }
            )
            
            return True, rag_response, None
            
        except Exception as e:
            logger.error(f"Error in _perform_rag_query_with_mcp: {e}")
            return False, None, str(e)

    def query_with_rag(self, query: str, context_messages: List[ChatMessage] = None, **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        messages = context_messages if context_messages else [ChatMessage(role="user", content=query)]
        return self._perform_rag_query(messages, **kwargs)

    def _perform_rag_query(self, messages: List[ChatMessage], **kwargs: Any) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        system_prompt = self._build_files_context() if self.file_cache else self.system_prompt
        is_successful, response, error = self.chat_completion(messages, system=system_prompt, **kwargs)
        if not is_successful:
            return False, None, error
        
        sources = self._extract_sources_from_response(response.content)
        return True, RAGResponse(answer=response.content, sources=sources, metadata=response.metadata), None

    def upload_knowledge_file(self, file_path: str, **kwargs) -> Tuple[bool, Optional[FileInfo], Optional[str]]:
        try:
            import os
            import mimetypes
            filename = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            if file_size > 100 * 1024 * 1024:
                return False, None, f"檔案過大: {file_size / 1024 / 1024:.1f}MB，超過 100MB 限制"
            
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            content_type, _ = mimetypes.guess_type(file_path)
            files = {'file': (filename, file_content, content_type or 'application/octet-stream')}
            data = {'purpose': kwargs.get('purpose', 'knowledge_base')}
            
            is_successful, response, error_message = self._request('POST', '/files', files=files, data=data)
            
            if not is_successful:
                return False, None, error_message
            
            file_info = FileInfo(
                file_id=response['id'], filename=filename, size=file_size, status='processed',
                purpose=response.get('purpose', 'knowledge_base'),
                metadata={'upload_time': time.time(), 'claude_file_id': response['id']}
            )
            self.file_cache[response['id']] = file_info
            return True, file_info, None
        except Exception as e:
            logger.error(f"Anthropic file upload failed for {file_path}: {e}")
            return False, None, str(e)

    def get_knowledge_files(self) -> Tuple[bool, Optional[List[FileInfo]], Optional[str]]:
        # This is a simplified implementation. A real-world scenario might involve pagination.
        try:
            if len(self.file_cache) > 0:
                return True, list(self.file_cache.values()), None
            is_successful, response, error = self._request('GET', '/files')
            if not is_successful:
                return False, None, error
            files = [FileInfo(
                file_id=f['id'], filename=f['filename'], size=f.get('bytes', 0),
                status='processed', purpose=f.get('purpose', 'knowledge_base'),
                metadata={'upload_time': f.get('created_at'), 'claude_file_id': f['id']}
            ) for f in response.get('data', [])]
            for file_info in files:
                self.file_cache[file_info.file_id] = file_info
            return True, files, None
        except Exception as e:
            logger.error(f"Failed to get knowledge files: {e}")
            return False, None, str(e)

    def get_file_references(self) -> Dict[str, str]:
        """Gets a map of file IDs to their clean names for citation."""
        return {info.file_id: info.filename.rsplit('.', 1)[0] for info in self.file_cache.values()}

    # Minimal implementation for interface compliance
    def create_thread(self) -> Tuple[bool, Optional[ThreadInfo], Optional[str]]:
        return True, ThreadInfo(thread_id=str(uuid.uuid4())), None

    def delete_thread(self, thread_id: str) -> Tuple[bool, Optional[str]]:
        return True, None

    def add_message_to_thread(self, thread_id: str, message: ChatMessage) -> Tuple[bool, Optional[str]]:
        return True, None

    def run_assistant(self, thread_id: str, **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        return False, None, "Not implemented. Use chat_with_user for conversation."

    def clear_user_history(self, user_id: str, platform: str = 'line') -> Tuple[bool, Optional[str]]:
        return self.conversation_manager.clear_user_history(user_id, 'anthropic', platform)

    def transcribe_audio(self, audio_file_path: str, **kwargs: Any) -> Tuple[bool, Optional[str], Optional[str]]:
        if not self.speech_service:
            return False, None, "Speech service not configured"
        try:
            return self.speech_service.transcribe(audio_file_path, **kwargs)
        except Exception as e:
            return False, None, str(e)

    def generate_image(self, prompt: str, **kwargs: Any) -> Tuple[bool, Optional[str], Optional[str]]:
        return False, None, "Anthropic does not support image generation."

    def set_speech_service(self, service: Any):
        self.speech_service = service

    def _get_recent_conversations(self, user_id: str, platform: str, limit: int) -> List[Dict]:
        return self.conversation_manager.get_recent_conversations(user_id, 'anthropic', limit, platform)

    def _build_conversation_context(self, recent_conversations: List[Dict], current_message: str) -> List[ChatMessage]:
        messages = [ChatMessage(role=conv['role'], content=conv['content']) for conv in recent_conversations]
        messages.append(ChatMessage(role='user', content=current_message))
        return messages

    def _build_system_prompt(self) -> str:
        """建構 system prompt（包含 MCP function schemas）"""
        # 從設定檔讀取基礎 system prompt
        if self.enable_mcp:
            try:
                from ..core.config import get_value
                base_prompt = get_value('mcp.system_prompt', "You are a helpful assistant.")
            except Exception:
                base_prompt = "You are a helpful assistant."
        else:
            base_prompt = "You are a helpful assistant."
        
        if self.enable_mcp and self.mcp_service:
            try:
                # 取得 MCP function schemas 為 Anthropic 格式
                function_schemas_prompt = self.mcp_service.get_function_schemas_for_anthropic()
                if function_schemas_prompt:
                    base_prompt += f"\n\n{function_schemas_prompt}"
                    
                    # 加入 MCP 最佳實踐的工具使用指引
                    base_prompt += """

## 工具使用指引 (Tool Usage Guidelines)

### 安全原則：
- 僅在用戶明確請求或需要時使用工具
- 在調用工具前說明您將執行的操作
- 引用工具結果時註明資料來源
- 對敏感查詢提供適當的上下文說明

### 工具調用格式：
當您需要使用工具時，請使用以下 JSON 格式：
```json
{"function_name": "工具名稱", "arguments": {"參數名": "參數值"}}
```

### 工具調用最佳實踐：
1. **明確意圖**：清楚說明為什麼需要使用這個工具
2. **參數驗證**：確保提供的參數完整且正確
3. **結果處理**：對工具返回的結果進行適當的解釋和整理
4. **錯誤處理**：如果工具調用失敗，向用戶說明情況並提供替代方案
5. **來源引用**：明確標示資訊來源，提高透明度"""
                    
                    logger.info("Anthropic Model: Added MCP function schemas and security guidelines to system prompt")
            except Exception as e:
                logger.error(f"Failed to add MCP function schemas to system prompt: {e}")
        
        return base_prompt
    
    def _has_function_calls(self, response_text: str) -> bool:
        """檢查回應是否包含 function calls"""
        import re
        # 檢查是否有 JSON 格式的 function call
        json_pattern = r'```json\s*\{[^}]*"function_name"[^}]*\}[^`]*```'
        return bool(re.search(json_pattern, response_text, re.DOTALL))
    
    def _extract_function_calls(self, response_text: str) -> List[Dict[str, Any]]:
        """從回應中提取 function calls"""
        function_calls = []
        json_pattern = r'```json\s*(\{[^}]*"function_name"[^}]*\})[^`]*```'
        
        logger.debug(f"🔍 Anthropic Model: Searching for function calls in response")
        logger.debug(f"📝 Response text length: {len(response_text)} chars")
        
        matches = re.findall(json_pattern, response_text, re.DOTALL)
        logger.info(f"🎯 Found {len(matches)} potential function call matches")
        
        for i, match in enumerate(matches, 1):
            try:
                logger.debug(f"📋 Parsing function call {i}: {match.strip()}")
                function_call = json.loads(match.strip())
                
                if 'function_name' in function_call and 'arguments' in function_call:
                    function_name = function_call['function_name']
                    logger.info(f"✅ Valid function call {i}: {function_name}")
                    logger.debug(f"📊 Arguments: {json.dumps(function_call['arguments'], ensure_ascii=False)}")
                    function_calls.append(function_call)
                else:
                    logger.warning(f"⚠️ Invalid function call structure {i}: missing function_name or arguments")
                    
            except json.JSONDecodeError as e:
                logger.warning(f"❌ Failed to parse function call JSON {i}: {e}")
                logger.debug(f"📄 Invalid JSON: {match.strip()}")
                continue
        
        logger.info(f"📋 Extracted {len(function_calls)} valid function calls")
        return function_calls
    
    async def chat_completion_with_mcp(self, messages: List[ChatMessage], **kwargs) -> Tuple[bool, Optional[ChatResponse], Optional[str]]:
        """支援 MCP function calling 的對話完成"""
        if not self.enable_mcp or not self.mcp_service:
            return self.chat_completion(messages, **kwargs)
        
        try:
            # 執行初始對話
            is_successful, chat_response, error = self.chat_completion(messages, **kwargs)
            if not is_successful:
                return False, None, error
            
            response_text = chat_response.content
            
            # 檢查是否有 function calls
            if not self._has_function_calls(response_text):
                logger.debug("No function calls detected in response")
                return True, chat_response, None
            
            # 提取並執行 function calls
            function_calls = self._extract_function_calls(response_text)
            if not function_calls:
                logger.warning("Function call pattern detected but extraction failed")
                return True, chat_response, None
            
            logger.info(f"🔧 Anthropic Model: Processing {len(function_calls)} function calls")
            logger.debug(f"📋 Function calls detected: {[call['function_name'] for call in function_calls]}")
            
            # 執行 function calls 並收集結果
            function_results = []
            mcp_interactions = []  # 🔥 收集 MCP 互動資訊，用於前端顯示
            for i, function_call in enumerate(function_calls, 1):
                function_name = function_call['function_name']
                arguments = function_call['arguments']
                
                logger.info(f"🎯 Anthropic Model: Executing function {i}/{len(function_calls)}: {function_name}")
                logger.debug(f"📊 Function arguments: {json.dumps(arguments, ensure_ascii=False, indent=2)}")
                
                result = await self.mcp_service.handle_function_call(function_name, arguments)
                
                if result.get('success', False):
                    logger.info(f"✅ Function {function_name} executed successfully")
                else:
                    error_msg = result.get('error', 'Unknown error')
                    logger.error(f"❌ Function {function_name} failed: {error_msg}")
                
                function_results.append({
                    'function_name': function_name,
                    'arguments': arguments,
                    'result': result
                })
                
                # 🔥 提取 MCP 互動資訊
                if 'mcp_interaction' in result:
                    mcp_interactions.append(result['mcp_interaction'])
            
            # 建構包含 function results 的新對話
            logger.info("🔄 Anthropic Model: Formatting function results for final response")
            function_results_text = self._format_function_results(function_results)
            logger.debug(f"📄 Formatted function results: {function_results_text[:500]}...")
            
            # 添加 function results 並繼續對話
            extended_messages = messages.copy()
            extended_messages.append(ChatMessage(role='assistant', content=response_text))
            extended_messages.append(ChatMessage(role='user', content=f"Function call results:\n{function_results_text}\n\nPlease provide a final response based on these results."))
            
            logger.info(f"📤 Anthropic Model: Sending final request with {len(extended_messages)} messages")
            
            # 執行最終對話
            final_success, final_response, final_error = self.chat_completion(extended_messages, **kwargs)
            
            if final_success:
                # 組合最終回應，包含來源信息
                sources = self._extract_sources_from_function_results(function_results)
                final_response.metadata = final_response.metadata or {}
                final_response.metadata['function_calls'] = function_calls
                final_response.metadata['function_results'] = function_results
                final_response.metadata['sources'] = sources
                # 🔥 添加 MCP 互動資訊，供前端顯示
                final_response.metadata['mcp_interactions'] = mcp_interactions
                
                logger.info(f"✅ Anthropic Model: MCP workflow completed successfully")
                logger.info(f"📊 Final response: {len(final_response.content)} chars, {len(sources)} sources")
                logger.debug(f"📚 Sources extracted: {[source.get('filename', 'Unknown') for source in sources[:3]]}")
                logger.info(f"🔧 MCP interactions: {len(mcp_interactions)} tool calls recorded")
                
                return True, final_response, None
            else:
                logger.error(f"❌ Anthropic Model: Final response failed: {final_error}")
                return False, None, final_error
                
        except Exception as e:
            logger.error(f"Error in chat_completion_with_mcp: {e}")
            return False, None, str(e)
    
    def _format_function_results(self, function_results: List[Dict[str, Any]]) -> str:
        """格式化 function results 為文字"""
        formatted_results = []
        
        for i, result in enumerate(function_results, 1):
            function_name = result['function_name']
            success = result['result'].get('success', False)
            
            if success:
                data = result['result'].get('data', 'No data')
                formatted_results.append(f"{i}. {function_name}: {data}")
            else:
                error = result['result'].get('error', 'Unknown error')
                formatted_results.append(f"{i}. {function_name}: Error - {error}")
        
        return '\n'.join(formatted_results)
    
    def _extract_sources_from_function_results(self, function_results: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """從 function results 中提取來源信息"""
        sources = []
        
        for result in function_results:
            if result['result'].get('success'):
                metadata = result['result'].get('metadata', {})
                if 'sources' in metadata:
                    sources.extend(metadata['sources'])
        
        return sources
    
    def get_mcp_status(self) -> Dict[str, Any]:
        """取得 MCP 服務狀態"""
        return {
            "enabled": self.enable_mcp,
            "service_available": self.mcp_service is not None,
            "service_info": self.mcp_service.get_service_info() if self.mcp_service else None
        }
    
    def reload_mcp_config(self) -> bool:
        """重新載入 MCP 設定"""
        if self.mcp_service:
            success = self.mcp_service.reload_config()
            if success:
                # 重新建立 system prompt
                self.system_prompt = self._build_system_prompt()
                logger.info("Anthropic Model: MCP config reloaded and system prompt updated")
            return success
        return False

    def _build_files_context(self) -> str:
        files_context = "\n".join([f"- {info.filename}" for info in self.file_cache.values()])
        return f"{self.system_prompt}\n\nUse the following documents to answer the question:\n{files_context}"

    def _extract_sources_from_response(self, response_text: str) -> List[Dict[str, str]]:
        import re
        sources = []
        matches = set(re.findall(r'\[([^\]]+)\]', response_text))
        file_refs = {info.filename: info.file_id for info in self.file_cache.values()}
        for match in matches:
            if match in file_refs:
                sources.append({'file_id': file_refs[match], 'filename': match})
        return sources

    @retry_on_rate_limit(max_retries=3, base_delay=1.0)
    def _request(self, method: str, endpoint: str, body: Optional[Dict] = None, files: Optional[Dict] = None, data: Optional[Dict] = None) -> Tuple[bool, Optional[Dict], Optional[str]]:
        headers = {'x-api-key': self.api_key, 'anthropic-version': '2023-06-01'}
        if not files:
            headers['Content-Type'] = 'application/json'
        
        try:
            response = requests.request(
                method, f'{self.base_url}{endpoint}', headers=headers, json=body, 
                files=files, data=data, timeout=(30, 60)
            )
            
            # 檢查 HTTP 狀態碼但不拋出異常
            if response.status_code >= 400:
                error_msg = f"HTTP Error: {response.status_code}"
                try:
                    error_details = response.json()
                    error_msg = error_details.get('error', {}).get('message', error_msg)
                except json.JSONDecodeError:
                    error_msg = response.text
                return False, None, error_msg
            
            return True, response.json(), None
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP Error: {e.response.status_code}"
            try:
                error_details = e.response.json()
                error_msg = error_details.get('error', {}).get('message', error_msg)
            except json.JSONDecodeError:
                error_msg = e.response.text
            return False, None, error_msg
        except requests.exceptions.RequestException as e:
            raise e
