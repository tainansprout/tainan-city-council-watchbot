from .logger import get_logger
from typing import Dict, Optional
from linebot.v3.messaging import TextMessage
from .exceptions import (
    ChatBotError, OpenAIError, DatabaseError, ThreadError, 
    ModelError, AnthropicError, GeminiError, OllamaError, 
    AudioError, PlatformError, ValidationError, ConfigurationError
)

logger = get_logger(__name__)


class ErrorHandler:
    """統一錯誤處理器 - 支援不同介面的錯誤訊息"""
    
    # 簡化的錯誤訊息（用於 LINE 等平台）
    SIMPLE_ERROR_MESSAGES = {
        'openai_api_key_invalid': '機器人發生錯誤，請換個問法，或稍後再嘗試。',
        'openai_overloaded': '機器人發生錯誤，請換個問法，或稍後再嘗試。',
        'thread_busy': '機器人發生錯誤，請換個問法，或稍後再嘗試。',
        'database_error': '機器人發生錯誤，請換個問法，或稍後再嘗試。',
        'thread_error': '機器人發生錯誤，請換個問法，或稍後再嘗試。',
        'model_error': '機器人發生錯誤，請換個問法，或稍後再嘗試。',
        'anthropic_error': '機器人發生錯誤，請換個問法，或稍後再嘗試。',
        'gemini_error': '機器人發生錯誤，請換個問法，或稍後再嘗試。',
        'ollama_error': '機器人發生錯誤，請換個問法，或稍後再嘗試。',
        'audio_error': '機器人發生錯誤，請換個問法，或稍後再嘗試。',
        'platform_error': '機器人發生錯誤，請換個問法，或稍後再嘗試。',
        'validation_error': '機器人發生錯誤，請換個問法，或稍後再嘗試。',
        'configuration_error': '機器人發生錯誤，請換個問法，或稍後再嘗試。',
        'unknown_error': '機器人發生錯誤，請換個問法，或稍後再嘗試。'
    }
    
    # 詳細的錯誤訊息（用於 /chat 測試介面）
    DETAILED_ERROR_MESSAGES = {
        'openai_api_key_invalid': 'OpenAI API Token 錯誤：請檢查 OPENAI_API_KEY 環境變數設定。',
        'openai_overloaded': 'OpenAI 服務過載：伺服器目前繁忙，請稍後再試。',
        'openai_rate_limit': 'OpenAI API 速率限制：請求頻率過高，請稍後再試。',
        'openai_quota_exceeded': 'OpenAI API 配額超出：請檢查帳戶使用量和付費狀態。',
        'anthropic_api_key_invalid': 'Anthropic API Token 錯誤：請檢查 ANTHROPIC_API_KEY 環境變數設定。',
        'anthropic_overloaded': 'Anthropic 服務過載：伺服器目前繁忙，請稍後再試。',
        'anthropic_rate_limit': 'Anthropic API 速率限制：請求頻率過高，請稍後再試。',
        'gemini_api_key_invalid': 'Gemini API Token 錯誤：請檢查 GEMINI_API_KEY 環境變數設定。',
        'gemini_overloaded': 'Gemini 服務過載：伺服器目前繁忙，請稍後再試。',
        'gemini_rate_limit': 'Gemini API 速率限制：請求頻率過高，請稍後再試。',
        'ollama_connection_failed': 'Ollama 連線失敗：請檢查 Ollama 服務是否正在運行。',
        'ollama_model_not_found': 'Ollama 模型不存在：請檢查指定的模型是否已安裝。',
        'thread_busy': '對話串處理中：機器人正在處理您的問題，請稍等片刻。',
        'database_connection_failed': '資料庫連線失敗：請檢查資料庫伺服器狀態和連線設定。',
        'database_query_failed': '資料庫查詢失敗：執行 SQL 查詢時發生錯誤。',
        'database_timeout': '資料庫超時：查詢執行時間過長，請稍後再試。',
        'thread_error': '對話串處理異常：請嘗試重新開始對話（使用 /reset 指令）。',
        'audio_transcription_failed': '音訊轉錄失敗：無法處理音訊檔案，請檢查檔案格式。',
        'audio_file_too_large': '音訊檔案過大：請上傳較小的音訊檔案。',
        'audio_format_unsupported': '音訊格式不支援：請使用支援的音訊格式。',
        'platform_config_invalid': '平台配置錯誤：請檢查平台相關的配置設定。',
        'platform_api_failed': '平台 API 呼叫失敗：無法與平台伺服器通訊。',
        'validation_input_too_long': '輸入過長：請縮短您的訊息內容。',
        'validation_invalid_format': '格式錯誤：請檢查輸入格式是否正確。',
        'configuration_missing': '配置缺失：請檢查必要的配置檔案和環境變數。',
        'configuration_invalid': '配置無效：請檢查配置檔案格式和內容。',
        'unknown_error': '未知錯誤：發生了未預期的系統錯誤，請聯繫管理員。'
    }
    
    def handle_error(self, error: Exception, use_detailed: bool = False) -> TextMessage:
        """統一錯誤處理"""
        logger.error(f"Error occurred: {type(error).__name__}: {error}")
        
        error_message = self._get_user_friendly_message(error, use_detailed)
        return TextMessage(text=error_message)
    
    def get_error_message(self, error: Exception, use_detailed: bool = False) -> str:
        """取得錯誤訊息（不包裝為 TextMessage）"""
        return self._get_user_friendly_message(error, use_detailed)
    
    def _get_user_friendly_message(self, error: Exception, use_detailed: bool = False) -> str:
        """取得使用者友善的錯誤訊息"""
        if isinstance(error, ChatBotError):
            return self._handle_chatbot_error(error, use_detailed)
        
        error_str = str(error)
        error_key = self._classify_error(error_str)
        
        if use_detailed:
            return self.DETAILED_ERROR_MESSAGES.get(error_key, self.DETAILED_ERROR_MESSAGES['unknown_error'])
        else:
            return self.SIMPLE_ERROR_MESSAGES.get(error_key, self.SIMPLE_ERROR_MESSAGES['unknown_error'])
    
    def _classify_error(self, error_str: str) -> str:
        """根據錯誤訊息分類錯誤類型"""
        error_str_lower = error_str.lower()
        
        # OpenAI 相關錯誤
        if 'incorrect api key' in error_str_lower or 'invalid api key' in error_str_lower:
            return 'openai_api_key_invalid'
        elif 'overloaded with other requests' in error_str_lower:
            return 'openai_overloaded'
        elif 'rate limit' in error_str_lower and 'openai' in error_str_lower:
            return 'openai_rate_limit'
        elif 'quota exceeded' in error_str_lower or 'billing' in error_str_lower:
            return 'openai_quota_exceeded'
        elif "can't add messages to thread" in error_str_lower:
            return 'thread_busy'
        
        # Anthropic 相關錯誤
        elif 'anthropic' in error_str_lower and ('api key' in error_str_lower or 'unauthorized' in error_str_lower):
            return 'anthropic_api_key_invalid'
        elif 'anthropic' in error_str_lower and 'overloaded' in error_str_lower:
            return 'anthropic_overloaded'
        elif 'anthropic' in error_str_lower and 'rate limit' in error_str_lower:
            return 'anthropic_rate_limit'
        
        # Gemini 相關錯誤
        elif 'gemini' in error_str_lower and ('api key' in error_str_lower or 'unauthorized' in error_str_lower):
            return 'gemini_api_key_invalid'
        elif 'gemini' in error_str_lower and 'overloaded' in error_str_lower:
            return 'gemini_overloaded'
        elif 'gemini' in error_str_lower and 'rate limit' in error_str_lower:
            return 'gemini_rate_limit'
        
        # Ollama 相關錯誤
        elif 'ollama' in error_str_lower and 'connection' in error_str_lower:
            return 'ollama_connection_failed'
        elif 'ollama' in error_str_lower and 'model not found' in error_str_lower:
            return 'ollama_model_not_found'
        
        # 資料庫相關錯誤
        elif 'database' in error_str_lower and 'connection' in error_str_lower:
            return 'database_connection_failed'
        elif 'database' in error_str_lower and 'timeout' in error_str_lower:
            return 'database_timeout'
        elif ('sql' in error_str_lower or 'query' in error_str_lower or 
              'column' in error_str_lower or 'table' in error_str_lower or
              'postgresql' in error_str_lower or 'psycopg' in error_str_lower or
              'relation' in error_str_lower or 'does not exist' in error_str_lower):
            return 'database_query_failed'
        
        # 音訊相關錯誤
        elif 'audio' in error_str_lower and 'transcription' in error_str_lower:
            return 'audio_transcription_failed'
        elif 'audio' in error_str_lower and 'size' in error_str_lower:
            return 'audio_file_too_large'
        elif 'audio' in error_str_lower and 'format' in error_str_lower:
            return 'audio_format_unsupported'
        
        # 輸入驗證相關錯誤
        elif 'too long' in error_str_lower or 'length' in error_str_lower:
            return 'validation_input_too_long'
        elif 'invalid format' in error_str_lower or 'format error' in error_str_lower:
            return 'validation_invalid_format'
        
        # 配置相關錯誤
        elif 'config' in error_str_lower and 'missing' in error_str_lower:
            return 'configuration_missing'
        elif 'config' in error_str_lower and 'invalid' in error_str_lower:
            return 'configuration_invalid'
        
        else:
            return 'unknown_error'
    
    def _handle_chatbot_error(self, error: ChatBotError, use_detailed: bool = False) -> str:
        """處理自定義錯誤"""
        if isinstance(error, OpenAIError):
            key = 'openai_api_key_invalid'
        elif isinstance(error, AnthropicError):
            key = 'anthropic_error'
        elif isinstance(error, GeminiError):
            key = 'gemini_error'
        elif isinstance(error, OllamaError):
            key = 'ollama_error'
        elif isinstance(error, DatabaseError):
            key = 'database_error'
        elif isinstance(error, ThreadError):
            key = 'thread_error'
        elif isinstance(error, AudioError):
            key = 'audio_error'
        elif isinstance(error, PlatformError):
            key = 'platform_error'
        elif isinstance(error, ValidationError):
            key = 'validation_error'
        elif isinstance(error, ConfigurationError):
            key = 'configuration_error'
        else:
            key = 'unknown_error'
        
        if use_detailed:
            return self.DETAILED_ERROR_MESSAGES.get(key, error.message or self.DETAILED_ERROR_MESSAGES['unknown_error'])
        else:
            return self.SIMPLE_ERROR_MESSAGES.get(key, self.SIMPLE_ERROR_MESSAGES['unknown_error'])