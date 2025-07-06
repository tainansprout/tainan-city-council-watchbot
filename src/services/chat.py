"""
核心聊天服務 - 平台無關的聊天邏輯
"""
import time
import os
from ..core.logger import get_logger
from typing import Dict, Any, Optional, Tuple
from ..models.base import FullLLMInterface, ModelProvider
from ..database.connection import Database
from ..utils import preprocess_text, postprocess_text
from ..core.exceptions import OpenAIError, DatabaseError, ThreadError
from ..core.error_handler import ErrorHandler
from .response import ResponseFormatter
from ..platforms.base import PlatformMessage, PlatformResponse, PlatformUser

logger = get_logger(__name__)


class CoreChatService:
    """
    核心聊天服務 - 處理平台無關的聊天邏輯
    
    這個服務專注於：
    1. 模型交互
    2. 對話歷史管理  
    3. 文字處理
    4. 錯誤處理
    
    不包含任何平台特定的邏輯
    """
    
    def __init__(self, model: FullLLMInterface, database: Database, config: Dict[str, Any]):
        self.model = model
        self.database = database
        self.config = config
        self.error_handler = ErrorHandler()
        self.response_formatter = ResponseFormatter(config)
        try:
            provider = model.get_provider()
            provider_name = provider.value if hasattr(provider, 'value') else str(provider)
            logger.info(f"CoreChatService initialized with model: {provider_name}")
        except (ValueError, AttributeError):
            pass
    
    def process_message(self, message: PlatformMessage) -> PlatformResponse:
        """
        處理平台訊息並返回統一的回應格式
        
        Args:
            message: 統一格式的平台訊息
            
        Returns:
            PlatformResponse: 統一格式的回應
        """
        user = message.user
        platform = user.platform.value
        try:
            logger.info(f'Processing message from {user.user_id} on {platform}: {message.content}')
        except ValueError:
            pass

        # 處理不同類型的訊息
        if message.message_type == "text":
            return self._handle_text_message(user, message.content, platform)
        elif message.message_type == "audio":
            return self._handle_audio_message(user, message.raw_data, platform)
        else:
            return PlatformResponse(
                content="抱歉，暫不支援此類型的訊息。",
                response_type="text"
            )
    
    def _handle_text_message(self, user: PlatformUser, text: str, platform: str) -> PlatformResponse:
        """處理文字訊息"""
        try:
            if text.startswith('/'):
                return self._handle_command(user, text, platform)
            else:
                return self._handle_chat_message(user, text, platform)
                
        except Exception as e:
            # 記錄詳細的錯誤 log
            try:
                logger.error(f"Error handling text message for user {user.user_id}: {type(e).__name__}: {e}")
            except ValueError:
                pass
            try:
                logger.error(f"Error details - Platform: {platform}, Message: {text[:100]}...")
            except ValueError:
                pass
            
            # 檢查是否為測試用戶（來自 /chat 介面）
            is_test_user = user.user_id.startswith("U" + "0" * 32)
            
            if is_test_user:
                # 測試用戶：拋出異常讓上層 /ask 端點處理，顯示詳細錯誤
                raise
            else:
                # 實際平台用戶：使用簡化錯誤訊息
                error_message = self.error_handler.get_error_message(e, use_detailed=False)
                return PlatformResponse(
                    content=error_message,
                    response_type="text"
                )
    
    def _handle_audio_message(self, user: PlatformUser, audio_data: bytes, platform: str) -> PlatformResponse:
        """處理音訊訊息"""
        import os
        import uuid
        from ..core.exceptions import OpenAIError
        
        input_audio_path = None
        
        try:
            # 儲存音訊檔案
            input_audio_path = self._save_audio_file(audio_data)
            
            # 轉錄音訊
            text = self._transcribe_audio(input_audio_path)
            try:
                logger.info(f"Audio transcribed for user {user.user_id}: {text}")
            except ValueError:
                pass
            
            # 處理轉錄的文字
            return self._handle_chat_message(user, text, platform)
            
        except Exception as e:
            # 記錄詳細的錯誤 log
            try:
                logger.error(f"Error processing audio for user {user.user_id}: {type(e).__name__}: {e}")
            except ValueError:
                pass
            try:
                logger.error(f"Error details - Platform: {platform}, Audio size: {len(audio_data) if audio_data else 0} bytes")
            except ValueError:
                pass
            
            # 檢查是否為測試用戶（來自 /chat 介面）
            is_test_user = user.user_id.startswith("U" + "0" * 32)
            
            if is_test_user:
                # 測試用戶：拋出異常讓上層 /ask 端點處理，顯示詳細錯誤
                raise
            else:
                # 實際平台用戶：使用簡化錯誤訊息
                error_message = self.error_handler.get_error_message(e, use_detailed=False)
                return PlatformResponse(
                    content=error_message,
                    response_type="text"
                )
        
        finally:
            self._delete_audio_file(input_audio_path)
    
    def _handle_command(self, user: PlatformUser, text: str, platform: str) -> PlatformResponse:
        """處理指令"""
        if text.startswith('/reset'):
            return self._handle_reset_command(user, platform)
        
        command = text[1:].split()[0]
        commands_config = self.config.get('commands', {})
        if command in commands_config:
            return PlatformResponse(
                content=commands_config[command] + "\n\n",
                response_type="text"
            )
        else:
            return PlatformResponse(
                content="Command not found.",
                response_type="text"
            )
    
    def _handle_reset_command(self, user: PlatformUser, platform: str) -> PlatformResponse:
        """處理重置指令 - 支援不同模型的重置策略"""
        try:
            # 使用統一接口清除對話歷史，thread_id 管理由模型層管理
            is_successful, error_message = self.model.clear_user_history(user.user_id, platform)
            if is_successful:
                return PlatformResponse(content='Reset The Chatbot.', response_type="text")
            else:
                try:
                    logger.warning(f"Failed to clear history for user {user.user_id}: {error_message}")
                except ValueError:
                    pass
                return PlatformResponse(content='Reset completed (with warnings).', response_type="text")
        except Exception as e:
            try:
                logger.error(f"Error resetting for user {user.user_id}: {e}")
            except ValueError:
                pass
            raise ThreadError(f"Failed to reset: {e}")
    
    def _handle_chat_message(self, user: PlatformUser, text: str, platform: str) -> PlatformResponse:
        """處理聊天訊息 - 支援統一接口和不同模型的對話管理策略"""
        try:
            # 預處理文字
            processed_text = preprocess_text(text, self.config)
            
            # 使用統一的對話處理邏輯，thread_id 等由模型層管理
            response_message = self._process_conversation(user, processed_text, platform)
            
            # 後處理回應
            final_response = postprocess_text(response_message, self.config)
            
            logger.info(f'Response message to {user.user_id} on {platform}: {final_response}')

            return PlatformResponse(
                content=final_response,
                response_type="text"
            )
            
        except Exception as e:
            # 記錄詳細的錯誤 log
            try:
                logger.error(f"Error processing chat message for user {user.user_id}: {type(e).__name__}: {e}")
            except ValueError:
                pass
            try:
                logger.error(f"Error details - Platform: {platform}, Processed text: {text[:100]}...")
            except ValueError:
                pass
            raise
    
    def _process_conversation(self, user: PlatformUser, text: str, platform: str) -> str:
        """處理對話邏輯 - 使用統一的 chat_with_user 接口，thread_id 由模型層管理"""
        try:
            is_successful, rag_response, error_message = self.model.chat_with_user(
                user_id=user.user_id,
                message=text,
                platform=platform
            )
            if not is_successful:
                # 檢查原始錯誤訊息，保留原始錯誤類型
                if error_message and 'database' in error_message.lower():
                    raise DatabaseError(error_message)
                elif error_message and ('column' in error_message.lower() or 'sql' in error_message.lower()):
                    raise DatabaseError(error_message)
                else:
                    raise OpenAIError(f"Chat with user failed: {error_message}")
            formatted_response = self.response_formatter.format_rag_response(rag_response)
            try:
                logger.debug(f"Processed conversation response length: {len(formatted_response)}")
            except ValueError:
                pass
            return formatted_response
        except Exception as e:
            if isinstance(e, (OpenAIError, DatabaseError)):
                raise
            # 檢查是否為資料庫相關錯誤
            error_str = str(e).lower()
            if ('database' in error_str or 'sql' in error_str or 'column' in error_str or 
                'psycopg' in error_str or 'table' in error_str):
                raise DatabaseError(f"Database operation failed: {e}")
            raise OpenAIError(f"Conversation processing failed: {e}")
    
    def _save_audio_file(self, audio_content: bytes) -> str:
        """儲存音訊檔案到臨時位置"""
        import uuid
        from ..core.exceptions import OpenAIError
        
        try:
            input_audio_path = f'{str(uuid.uuid4())}.m4a'
            with open(input_audio_path, 'wb') as fd:
                fd.write(audio_content)
            try:
                logger.debug(f"Audio file saved: {input_audio_path}")
            except ValueError:
                pass
            return input_audio_path
        except Exception as e:
            raise OpenAIError(f"Failed to save audio file: {e}")

    def _delete_audio_file(self, file_path: Optional[str]) -> None:
        """刪除臨時音訊檔案"""
        if not file_path:
            return
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                try:
                    logger.debug(f"Cleaned up audio file: {file_path}")
                except ValueError:
                    pass
        except Exception as e:
            try:
                logger.warning(f"Failed to clean up audio file {file_path}: {e}")
            except ValueError:
                pass
    
    def _transcribe_audio(self, input_audio_path: str) -> str:
        """轉錄音訊檔案 - 使用統一接口"""
        try:
            # 使用統一的音訊轉錄接口，不指定特定模型
            is_successful, transcribed_text, error_message = self.model.transcribe_audio(
                input_audio_path
            )
            
            if not is_successful:
                raise OpenAIError(f"Audio transcription failed: {error_message}")
            
            return transcribed_text
            
        except Exception as e:
            if isinstance(e, OpenAIError):
                raise
            raise OpenAIError(f"Audio transcription error: {e}")
    
    