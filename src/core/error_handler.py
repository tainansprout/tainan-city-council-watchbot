import logging
from typing import Dict
from linebot.v3.messaging import TextMessage
from .exceptions import ChatBotError, OpenAIError, DatabaseError, ThreadError

logger = logging.getLogger(__name__)


class ErrorHandler:
    """統一錯誤處理器"""
    
    ERROR_MESSAGES = {
        'openai_api_key_invalid': 'OpenAI API Token 有誤，請重新設定。',
        'openai_overloaded': '服務繁忙，請稍後再試。',
        'thread_busy': '機器人正在處理您的問題，請稍等。',
        'database_error': '資料庫連線異常，請稍後再試。',
        'thread_error': '對話串處理異常，請嘗試重新開始對話。',
        'unknown_error': '發生未知錯誤，請稍後再試。'
    }
    
    def handle_error(self, error: Exception) -> TextMessage:
        """統一錯誤處理"""
        logger.error(f"Error occurred: {type(error).__name__}: {error}")
        
        error_message = self._get_user_friendly_message(error)
        return TextMessage(text=error_message)
    
    def _get_user_friendly_message(self, error: Exception) -> str:
        """取得使用者友善的錯誤訊息"""
        if isinstance(error, ChatBotError):
            return self._handle_chatbot_error(error)
        
        error_str = str(error)
        
        if 'Incorrect API key provided' in error_str:
            return self.ERROR_MESSAGES['openai_api_key_invalid']
        elif 'overloaded with other requests' in error_str:
            return self.ERROR_MESSAGES['openai_overloaded']
        elif "Can't add messages to thread" in error_str:
            return self.ERROR_MESSAGES['thread_busy']
        else:
            return self.ERROR_MESSAGES['unknown_error']
    
    def _handle_chatbot_error(self, error: ChatBotError) -> str:
        """處理自定義錯誤"""
        if isinstance(error, OpenAIError):
            return self.ERROR_MESSAGES['openai_api_key_invalid']
        elif isinstance(error, DatabaseError):
            return self.ERROR_MESSAGES['database_error']
        elif isinstance(error, ThreadError):
            return self.ERROR_MESSAGES['thread_error']
        else:
            return error.message or self.ERROR_MESSAGES['unknown_error']