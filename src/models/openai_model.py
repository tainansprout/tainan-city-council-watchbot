"""
OpenAI Model 實作
使用 OpenAI Assistant API 提供聊天和音訊轉錄功能

📋 架構職責分工：
✅ RESPONSIBILITIES (模型層職責):
  - 實作統一的 FullLLMInterface 接口
  - 提供 chat_with_user() 文字對話功能
  - 提供 transcribe_audio() 音訊轉錄功能
  - 管理 OpenAI Assistant threads 和對話歷史
  - 處理 OpenAI API 限流和重試邏輯

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
  - 使用 Assistant API 進行對話管理
  - 支援 RAG (檢索增強生成)
  - 使用 Whisper API 進行音訊轉錄
  - DALL-E API 圖片生成
  - 智慧重試和錯誤處理
  - Thread-based 對話歷史管理

✅ 完整功能支援：
  - 對話: Assistant API (最穩定)
  - 音訊轉錄: Whisper API (原生支援，最佳品質)
  - 圖片生成: DALL-E API (原生支援)
  - 連線狀態: 企業級穩定性
"""

import requests
from ..core.logger import get_logger
from ..core.api_timeouts import SmartTimeoutConfig, TimeoutContext
from ..core.smart_polling import OpenAIPollingStrategy, PollingContext
import re
from typing import List, Dict, Tuple, Optional, Any
import time

logger = get_logger(__name__)
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
from ..utils.retry import retry_with_backoff, retry_on_rate_limit, CircuitBreaker
from ..utils import s2t_converter, dedup_citation_blocks


