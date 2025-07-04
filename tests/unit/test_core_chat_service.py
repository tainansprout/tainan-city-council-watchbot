"""
核心聊天服務的單元測試
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.services.core_chat_service import CoreChatService
from src.platforms.base import PlatformMessage, PlatformResponse, PlatformUser, PlatformType
from src.models.base import ModelProvider, RAGResponse
from src.core.exceptions import OpenAIError, DatabaseError, ThreadError


# Global fixtures for all test classes

@pytest.fixture
def mock_model():
    """Mock AI 模型"""
    model = Mock()
    model.get_provider.return_value = ModelProvider.OPENAI
    model.check_connection.return_value = (True, None)
    # 清除對話歷史接口
    model.clear_user_history.return_value = (True, None)

    # Set up default chat response for unified chat interface
    mock_rag = RAGResponse(answer="Default test response", sources=[], metadata={})
    model.chat_with_user.return_value = (True, mock_rag, None)

    return model

@pytest.fixture
def mock_database():
    """Mock 資料庫"""
    database = Mock()
    # Set up common database methods to return expected values
    database.query_thread.return_value = "test_thread_123"
    database.save_thread.return_value = None
    database.delete_thread.return_value = None
    return database

@pytest.fixture
def mock_config():
    """Mock 配置"""
    return {
        'commands': {
            'help': 'Help message',
            'about': 'About message'
        },
        'text_processing': {
            'preprocessors': [],
            'post_replacements': []
        }
    }

@pytest.fixture
def chat_service(mock_model, mock_database, mock_config):
    """創建核心聊天服務實例"""
    return CoreChatService(mock_model, mock_database, mock_config)

@pytest.fixture
def sample_user():
    """示例用戶"""
    return PlatformUser(
        user_id="test_user_123",
        platform=PlatformType.LINE,
        display_name="Test User"
    )

@pytest.fixture
def sample_text_message(sample_user):
    """示例文字訊息"""
    return PlatformMessage(
        message_id="msg_123",
        user=sample_user,
        content="Hello, how are you?",
        message_type="text",
        reply_token="reply_123"
    )

@pytest.fixture
def sample_command_message(sample_user):
    """示例指令訊息"""
    return PlatformMessage(
        message_id="msg_456",
        user=sample_user,
        content="/help",
        message_type="text",
        reply_token="reply_456"
    )


class TestCoreChatService:
    """測試核心聊天服務"""


class TestMessageProcessing:
    """測試訊息處理"""
    
    def test_process_text_message(self, chat_service, sample_text_message):
        """測試處理文字訊息"""
        # Override mock model unified chat response
        mock_rag = RAGResponse(answer="I am well, thanks!", sources=[], metadata={})
        chat_service.model.chat_with_user.return_value = (True, mock_rag, None)

        response = chat_service.process_message(sample_text_message)
        assert isinstance(response, PlatformResponse)
        assert response.response_type == "text"
        assert "I am well, thanks!" in response.content
    
    def test_process_command_message(self, chat_service, sample_command_message):
        """測試處理指令訊息"""
        response = chat_service.process_message(sample_command_message)
        
        # 驗證指令回應
        assert isinstance(response, PlatformResponse)
        assert response.response_type == "text"
        assert "Help message" in response.content
    
    def test_process_unknown_command(self, chat_service, sample_user):
        """測試處理未知指令"""
        unknown_command_message = PlatformMessage(
            message_id="msg_789",
            user=sample_user,
            content="/unknown_command",
            message_type="text",
            reply_token="reply_789"
        )
        
        response = chat_service.process_message(unknown_command_message)
        
        assert isinstance(response, PlatformResponse)
        assert "Command not found" in response.content
    
    def test_process_unsupported_message_type(self, chat_service, sample_user):
        """測試處理不支援的訊息類型"""
        unsupported_message = PlatformMessage(
            message_id="msg_unsupported",
            user=sample_user,
            content="[Unsupported Content]",
            message_type="video",  # 不支援的類型
            reply_token="reply_unsupported"
        )
        
        response = chat_service.process_message(unsupported_message)
        
        assert isinstance(response, PlatformResponse)
        assert "暫不支援此類型的訊息" in response.content


class TestCommandHandling:
    """測試指令處理"""
    
    def test_handle_reset_command_openai(self, chat_service, sample_user):
        """測試處理 OpenAI 的重置指令"""
        # 模擬清除對話歷史成功
        chat_service.model.clear_user_history.return_value = (True, None)

        response = chat_service._handle_reset_command(sample_user, "line")
        assert isinstance(response, PlatformResponse)
        assert "Reset The Chatbot" in response.content
        chat_service.model.clear_user_history.assert_called_once_with("test_user_123", "line")
    
    def test_handle_reset_command_no_thread(self, chat_service, sample_user):
        """測試處理沒有 thread 的重置指令"""
        # 模擬清除對話歷史失敗
        chat_service.model.clear_user_history.return_value = (False, "Error")

        response = chat_service._handle_reset_command(sample_user, "line")
        assert isinstance(response, PlatformResponse)
        assert "Reset completed (with warnings)." in response.content
    
    def test_handle_reset_command_other_model(self, chat_service, sample_user):
        """測試處理其他模型的重置指令"""
        # 模擬清除對話歷史成功（非 OpenAI）
        chat_service.model.clear_user_history.return_value = (True, None)

        response = chat_service._handle_reset_command(sample_user, "line")
        assert isinstance(response, PlatformResponse)
        assert "Reset The Chatbot" in response.content
        chat_service.model.clear_user_history.assert_called_once_with("test_user_123", "line")


class TestErrorHandling:
    """測試錯誤處理"""
    
    def test_handle_model_error(self, chat_service, sample_text_message):
        """測試處理模型錯誤"""
        # Mock 模型錯誤
        chat_service.model.chat_with_user.side_effect = OpenAIError("Model error")

        response = chat_service.process_message(sample_text_message)

        # 應該返回錯誤回應
        assert isinstance(response, PlatformResponse)
        assert response.response_type == "text"

    def test_handle_database_error(self, chat_service, sample_text_message):
        """測試處理資料庫錯誤"""
        # 模擬 chat_with_user 拋出資料庫錯誤
        chat_service.model.chat_with_user.side_effect = DatabaseError("Database error")

        response = chat_service.process_message(sample_text_message)

        assert isinstance(response, PlatformResponse)
        assert response.response_type == "text"

    def test_handle_unexpected_error(self, chat_service, sample_text_message):
        """測試處理意外錯誤"""
        # Mock 意外錯誤
        chat_service.model.chat_with_user.side_effect = Exception("Unexpected error")

        response = chat_service.process_message(sample_text_message)

        # 應該返回錯誤回應
        assert isinstance(response, PlatformResponse)
        assert response.response_type == "text"




class TestAudioProcessing:
    """測試音訊處理"""
    
    @patch('src.services.core_chat_service.os.path.exists')
    @patch('src.services.core_chat_service.os.remove')
    @patch('builtins.open', create=True)
    def test_handle_audio_message(self, mock_open, mock_remove, mock_exists, chat_service, sample_user):
        """測試處理音訊訊息"""
        # Mock 音訊資料
        audio_data = b"fake_audio_data"
        
        # Mock 檔案操作
        mock_exists.return_value = True
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        # Mock 轉錄
        chat_service.model.transcribe_audio.return_value = (True, "Transcribed text", None)
        
        # Mock 聊天處理
        mock_rag_response = RAGResponse(
            answer="Response to transcribed text",
            sources=[],
            metadata={}
        )
        chat_service.model.chat_with_user.return_value = (True, mock_rag_response, None)
        
        # 處理音訊訊息
        response = chat_service._handle_audio_message(sample_user, audio_data, "line")
        
        # 驗證結果
        assert isinstance(response, PlatformResponse)
        assert response.response_type == "text"
        assert "Response to transcribed text" in response.content
        
        # 驗證檔案清理與統一聊天接口呼叫
        mock_remove.assert_called_once()
        chat_service.model.chat_with_user.assert_called_once_with(
            user_id="test_user_123", message="Transcribed text", platform="line"
        )


if __name__ == "__main__":
    pytest.main([__file__])