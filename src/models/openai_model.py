"""
OpenAI Model 實作
使用 OpenAI Responses API + Conversations API 提供聊天和音訊轉錄功能

📋 架構職責分工：
✅ RESPONSIBILITIES (模型層職責):
  - 實作統一的 FullLLMInterface 接口
  - 提供 chat_with_user() 文字對話功能
  - 提供 transcribe_audio() 音訊轉錄功能
  - 管理 OpenAI Conversations 和對話歷史
  - 處理 OpenAI API 限流和重試邏輯

❌ NEVER DO (絕對禁止):
  - 知道訊息來源平台 (LINE、Telegram 等)
  - 處理平台特定的訊息格式
  - 直接處理 webhook 或網路請求
  - 路由訊息或協調服務

🔄 統一接口：
  - chat_with_user(user_id, message, platform) -> (bool, RAGResponse, str)
  - transcribe_audio(file_path) -> (bool, str, str)
  - clear_user_history(user_id, platform) -> (bool, str)
  - check_connection() -> (bool, str)

🎯 模型特色：
  - 使用 Responses API 進行對話（取代 Assistant API）
  - 使用 Conversations API 管理對話狀態（取代 Threads API）
  - 支援 RAG（file_search 工具 + vector_store）
  - 同步回應，無需 Polling
  - 使用 Whisper API 進行音訊轉錄
  - DALL-E API 圖片生成
"""

import requests
import json
import yaml
import re
import time
from typing import List, Dict, Tuple, Optional, Any

from openai import OpenAI

from ..core.logger import get_logger
from ..core.api_timeouts import SmartTimeoutConfig
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

logger = get_logger(__name__)


