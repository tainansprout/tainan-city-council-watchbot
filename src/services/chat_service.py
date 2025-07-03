import time
import logging
from typing import Dict, Any, Optional
from linebot.v3.messaging import TextMessage

from ..models.base import FullLLMInterface, ModelProvider
from ..database.db import Database
from ..utils import preprocess_text, postprocess_text
from ..core.exceptions import OpenAIError, DatabaseError, ThreadError
from ..core.error_handler import ErrorHandler
from .response_formatter import ResponseFormatter

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self, model: FullLLMInterface, database: Database, config: Dict[str, Any]):
        self.model = model
        self.database = database
        self.config = config
        self.error_handler = ErrorHandler()
        self.response_formatter = ResponseFormatter(config)
    
    def handle_message(self, user_id: str, text: str, platform: str = 'line') -> TextMessage:
        """主要訊息處理入口"""
        try:
            logger.info(f'{user_id}: {text}')
            
            if text.startswith('/'):
                return self._handle_command(user_id, text, platform)
            else:
                return self._handle_chat_message(user_id, text, platform)
                
        except Exception as e:
            logger.error(f"Error handling message for user {user_id}: {e}")
            return self.error_handler.handle_error(e)
    
    def _handle_command(self, user_id: str, text: str, platform: str = 'line') -> TextMessage:
        """處理指令"""
        if text.startswith('/reset'):
            return self._handle_reset_command(user_id, platform)
        
        command = text[1:].split()[0]
        if command in self.config.get('commands', {}):
            return TextMessage(text=self.config['commands'][command] + "\n\n")
        else:
            return TextMessage(text="Command not found.")
    
    def _handle_reset_command(self, user_id: str, platform: str = 'line') -> TextMessage:
        """處理重置指令 - 支援不同模型的重置策略"""
        try:
            # 使用統一接口清除對話歷史，thread_id 管理由模型層處理
            is_successful, error_message = self.model.clear_user_history(user_id, platform)
            if is_successful:
                return TextMessage(text='Reset The Chatbot.')
            else:
                logger.warning(f"Failed to clear history for user {user_id}: {error_message}")
                return TextMessage(text='Reset completed (with warnings).')
        except Exception as e:
            logger.error(f"Error resetting for user {user_id}: {e}")
            raise ThreadError(f"Failed to reset: {e}")
    
    def _handle_chat_message(self, user_id: str, text: str, platform: str = 'line') -> TextMessage:
        """處理聊天訊息 - 支援統一接口和不同模型的對話管理策略"""
        try:
            # 預處理文字
            processed_text = preprocess_text(text, self.config)
            
            # 根據模型提供商使用不同的對話處理策略
            # 使用統一的對話處理邏輯
            response_message = self._process_conversation(user_id, processed_text, platform)
            
            # 後處理回應
            final_response = postprocess_text(response_message, self.config)
            
            return TextMessage(text=final_response)
            
        except Exception as e:
            logger.error(f"Error processing chat message for user {user_id}: {e}")
            raise
    
    def _process_conversation(self, user_id: str, text: str, platform: str = 'line') -> str:
        """處理對話邏輯 - 使用統一的 chat_with_user 接口，thread_id 由模型層管理"""
        try:
            is_successful, rag_response, error_message = self.model.chat_with_user(
                user_id=user_id,
                message=text,
                platform=platform
            )
            if not is_successful:
                raise OpenAIError(f"Chat with user failed: {error_message}")
            formatted_response = self.response_formatter.format_rag_response(rag_response)
            logger.debug(f"Processed conversation response length: {len(formatted_response)}")
            return formatted_response
        except Exception as e:
            if isinstance(e, OpenAIError):
                raise
            raise OpenAIError(f"Conversation processing failed: {e}")
    
    
    def _wait_for_completion(self, thread_id: str, response: Dict[str, Any]) -> Dict[str, Any]:
        """等待 OpenAI 回應完成"""
        max_wait_time = 120  # 最大等待時間 2 分鐘
        start_time = time.time()
        
        while response['status'] not in ['completed', 'failed', 'expired', 'cancelled']:
            if time.time() - start_time > max_wait_time:
                raise OpenAIError("Request timeout")
            
            run_id = response['id']
            
            # 根據狀態調整等待時間
            if response['status'] == 'queued':
                time.sleep(10)
            else:
                time.sleep(3)
            
            is_successful, response, error_message = self.model.retrieve_thread_run(thread_id, run_id)
            if not is_successful:
                raise OpenAIError(f"Failed to retrieve run status: {error_message}")
            
            logger.debug(f"Run {run_id} status: {response['status']}")
        
        return response
    
    