class OpenAIModel(FullLLMInterface):
    """OpenAI 模型實作"""
    
    def __init__(self, api_key: str, assistant_id: str = None, base_url: str = None, enable_mcp: bool = None):
        self.api_key = api_key
        self.assistant_id = assistant_id
        self.base_url = base_url or 'https://api.openai.com/v1'
        self.polling_strategy = OpenAIPollingStrategy()
        
        # MCP 支援 - 從設定檔讀取
        if enable_mcp is None:
            try:
                from ..core.config import get_value
                feature_enabled = get_value('features.enable_mcp', False)
                mcp_enabled = get_value('mcp.enabled', False)
                self.enable_mcp = feature_enabled and mcp_enabled
            except Exception as e:
                logger.warning(f"Error reading MCP config: {e}")
                self.enable_mcp = False
        else:
            self.enable_mcp = enable_mcp
            
        self.mcp_service = None
        if self.enable_mcp:
            self._init_mcp_service()
        
        # 建構 system prompt（為未來的 Chat Completion API 準備）
        self.system_prompt = self._build_system_prompt()
    
    def get_provider(self) -> ModelProvider:
        return ModelProvider.OPENAI
    
    def _init_mcp_service(self) -> None:
        """初始化 MCP 服務"""
        try:
            from ..services.mcp_service import get_mcp_service
            
            mcp_service = get_mcp_service()
            if mcp_service.is_enabled:
                self.mcp_service = mcp_service
                logger.info("OpenAI Model: MCP service initialized successfully")
            else:
                logger.warning("OpenAI Model: MCP service is not enabled")
                self.enable_mcp = False
        except Exception as e:
            logger.warning(f"OpenAI Model: Failed to initialize MCP service: {e}")
            self.enable_mcp = False
            self.mcp_service = None
    
    def create_assistant_with_mcp_functions(self, **kwargs) -> Tuple[bool, Optional[str], Optional[str]]:
        """創建包含 MCP functions 的 Assistant"""
        try:
            if not self.enable_mcp or not self.mcp_service:
                logger.info("Creating regular assistant (MCP disabled)")
                return self._create_regular_assistant(**kwargs)
            
            # 取得 MCP function schemas
            function_schemas = self.mcp_service.get_function_schemas_for_openai()
            if not function_schemas:
                logger.warning("No MCP function schemas available, creating regular assistant")
                return self._create_regular_assistant(**kwargs)
            
            logger.info(f"Creating MCP-enabled assistant with {len(function_schemas)} functions")
            
            # 創建包含 MCP functions 的 Assistant
            json_body = {
                'name': kwargs.get('name', 'MCP-Enabled Assistant'),
                'instructions': kwargs.get('instructions', 'You are a helpful assistant with access to external tools.'),
                'model': kwargs.get('model', 'gpt-4'),
                'tools': function_schemas,
                'temperature': kwargs.get('temperature', 0.01)
            }
            
            is_successful, response, error_message = self._request('POST', '/assistants', body=json_body, assistant=True)
            
            if is_successful:
                assistant_id = response['id']
                self.assistant_id = assistant_id
                logger.info(f"Created MCP-enabled assistant: {assistant_id}")
                return True, assistant_id, None
            else:
                logger.error(f"Failed to create MCP assistant: {error_message}")
                return False, None, error_message
                
        except Exception as e:
            logger.error(f"Error creating MCP assistant: {e}")
            return False, None, str(e)
    
    def _create_regular_assistant(self, **kwargs) -> Tuple[bool, Optional[str], Optional[str]]:
        """創建一般的 Assistant（無 MCP functions）"""
        try:
            json_body = {
                'name': kwargs.get('name', 'Regular Assistant'),
                'instructions': kwargs.get('instructions', 'You are a helpful assistant.'),
                'model': kwargs.get('model', 'gpt-4'),
                'temperature': kwargs.get('temperature', 0.01)
            }
            
            is_successful, response, error_message = self._request('POST', '/assistants', body=json_body, assistant=True)
            
            if is_successful:
                assistant_id = response['id']
                self.assistant_id = assistant_id
                logger.info(f"Created regular assistant: {assistant_id}")
                return True, assistant_id, None
            else:
                return False, None, error_message
                
        except Exception as e:
            return False, None, str(e)
    
    def check_connection(self) -> Tuple[bool, Optional[str]]:
        """檢查 OpenAI API 連線"""
        try:
            is_successful, response, error_message = self._request('GET', '/models', operation='health_check')
            if is_successful:
                return True, None
            else:
                return False, error_message
        except Exception as e:
            return False, str(e)
    
    def chat_completion(self, messages: List[ChatMessage], **kwargs) -> Tuple[bool, Optional[ChatResponse], Optional[str]]:
        """OpenAI Chat Completion"""
        try:
            # 轉換訊息格式
            openai_messages = [
                {"role": msg.role, "content": msg.content} 
                for msg in messages
            ]
            
            json_body = {
                'model': kwargs.get('model', 'gpt-4'),
                'messages': openai_messages,
                'temperature': kwargs.get('temperature', 0.01)
            }
            
            is_successful, response, error_message = self._request('POST', '/chat/completions', body=json_body)
            
            if not is_successful:
                return False, None, error_message
            
            content = response['choices'][0]['message']['content']
            finish_reason = response['choices'][0].get('finish_reason')
            
            chat_response = ChatResponse(
                content=content,
                finish_reason=finish_reason,
                metadata={'usage': response.get('usage')}
            )
            
            return True, chat_response, None
            
        except Exception as e:
            return False, None, str(e)
    
    def create_thread(self) -> Tuple[bool, Optional[ThreadInfo], Optional[str]]:
        """建立 OpenAI Assistant 對話串"""
        try:
            is_successful, response, error_message = self._request('POST', '/threads', assistant=True)
            
            if not is_successful:
                return False, None, error_message
            
            thread_info = ThreadInfo(
                thread_id=response['id'],
                created_at=response.get('created_at'),
                metadata=response
            )
            
            return True, thread_info, None
            
        except Exception as e:
            return False, None, str(e)
    
    def delete_thread(self, thread_id: str) -> Tuple[bool, Optional[str]]:
        """刪除對話串"""
        try:
            endpoint = f'/threads/{thread_id}'
            is_successful, response, error_message = self._request('DELETE', endpoint, assistant=True)
            return is_successful, error_message
        except Exception as e:
            return False, str(e)
    
    def add_message_to_thread(self, thread_id: str, message: ChatMessage) -> Tuple[bool, Optional[str]]:
        """新增訊息到對話串"""
        try:
            endpoint = f'/threads/{thread_id}/messages'
            json_body = {
                'role': message.role,
                'content': message.content
            }
            is_successful, response, error_message = self._request('POST', endpoint, body=json_body, assistant=True)
            return is_successful, error_message
        except Exception as e:
            return False, str(e)
    
    def run_assistant(self, thread_id: str, **kwargs) -> Tuple[bool, Optional[ChatResponse], Optional[str]]:
        """執行 OpenAI Assistant（支援 MCP function calling）"""
        try:
            # 啟動執行
            endpoint = f'/threads/{thread_id}/runs'
            json_body = {
                'assistant_id': self.assistant_id,
                'temperature': kwargs.get('temperature', 0.01)
            }
            
            is_successful, run_response, error_message = self._request('POST', endpoint, body=json_body, assistant=True)
            if not is_successful:
                return False, None, error_message
            
            # 等待完成（包含 MCP function calling 處理）
            run_id = run_response['id']
            if self.enable_mcp and self.mcp_service:
                import asyncio
                is_successful, final_response, error_message = asyncio.run(
                    self._wait_for_run_completion_with_mcp(thread_id, run_id)
                )
            else:
                is_successful, final_response, error_message = self._wait_for_run_completion(thread_id, run_id)

            if not is_successful:
                return False, None, f"Assistant run failed: {error_message}"
            
            # 取得回應
            return self._get_thread_messages(thread_id)
            
        except Exception as e:
            return False, None, str(e)
    
    async def _wait_for_run_completion_with_mcp(self, thread_id: str, run_id: str, max_wait_time: int = None) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """智慧等待執行完成（支援 MCP function calling）"""
        
        if max_wait_time:
            self.polling_strategy.max_wait_time = max_wait_time
        
        max_iterations = 10  # 防止無限循環
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # 檢查執行狀態
            is_successful, response, error_message = self.retrieve_thread_run(thread_id, run_id)
            if not is_successful:
                return False, None, error_message
            
            status = response['status']
            logger.debug(f"Run {run_id} status: {status} (iteration {iteration})")
            
            if status == 'completed':
                return True, response, None
            elif status in ['failed', 'expired', 'cancelled']:
                return False, None, f"Run {status}: {response.get('last_error', {}).get('message', 'Unknown error')}"
            elif status == 'requires_action':
                # 處理 MCP function calling
                logger.info("Run requires action - processing MCP function calls")
                success = await self._handle_mcp_function_calls(thread_id, run_id, response)
                if not success:
                    return False, None, "Failed to handle MCP function calls"
                # 繼續輪詢
            elif status in ['queued', 'in_progress']:
                # 繼續等待
                pass
            
            # 等待一段時間再檢查
            import time
            time.sleep(1)
        
        return False, None, f"Run did not complete within {max_iterations} iterations"
    
    async def _handle_mcp_function_calls(self, thread_id: str, run_id: str, run_response: Dict) -> bool:
        """處理 MCP function calls"""
        try:
            required_action = run_response.get('required_action', {})
            tool_calls = required_action.get('submit_tool_outputs', {}).get('tool_calls', [])
            
            if not tool_calls:
                logger.warning("No tool calls found in requires_action")
                return False
            
            logger.info(f"Processing {len(tool_calls)} MCP function calls")
            tool_outputs = []
            
            for tool_call in tool_calls:
                function_name = tool_call['function']['name']
                arguments_str = tool_call['function']['arguments']
                
                try:
                    import json
                    arguments = json.loads(arguments_str)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in function arguments: {e}")
                    tool_outputs.append({
                        "tool_call_id": tool_call['id'],
                        "output": json.dumps({
                            "success": False,
                            "error": "Invalid function arguments format"
                        }, ensure_ascii=False)
                    })
                    continue
                
                logger.info(f"Executing MCP function: {function_name} with args: {arguments}")
                
                # 執行 MCP function call
                result = await self.mcp_service.handle_function_call(function_name, arguments)
                
                tool_outputs.append({
                    "tool_call_id": tool_call['id'],
                    "output": json.dumps(result, ensure_ascii=False)
                })
            
            # 提交 tool outputs 到 OpenAI
            endpoint = f'/threads/{thread_id}/runs/{run_id}/submit_tool_outputs'
            json_body = {
                "tool_outputs": tool_outputs
            }
            
            is_successful, response, error_message = self._request('POST', endpoint, body=json_body, assistant=True)
            
            if is_successful:
                logger.info(f"Successfully submitted {len(tool_outputs)} tool outputs")
                return True
            else:
                logger.error(f"Failed to submit tool outputs: {error_message}")
                return False
                
        except Exception as e:
            logger.error(f"Error handling MCP function calls: {e}")
            return False
    
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
                # 重新建構 system prompt
                self.system_prompt = self._build_system_prompt()
                logger.info("OpenAI Model: MCP config reloaded and system prompt updated")
            return success
        return False
    
    def _build_system_prompt(self) -> str:
        """建構 system prompt（為未來 Chat Completion API 使用）
        
        注意：OpenAI Assistant API 使用預設的 instructions，不會直接使用此 system prompt。
        但保留此功能以便未來可能的 Chat Completion API 整合。
        """
        # 從設定檔讀取基礎 system prompt
        if self.enable_mcp:
            try:
                from ..core.config import get_value
                base_prompt = get_value('mcp.system_prompt', "You are a helpful AI assistant.")
            except Exception:
                base_prompt = "You are a helpful AI assistant."
        else:
            base_prompt = "You are a helpful AI assistant."
        
        if self.enable_mcp and self.mcp_service:
            try:
                # 取得可用的 function schemas
                function_schemas = self.mcp_service.get_function_schemas_for_openai()
                if function_schemas:
                    base_prompt += """

## 工具調用能力 (Function Calling Capabilities)

您具備調用外部工具的能力，請遵循以下指引：

### 調用原則：
- 僅在用戶明確需要或有明確指示時調用工具
- 調用前向用戶說明將要執行的操作
- 對工具返回的結果進行適當的解釋和分析
- 明確標示資訊來源，提升回應的透明度

### 安全考量：
- 確保參數的準確性和完整性
- 對敏感查詢提供適當的上下文
- 保護用戶查詢的隱私性
- 遵循最小權限原則

### 錯誤處理：
- 如果工具調用失敗，解釋問題並提供替代方案
- 對不確定的結果進行適當的警示
- 引導用戶提供更明確的查詢條件

這些工具將通過 OpenAI function calling 機制自動調用，您無需手動格式化函數調用。"""
                    
                    logger.info("OpenAI Model: Added MCP tool usage guidelines to system prompt")
            except Exception as e:
                logger.error(f"Failed to add MCP guidelines to system prompt: {e}")
        
        return base_prompt
    
    # === RAG 介面實作（使用 OpenAI Assistant API） ===
    
    def upload_knowledge_file(self, file_path: str, **kwargs) -> Tuple[bool, Optional[FileInfo], Optional[str]]:
        """上傳檔案到 OpenAI（用於 Assistant API）"""
        try:
            with open(file_path, 'rb') as f:
                files = {
                    'file': f,
                    'purpose': (None, 'assistants')
                }
                is_successful, response, error_message = self._request('POST', '/files', files=files)
            
            if not is_successful:
                return False, None, error_message
            
            file_info = FileInfo(
                file_id=response['id'],
                filename=response['filename'],
                size=response.get('bytes'),
                status=response.get('status'),
                purpose=response.get('purpose'),
                metadata=response
            )
            
            return True, file_info, None
            
        except Exception as e:
            return False, None, str(e)
    
    def query_with_rag(self, query: str, thread_id: str = None, **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        """使用 OpenAI Assistant API 進行 RAG 查詢"""
        try:
            # 如果沒有 thread_id，建立新的
            if not thread_id:
                is_successful, thread_info, error_message = self.create_thread()
                if not is_successful:
                    return False, None, error_message
                thread_id = thread_info.thread_id
            
            # 新增訊息到對話串
            message = ChatMessage(role='user', content=query)
            is_successful, error_message = self.add_message_to_thread(thread_id, message)
            if not is_successful:
                return False, None, error_message
            
            # 執行助理
            is_successful, chat_response, error_message = self.run_assistant(thread_id, **kwargs)
            if not is_successful:
                return False, None, error_message
            
            # 使用 OpenAI 特定的引用處理邏輯
            thread_messages = chat_response.metadata.get('thread_messages', {})
            formatted_content, sources = self._process_openai_response(thread_messages)
            
            rag_response = RAGResponse(
                answer=formatted_content,
                sources=sources,
                metadata={
                    'thread_id': thread_id,
                    'model': 'openai-assistant',
                    'thread_messages': thread_messages,
                    'raw_content': chat_response.content
                }
            )
            
            return True, rag_response, None
            
        except Exception as e:
            return False, None, str(e)
    
    def get_knowledge_files(self) -> Tuple[bool, Optional[List[FileInfo]], Optional[str]]:
        """取得 OpenAI 檔案列表"""
        return self.list_files()
    
    def list_files(self) -> Tuple[bool, Optional[List[FileInfo]], Optional[str]]:
        """列出檔案"""
        try:
            is_successful, response, error_message = self._request('GET', '/files', assistant=True)
            
            if not is_successful:
                return False, None, error_message
            
            files = [
                FileInfo(
                    file_id=file['id'],
                    filename=file['filename'],
                    size=file.get('bytes'),
                    status=file.get('status'),
                    purpose=file.get('purpose'),
                    metadata=file
                )
                for file in response['data']
            ]
            
            return True, files, None
            
        except Exception as e:
            return False, None, str(e)
    
    def get_file_references(self) -> Dict[str, str]:
        """取得檔案引用對應表"""
        try:
            is_successful, files, error_message = self.list_files()
            if not is_successful:
                logger.warning(f"Failed to get file references: {error_message}")
                return {}
            
            file_dict = {}
            for file in files:
                filename = file.filename.replace('.txt', '').replace('.json', '')
                file_dict[file.file_id] = filename
            
            logger.debug(f"Loaded {len(file_dict)} file references")
            return file_dict
            
        except Exception as e:
            logger.error(f"Error getting file references: {e}")
            return {}
    
    def _process_openai_response(self, thread_messages: Dict) -> Tuple[str, List[Dict[str, str]]]:
        """
        處理 OpenAI Assistant API 的回應，包括引用格式化
        這個方法封裝了原本的 get_content_and_reference 邏輯
        """
        try:
            # 取得助理回應數據
            data = self._get_response_data(thread_messages)
            logger.debug("OpenAI Assistant response data:")
            logger.debug(data)
            if not data:
                logger.debug("_process_openai_response: 沒有找到助理回應數據")
                return '', []
            text = data['content'][0]['text']['value']
            annotations = data['content'][0]['text']['annotations']
            
            logger.debug(f"_process_openai_response: 註解數量={len(annotations)}")
            
            # 檢查是否有複雜引用格式在原始文本中
            complex_citations = re.findall(r'【[^】]+】', text)
            if complex_citations:
                logger.debug(f"_process_openai_response: 發現 {len(complex_citations)} 個複雜引用格式")
            
            # 轉換為繁體中文
            text = s2t_converter.convert(text)
            
            # 取得檔案字典用於引用處理
            file_dict = self.get_file_references()
            
            # 替換註釋文本和建立來源清單
            citation_map: dict[str, int] = {}
            sources: list[dict] = []
            next_num = 1  # 下一個可用的引用編號

            for annotation in annotations:
                original_text = s2t_converter.convert(annotation["text"])
                file_id = annotation["file_citation"]["file_id"]
                filename = file_dict.get(file_id, "Unknown")

                # 2) 取得（或產生）此檔案的編號
                if filename in citation_map:
                    ref_num = citation_map[filename]          # 已經有 → 直接重用
                else:
                    ref_num = next_num                        # 第一次看到 → 指派新號碼
                    citation_map[filename] = ref_num
                    next_num += 1

                    # 只在第一次看到時，把它放進 sources，避免重複
                    sources.append({
                        "file_id": file_id,
                        "filename": filename,
                        "quote": annotation["file_citation"].get("quote", ""),
                        "type": "file_citation",
                    })

                # 3) 取代正文中的引用標籤
                replacement_text = f"[{ref_num}]"
                text = text.replace(original_text, replacement_text)
            
            # 直接返回處理後的文本，讓 ResponseFormatter 統一處理 sources
            final_text = dedup_citation_blocks(text.strip())
            
            logger.debug(f"_process_openai_response: 最終文本長度={len(final_text)}, 生成了 {len(sources)} 個來源")
            
            return final_text, sources
            
        except Exception as e:
            logger.error(f"Error processing OpenAI response: {e}")
            return '', []
    
    def _get_response_data(self, response: Dict) -> Dict:
        """從 OpenAI 回應中提取助理數據"""
        try:
            for item in response.get('data', []):
                if item.get('role') == 'assistant' and item.get('content') and item['content'][0].get('type') == 'text':
                    return item
            return None
        except Exception as e:
            logger.error(f"Error getting response data: {e}")
            return None
    
    def transcribe_audio(self, audio_file_path: str, **kwargs) -> Tuple[bool, Optional[str], Optional[str]]:
        """音訊轉文字"""
        try:
            # OpenAI 模型預設使用 whisper-1
            model = kwargs.get('model', 'whisper-1')
            
            files = {
                'file': open(audio_file_path, 'rb'),
                'model': (None, model),
            }
            is_successful, response, error_message = self._request('POST', '/audio/transcriptions', files=files, operation='audio_transcription')
            
            if not is_successful:
                return False, None, error_message
            
            return True, response['text'], None
            
        except Exception as e:
            return False, None, str(e)
    
    def generate_image(self, prompt: str, **kwargs) -> Tuple[bool, Optional[str], Optional[str]]:
        """生成圖片"""
        try:
            json_body = {
                "prompt": prompt,
                "n": kwargs.get('n', 1),
                "size": kwargs.get('size', '512x512')
            }
            is_successful, response, error_message = self._request('POST', '/images/generations', body=json_body)
            
            if not is_successful:
                return False, None, error_message
            
            image_url = response['data'][0]['url']
            return True, image_url, None
            
        except Exception as e:
            return False, None, str(e)
    
    # === 向後相容的方法 ===
    def check_token_valid(self):
        """向後相容方法"""
        is_successful, error = self.check_connection()
        return is_successful, None, error
    
    def retrieve_thread(self, thread_id: str):
        """向後相容方法"""
        try:
            endpoint = f'/threads/{thread_id}'
            return self._request('GET', endpoint, assistant=True)
        except Exception as e:
            return False, None, str(e)
    
    def create_thread_message(self, thread_id: str, content: str):
        """向後相容方法"""
        message = ChatMessage(role='user', content=content)
        is_successful, error = self.add_message_to_thread(thread_id, message)
        return is_successful, None, error
    
    def create_thread_run(self, thread_id: str):
        """向後相容方法"""
        try:
            endpoint = f'/threads/{thread_id}/runs'
            json_body = {
                'assistant_id': self.assistant_id,
                'temperature': 0
            }
            return self._request('POST', endpoint, body=json_body, assistant=True, operation='assistant_run')
        except Exception as e:
            return False, None, str(e)
    
    def retrieve_thread_run(self, thread_id: str, run_id: str):
        """向後相容方法"""
        try:
            endpoint = f'/threads/{thread_id}/runs/{run_id}'
            return self._request('GET', endpoint, assistant=True)
        except Exception as e:
            return False, None, str(e)
    
    def list_thread_messages(self, thread_id: str):
        """向後相容方法"""
        try:
            endpoint = f'/threads/{thread_id}/messages'
            return self._request('GET', endpoint, assistant=True)
        except Exception as e:
            return False, None, str(e)
    
    def audio_transcriptions(self, file_path: str, model: str):
        """向後相容方法"""
        return self.transcribe_audio(file_path, model=model)
    
    # === 內部方法 ===
    @retry_on_rate_limit(max_retries=3, base_delay=1.0)
    def _request(self, method: str, endpoint: str, body=None, files=None, assistant=False, operation='chat_completion'):
        """發送 HTTP 請求（智慧超時配置）"""
        headers = {
            'Authorization': f'Bearer {self.api_key}'
        }
        
        # 根據操作類型決定超時時間
        timeout = SmartTimeoutConfig.get_timeout_for_model(operation, 'openai')
        
        try:
            if method == 'GET':
                if assistant:
                    headers['Content-Type'] = 'application/json'
                    headers['OpenAI-Beta'] = 'assistants=v2'
                if 'models' in endpoint:
                    timeout = SmartTimeoutConfig.get_timeout('model_list')
                r = requests.get(f'{self.base_url}{endpoint}', headers=headers, timeout=timeout)
            elif method == 'POST':
                if body:
                    headers['Content-Type'] = 'application/json'
                if assistant:
                    headers['OpenAI-Beta'] = 'assistants=v2'
                if files:  # 檔案上傳
                    timeout = SmartTimeoutConfig.get_timeout('file_upload')
                r = requests.post(f'{self.base_url}{endpoint}', headers=headers, json=body, files=files, timeout=timeout)
            elif method == 'DELETE':
                if assistant:
                    headers['OpenAI-Beta'] = 'assistants=v2'
                r = requests.delete(f'{self.base_url}{endpoint}', headers=headers, timeout=timeout)
            
            # 檢查 HTTP 狀態碼
            if r.status_code == 429:  # Rate limit
                raise requests.exceptions.RequestException(f"Rate limit exceeded: {r.status_code}")
            elif r.status_code >= 500:  # Server error
                raise requests.exceptions.RequestException(f"Server error: {r.status_code}")
            elif r.status_code >= 400:  # Client error
                try:
                    error_data = r.json()
                    error_msg = error_data.get('error', {}).get('message', f'HTTP {r.status_code}')
                    return False, None, error_msg
                except:
                    return False, None, f'HTTP {r.status_code}: {r.text[:200]}'
            
            response_data = r.json()
            if response_data.get('error'):
                return False, None, response_data.get('error', {}).get('message')
                
            return True, response_data, None
            
        except requests.exceptions.RequestException as e:
            # 網路相關錯誤會被重試裝飾器處理
            raise e
        except Exception as e:
            return False, None, f'OpenAI API 系統不穩定，請稍後再試: {str(e)}'
    
    def _wait_for_run_completion(self, thread_id: str, run_id: str, max_wait_time: int = None) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """智慧等待執行完成 - 使用 5s→3s→2s→1s→1s 策略"""
        
        # 使用智慧輪詢策略
        if max_wait_time:
            self.polling_strategy.max_wait_time = max_wait_time
        
        def check_run_status():
            """檢查執行狀態的回調函數"""
            is_successful, response, error_message = self.retrieve_thread_run(thread_id, run_id)
            if not is_successful:
                return False, 'error', error_message
            
            status = response['status']
            return True, status, response
        
        # 使用智慧輪詢等待
        with PollingContext(f"OpenAI Assistant Run {run_id}", self.polling_strategy) as context:
            return context.wait_for_condition(
                check_function=check_run_status,
                completion_statuses=['completed'],
                failure_statuses=['failed', 'expired', 'cancelled', 'requires_action']
            )
    
    def _get_thread_messages(self, thread_id: str) -> Tuple[bool, Optional[ChatResponse], Optional[str]]:
        """取得對話串訊息"""
        try:
            is_successful, response, error_message = self.list_thread_messages(thread_id)
            if not is_successful:
                return False, None, error_message
            
            # 記錄完整的API回應用於除錯
            logger.debug(f"OpenAI Assistant API 完整回應: {response}")
            # 取得最新的助理回應
            for message in response['data']:
                if message['role'] == 'assistant' and message['content']:
                    content = message['content'][0]['text']['value']
                    chat_response = ChatResponse(
                        content=content,
                        metadata={'thread_messages': response}
                    )
                    return True, chat_response, None
            
            return False, None, "No assistant response found"
            
        except Exception as e:
            return False, None, str(e)
    
    # === 🆕 新的用戶級對話管理接口 ===
    
    def chat_with_user(self, user_id: str, message: str, platform: str = 'line', **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        """
        主要對話接口：使用 OpenAI Assistant API 的 thread 系統
        
        OpenAI 使用原生 thread 管理，與其他模型的簡化對話歷史不同
        
        Args:
            user_id: 用戶 ID (如 Line user ID)
            message: 用戶訊息
            platform: 平台識別 (\'line\', \'discord\', \'telegram\')
            **kwargs: 額外參數
                
        Returns:
            (is_successful, rag_response, error_message)
        """
        try:
            # 1. 取得或創建用戶的 thread
            from ..database.connection import get_thread_id_by_user_id, save_thread_id
            
            thread_id = get_thread_id_by_user_id(user_id, platform)
            
            if not thread_id:
                # 創建新 thread
                is_successful, thread_info, error = self.create_thread()
                if not is_successful:
                    return False, None, f"Failed to create thread: {error}"
                
                thread_id = thread_info.thread_id
                save_thread_id(user_id, thread_id, platform)
                logger.info(f"Created new thread {thread_id} for user {user_id} on platform {platform}")
            
            # 2. 添加用戶訊息到 thread
            user_message = ChatMessage(role='user', content=message)
            is_successful, error = self.add_message_to_thread(thread_id, user_message)
            if not is_successful:
                return False, None, f"Failed to add message to thread: {error}"
            
            # 3. 執行 Assistant
            is_successful, chat_response, error = self.run_assistant(thread_id, **kwargs)
            if not is_successful:
                return False, None, error
            
            # 4. 處理 OpenAI 回應格式（引用等）
            thread_messages = chat_response.metadata.get('thread_messages', {})
            formatted_content, sources = self._process_openai_response(thread_messages)
            
            # 5. 將處理後的內容轉換為 RAGResponse
            rag_response = RAGResponse(
                answer=formatted_content,
                sources=sources,  # 傳遞 sources 給 ResponseFormatter 統一處理
                metadata={
                    'user_id': user_id,
                    'thread_id': thread_id,
                    'model_provider': 'openai',
                    'uses_native_threads': True,
                    'finish_reason': chat_response.finish_reason,
                    'raw_metadata': chat_response.metadata,
                    'raw_content': chat_response.content
                }
            )
            
            logger.info(f"Completed OpenAI chat with user {user_id}, thread {thread_id}, response length: {len(rag_response.answer) if rag_response else 0}")
            return True, rag_response, None
            
        except Exception as e:
            logger.error(f"Error in chat_with_user for user {user_id}: {e}")
            return False, None, str(e)
    
    def clear_user_history(self, user_id: str, platform: str = 'line') -> Tuple[bool, Optional[str]]:
        """清除用戶對話歷史（刪除 OpenAI thread）"""
        try:
            from ..database.connection import get_thread_id_by_user_id, delete_thread_id
            
            # 1. 取得用戶的 thread ID
            thread_id = get_thread_id_by_user_id(user_id, platform)
            if not thread_id:
                logger.info(f"No thread found for user {user_id} on platform {platform}")
                return True, None  # 沒有 thread 也算成功
            
            # 2. 刪除 OpenAI thread
            is_successful, error = self.delete_thread(thread_id)
            if not is_successful:
                logger.error(f"Failed to delete OpenAI thread {thread_id}: {error}")
                # 繼續執行，至少清除本地記錄
            
            # 3. 刪除本地 thread 記錄
            delete_thread_id(user_id, platform)
            
            logger.info(f"Cleared conversation history for user {user_id} on platform {platform}, thread {thread_id}")
            return True, None
            
        except Exception as e:
            logger.error(f"Error clearing history for user {user_id}: {e}")
            return False, str(e)