class OpenAIModel(FullLLMInterface):
    """OpenAI 模型實作 - 使用 Responses API + Conversations API"""

    def __init__(self, api_key: str, assistant_id: str = None, base_url: str = None, enable_mcp: bool = False):
        self.api_key = api_key
        self.assistant_id = assistant_id  # 保留向後相容
        self.base_url = base_url or 'https://api.openai.com/v1'

        # 初始化 OpenAI SDK client
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self.client = OpenAI(**client_kwargs)

        # 從設定檔載入模型參數
        self._load_model_params()

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

        # 建構 system prompt（從 prompts.yml 載入）
        self.system_prompt = self._build_system_prompt()

    def get_provider(self) -> ModelProvider:
        return ModelProvider.OPENAI

    def _load_model_params(self):
        """從設定檔載入模型參數"""
        try:
            from ..core.config import get_value
            self.model = get_value('openai.model', 'gpt-5')
            self.max_output_tokens = get_value('openai.max_output_tokens', 8000)
            self.reasoning_effort = get_value('openai.reasoning_effort', None)
            self.temperature = get_value('openai.temperature', 0.1)
            self.vector_store_id = get_value('openai.vector_store_id', None)
        except Exception:
            self.model = 'gpt-5'
            self.max_output_tokens = 8000
            self.reasoning_effort = None
            self.temperature = 0.1
            self.vector_store_id = None

    def _get_model_params(self) -> Dict[str, Any]:
        """建構 responses.create() 所需的模型參數"""
        params = {
            "model": self.model,
            "max_output_tokens": self.max_output_tokens,
        }
        if self.reasoning_effort:
            params["reasoning"] = {"effort": self.reasoning_effort}
        else:
            params["temperature"] = self.temperature
        return params

    def _build_system_prompt(self) -> str:
        """從 prompts.yml 載入 system prompt"""
        base_prompt = "You are a helpful assistant."

        try:
            with open("config/prompts.yml", "r", encoding="utf-8") as f:
                prompts = yaml.safe_load(f)
            base_prompt = prompts.get("system_prompt", base_prompt)

            # MCP 啟用時附加 guidelines
            if self.enable_mcp and self.mcp_service:
                mcp_guidelines = prompts.get("mcp_guidelines", "")
                if mcp_guidelines:
                    base_prompt += "\n\n" + mcp_guidelines
        except FileNotFoundError:
            logger.warning("config/prompts.yml not found, using default system prompt")
            if self.enable_mcp:
                try:
                    from ..core.config import get_value
                    base_prompt = get_value('mcp.system_prompt', base_prompt)
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Error loading prompts.yml: {e}")

        return base_prompt

    # === MCP 支援 ===

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
                self.system_prompt = self._build_system_prompt()
                logger.info("OpenAI Model: MCP config reloaded and system prompt updated")
            return success
        return False

    # === 連線檢查與基本聊天 ===

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
        """OpenAI Chat Completion（保留給簡單的聊天完成需求）"""
        try:
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

    # === Responses API 核心 ===

    def _create_response(self, conversation_id: str, user_input: str):
        """
        呼叫 Responses API 建立回應

        Args:
            conversation_id: Conversation ID（取代 thread_id）
            user_input: 使用者訊息

        Returns:
            OpenAI Response 物件
        """
        model_params = self._get_model_params()

        # 建構 tools
        tools = []
        if self.vector_store_id:
            tools.append({
                "type": "file_search",
                "vector_store_ids": [self.vector_store_id],
            })

        # MCP function tools
        if self.enable_mcp and self.mcp_service:
            function_schemas = self.mcp_service.get_function_schemas_for_openai()
            if function_schemas:
                tools.extend(function_schemas)

        create_kwargs = {
            "instructions": self.system_prompt,
            "input": user_input,
            "conversation": conversation_id,
            "store": True,
            **model_params,
        }

        if tools:
            create_kwargs["tools"] = tools
            if self.vector_store_id:
                create_kwargs["include"] = ["file_search_call.results"]

        response = self.client.responses.create(**create_kwargs)

        # 處理 MCP function calls（如果有）
        if self.enable_mcp and self.mcp_service:
            response = self._handle_mcp_function_calls(response)

        return response

    def _handle_mcp_function_calls(self, response, max_iterations: int = 5):
        """處理 Responses API 中的 MCP function calls"""
        for iteration in range(max_iterations):
            function_calls = [
                item for item in response.output
                if item.type == "function_call"
            ]

            if not function_calls:
                return response

            logger.info(f"Processing {len(function_calls)} MCP function calls (iteration {iteration + 1})")

            function_outputs = []
            for fc in function_calls:
                try:
                    arguments = json.loads(fc.arguments) if isinstance(fc.arguments, str) else fc.arguments
                    result = self.mcp_service.handle_function_call_sync(fc.name, arguments)

                    function_outputs.append({
                        "type": "function_call_output",
                        "call_id": fc.call_id,
                        "output": json.dumps(result, ensure_ascii=False),
                    })

                    if result.get('success', False):
                        logger.info(f"MCP function {fc.name} executed successfully")
                    else:
                        logger.error(f"MCP function {fc.name} failed: {result.get('error', 'Unknown')}")
                except Exception as e:
                    logger.error(f"Error executing MCP function {fc.name}: {e}")
                    function_outputs.append({
                        "type": "function_call_output",
                        "call_id": fc.call_id,
                        "output": json.dumps({"success": False, "error": str(e)}, ensure_ascii=False),
                    })

            # 用 previous_response_id 繼續對話
            model_params = self._get_model_params()
            response = self.client.responses.create(
                input=function_outputs,
                previous_response_id=response.id,
                store=True,
                **model_params,
            )

        logger.warning(f"MCP function call loop exceeded {max_iterations} iterations")
        return response

    def _process_openai_response(self, response) -> Tuple[str, List[Dict[str, str]]]:
        """
        處理 Responses API 回應，提取文字和引用

        Responses API 的 annotation 格式：
          - annotation.type = 'file_citation'
          - annotation.index = N（字元位置）
          - annotation.file_id = 'file-xxx'
          - annotation.filename = 'xxx.pdf'（直接提供，不需另外查詢）

        Args:
            response: OpenAI Responses API 回應物件

        Returns:
            (formatted_text, sources)
        """
        try:
            # 從 output items 中提取文字和 annotations
            full_text = ""
            all_annotations = []

            for item in response.output:
                if item.type == "message":
                    for content_part in item.content:
                        if content_part.type == "output_text":
                            full_text = content_part.text
                            all_annotations = getattr(content_part, 'annotations', []) or []
                            break
                    break

            if not full_text:
                full_text = response.output_text or ""

            # 轉換為繁體中文
            text = s2t_converter.convert(full_text)

            if not all_annotations:
                logger.debug("_process_openai_response: no annotations")
                return text.strip(), []

            logger.debug(f"_process_openai_response: {len(all_annotations)} annotations")

            # 篩選 file_citation annotations
            file_citations = [
                ann for ann in all_annotations
                if getattr(ann, 'type', '') == 'file_citation'
            ]

            if not file_citations:
                return text.strip(), []

            # 建立引用對照表：filename -> citation number
            citation_map: Dict[str, int] = {}
            sources: List[Dict] = []
            next_num = 1

            for ann in file_citations:
                filename = getattr(ann, 'filename', None) or 'Unknown'
                file_id = getattr(ann, 'file_id', '')

                if filename not in citation_map:
                    citation_map[filename] = next_num
                    sources.append({
                        "file_id": file_id,
                        "filename": filename,
                        "quote": "",
                        "type": "file_citation",
                    })
                    next_num += 1

            # 在文字中插入引用標記 [N]
            # 按 index 從大到小排序，避免插入後位移影響前面的 index
            sorted_citations = sorted(
                file_citations,
                key=lambda a: getattr(a, 'index', 0),
                reverse=True
            )

            for ann in sorted_citations:
                idx = getattr(ann, 'index', None)
                if idx is None:
                    continue
                filename = getattr(ann, 'filename', 'Unknown')
                ref_num = citation_map.get(filename, 0)
                if ref_num > 0:
                    text = text[:idx] + f" [{ref_num}]" + text[idx:]

            # 去重連續引用標記
            final_text = dedup_citation_blocks(text.strip())

            logger.debug(f"_process_openai_response: text_len={len(final_text)}, {len(sources)} sources")
            return final_text, sources

        except Exception as e:
            logger.error(f"Error processing OpenAI response: {e}")
            try:
                return response.output_text or '', []
            except Exception:
                return '', []

    # === 對話管理（Conversations API，取代 Threads） ===

    def create_thread(self) -> Tuple[bool, Optional[ThreadInfo], Optional[str]]:
        """建立 OpenAI Conversation（取代 Thread）"""
        try:
            conversation = self.client.conversations.create()
            thread_info = ThreadInfo(
                thread_id=conversation.id,
                created_at=getattr(conversation, 'created_at', None),
                metadata={'object': getattr(conversation, 'object', None)}
            )
            return True, thread_info, None
        except Exception as e:
            return False, None, str(e)

    def delete_thread(self, thread_id: str) -> Tuple[bool, Optional[str]]:
        """刪除 Conversation（取代 Thread 刪除）"""
        try:
            self.client.conversations.delete(thread_id)
            return True, None
        except Exception as e:
            return False, str(e)

    def add_message_to_thread(self, thread_id: str, message: ChatMessage) -> Tuple[bool, Optional[str]]:
        """Responses API 不需要單獨添加訊息，訊息在 responses.create() 中直接傳入"""
        logger.debug("add_message_to_thread: no-op in Responses API mode")
        return True, None

    def run_assistant(self, thread_id: str, **kwargs) -> Tuple[bool, Optional[ChatResponse], Optional[str]]:
        """使用 Responses API 執行回應（取代 Assistant Run + Polling）"""
        try:
            user_input = kwargs.get('user_input', '')
            if not user_input:
                return False, None, "user_input is required"

            response = self._create_response(thread_id, user_input)
            formatted_content, sources = self._process_openai_response(response)

            chat_response = ChatResponse(
                content=formatted_content,
                metadata={
                    'response_id': response.id,
                    'sources': sources,
                    'usage': {
                        'input_tokens': response.usage.input_tokens if response.usage else None,
                        'output_tokens': response.usage.output_tokens if response.usage else None,
                    }
                }
            )
            return True, chat_response, None
        except Exception as e:
            return False, None, str(e)

    # === 用戶級對話管理 ===

    def chat_with_user(self, user_id: str, message: str, platform: str = 'line', **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        """主要對話接口：使用 Responses API + Conversations API"""
        try:
            from ..database.connection import get_thread_id_by_user_id, save_thread_id

            # 1. 取得或建立 conversation
            thread_id = get_thread_id_by_user_id(user_id, platform)

            # 舊 Assistant API 的 thread_id 格式為 thread_xxx，Responses API 需要 conv_ 開頭
            if thread_id and not thread_id.startswith('conv_'):
                logger.info(f"Migrating legacy thread_id {thread_id} for user {user_id} on {platform}")
                thread_id = None

            if not thread_id:
                is_successful, thread_info, error = self.create_thread()
                if not is_successful:
                    return False, None, f"Failed to create conversation: {error}"
                thread_id = thread_info.thread_id
                save_thread_id(user_id, thread_id, platform)
                logger.info(f"Created new conversation {thread_id} for user {user_id} on {platform}")

            # 2. 呼叫 Responses API
            response = self._create_response(thread_id, message)

            # 3. 處理回應
            formatted_content, sources = self._process_openai_response(response)

            # 4. 回傳 RAGResponse
            rag_response = RAGResponse(
                answer=formatted_content,
                sources=sources,
                metadata={
                    'user_id': user_id,
                    'thread_id': thread_id,
                    'model_provider': 'openai',
                    'response_id': response.id,
                    'uses_native_threads': True,
                }
            )

            logger.info(f"Completed OpenAI chat with user {user_id}, conversation {thread_id}, response length: {len(formatted_content)}")
            return True, rag_response, None

        except Exception as e:
            logger.error(f"Error in chat_with_user for user {user_id}: {e}")
            return False, None, str(e)

    def clear_user_history(self, user_id: str, platform: str = 'line') -> Tuple[bool, Optional[str]]:
        """清除用戶對話歷史（刪除 Conversation）"""
        try:
            from ..database.connection import get_thread_id_by_user_id, delete_thread_id

            thread_id = get_thread_id_by_user_id(user_id, platform)
            if not thread_id:
                logger.info(f"No conversation found for user {user_id} on {platform}")
                return True, None

            is_successful, error = self.delete_thread(thread_id)
            if not is_successful:
                logger.error(f"Failed to delete conversation {thread_id}: {error}")

            delete_thread_id(user_id, platform)

            logger.info(f"Cleared conversation history for user {user_id} on {platform}, conversation {thread_id}")
            return True, None
        except Exception as e:
            logger.error(f"Error clearing history for user {user_id}: {e}")
            return False, str(e)

    # === RAG 介面 ===

    def upload_knowledge_file(self, file_path: str, **kwargs) -> Tuple[bool, Optional[FileInfo], Optional[str]]:
        """上傳檔案到 OpenAI"""
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
        """使用 Responses API 進行 RAG 查詢"""
        try:
            if not thread_id:
                is_successful, thread_info, error_message = self.create_thread()
                if not is_successful:
                    return False, None, error_message
                thread_id = thread_info.thread_id

            response = self._create_response(thread_id, query)
            formatted_content, sources = self._process_openai_response(response)

            rag_response = RAGResponse(
                answer=formatted_content,
                sources=sources,
                metadata={
                    'thread_id': thread_id,
                    'model': 'openai-responses',
                    'response_id': response.id,
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
            is_successful, response, error_message = self._request('GET', '/files')

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
        """取得檔案引用對應表（Responses API 已直接提供 filename，此方法做為備用）"""
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

    # === 音訊與圖片 ===

    def transcribe_audio(self, audio_file_path: str, **kwargs) -> Tuple[bool, Optional[str], Optional[str]]:
        """音訊轉文字"""
        try:
            model = kwargs.get('model', 'gpt-4o-mini-transcribe')

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

    # === 向後相容 ===

    def check_token_valid(self):
        """向後相容方法"""
        is_successful, error = self.check_connection()
        return is_successful, None, error

    # === 內部 HTTP 請求 ===

    @retry_on_rate_limit(max_retries=3, base_delay=1.0)
    def _request(self, method: str, endpoint: str, body=None, files=None, operation='chat_completion'):
        """發送 HTTP 請求（用於非 Responses API 的端點：files, models, chat/completions 等）"""
        headers = {
            'Authorization': f'Bearer {self.api_key}'
        }

        timeout = SmartTimeoutConfig.get_timeout_for_model(operation, 'openai')

        try:
            if method == 'GET':
                if body:
                    headers['Content-Type'] = 'application/json'
                if 'models' in endpoint:
                    timeout = SmartTimeoutConfig.get_timeout('model_list')
                r = requests.get(f'{self.base_url}{endpoint}', headers=headers, timeout=timeout)
            elif method == 'POST':
                if body:
                    headers['Content-Type'] = 'application/json'
                if files:
                    timeout = SmartTimeoutConfig.get_timeout('file_upload')
                r = requests.post(f'{self.base_url}{endpoint}', headers=headers, json=body, files=files, timeout=timeout)
            elif method == 'DELETE':
                r = requests.delete(f'{self.base_url}{endpoint}', headers=headers, timeout=timeout)

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
                except Exception:
                    return False, None, f'HTTP {r.status_code}: {r.text[:200]}'

            response_data = r.json()
            if response_data.get('error'):
                return False, None, response_data.get('error', {}).get('message')

            return True, response_data, None

        except requests.exceptions.RequestException as e:
            raise e
        except Exception as e:
            return False, None, f'OpenAI API 系統不穩定，請稍後再試: {str(e)}'
