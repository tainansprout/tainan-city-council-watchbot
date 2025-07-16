"""
測試 ErrorHandler 類別
"""
import pytest
from unittest.mock import Mock, patch

from src.core.error_handler import ErrorHandler
from src.core.exceptions import (
    ChatBotError, OpenAIError, DatabaseError, ThreadError, 
    ModelError, AnthropicError, GeminiError, OllamaError, 
    AudioError, PlatformError, ValidationError, ConfigurationError
)
from linebot.v3.messaging import TextMessage


class TestErrorHandler:
    """測試 ErrorHandler 類別"""
    
    @pytest.fixture
    def error_handler(self):
        """創建 ErrorHandler 實例"""
        return ErrorHandler()
    
    def test_handle_error_simple_message(self, error_handler):
        """測試處理錯誤並返回簡化訊息"""
        error = Exception("Test error")
        
        with patch('src.core.error_handler.logger') as mock_logger:
            result = error_handler.handle_error(error, use_detailed=False)
            
            # 檢查返回類型
            assert isinstance(result, TextMessage)
            assert result.text == '機器人發生錯誤，請換個問法，或稍後再嘗試。'
            
            # 檢查錯誤被記錄
            mock_logger.error.assert_called_once()
    
    def test_handle_error_detailed_message(self, error_handler):
        """測試處理錯誤並返回詳細訊息"""
        error = Exception("Test error")
        
        with patch('src.core.error_handler.logger') as mock_logger:
            result = error_handler.handle_error(error, use_detailed=True)
            
            assert isinstance(result, TextMessage)
            assert result.text == '未知錯誤：發生了未預期的系統錯誤，請聯繫管理員。'
            mock_logger.error.assert_called_once()
    
    def test_get_error_message_without_textmessage(self, error_handler):
        """測試取得錯誤訊息（不包裝為 TextMessage）"""
        error = Exception("Test error")
        
        simple_message = error_handler.get_error_message(error, use_detailed=False)
        detailed_message = error_handler.get_error_message(error, use_detailed=True)
        
        assert isinstance(simple_message, str)
        assert isinstance(detailed_message, str)
        assert simple_message == '機器人發生錯誤，請換個問法，或稍後再嘗試。'
        assert detailed_message == '未知錯誤：發生了未預期的系統錯誤，請聯繫管理員。'


class TestErrorClassification:
    """測試錯誤分類功能"""
    
    @pytest.fixture
    def error_handler(self):
        return ErrorHandler()
    
    def test_classify_openai_errors(self, error_handler):
        """測試 OpenAI 錯誤分類"""
        test_cases = [
            ("Incorrect API key provided", "openai_api_key_invalid"),
            ("Invalid API key", "openai_api_key_invalid"),
            ("The server is overloaded with other requests", "openai_overloaded"),
            ("Rate limit exceeded for OpenAI", "openai_rate_limit"),
            ("quota exceeded", "openai_quota_exceeded"),
            ("Can't add messages to thread while a run is active", "thread_busy"),
        ]
        
        for error_str, expected_key in test_cases:
            result = error_handler._classify_error(error_str)
            assert result == expected_key, f"Failed for: {error_str}"
    
    def test_classify_anthropic_errors(self, error_handler):
        """測試 Anthropic 錯誤分類"""
        test_cases = [
            ("Anthropic API key is invalid", "anthropic_api_key_invalid"),
            ("Anthropic unauthorized access", "anthropic_api_key_invalid"),
            ("Anthropic service overloaded", "anthropic_overloaded"),
            ("Anthropic rate limit exceeded", "anthropic_rate_limit"),
        ]
        
        for error_str, expected_key in test_cases:
            result = error_handler._classify_error(error_str)
            assert result == expected_key, f"Failed for: {error_str}"
    
    def test_classify_gemini_errors(self, error_handler):
        """測試 Gemini 錯誤分類"""
        test_cases = [
            ("Gemini API key is invalid", "gemini_api_key_invalid"),
            ("Gemini unauthorized", "gemini_api_key_invalid"),
            ("Gemini service overloaded", "gemini_overloaded"),
            ("Gemini rate limit reached", "gemini_rate_limit"),
        ]
        
        for error_str, expected_key in test_cases:
            result = error_handler._classify_error(error_str)
            assert result == expected_key, f"Failed for: {error_str}"
    
    def test_classify_ollama_errors(self, error_handler):
        """測試 Ollama 錯誤分類"""
        test_cases = [
            ("Ollama connection failed", "ollama_connection_failed"),
            ("Ollama model not found", "ollama_model_not_found"),
        ]
        
        for error_str, expected_key in test_cases:
            result = error_handler._classify_error(error_str)
            assert result == expected_key, f"Failed for: {error_str}"
    
    def test_classify_database_errors(self, error_handler):
        """測試資料庫錯誤分類"""
        test_cases = [
            ("Database connection failed", "database_connection_failed"),
            ("Database timeout occurred", "database_timeout"),
            ("SQL query failed", "database_query_failed"),
            ("PostgreSQL error", "database_query_failed"),
            ("Table does not exist", "database_query_failed"),
            ("Column not found", "database_query_failed"),
        ]
        
        for error_str, expected_key in test_cases:
            result = error_handler._classify_error(error_str)
            assert result == expected_key, f"Failed for: {error_str}"
    
    def test_classify_audio_errors(self, error_handler):
        """測試音訊錯誤分類"""
        test_cases = [
            ("Audio transcription failed", "audio_transcription_failed"),
            ("Audio file size too large", "audio_file_too_large"),
            ("Audio format not supported", "audio_format_unsupported"),
        ]
        
        for error_str, expected_key in test_cases:
            result = error_handler._classify_error(error_str)
            assert result == expected_key, f"Failed for: {error_str}"
    
    def test_classify_validation_errors(self, error_handler):
        """測試驗證錯誤分類"""
        test_cases = [
            ("Input too long", "validation_input_too_long"),
            ("Message length exceeded", "validation_input_too_long"),
            ("Invalid format provided", "validation_invalid_format"),
            ("Format error in input", "validation_invalid_format"),
        ]
        
        for error_str, expected_key in test_cases:
            result = error_handler._classify_error(error_str)
            assert result == expected_key, f"Failed for: {error_str}"
    
    def test_classify_configuration_errors(self, error_handler):
        """測試配置錯誤分類"""
        test_cases = [
            ("Configuration file missing", "configuration_missing"),
            ("Config parameter missing", "configuration_missing"),
            ("Configuration is invalid", "configuration_invalid"),
            ("Config format invalid", "configuration_invalid"),
        ]
        
        for error_str, expected_key in test_cases:
            result = error_handler._classify_error(error_str)
            assert result == expected_key, f"Failed for: {error_str}"
    
    def test_classify_unknown_error(self, error_handler):
        """測試未知錯誤分類"""
        unknown_error = "Some random error message"
        result = error_handler._classify_error(unknown_error)
        assert result == "unknown_error"


class TestCustomExceptionHandling:
    """測試自定義異常處理"""
    
    @pytest.fixture
    def error_handler(self):
        return ErrorHandler()
    
    def test_handle_openai_error(self, error_handler):
        """測試處理 OpenAI 錯誤"""
        error = OpenAIError("API key invalid")
        
        simple_msg = error_handler._handle_chatbot_error(error, use_detailed=False)
        detailed_msg = error_handler._handle_chatbot_error(error, use_detailed=True)
        
        assert simple_msg == '機器人發生錯誤，請換個問法，或稍後再嘗試。'
        assert detailed_msg == 'OpenAI API Token 錯誤：請檢查 OPENAI_API_KEY 環境變數設定。'
    
    def test_handle_anthropic_error(self, error_handler):
        """測試處理 Anthropic 錯誤"""
        error = AnthropicError("API error")
        
        simple_msg = error_handler._handle_chatbot_error(error, use_detailed=False)
        detailed_msg = error_handler._handle_chatbot_error(error, use_detailed=True)
        
        assert simple_msg == '機器人發生錯誤，請換個問法，或稍後再嘗試。'
        # 詳細訊息會返回 error.message，因為 anthropic_error 不在 DETAILED_ERROR_MESSAGES 中
        assert detailed_msg == "API error"
    
    def test_handle_database_error(self, error_handler):
        """測試處理資料庫錯誤"""
        error = DatabaseError("Connection failed")
        
        simple_msg = error_handler._handle_chatbot_error(error, use_detailed=False)
        detailed_msg = error_handler._handle_chatbot_error(error, use_detailed=True)
        
        assert simple_msg == '機器人發生錯誤，請換個問法，或稍後再嘗試。'
        # 詳細訊息會返回 error.message，因為 database_error 不在 DETAILED_ERROR_MESSAGES 中
        assert detailed_msg == "Connection failed"
    
    def test_handle_all_custom_errors(self, error_handler):
        """測試處理所有自定義錯誤類型"""
        custom_errors = [
            (GeminiError("test"), "gemini_error"),
            (OllamaError("test"), "ollama_error"),
            (ThreadError("test"), "thread_error"),
            (AudioError("test"), "audio_error"),
            (PlatformError("test"), "platform_error"),
            (ValidationError("test"), "validation_error"),
            (ConfigurationError("test"), "configuration_error"),
        ]
        
        for error, expected_key in custom_errors:
            simple_msg = error_handler._handle_chatbot_error(error, use_detailed=False)
            detailed_msg = error_handler._handle_chatbot_error(error, use_detailed=True)
            
            # 所有錯誤的簡化訊息都應該相同
            assert simple_msg == '機器人發生錯誤，請換個問法，或稍後再嘗試。'
            # 詳細訊息應該有對應的內容
            assert detailed_msg is not None
    
    def test_handle_chatbot_error_with_custom_message(self, error_handler):
        """測試處理帶有自定義訊息的 ChatBot 錯誤"""
        # 創建一個帶有自定義訊息的錯誤
        error = ChatBotError("Custom error message")
        
        detailed_msg = error_handler._handle_chatbot_error(error, use_detailed=True)
        
        # 應該回退到 unknown_error 的詳細訊息
        assert detailed_msg == '未知錯誤：發生了未預期的系統錯誤，請聯繫管理員。'


class TestErrorHandlerIntegration:
    """測試 ErrorHandler 整合功能"""
    
    @pytest.fixture
    def error_handler(self):
        return ErrorHandler()
    
    def test_end_to_end_custom_error_handling(self, error_handler):
        """測試端到端的自定義錯誤處理"""
        error = OpenAIError("Invalid API key")
        
        with patch('src.core.error_handler.logger') as mock_logger:
            # 測試簡化訊息
            simple_result = error_handler.handle_error(error, use_detailed=False)
            assert isinstance(simple_result, TextMessage)
            assert simple_result.text == '機器人發生錯誤，請換個問法，或稍後再嘗試。'
            
            # 測試詳細訊息
            detailed_result = error_handler.handle_error(error, use_detailed=True)
            assert isinstance(detailed_result, TextMessage)
            assert detailed_result.text == 'OpenAI API Token 錯誤：請檢查 OPENAI_API_KEY 環境變數設定。'
            
            # 檢查日誌記錄
            assert mock_logger.error.call_count == 2
    
    def test_end_to_end_standard_error_handling(self, error_handler):
        """測試端到端的標準錯誤處理"""
        error = Exception("Incorrect API key provided")
        
        with patch('src.core.error_handler.logger') as mock_logger:
            result = error_handler.handle_error(error, use_detailed=True)
            
            assert isinstance(result, TextMessage)
            assert result.text == 'OpenAI API Token 錯誤：請檢查 OPENAI_API_KEY 環境變數設定。'
            mock_logger.error.assert_called_once()
    
    def test_error_messages_consistency(self, error_handler):
        """測試錯誤訊息的一致性"""
        # 檢查所有簡化訊息中有主要訊息和一些特殊的訊息
        simple_messages = set(error_handler.SIMPLE_ERROR_MESSAGES.values())
        # 應該有：1) 主要錯誤訊息 2) thread_busy 訊息 3) openai_overloaded 訊息 
        assert len(simple_messages) == 3
        
        # 檢查詳細訊息是否都存在且不為空
        for key, message in error_handler.DETAILED_ERROR_MESSAGES.items():
            assert message is not None
            assert len(message.strip()) > 0
            assert isinstance(message, str)