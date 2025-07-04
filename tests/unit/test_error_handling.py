"""
錯誤處理機制測試
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.exc import ProgrammingError
import psycopg2.errors

from src.core.error_handler import ErrorHandler
from src.core.exceptions import (
    DatabaseError, OpenAIError, AnthropicError, GeminiError, 
    OllamaError, AudioError, PlatformError, ValidationError, 
    ConfigurationError, ThreadError
)
from src.services.chat import CoreChatService
from src.platforms.base import PlatformUser, PlatformMessage, PlatformType


class TestErrorHandler:
    """ErrorHandler 測試"""
    
    @pytest.fixture
    def error_handler(self):
        """創建 ErrorHandler 實例"""
        return ErrorHandler()
    
    def test_database_error_classification(self, error_handler):
        """測試資料庫錯誤分類"""
        # 測試 DatabaseError
        db_error = DatabaseError("Database connection failed")
        detailed_msg = error_handler.get_error_message(db_error, use_detailed=True)
        simple_msg = error_handler.get_error_message(db_error, use_detailed=False)
        
        # DatabaseError 會被分類為 database_error，返回預設的詳細訊息
        assert "Database connection failed" in detailed_msg
        assert "機器人發生錯誤" in simple_msg
    
    def test_column_not_exist_error_classification(self, error_handler):
        """測試欄位不存在錯誤分類"""
        # 模擬 psycopg2 column 錯誤
        column_error = Exception("column 'platform' does not exist")
        
        detailed_msg = error_handler.get_error_message(column_error, use_detailed=True)
        simple_msg = error_handler.get_error_message(column_error, use_detailed=False)
        
        assert "資料庫查詢失敗" in detailed_msg
        assert "機器人發生錯誤" in simple_msg
    
    def test_sqlalchemy_error_classification(self, error_handler):
        """測試 SQLAlchemy 錯誤分類"""
        # 模擬 SQLAlchemy ProgrammingError
        sql_error = ProgrammingError("", "", "relation 'user_thread_table' does not exist")
        
        detailed_msg = error_handler.get_error_message(sql_error, use_detailed=True)
        simple_msg = error_handler.get_error_message(sql_error, use_detailed=False)
        
        assert "資料庫查詢失敗" in detailed_msg
        assert "機器人發生錯誤" in simple_msg
    
    def test_openai_error_classification(self, error_handler):
        """測試 OpenAI 錯誤分類"""
        openai_error = OpenAIError("Invalid API key")
        
        detailed_msg = error_handler.get_error_message(openai_error, use_detailed=True)
        simple_msg = error_handler.get_error_message(openai_error, use_detailed=False)
        
        assert "API" in detailed_msg or "金鑰" in detailed_msg
        assert "機器人發生錯誤" in simple_msg
    
    def test_unknown_error_classification(self, error_handler):
        """測試未知錯誤分類"""
        unknown_error = Exception("Some random error")
        
        detailed_msg = error_handler.get_error_message(unknown_error, use_detailed=True)
        simple_msg = error_handler.get_error_message(unknown_error, use_detailed=False)
        
        assert "未知錯誤" in detailed_msg
        assert "機器人發生錯誤" in simple_msg
    
    @pytest.mark.parametrize("error_type,expected_key", [
        (AnthropicError("test"), "anthropic_error"),
        (GeminiError("test"), "gemini_error"),
        (OllamaError("test"), "ollama_error"),
        (AudioError("test"), "audio_error"),
        (PlatformError("test"), "platform_error"),
        (ValidationError("test"), "validation_error"),
        (ThreadError("test"), "thread_error"),
        (ConfigurationError("test"), "configuration_error")
    ])
    def test_specific_error_types(self, error_handler, error_type, expected_key):
        """測試特定錯誤類型的分類"""
        detailed_msg = error_handler.get_error_message(error_type, use_detailed=True)
        simple_msg = error_handler.get_error_message(error_type, use_detailed=False)
        
        # 詳細訊息應該不同於簡化訊息
        assert detailed_msg != simple_msg
        # 簡化訊息都應該是統一格式
        assert "機器人發生錯誤" in simple_msg


class TestCoreChatServiceErrorHandling:
    """CoreChatService 錯誤處理測試"""
    
    @pytest.fixture
    def mock_model(self):
        """創建模擬的模型"""
        model = Mock()
        model.get_provider.return_value.value = "openai"
        return model
    
    @pytest.fixture
    def mock_database(self):
        """創建模擬的資料庫"""
        return Mock()
    
    @pytest.fixture
    def config(self):
        """創建測試配置"""
        return {
            'text_processing': {
                'preprocessors': [],
                'post_replacements': []
            }
        }
    
    @pytest.fixture
    def chat(self, mock_model, mock_database, config):
        """創建 CoreChatService 實例"""
        return CoreChatService(mock_model, mock_database, config)
    
    @pytest.fixture
    def test_user(self):
        """創建測試用戶（來自 /chat 介面）"""
        return PlatformUser(
            user_id="U" + "0" * 32,  # 測試用戶 ID
            display_name="測試用戶",
            platform=PlatformType.LINE
        )
    
    @pytest.fixture
    def real_user(self):
        """創建真實用戶（來自 LINE 平台）"""
        return PlatformUser(
            user_id="U1234567890abcdef",
            display_name="真實用戶",
            platform=PlatformType.LINE
        )
    
    @pytest.fixture
    def test_message(self, test_user):
        """創建測試訊息"""
        return PlatformMessage(
            message_id="test_msg_123",
            user=test_user,
            content="測試訊息",
            message_type="text",
            reply_token="test_reply_token"
        )
    
    @pytest.fixture
    def real_message(self, real_user):
        """創建真實訊息"""
        return PlatformMessage(
            message_id="real_msg_123",
            user=real_user,
            content="真實訊息",
            message_type="text",
            reply_token="real_reply_token"
        )
    
    def test_database_error_for_test_user_raises_exception(self, chat, test_message, mock_model):
        """測試資料庫錯誤對測試用戶會拋出異常"""
        # 模擬資料庫錯誤
        mock_model.chat_with_user.return_value = (
            False, 
            None, 
            "Database operation failed: column 'platform' does not exist"
        )
        
        # 測試用戶應該拋出 DatabaseError
        with pytest.raises(DatabaseError) as exc_info:
            chat.process_message(test_message)
        
        assert "Database operation failed" in str(exc_info.value)
    
    def test_database_error_for_real_user_returns_simple_message(self, chat, real_message, mock_model):
        """測試資料庫錯誤對真實用戶返回簡化訊息"""
        # 模擬資料庫錯誤
        mock_model.chat_with_user.return_value = (
            False, 
            None, 
            "Database operation failed: column 'platform' does not exist"
        )
        
        # 真實用戶應該返回 PlatformResponse 而不是拋出異常
        response = chat.process_message(real_message)
        
        assert response.response_type == "text"
        assert "機器人發生錯誤" in response.content
    
    def test_openai_error_for_test_user_raises_exception(self, chat, test_message, mock_model):
        """測試 OpenAI 錯誤對測試用戶會拋出異常"""
        # 模擬 OpenAI 錯誤
        mock_model.chat_with_user.return_value = (
            False, 
            None, 
            "Invalid API key"
        )
        
        # 測試用戶應該拋出 OpenAIError
        with pytest.raises(OpenAIError) as exc_info:
            chat.process_message(test_message)
        
        assert "Chat with user failed" in str(exc_info.value)
    
    def test_openai_error_for_real_user_returns_simple_message(self, chat, real_message, mock_model):
        """測試 OpenAI 錯誤對真實用戶返回簡化訊息"""
        # 模擬 OpenAI 錯誤
        mock_model.chat_with_user.return_value = (
            False, 
            None, 
            "Invalid API key"
        )
        
        # 真實用戶應該返回 PlatformResponse
        response = chat.process_message(real_message)
        
        assert response.response_type == "text"
        assert "機器人發生錯誤" in response.content
    
    def test_sql_exception_gets_classified_as_database_error(self, chat, test_message, mock_model):
        """測試 SQL 異常被正確分類為資料庫錯誤"""
        # 模擬 SQL 異常在 chat_with_user 中拋出
        mock_model.chat_with_user.side_effect = ProgrammingError(
            "", "", "column 'platform' does not exist"
        )
        
        # 應該被重新分類為 DatabaseError
        with pytest.raises(DatabaseError) as exc_info:
            chat.process_message(test_message)
        
        assert "Database operation failed" in str(exc_info.value)
    
    def test_user_id_test_detection(self, chat):
        """測試用戶 ID 檢測邏輯"""
        # 測試用戶 ID
        test_user_id = "U" + "0" * 32
        assert test_user_id.startswith("U" + "0" * 32)
        
        # 真實用戶 ID
        real_user_id = "U1234567890abcdef"
        assert not real_user_id.startswith("U" + "0" * 32)
        
        # 其他格式的真實用戶 ID
        real_user_id2 = "Uabcdef1234567890"
        assert not real_user_id2.startswith("U" + "0" * 32)


class TestErrorHandlingIntegration:
    """錯誤處理整合測試"""
    
    def test_database_error_flow_with_column_not_exist(self):
        """測試 column 不存在錯誤的完整流程"""
        # 模擬真實的 psycopg2 錯誤
        original_error = psycopg2.errors.UndefinedColumn(
            "column user_thread_table.platform does not exist"
        )
        
        # 測試錯誤分類
        error_handler = ErrorHandler()
        detailed_msg = error_handler.get_error_message(original_error, use_detailed=True)
        simple_msg = error_handler.get_error_message(original_error, use_detailed=False)
        
        assert "資料庫查詢失敗" in detailed_msg
        assert "機器人發生錯誤" in simple_msg
    
    def test_error_message_consistency(self):
        """測試錯誤訊息的一致性"""
        error_handler = ErrorHandler()
        
        # 所有簡化錯誤訊息都應該是統一格式
        test_errors = [
            DatabaseError("test"),
            OpenAIError("test"),
            AnthropicError("test"),
            Exception("test")
        ]
        
        simple_messages = [
            error_handler.get_error_message(error, use_detailed=False)
            for error in test_errors
        ]
        
        # 所有簡化訊息都應該包含統一的用戶友好文字
        for msg in simple_messages:
            assert "機器人發生錯誤" in msg
            assert "請換個問法" in msg or "稍後再嘗試" in msg
    
    @patch('src.services.chat.logger')
    def test_error_logging(self, mock_logger):
        """測試錯誤日誌記錄"""
        from src.services.chat import CoreChatService
        from src.platforms.base import PlatformUser, PlatformMessage, PlatformType
        
        # 創建模擬對象
        mock_model = Mock()
        mock_model.get_provider.return_value.value = "openai"
        mock_model.chat_with_user.return_value = (
            False, None, "Database operation failed: column does not exist"
        )
        
        mock_database = Mock()
        config = {'text_processing': {'preprocessors': [], 'post_replacements': []}}
        
        service = CoreChatService(mock_model, mock_database, config)
        
        # 創建真實用戶訊息
        user = PlatformUser(
            user_id="U1234567890",
            display_name="真實用戶", 
            platform=PlatformType.LINE
        )
        message = PlatformMessage(
            message_id="msg_123",
            user=user,
            content="測試訊息",
            message_type="text"
        )
        
        # 處理訊息
        response = service.process_message(message)
        
        # 驗證錯誤日誌被記錄
        assert mock_logger.error.called
        # 檢查日誌內容包含重要資訊
        log_calls = [call[0][0] for call in mock_logger.error.call_args_list]
        assert any("Error handling text message" in log for log in log_calls)
        assert any("Error details - Platform: line" in log for log in log_calls)