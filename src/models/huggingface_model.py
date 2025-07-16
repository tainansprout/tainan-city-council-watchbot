"""
Hugging Face API 模型整合
支援 Inference API, Serverless Inference 和多種開源模型
"""
import requests
import json
import time
import uuid
import base64
from typing import List, Dict, Tuple, Optional, Any
from ..core.logger import get_logger
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

logger = get_logger(__name__)

class HuggingFaceModel(FullLLMInterface):
    """
    Hugging Face API 模型實作
    
    📋 架構職責分工：
    ✅ RESPONSIBILITIES (模型層職責):
      - 實作統一的 FullLLMInterface 接口
      - 提供 chat_with_user() 文字對話功能
      - 提供 transcribe_audio() 音訊轉錄功能
      - 管理對話歷史和上下文
      - 處理 Hugging Face API 限流和重試邏輯

    🎯 模型特色：
    - 支援多種開源模型 (Mistral, Llama, CodeLlama等)
    - Inference API 彈性使用不同模型
    - 語音轉文字 (Whisper/Wav2Vec2 模型)
    - 圖片生成 (Stable Diffusion系列)
    - 對話歷史管理 (本地資料庫)

    ⚠️ 功能限制：
    - 模型可用性: 依賴 Hugging Face 服務和模型狀態
    - 音訊轉錄: 依賴特定ASR模型是否可用
    - 連線狀態: 服務可能因負載過高而不可用
    """
    
    def __init__(self, 
                 api_key: str,
                 model_name: str = "mistralai/Mistral-7B-Instruct-v0.1",
                 api_type: str = "inference_api",
                 base_url: str = "https://api-inference.huggingface.co",
                 enable_mcp: bool = False,
                 **kwargs):
        """
        初始化 Hugging Face 模型
        
        Args:
            api_key: Hugging Face API 金鑰
            model_name: 主要聊天模型名稱
            api_type: API 類型 (inference_api, serverless, dedicated)
            base_url: API 基礎 URL
            **kwargs: 額外配置參數
                - fallback_models: 備用模型列表
                - embedding_model: 嵌入模型
                - speech_model: 語音模型
                - image_model: 圖片生成模型
                - temperature: 生成溫度
                - max_tokens: 最大token數
                - timeout: 請求超時時間
        """
        self.api_key = api_key
        self.model_name = model_name
        self.api_type = api_type
        self.base_url = base_url
        
        # 功能專用模型配置（支援從配置覆蓋）
        self.embedding_model = kwargs.get('embedding_model', "sentence-transformers/all-MiniLM-L6-v2")
        self.speech_model = kwargs.get('speech_model', "openai/whisper-large-v3")
        self.image_model = kwargs.get('image_model', "stabilityai/stable-diffusion-xl-base-1.0")
        
        # 備用模型列表（支援從配置覆蓋）
        self.fallback_models = kwargs.get('fallback_models', [
            "microsoft/DialoGPT-medium",
            "HuggingFaceH4/zephyr-7b-beta",
            "mistralai/Mistral-7B-Instruct-v0.2"
        ])
        
        # 生成參數（支援從配置覆蓋）
        self.temperature = kwargs.get('temperature', 0.7)
        self.max_tokens = kwargs.get('max_tokens', 512)
        
        # HTTP 請求設定
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.timeout = kwargs.get('timeout', 60)  # 支援從配置覆蓋
        
        # 對話管理和本地存儲
        self.conversation_manager = get_conversation_manager()
        self.local_threads = {}  # 本地線程管理
        self.knowledge_store = {}  # 本地知識庫
        self.embeddings_cache = {}  # 嵌入向量緩存

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
        
        logger.info(f"HuggingFace model initialized: {self.model_name}")

    def get_provider(self) -> ModelProvider:
        """返回 Hugging Face 提供商標識""" 
        return ModelProvider.HUGGINGFACE

    def _init_mcp_service(self) -> None:
        """初始化 MCP 服務"""
        try:
            from ..services.mcp_service import get_mcp_service
            
            mcp_service = get_mcp_service()
            if mcp_service.is_enabled:
                self.mcp_service = mcp_service
                logger.info("HuggingFace Model: MCP service initialized successfully")
            else:
                logger.warning("HuggingFace Model: MCP service is not enabled")
                self.enable_mcp = False
        except Exception as e:
            logger.warning(f"HuggingFace Model: Failed to initialize MCP service: {e}")
            self.enable_mcp = False
            self.mcp_service = None

    def check_connection(self) -> Tuple[bool, Optional[str]]:
        """
        檢查 Hugging Face API 連接狀態
        
        Returns:
            Tuple[bool, Optional[str]]: (連接成功, 錯誤訊息)
        """
        try:
            # 使用簡單的文本生成測試連接
            test_message = ChatMessage(role="user", content="Hello")
            is_successful, response, error = self.chat_completion([test_message], max_tokens=10)
            
            if is_successful:
                logger.info("HuggingFace API connection verified")
                return True, None
            else:
                logger.error(f"HuggingFace API connection failed: {error}")
                return False, error
                
        except Exception as e:
            error_msg = f"HuggingFace connection check failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def chat_completion(self, messages: List[ChatMessage], **kwargs) -> Tuple[bool, Optional[ChatResponse], Optional[str]]:
        """
        Hugging Face 聊天完成功能
        
        Args:
            messages: 對話訊息列表
            **kwargs: 生成參數
                - max_tokens: 最大生成長度 (default: 512)
                - temperature: 創造性控制 (default: 0.7)
                - do_sample: 是否使用採樣 (default: True)
                - top_p: 核採樣參數 (default: 0.9)
        
        Returns:
            Tuple[bool, Optional[ChatResponse], Optional[str]]
        """
        try:
            # 提取參數
            max_tokens = kwargs.get('max_tokens', 512)
            temperature = kwargs.get('temperature', 0.7)
            do_sample = kwargs.get('do_sample', True)
            top_p = kwargs.get('top_p', 0.9)
            
            # 構建 Hugging Face 格式的輸入
            prompt = self._build_chat_prompt(messages)
            
            # 準備 API 請求
            payload = {
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": max_tokens,
                    "temperature": temperature,
                    "do_sample": do_sample,
                    "top_p": top_p,
                    "return_full_text": False  # 只返回生成的部分
                },
                "options": {
                    "wait_for_model": True,  # 等待模型載入
                    "use_cache": False  # 避免緩存問題
                }
            }
            
            # 發送請求
            response = self._make_request(self.model_name, payload)
            
            if not response:
                return False, None, "Failed to get response from Hugging Face API"
            
            # 解析回應
            if isinstance(response, list) and len(response) > 0:
                generated_text = response[0].get('generated_text', '').strip()
            elif isinstance(response, dict):
                generated_text = response.get('generated_text', '').strip()
            else:
                generated_text = str(response).strip()
            
            if not generated_text:
                return False, None, "Empty response from model"
            
            # 創建 ChatResponse
            chat_response = ChatResponse(
                content=generated_text,
                finish_reason="stop",
                metadata={
                    "model": self.model_name,
                    "provider": "huggingface",
                    "api_type": self.api_type,
                    "input_tokens": len(prompt.split()),
                    "output_tokens": len(generated_text.split())
                }
            )
            
            logger.debug(f"HuggingFace chat completion successful: {len(generated_text)} chars")
            return True, chat_response, None
            
        except Exception as e:
            error_msg = f"HuggingFace chat completion failed: {str(e)}"
            logger.error(error_msg)
            
            # 嘗試備用模型
            if hasattr(self, '_retry_count') and self._retry_count < len(self.fallback_models):
                fallback_model = self.fallback_models[self._retry_count]
                logger.info(f"Trying fallback model: {fallback_model}")
                
                original_model = self.model_name
                self.model_name = fallback_model
                self._retry_count += 1
                
                try:
                    result = self.chat_completion(messages, **kwargs)
                    self.model_name = original_model  # 恢復原始模型
                    return result
                except:
                    self.model_name = original_model
            
            return False, None, error_msg

    def _build_chat_prompt(self, messages: List[ChatMessage]) -> str:
        """
        將 ChatMessage 列表轉換為 Hugging Face 模型格式的提示詞
        
        不同模型可能需要不同的格式，這裡使用通用的聊天格式
        """
        if "mistral" in self.model_name.lower():
            # Mistral 格式: <s>[INST] prompt [/INST]
            user_messages = [msg for msg in messages if msg.role == "user"]
            assistant_messages = [msg for msg in messages if msg.role == "assistant"]
            system_messages = [msg for msg in messages if msg.role == "system"]
            
            prompt_parts = []
            
            # 添加系統訊息
            if system_messages:
                system_content = " ".join([msg.content for msg in system_messages])
                prompt_parts.append(f"<s>[INST] {system_content}")
            
            # 構建對話
            for i, msg in enumerate(messages):
                if msg.role == "user":
                    if i == 0 and not system_messages:
                        prompt_parts.append(f"<s>[INST] {msg.content} [/INST]")
                    else:
                        prompt_parts.append(f"[INST] {msg.content} [/INST]")
                elif msg.role == "assistant":
                    prompt_parts.append(f" {msg.content}</s>")
            
            return " ".join(prompt_parts)
            
        elif "zephyr" in self.model_name.lower():
            # Zephyr 格式: <|system|>, <|user|>, <|assistant|>
            prompt_parts = []
            for msg in messages:
                if msg.role == "system":
                    prompt_parts.append(f"<|system|>\n{msg.content}</s>")
                elif msg.role == "user":
                    prompt_parts.append(f"<|user|>\n{msg.content}</s>")
                elif msg.role == "assistant":
                    prompt_parts.append(f"<|assistant|>\n{msg.content}</s>")
            
            prompt_parts.append("<|assistant|>\n")  # 提示模型生成
            return "\n".join(prompt_parts)
            
        else:
            # 通用格式: 簡單的角色標記
            prompt_parts = []
            for msg in messages:
                role_prefix = {
                    "system": "System:",
                    "user": "Human:",
                    "assistant": "Assistant:"
                }.get(msg.role, f"{msg.role.title()}:")
                
                prompt_parts.append(f"{role_prefix} {msg.content}")
            
            prompt_parts.append("Assistant:")  # 提示模型生成
            return "\n\n".join(prompt_parts)

    def _make_request(self, model_name: str, payload: Dict[str, Any], timeout: int = None) -> Optional[Any]:
        """
        向 Hugging Face API 發送請求
        
        Args:
            model_name: 模型名稱
            payload: 請求載荷
            timeout: 請求超時時間
            
        Returns:
            API 回應數據或 None
        """
        try:
            url = f"{self.base_url}/models/{model_name}"
            
            response = requests.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=timeout or self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 503:
                # 模型正在載入
                logger.warning(f"Model {model_name} is loading, waiting...")
                time.sleep(10)  # 等待模型載入
                return self._make_request(model_name, payload, timeout)
            else:
                logger.error(f"HuggingFace API error {response.status_code}: {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error(f"Request timeout for model {model_name}")
            return None
        except Exception as e:
            logger.error(f"Request failed for model {model_name}: {str(e)}")
            return None

    # ==================== UserConversationInterface ====================
    
    def chat_with_user(self, user_id: str, message: str, platform: str = 'line', **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        """
        與用戶進行對話，整合歷史記錄和 RAG 功能
        
        Args:
            user_id: 用戶 ID
            message: 用戶訊息
            platform: 平台標識
            **kwargs: 額外參數
                - conversation_limit: 對話歷史限制 (default: 10)
                - use_rag: 是否使用 RAG (default: True)
                - temperature: 生成溫度 (default: 0.7)
        
        Returns:
            Tuple[bool, Optional[RAGResponse], Optional[str]]
        """
        try:
            conversation_limit = kwargs.get('conversation_limit', 10)
            use_rag = kwargs.get('use_rag', True)
            
            # 1. 取得對話歷史
            conversation_history = self._get_recent_conversations(user_id, platform, conversation_limit)
            
            # 2. 檢查是否為重置命令
            if message.strip().lower() in ['/reset', '重置', '清除歷史']:
                success, error = self.clear_user_history(user_id, platform)
                if success:
                    reset_response = RAGResponse(
                        answer="已清除您的對話歷史，讓我們重新開始吧！",
                        sources=[],
                        metadata={
                            "user_id": user_id,
                            "platform": platform,
                            "model_provider": "huggingface",
                            "action": "reset_history"
                        }
                    )
                    return True, reset_response, None
                else:
                    return False, None, f"清除歷史失敗: {error}"
            
            # 3. 執行 RAG 查詢（如果啟用且有知識庫）
            if use_rag and self.knowledge_store:
                is_successful, rag_response, error = self.query_with_rag(
                    message, 
                    context_messages=conversation_history,
                    **kwargs
                )
                
                if is_successful and rag_response:
                    # 更新元數據
                    rag_response.metadata.update({
                        "user_id": user_id,
                        "platform": platform,
                        "model_provider": "huggingface",
                        "conversation_enabled": True
                    })
                    
                    # 保存對話歷史
                    self._save_conversation(user_id, platform, message, rag_response.answer)
                    
                    return True, rag_response, None
            
            # 4. 普通聊天對話（無 RAG）
            # 構建完整的對話上下文
            context_messages = self._build_conversation_context(conversation_history, message)
            
            if self.enable_mcp and self.mcp_service:
                # MCP 需要 async，但目前在 sync 模式下禁用
                logger.warning("MCP is disabled in sync mode. Falling back to regular chat.")
                is_successful, chat_response, error = self.chat_completion(context_messages, **kwargs)
                if is_successful:
                    rag_response = RAGResponse(
                        answer=chat_response.content,
                        sources=[],
                        metadata=chat_response.metadata
                    )
            else:
                is_successful, chat_response, error = self.chat_completion(context_messages, **kwargs)
                if is_successful:
                    rag_response = RAGResponse(
                        answer=chat_response.content,
                        sources=[],
                        metadata=chat_response.metadata
                    )

            if not is_successful:
                return False, None, error
            
            # 轉換為 RAGResponse 格式
            rag_response.metadata.update({
                "user_id": user_id,
                "platform": platform,
                "model_provider": "huggingface",
                "model_name": self.model_name,
                "rag_enabled": False,
                "conversation_enabled": True
            })
            
            # 保存對話歷史
            self._save_conversation(user_id, platform, message, rag_response.answer)
            
            logger.info(f"HuggingFace conversation completed for user {user_id}")
            return True, rag_response, None
            
        except Exception as e:
            error_msg = f"HuggingFace chat_with_user failed: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg

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
            
            logger.info(f"🔧 HuggingFace Model: Executing tool '{tool_name}' with args: {arguments}")
            tool_result = self.mcp_service.handle_function_call_sync(tool_name, arguments)
            
            # 5. 將工具結果加到對話歷史中
            final_messages.append(ChatMessage(role="assistant", content=response.content)) # 加入模型的工具請求
            final_messages.append(ChatMessage(
                role="function",
                content=json.dumps(tool_result, ensure_ascii=False),
                metadata={"function_name": tool_name}
            ))

            # 6. 再次呼叫模型，生成最終回覆
            logger.info("🔄 HuggingFace Model: Calling model again with tool result.")
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
            logger.error(f"Error in chat_completion_with_mcp for HuggingFace: {e}")
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
        base_prompt = self._build_system_prompt()
        
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
            logger.error(f"Failed to build MCP system prompt for HuggingFace: {e}")
            return base_prompt

    def clear_user_history(self, user_id: str, platform: str = 'line') -> Tuple[bool, Optional[str]]:
        """
        清除用戶對話歷史
        
        Args:
            user_id: 用戶 ID
            platform: 平台標識
            
        Returns:
            Tuple[bool, Optional[str]]: (成功狀態, 錯誤訊息)
        """
        try:
            # 清除數據庫中的對話歷史
            if self.conversation_manager:
                success = self.conversation_manager.clear_user_history(user_id, "huggingface", platform)
                if not success:
                    logger.warning(f"Failed to clear database history for user {user_id}")
            
            # 清除本地線程緩存
            thread_key = f"{user_id}:{platform}"
            if thread_key in self.local_threads:
                del self.local_threads[thread_key]
            
            logger.info(f"Cleared conversation history for user {user_id} on platform {platform}")
            return True, None
            
        except Exception as e:
            error_msg = f"Failed to clear user history: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def _get_recent_conversations(self, user_id: str, platform: str, limit: int = 10) -> List[Dict[str, Any]]:
        """取得用戶最近的對話歷史"""
        try:
            if self.conversation_manager:
                conversations = self.conversation_manager.get_recent_conversations(
                    user_id, "huggingface", platform, limit
                )
                return conversations or []
            return []
        except Exception as e:
            logger.error(f"Failed to get conversation history: {str(e)}")
            return []

    def _save_conversation(self, user_id: str, platform: str, user_message: str, assistant_response: str):
        """保存對話到歷史記錄"""
        try:
            if self.conversation_manager:
                # 保存用戶訊息
                self.conversation_manager.add_message(
                    user_id, "huggingface", "user", user_message, platform
                )
                # 保存助理回應
                self.conversation_manager.add_message(
                    user_id, "huggingface", "assistant", assistant_response, platform
                )
        except Exception as e:
            logger.error(f"Failed to save conversation: {str(e)}")

    def _build_conversation_context(self, conversation_history: List[Dict[str, Any]], current_message: str) -> List[ChatMessage]:
        """構建對話上下文"""
        messages = []
        
        # 添加系統提示
        system_prompt = self._build_system_prompt()
        messages.append(ChatMessage(role="system", content=system_prompt))
        
        # 添加歷史對話（限制數量避免超過 token 限制）
        for conv in conversation_history[-20:]:  # 最多 20 輪對話
            role = conv.get('role', 'user')
            content = conv.get('content', '')
            if content.strip():
                messages.append(ChatMessage(role=role, content=content))
        
        # 添加當前用戶訊息
        messages.append(ChatMessage(role="user", content=current_message))
        
        return messages

    def _build_system_prompt(self) -> str:
        """
        構建系統提示詞
        """
        return """你是一個專業的 AI 助理，基於 Hugging Face 開源模型技術。請遵循以下準則：

1. 提供準確、有用的回應
2. 使用繁體中文回答（除非用戶指定其他語言）
3. 保持友善和專業的語調
4. 如果不確定答案，請誠實說明
5. 可以參考提供的文檔來源給出更準確的回答

請根據用戶的問題提供最佳回應。"""

    # ==================== RAGInterface ====================
    
    def upload_knowledge_file(self, file_path: str, **kwargs) -> Tuple[bool, Optional[FileInfo], Optional[str]]:
        """
        上傳文件到本地知識庫
        
        Hugging Face 沒有原生文件存儲服務，所以我們使用本地實現
        """
        try:
            import os
            from pathlib import Path
            
            if not os.path.exists(file_path):
                return False, None, f"File not found: {file_path}"
            
            file_path_obj = Path(file_path)
            filename = file_path_obj.name
            file_size = file_path_obj.stat().st_size
            
            # 讀取文件內容
            content = self._read_file_content(file_path)
            if not content:
                return False, None, "Failed to read file content"
            
            # 生成文件 ID
            file_id = f"hf_{uuid.uuid4().hex[:12]}"
            
            # 將文件分塊
            chunks = self._chunk_text(content)
            
            # 為每個塊生成嵌入向量
            embedded_chunks = []
            for chunk in chunks:
                embedding = self._get_embedding(chunk['text'])
                if embedding:
                    chunk['embedding'] = embedding
                    embedded_chunks.append(chunk)
            
            # 存儲到本地知識庫
            self.knowledge_store[file_id] = {
                'filename': filename,
                'content': content,
                'chunks': embedded_chunks,
                'metadata': {
                    'size': file_size,
                    'chunks_count': len(embedded_chunks),
                    'upload_time': time.time()
                }
            }
            
            # 創建 FileInfo
            file_info = FileInfo(
                file_id=file_id,
                filename=filename,
                size=file_size,
                status="processed",
                metadata={
                    'chunks': len(embedded_chunks),
                    'provider': 'huggingface_local'
                }
            )
            
            logger.info(f"Knowledge file uploaded: {filename} ({len(embedded_chunks)} chunks)")
            return True, file_info, None
            
        except Exception as e:
            error_msg = f"Failed to upload knowledge file: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg

    def query_with_rag(self, query: str, thread_id: str = None, **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        """
        使用 RAG 功能進行查詢
        
        Args:
            query: 查詢文字
            thread_id: 線程 ID（未使用，保持接口一致性）
            **kwargs: 額外參數
                - context_messages: 對話上下文
                - top_k: 檢索結果數量 (default: 3)
                - similarity_threshold: 相似度閾值 (default: 0.7)
        """
        try:
            if not self.knowledge_store:
                # 沒有知識庫，使用普通對話
                return self._fallback_chat_completion(query, kwargs.get('context_messages', []))
            
            # 1. 生成查詢的嵌入向量
            query_embedding = self._get_embedding(query)
            if not query_embedding:
                logger.warning("Failed to generate query embedding, falling back to normal chat")
                return self._fallback_chat_completion(query, kwargs.get('context_messages', []))
            
            # 2. 檢索相關文檔片段
            top_k = kwargs.get('top_k', 3)
            similarity_threshold = kwargs.get('similarity_threshold', 0.7)
            
            relevant_chunks = self._vector_search(query_embedding, top_k, similarity_threshold)
            
            if not relevant_chunks:
                logger.info("No relevant documents found, using normal chat")
                return self._fallback_chat_completion(query, kwargs.get('context_messages', []))
            
            # 3. 構建包含檢索內容的上下文
            context_messages = self._build_rag_context(
                query, 
                relevant_chunks, 
                kwargs.get('context_messages', [])
            )
            
            # 4. 生成回應
            is_successful, chat_response, error = self.chat_completion(context_messages, **kwargs)
            
            if not is_successful:
                return False, None, error
            
            # 5. 處理引用和來源
            answer_with_citations, sources = self._process_inline_citations(
                chat_response.content, 
                relevant_chunks
            )
            
            # 6. 創建 RAGResponse
            rag_response = RAGResponse(
                answer=answer_with_citations,
                sources=sources,
                metadata={
                    "model_provider": "huggingface",
                    "model_name": self.model_name,
                    "rag_enabled": True,
                    "sources_count": len(sources),
                    "similarity_scores": [chunk.get('similarity', 0) for chunk in relevant_chunks],
                    **chat_response.metadata
                }
            )
            
            logger.info(f"RAG query completed with {len(sources)} sources")
            return True, rag_response, None
            
        except Exception as e:
            error_msg = f"RAG query failed: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg

    def get_knowledge_files(self) -> Tuple[bool, Optional[List[FileInfo]], Optional[str]]:
        """取得知識庫文件列表"""
        try:
            files = []
            for file_id, file_data in self.knowledge_store.items():
                file_info = FileInfo(
                    file_id=file_id,
                    filename=file_data['filename'],
                    size=file_data['metadata'].get('size', 0),
                    status="processed",
                    metadata=file_data['metadata']
                )
                files.append(file_info)
            
            return True, files, None
            
        except Exception as e:
            error_msg = f"Failed to get knowledge files: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg

    def get_file_references(self) -> Dict[str, str]:
        """取得文件引用映射"""
        references = {}
        for file_id, file_data in self.knowledge_store.items():
            filename = file_data['filename']
            # 移除擴展名
            clean_name = filename.rsplit('.', 1)[0] if '.' in filename else filename
            references[file_id] = clean_name
        return references

    # ==================== 輔助方法 ====================
    
    def _read_file_content(self, file_path: str) -> Optional[str]:
        """
        讀取文件內容
        """
        try:
            import os
            from pathlib import Path
            
            path = Path(file_path)
            
            if path.suffix.lower() == '.pdf':
                # PDF 文件處理
                try:
                    import PyPDF2
                    with open(file_path, 'rb') as file:
                        reader = PyPDF2.PdfReader(file)
                        text = ""
                        for page in reader.pages:
                            text += page.extract_text() + "\n"
                        return text
                except ImportError:
                    logger.warning("PyPDF2 not installed, cannot read PDF files")
                    return None
            
            elif path.suffix.lower() in ['.txt', '.md', '.json', '.csv']:
                # 文本文件處理
                encodings = ['utf-8', 'utf-8-sig', 'big5', 'gb2312']
                for encoding in encodings:
                    try:
                        with open(file_path, 'r', encoding=encoding) as file:
                            return file.read()
                    except UnicodeDecodeError:
                        continue
                
                logger.error(f"Cannot decode file {file_path} with any supported encoding")
                return None
            
            else:
                logger.warning(f"Unsupported file type: {path.suffix}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {str(e)}")
            return None

    def _chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 100) -> List[Dict[str, Any]]:
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

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """
        生成文本的嵌入向量
        """
        try:
            # 檢查緩存
            text_hash = str(hash(text))
            if text_hash in self.embeddings_cache:
                return self.embeddings_cache[text_hash]
            
            # 調用 Hugging Face Embedding API
            payload = {
                "inputs": text,
                "options": {"wait_for_model": True}
            }
            
            embedding = self._make_request(self.embedding_model, payload)
            
            if embedding and isinstance(embedding, list):
                # 緩存結果
                self.embeddings_cache[text_hash] = embedding
                return embedding
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to generate embedding: {str(e)}")
            return None

    def _vector_search(self, query_embedding: List[float], top_k: int = 3, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """向量搜索相關文檔"""
        try:
            results = []
            
            for file_id, file_data in self.knowledge_store.items():
                for chunk in file_data['chunks']:
                    if 'embedding' in chunk:
                        similarity = self._cosine_similarity(query_embedding, chunk['embedding'])
                        
                        if similarity >= threshold:
                            results.append({
                                'file_id': file_id,
                                'filename': file_data['filename'],
                                'text': chunk['text'],
                                'similarity': similarity
                            })
            
            # 按相似度排序
            results.sort(key=lambda x: x['similarity'], reverse=True)
            return results[:top_k]
            
        except Exception as e:
            logger.error(f"Vector search failed: {str(e)}")
            return []

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        計算餘弦相似度
        """
        try:
            import math
            
            dot_product = sum(a * b for a, b in zip(vec1, vec2))
            magnitude1 = math.sqrt(sum(a * a for a in vec1))
            magnitude2 = math.sqrt(sum(a * a for a in vec2))
            
            if magnitude1 == 0 or magnitude2 == 0:
                return 0.0
            
            return dot_product / (magnitude1 * magnitude2)
            
        except Exception as e:
            logger.error(f"Failed to calculate cosine similarity: {str(e)}")
            return 0.0

    def _build_rag_context(self, query: str, relevant_chunks: List[Dict[str, Any]], conversation_history: List[Dict[str, Any]]) -> List[ChatMessage]:
        """構建 RAG 上下文"""
        messages = []
        
        # 系統提示
        system_prompt = self._build_rag_system_prompt(relevant_chunks)
        messages.append(ChatMessage(role="system", content=system_prompt))
        
        # 對話歷史
        for conv in conversation_history[-10:]:  # 限制歷史長度
            role = conv.get('role', 'user')
            content = conv.get('content', '')
            if content.strip():
                messages.append(ChatMessage(role=role, content=content))
        
        # 當前查詢
        messages.append(ChatMessage(role="user", content=query))
        
        return messages

    def _build_rag_system_prompt(self, relevant_chunks: List[Dict[str, Any]]) -> str:
        """
        構建 RAG 系統提示
        """
        context_parts = []
        for i, chunk in enumerate(relevant_chunks, 1):
            filename = chunk['filename']
            text = chunk['text']
            context_parts.append(f"[{i}] 來源文件: {filename}\n內容: {text}")
        
        context_text = "\n\n".join(context_parts)
        
        return f"""你是一個專業的 AI 助理。請基於以下提供的文檔內容來回答用戶問題。

相關文檔內容：
{context_text}

回答指南：
1. 主要基於提供的文檔內容回答
2. 在回答中使用 [1], [2] 等數字來標註引用來源
3. 如果文檔內容不足以回答問題，可以結合你的知識補充
4. 保持回答準確、客觀、有用
5. 使用繁體中文回答"""

    def _process_inline_citations(self, text: str, relevant_chunks: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
        """處理內聯引用"""
        import re
        
        sources = []
        
        # 查找 [數字] 格式的引用
        citations = re.findall(r'\[(\d+)\]', text)
        
        for citation in set(citations):
            citation_num = int(citation)
            if 0 < citation_num <= len(relevant_chunks):
                chunk = relevant_chunks[citation_num - 1]
                sources.append({
                    'file_id': chunk['file_id'],
                    'filename': chunk['filename'],
                    'quote': chunk['text'][:200] + "..." if len(chunk['text']) > 200 else chunk['text'],
                    'type': 'file_citation'
                })
        
        # 如果沒有找到引用，使用所有檢索到的文檔作為來源
        if not sources:
            for chunk in relevant_chunks:
                sources.append({
                    'file_id': chunk['file_id'],
                    'filename': chunk['filename'],
                    'quote': chunk['text'][:200] + "..." if len(chunk['text']) > 200 else chunk['text'],
                    'type': 'file_citation'
                })
        
        return text, sources

    def _fallback_chat_completion(self, query: str, context_messages: List[Dict[str, Any]]) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        """
        備用聊天完成（無 RAG）
        """
        try:
            messages = self._build_conversation_context(context_messages, query)
            is_successful, chat_response, error = self.chat_completion(messages)
            
            if not is_successful:
                return False, None, error
            
            rag_response = RAGResponse(
                answer=chat_response.content,
                sources=[],
                metadata={
                    "model_provider": "huggingface",
                    "rag_enabled": False,
                    "no_sources": True,
                    **chat_response.metadata
                }
            )
            
            return True, rag_response, None
            
        except Exception as e:
            return False, None, str(e)

    # ==================== AssistantInterface ====================
    
    def create_thread(self) -> Tuple[bool, Optional[ThreadInfo], Optional[str]]:
        """創建新的對話線程"""
        try:
            thread_id = f"hf_thread_{uuid.uuid4().hex[:12]}"
            thread_info = ThreadInfo(
                thread_id=thread_id,
                created_at=str(int(time.time())),
                metadata={"provider": "huggingface", "messages": []}
            )
            
            self.local_threads[thread_id] = {
                "created_at": time.time(),
                "messages": []
            }
            
            return True, thread_info, None
            
        except Exception as e:
            return False, None, str(e)

    def delete_thread(self, thread_id: str) -> Tuple[bool, Optional[str]]:
        """刪除對話線程"""
        try:
            if thread_id in self.local_threads:
                del self.local_threads[thread_id]
            return True, None
        except Exception as e:
            return False, str(e)

    def add_message_to_thread(self, thread_id: str, message: ChatMessage) -> Tuple[bool, Optional[str]]:
        """添加訊息到線程"""
        try:
            if thread_id not in self.local_threads:
                return False, f"Thread {thread_id} not found"
            
            self.local_threads[thread_id]["messages"].append({
                "role": message.role,
                "content": message.content,
                "timestamp": time.time()
            })
            
            return True, None
        except Exception as e:
            return False, str(e)

    def run_assistant(self, thread_id: str, **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        """
        執行助理
        """
        try:
            if thread_id not in self.local_threads:
                return False, None, f"Thread {thread_id} not found"
            
            # 取得線程中的最後一個用戶訊息
            messages = self.local_threads[thread_id]["messages"]
            user_messages = [msg for msg in messages if msg["role"] == "user"]
            
            if not user_messages:
                return False, None, "No user message in thread"
            
            last_message = user_messages[-1]["content"]
            
            # 使用 query_with_rag 處理
            return self.query_with_rag(last_message, thread_id, **kwargs)
            
        except Exception as e:
            return False, None, str(e)

    # ==================== AudioInterface ====================
    
    def transcribe_audio(self, audio_file_path: str, **kwargs) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        語音轉文字
        """
        try:
            import os
            
            if not os.path.exists(audio_file_path):
                return False, None, f"Audio file not found: {audio_file_path}"
            
            # 讀取音頻文件
            with open(audio_file_path, 'rb') as audio_file:
                audio_data = audio_file.read()
            
            # 使用 Hugging Face Automatic Speech Recognition API
            headers = {
                "Authorization": f"Bearer {self.api_key}"
            }
            
            response = requests.post(
                f"{self.base_url}/models/{self.speech_model}",
                headers=headers,
                data=audio_data,
                timeout=120  # 語音處理可能需要更長時間
            )
            
            if response.status_code == 200:
                result = response.json()
                if isinstance(result, dict) and 'text' in result:
                    transcribed_text = result['text']
                elif isinstance(result, list) and len(result) > 0:
                    transcribed_text = result[0].get('text', str(result))
                else:
                    transcribed_text = str(result)
                
                logger.info(f"Audio transcription successful: {len(transcribed_text)} chars")
                return True, transcribed_text, None
            else:
                error_msg = f"Transcription failed: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return False, None, error_msg
                
        except Exception as e:
            error_msg = f"Audio transcription failed: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg

    # ==================== ImageInterface ====================
    
    def generate_image(self, prompt: str, **kwargs) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        圖片生成
        """
        try:
            # 準備請求參數
            payload = {
                "inputs": prompt,
                "parameters": {
                    "num_inference_steps": kwargs.get('steps', 20),
                    "guidance_scale": kwargs.get('guidance_scale', 7.5),
                    "width": kwargs.get('width', 512),
                    "height": kwargs.get('height', 512)
                },
                "options": {
                    "wait_for_model": True
                }
            }
            
            response = requests.post(
                f"{self.base_url}/models/{self.image_model}",
                headers=self.headers,
                json=payload,
                timeout=180  # 圖片生成需要較長時間
            )
            
            if response.status_code == 200:
                # Hugging Face 返回的是圖片的二進制數據
                image_data = response.content
                
                # 將圖片數據轉換為 base64 編碼
                image_base64 = base64.b64encode(image_data).decode('utf-8')
                image_url = f"data:image/png;base64,{image_base64}"
                
                logger.info(f"Image generation successful: {len(image_data)} bytes")
                return True, image_url, None
            else:
                error_msg = f"Image generation failed: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return False, None, error_msg
                
        except Exception as e:
            error_msg = f"Image generation failed: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg