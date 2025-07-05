"""
測試核心聊天服務的單元測試
"""
import pytest
import os
import time
from unittest.mock import Mock, patch, MagicMock, mock_open
from src.services.chat import CoreChatService
from src.models.base import FullLLMInterface, ModelProvider, RAGResponse, ChatMessage
from src.database.connection import Database
from src.platforms.base import PlatformMessage, PlatformResponse, PlatformUser, PlatformType
from src.core.exceptions import OpenAIError, DatabaseError, ThreadError
from src.core.error_handler import ErrorHandler
from src.services.response import ResponseFormatter


class TestCoreChatServiceInitialization:
    """測試核心聊天服務初始化"""
    
    @pytest.fixture
    def mock_model(self):
        """模擬 AI 模型"""
        model = Mock(spec=FullLLMInterface)
        model.get_provider.return_value = ModelProvider.OPENAI
        return model
    
    @pytest.fixture
    def mock_database(self):
        """模擬資料庫"""
        return Mock(spec=Database)
    
    @pytest.fixture
    def mock_config(self):
        """模擬配置"""
        return {
            'commands': {
                'help': '系統說明',
                'reset': '重置對話歷史'
            },
            'text_processing': {
                'preprocessors': [],
                'post_replacements': []
            }
        }
    
    def test_initialization_success(self, mock_model, mock_database, mock_config):
        """測試成功初始化"""
        service = CoreChatService(mock_model, mock_database, mock_config)
        
        assert service.model == mock_model
        assert service.database == mock_database
        assert service.config == mock_config
        assert isinstance(service.error_handler, ErrorHandler)
        assert isinstance(service.response_formatter, ResponseFormatter)
    
    def test_initialization_with_model_provider_logging(self, mock_model, mock_database, mock_config):
        """測試初始化時記錄模型提供商"""
        mock_model.get_provider.return_value = ModelProvider.ANTHROPIC
        
        with patch('src.services.chat.logger') as mock_logger:
            service = CoreChatService(mock_model, mock_database, mock_config)
            
            mock_logger.info.assert_called_once_with("CoreChatService initialized with model: anthropic")
    
    def test_initialization_with_invalid_provider(self, mock_model, mock_database, mock_config):
        """測試初始化時處理無效的模型提供商"""
        mock_model.get_provider.side_effect = ValueError("Invalid provider")
        
        with patch('src.services.chat.logger') as mock_logger:
            service = CoreChatService(mock_model, mock_database, mock_config)
            
            # 應該不會拋出異常，只是不記錄日誌
            assert service.model == mock_model
            mock_logger.info.assert_not_called()


class TestProcessMessage:
    """測試訊息處理功能"""
    
    @pytest.fixture
    def chat_service(self):
        """創建聊天服務實例"""
        mock_model = Mock(spec=FullLLMInterface)
        mock_model.get_provider.return_value = ModelProvider.OPENAI
        mock_database = Mock(spec=Database)
        mock_config = {'commands': {}}
        return CoreChatService(mock_model, mock_database, mock_config)
    
    @pytest.fixture
    def mock_user(self):
        """模擬用戶"""
        return PlatformUser(
            user_id="test_user_123",
            platform=PlatformType.LINE,
            display_name="Test User"
        )
    
    def test_process_text_message(self, chat_service, mock_user):
        """測試處理文字訊息"""
        message = PlatformMessage(
            user=mock_user,
            content="Hello world",
            message_type="text"
        )
        
        expected_response = PlatformResponse(
            content="Hello back!",
            response_type="text"
        )
        
        with patch.object(chat_service, '_handle_text_message', return_value=expected_response) as mock_handle:
            result = chat_service.process_message(message)
            
            assert result == expected_response
            mock_handle.assert_called_once_with(mock_user, "Hello world", "line")
    
    def test_process_audio_message(self, chat_service, mock_user):
        """測試處理音訊訊息"""
        audio_data = b"fake_audio_data"
        message = PlatformMessage(
            user=mock_user,
            content="",
            message_type="audio",
            raw_data=audio_data
        )
        
        expected_response = PlatformResponse(
            content="Audio processed",
            response_type="text"
        )
        
        with patch.object(chat_service, '_handle_audio_message', return_value=expected_response) as mock_handle:
            result = chat_service.process_message(message)
            
            assert result == expected_response
            mock_handle.assert_called_once_with(mock_user, audio_data, "line")
    
    def test_process_unsupported_message_type(self, chat_service, mock_user):
        """測試處理不支援的訊息類型"""
        message = PlatformMessage(
            user=mock_user,
            content="",
            message_type="video"
        )
        
        result = chat_service.process_message(message)
        
        assert result.content == "抱歉，暫不支援此類型的訊息。"
        assert result.response_type == "text"
    
    def test_process_message_logging(self, chat_service, mock_user):
        """測試訊息處理的日誌記錄"""
        message = PlatformMessage(
            user=mock_user,
            content="Test message",
            message_type="text"
        )
        
        with patch.object(chat_service, '_handle_text_message', return_value=Mock()), \
             patch('src.services.chat.logger') as mock_logger:
            
            chat_service.process_message(message)
            
            mock_logger.info.assert_called_once_with(
                'Processing message from test_user_123 on line: Test message'
            )
    
    def test_process_message_logging_value_error(self, chat_service, mock_user):
        """測試訊息處理日誌記錄時的 ValueError 處理"""
        message = PlatformMessage(
            user=mock_user,
            content="Test message",
            message_type="text"
        )
        
        with patch.object(chat_service, '_handle_text_message', return_value=Mock()), \
             patch('src.services.chat.logger') as mock_logger:
            
            mock_logger.info.side_effect = ValueError("Logger error")
            
            # 應該不會拋出異常
            result = chat_service.process_message(message)
            assert result is not None


class TestHandleTextMessage:
    """測試文字訊息處理"""
    
    @pytest.fixture
    def chat_service(self):
        """創建聊天服務實例"""
        mock_model = Mock(spec=FullLLMInterface)
        mock_model.get_provider.return_value = ModelProvider.OPENAI
        mock_database = Mock(spec=Database)
        mock_config = {'commands': {}}
        return CoreChatService(mock_model, mock_database, mock_config)
    
    @pytest.fixture
    def mock_user(self):
        """模擬用戶"""
        return PlatformUser(
            user_id="test_user_123",
            platform=PlatformType.LINE,
            display_name="Test User"
        )
    
    def test_handle_command_message(self, chat_service, mock_user):
        """測試處理指令訊息"""
        expected_response = PlatformResponse(
            content="Reset completed",
            response_type="text"
        )
        
        with patch.object(chat_service, '_handle_command', return_value=expected_response) as mock_handle:
            result = chat_service._handle_text_message(mock_user, "/reset", "line")
            
            assert result == expected_response
            mock_handle.assert_called_once_with(mock_user, "/reset", "line")
    
    def test_handle_regular_chat_message(self, chat_service, mock_user):
        """測試處理一般聊天訊息"""
        expected_response = PlatformResponse(
            content="Chat response",
            response_type="text"
        )
        
        with patch.object(chat_service, '_handle_chat_message', return_value=expected_response) as mock_handle:
            result = chat_service._handle_text_message(mock_user, "Hello", "line")
            
            assert result == expected_response
            mock_handle.assert_called_once_with(mock_user, "Hello", "line")
    
    def test_handle_text_message_error_for_test_user(self, chat_service, mock_user):
        """測試測試用戶的錯誤處理"""
        # 設定為測試用戶 ID
        mock_user.user_id = "U" + "0" * 32
        
        with patch.object(chat_service, '_handle_chat_message', side_effect=Exception("Test error")):
            with pytest.raises(Exception, match="Test error"):
                chat_service._handle_text_message(mock_user, "Hello", "line")
    
    def test_handle_text_message_error_for_real_user(self, chat_service, mock_user):
        """測試真實用戶的錯誤處理"""
        with patch.object(chat_service, '_handle_chat_message', side_effect=Exception("Test error")), \
             patch.object(chat_service.error_handler, 'get_error_message', return_value="簡化錯誤訊息") as mock_error:
            
            result = chat_service._handle_text_message(mock_user, "Hello", "line")
            
            assert result.content == "簡化錯誤訊息"
            assert result.response_type == "text"
            mock_error.assert_called_once_with(Exception("Test error"), use_detailed=False)
    
    def test_handle_text_message_error_logging(self, chat_service, mock_user):
        """測試錯誤處理的日誌記錄"""
        with patch.object(chat_service, '_handle_chat_message', side_effect=ValueError("Test error")), \
             patch.object(chat_service.error_handler, 'get_error_message', return_value="Error message"), \
             patch('src.services.chat.logger') as mock_logger:
            
            chat_service._handle_text_message(mock_user, "Hello", "line")
            
            mock_logger.error.assert_any_call(
                "Error handling text message for user test_user_123: ValueError: Test error"
            )
            mock_logger.error.assert_any_call(
                "Error details - Platform: line, Message: Hello"
            )


class TestHandleAudioMessage:
    """測試音訊訊息處理"""
    
    @pytest.fixture
    def chat_service(self):
        """創建聊天服務實例"""
        mock_model = Mock(spec=FullLLMInterface)
        mock_model.get_provider.return_value = ModelProvider.OPENAI
        mock_database = Mock(spec=Database)
        mock_config = {'commands': {}}
        return CoreChatService(mock_model, mock_database, mock_config)
    
    @pytest.fixture
    def mock_user(self):
        """模擬用戶"""
        return PlatformUser(
            user_id="test_user_123",
            platform=PlatformType.LINE,
            display_name="Test User"
        )
    
    def test_handle_audio_message_success(self, chat_service, mock_user):
        """測試成功處理音訊訊息"""
        audio_data = b"fake_audio_data"
        transcribed_text = "Hello from audio"
        
        expected_response = PlatformResponse(
            content="Audio response",
            response_type="text"
        )
        
        with patch.object(chat_service, '_save_audio_file', return_value='test_audio.m4a') as mock_save, \
             patch.object(chat_service, '_transcribe_audio', return_value=transcribed_text) as mock_transcribe, \
             patch.object(chat_service, '_handle_chat_message', return_value=expected_response) as mock_chat, \
             patch.object(chat_service, '_delete_audio_file') as mock_delete:
            
            result = chat_service._handle_audio_message(mock_user, audio_data, "line")
            
            assert result == expected_response
            mock_save.assert_called_once_with(audio_data)
            mock_transcribe.assert_called_once_with('test_audio.m4a')
            mock_chat.assert_called_once_with(mock_user, transcribed_text, "line")
            mock_delete.assert_called_once_with('test_audio.m4a')
    
    def test_handle_audio_message_error_for_test_user(self, chat_service, mock_user):
        """測試測試用戶的音訊錯誤處理"""
        # 設定為測試用戶 ID
        mock_user.user_id = "U" + "0" * 32
        audio_data = b"fake_audio_data"
        
        with patch.object(chat_service, '_save_audio_file', side_effect=Exception("Save error")), \
             patch.object(chat_service, '_delete_audio_file'):
            
            with pytest.raises(Exception, match="Save error"):
                chat_service._handle_audio_message(mock_user, audio_data, "line")
    
    def test_handle_audio_message_error_for_real_user(self, chat_service, mock_user):
        """測試真實用戶的音訊錯誤處理"""
        audio_data = b"fake_audio_data"
        
        with patch.object(chat_service, '_save_audio_file', side_effect=Exception("Save error")), \
             patch.object(chat_service, '_delete_audio_file'), \
             patch.object(chat_service.error_handler, 'get_error_message', return_value="音訊處理錯誤") as mock_error:
            
            result = chat_service._handle_audio_message(mock_user, audio_data, "line")
            
            assert result.content == "音訊處理錯誤"
            assert result.response_type == "text"
            mock_error.assert_called_once()
    
    def test_handle_audio_message_cleanup_on_error(self, chat_service, mock_user):
        """測試音訊處理錯誤時的清理工作"""
        audio_data = b"fake_audio_data"
        
        with patch.object(chat_service, '_save_audio_file', return_value='test_audio.m4a'), \
             patch.object(chat_service, '_transcribe_audio', side_effect=Exception("Transcribe error")), \
             patch.object(chat_service, '_delete_audio_file') as mock_delete, \
             patch.object(chat_service.error_handler, 'get_error_message', return_value="Error"):
            
            chat_service._handle_audio_message(mock_user, audio_data, "line")
            
            mock_delete.assert_called_once_with('test_audio.m4a')
    
    def test_handle_audio_message_logging(self, chat_service, mock_user):
        """測試音訊處理的日誌記錄"""
        audio_data = b"fake_audio_data"
        transcribed_text = "Hello from audio"
        
        with patch.object(chat_service, '_save_audio_file', return_value='test_audio.m4a'), \
             patch.object(chat_service, '_transcribe_audio', return_value=transcribed_text), \
             patch.object(chat_service, '_handle_chat_message', return_value=Mock()), \
             patch.object(chat_service, '_delete_audio_file'), \
             patch('src.services.chat.logger') as mock_logger:
            
            chat_service._handle_audio_message(mock_user, audio_data, "line")
            
            mock_logger.info.assert_called_once_with(
                f"Audio transcribed for user {mock_user.user_id}: {transcribed_text}"
            )


class TestHandleCommand:
    """測試指令處理"""
    
    @pytest.fixture
    def chat_service(self):
        """創建聊天服務實例"""
        mock_model = Mock(spec=FullLLMInterface)
        mock_model.get_provider.return_value = ModelProvider.OPENAI
        mock_database = Mock(spec=Database)
        mock_config = {
            'commands': {
                'help': '系統說明',
                'status': '系統狀態'
            }
        }
        return CoreChatService(mock_model, mock_database, mock_config)
    
    @pytest.fixture
    def mock_user(self):
        """模擬用戶"""
        return PlatformUser(
            user_id="test_user_123",
            platform=PlatformType.LINE,
            display_name="Test User"
        )
    
    def test_handle_reset_command(self, chat_service, mock_user):
        """測試重置指令"""
        expected_response = PlatformResponse(
            content="Reset completed",
            response_type="text"
        )
        
        with patch.object(chat_service, '_handle_reset_command', return_value=expected_response) as mock_handle:
            result = chat_service._handle_command(mock_user, "/reset", "line")
            
            assert result == expected_response
            mock_handle.assert_called_once_with(mock_user, "line")
    
    def test_handle_known_command(self, chat_service, mock_user):
        """測試已知指令"""
        result = chat_service._handle_command(mock_user, "/help", "line")
        
        assert result.content == "系統說明\n\n"
        assert result.response_type == "text"
    
    def test_handle_unknown_command(self, chat_service, mock_user):
        """測試未知指令"""
        result = chat_service._handle_command(mock_user, "/unknown", "line")
        
        assert result.content == "Command not found."
        assert result.response_type == "text"
    
    def test_handle_command_with_parameters(self, chat_service, mock_user):
        """測試帶參數的指令"""
        result = chat_service._handle_command(mock_user, "/help detailed", "line")
        
        assert result.content == "系統說明\n\n"
        assert result.response_type == "text"


class TestHandleResetCommand:
    """測試重置指令處理"""
    
    @pytest.fixture
    def chat_service(self):
        """創建聊天服務實例"""
        mock_model = Mock(spec=FullLLMInterface)
        mock_model.get_provider.return_value = ModelProvider.OPENAI
        mock_database = Mock(spec=Database)
        mock_config = {}
        return CoreChatService(mock_model, mock_database, mock_config)
    
    @pytest.fixture
    def mock_user(self):
        """模擬用戶"""
        return PlatformUser(
            user_id="test_user_123",
            platform=PlatformType.LINE,
            display_name="Test User"
        )
    
    def test_reset_command_success(self, chat_service, mock_user):
        """測試成功重置"""
        chat_service.model.clear_user_history.return_value = (True, None)
        
        result = chat_service._handle_reset_command(mock_user, "line")
        
        assert result.content == "Reset The Chatbot."
        assert result.response_type == "text"
        chat_service.model.clear_user_history.assert_called_once_with(mock_user.user_id, "line")
    
    def test_reset_command_with_warnings(self, chat_service, mock_user):
        """測試重置時有警告"""
        chat_service.model.clear_user_history.return_value = (False, "Some warning")
        
        with patch('src.services.chat.logger') as mock_logger:
            result = chat_service._handle_reset_command(mock_user, "line")
            
            assert result.content == "Reset completed (with warnings)."
            assert result.response_type == "text"
            mock_logger.warning.assert_called_once_with(
                f"Failed to clear history for user {mock_user.user_id}: Some warning"
            )
    
    def test_reset_command_exception(self, chat_service, mock_user):
        """測試重置時異常"""
        chat_service.model.clear_user_history.side_effect = Exception("Reset failed")
        
        with patch('src.services.chat.logger') as mock_logger:
            with pytest.raises(ThreadError, match="Failed to reset: Reset failed"):
                chat_service._handle_reset_command(mock_user, "line")
            
            mock_logger.error.assert_called_once_with(
                f"Error resetting for user {mock_user.user_id}: Reset failed"
            )


class TestHandleChatMessage:
    """測試聊天訊息處理"""
    
    @pytest.fixture
    def chat_service(self):
        """創建聊天服務實例"""
        mock_model = Mock(spec=FullLLMInterface)
        mock_model.get_provider.return_value = ModelProvider.OPENAI
        mock_database = Mock(spec=Database)
        mock_config = {}
        return CoreChatService(mock_model, mock_database, mock_config)
    
    @pytest.fixture
    def mock_user(self):
        """模擬用戶"""
        return PlatformUser(
            user_id="test_user_123",
            platform=PlatformType.LINE,
            display_name="Test User"
        )
    
    def test_handle_chat_message_success(self, chat_service, mock_user):
        """測試成功處理聊天訊息"""
        with patch('src.services.chat.preprocess_text', return_value="processed text") as mock_preprocess, \
             patch.object(chat_service, '_process_conversation', return_value="response text") as mock_process, \
             patch('src.services.chat.postprocess_text', return_value="final response") as mock_postprocess:
            
            result = chat_service._handle_chat_message(mock_user, "Hello", "line")
            
            assert result.content == "final response"
            assert result.response_type == "text"
            mock_preprocess.assert_called_once_with("Hello", chat_service.config)
            mock_process.assert_called_once_with(mock_user, "processed text", "line")
            mock_postprocess.assert_called_once_with("response text", chat_service.config)
    
    def test_handle_chat_message_exception(self, chat_service, mock_user):
        """測試聊天訊息處理異常"""
        with patch('src.services.chat.preprocess_text', side_effect=Exception("Process error")), \
             patch('src.services.chat.logger') as mock_logger:
            
            with pytest.raises(Exception, match="Process error"):
                chat_service._handle_chat_message(mock_user, "Hello", "line")
            
            mock_logger.error.assert_any_call(
                "Error processing chat message for user test_user_123: Exception: Process error"
            )
            mock_logger.error.assert_any_call(
                "Error details - Platform: line, Processed text: Hello"
            )


class TestProcessConversation:
    """測試對話處理"""
    
    @pytest.fixture
    def chat_service(self):
        """創建聊天服務實例"""
        mock_model = Mock(spec=FullLLMInterface)
        mock_model.get_provider.return_value = ModelProvider.OPENAI
        mock_database = Mock(spec=Database)
        mock_config = {}
        return CoreChatService(mock_model, mock_database, mock_config)
    
    @pytest.fixture
    def mock_user(self):
        """模擬用戶"""
        return PlatformUser(
            user_id="test_user_123",
            platform=PlatformType.LINE,
            display_name="Test User"
        )
    
    def test_process_conversation_success(self, chat_service, mock_user):
        """測試成功處理對話"""
        mock_rag_response = RAGResponse(
            content="AI response",
            sources=[],
            model_info={}
        )
        
        chat_service.model.chat_with_user.return_value = (True, mock_rag_response, None)
        chat_service.response_formatter.format_rag_response.return_value = "formatted response"
        
        result = chat_service._process_conversation(mock_user, "Hello", "line")
        
        assert result == "formatted response"
        chat_service.model.chat_with_user.assert_called_once_with(
            user_id=mock_user.user_id,
            message="Hello",
            platform="line"
        )
        chat_service.response_formatter.format_rag_response.assert_called_once_with(mock_rag_response)
    
    def test_process_conversation_failure_database_error(self, chat_service, mock_user):
        """測試對話處理失敗 - 資料庫錯誤"""
        chat_service.model.chat_with_user.return_value = (False, None, "database connection failed")
        
        with pytest.raises(DatabaseError, match="database connection failed"):
            chat_service._process_conversation(mock_user, "Hello", "line")
    
    def test_process_conversation_failure_sql_error(self, chat_service, mock_user):
        """測試對話處理失敗 - SQL 錯誤"""
        chat_service.model.chat_with_user.return_value = (False, None, "column not found")
        
        with pytest.raises(DatabaseError, match="column not found"):
            chat_service._process_conversation(mock_user, "Hello", "line")
    
    def test_process_conversation_failure_openai_error(self, chat_service, mock_user):
        """測試對話處理失敗 - OpenAI 錯誤"""
        chat_service.model.chat_with_user.return_value = (False, None, "API rate limit exceeded")
        
        with pytest.raises(OpenAIError, match="Chat with user failed: API rate limit exceeded"):
            chat_service._process_conversation(mock_user, "Hello", "line")
    
    def test_process_conversation_exception_database_related(self, chat_service, mock_user):
        """測試對話處理異常 - 資料庫相關"""
        chat_service.model.chat_with_user.side_effect = Exception("psycopg2 connection error")
        
        with pytest.raises(DatabaseError, match="Database operation failed"):
            chat_service._process_conversation(mock_user, "Hello", "line")
    
    def test_process_conversation_exception_general(self, chat_service, mock_user):
        """測試對話處理異常 - 一般錯誤"""
        chat_service.model.chat_with_user.side_effect = Exception("General error")
        
        with pytest.raises(OpenAIError, match="Conversation processing failed"):
            chat_service._process_conversation(mock_user, "Hello", "line")
    
    def test_process_conversation_logging(self, chat_service, mock_user):
        """測試對話處理的日誌記錄"""
        mock_rag_response = RAGResponse(content="AI response", sources=[], model_info={})
        chat_service.model.chat_with_user.return_value = (True, mock_rag_response, None)
        chat_service.response_formatter.format_rag_response.return_value = "formatted response"
        
        with patch('src.services.chat.logger') as mock_logger:
            chat_service._process_conversation(mock_user, "Hello", "line")
            
            mock_logger.debug.assert_called_once_with(
                "Processed conversation response length: 18"
            )


class TestAudioFileOperations:
    """測試音訊檔案操作"""
    
    @pytest.fixture
    def chat_service(self):
        """創建聊天服務實例"""
        mock_model = Mock(spec=FullLLMInterface)
        mock_model.get_provider.return_value = ModelProvider.OPENAI
        mock_database = Mock(spec=Database)
        mock_config = {}
        return CoreChatService(mock_model, mock_database, mock_config)
    
    def test_save_audio_file_success(self, chat_service):
        """測試成功儲存音訊檔案"""
        audio_content = b"fake_audio_data"
        
        with patch('uuid.uuid4') as mock_uuid, \
             patch('builtins.open', mock_open()) as mock_file, \
             patch('src.services.chat.logger') as mock_logger:
            
            mock_uuid.return_value = Mock(__str__=Mock(return_value="test-uuid"))
            
            result = chat_service._save_audio_file(audio_content)
            
            assert result == "test-uuid.m4a"
            mock_file.assert_called_once_with("test-uuid.m4a", 'wb')
            mock_file().write.assert_called_once_with(audio_content)
            mock_logger.debug.assert_called_once_with("Audio file saved: test-uuid.m4a")
    
    def test_save_audio_file_failure(self, chat_service):
        """測試儲存音訊檔案失敗"""
        audio_content = b"fake_audio_data"
        
        with patch('uuid.uuid4') as mock_uuid, \
             patch('builtins.open', side_effect=IOError("Disk full")):
            
            mock_uuid.return_value = Mock(__str__=Mock(return_value="test-uuid"))
            
            with pytest.raises(OpenAIError, match="Failed to save audio file: Disk full"):
                chat_service._save_audio_file(audio_content)
    
    def test_delete_audio_file_success(self, chat_service):
        """測試成功刪除音訊檔案"""
        file_path = "test_audio.m4a"
        
        with patch('os.path.exists', return_value=True), \
             patch('os.remove') as mock_remove, \
             patch('src.services.chat.logger') as mock_logger:
            
            chat_service._delete_audio_file(file_path)
            
            mock_remove.assert_called_once_with(file_path)
            mock_logger.debug.assert_called_once_with("Cleaned up audio file: test_audio.m4a")
    
    def test_delete_audio_file_not_exists(self, chat_service):
        """測試刪除不存在的音訊檔案"""
        file_path = "test_audio.m4a"
        
        with patch('os.path.exists', return_value=False), \
             patch('os.remove') as mock_remove:
            
            chat_service._delete_audio_file(file_path)
            
            mock_remove.assert_not_called()
    
    def test_delete_audio_file_none_path(self, chat_service):
        """測試刪除音訊檔案時路徑為 None"""
        with patch('os.path.exists') as mock_exists, \
             patch('os.remove') as mock_remove:
            
            chat_service._delete_audio_file(None)
            
            mock_exists.assert_not_called()
            mock_remove.assert_not_called()
    
    def test_delete_audio_file_failure(self, chat_service):
        """測試刪除音訊檔案失敗"""
        file_path = "test_audio.m4a"
        
        with patch('os.path.exists', return_value=True), \
             patch('os.remove', side_effect=OSError("Permission denied")), \
             patch('src.services.chat.logger') as mock_logger:
            
            chat_service._delete_audio_file(file_path)
            
            mock_logger.warning.assert_called_once_with(
                "Failed to clean up audio file test_audio.m4a: Permission denied"
            )


class TestTranscribeAudio:
    """測試音訊轉錄"""
    
    @pytest.fixture
    def chat_service(self):
        """創建聊天服務實例"""
        mock_model = Mock(spec=FullLLMInterface)
        mock_model.get_provider.return_value = ModelProvider.OPENAI
        mock_database = Mock(spec=Database)
        mock_config = {}
        return CoreChatService(mock_model, mock_database, mock_config)
    
    def test_transcribe_audio_success(self, chat_service):
        """測試成功轉錄音訊"""
        audio_path = "test_audio.m4a"
        expected_text = "Hello from audio"
        
        chat_service.model.transcribe_audio.return_value = (True, expected_text, None)
        
        result = chat_service._transcribe_audio(audio_path)
        
        assert result == expected_text
        chat_service.model.transcribe_audio.assert_called_once_with(audio_path, model='whisper-1')
    
    def test_transcribe_audio_failure(self, chat_service):
        """測試轉錄音訊失敗"""
        audio_path = "test_audio.m4a"
        error_message = "Transcription failed"
        
        chat_service.model.transcribe_audio.return_value = (False, None, error_message)
        
        with pytest.raises(OpenAIError, match=f"Audio transcription failed: {error_message}"):
            chat_service._transcribe_audio(audio_path)
    
    def test_transcribe_audio_exception(self, chat_service):
        """測試轉錄音訊異常"""
        audio_path = "test_audio.m4a"
        
        chat_service.model.transcribe_audio.side_effect = Exception("Network error")
        
        with pytest.raises(OpenAIError, match="Audio transcription error: Network error"):
            chat_service._transcribe_audio(audio_path)
    
    def test_transcribe_audio_openai_error_passthrough(self, chat_service):
        """測試轉錄音訊時 OpenAIError 直接傳遞"""
        audio_path = "test_audio.m4a"
        original_error = OpenAIError("Original error")
        
        chat_service.model.transcribe_audio.side_effect = original_error
        
        with pytest.raises(OpenAIError, match="Original error"):
            chat_service._transcribe_audio(audio_path)


class TestWaitForCompletion:
    """測試等待完成功能"""
    
    @pytest.fixture
    def chat_service(self):
        """創建聊天服務實例"""
        mock_model = Mock(spec=FullLLMInterface)
        mock_model.get_provider.return_value = ModelProvider.OPENAI
        mock_database = Mock(spec=Database)
        mock_config = {}
        return CoreChatService(mock_model, mock_database, mock_config)
    
    def test_wait_for_completion_success(self, chat_service):
        """測試成功等待完成"""
        thread_id = "test_thread"
        initial_response = {'id': 'run_123', 'status': 'in_progress'}
        final_response = {'id': 'run_123', 'status': 'completed'}
        
        chat_service.model.retrieve_thread_run.return_value = (True, final_response, None)
        
        with patch('time.sleep') as mock_sleep:
            result = chat_service._wait_for_completion(thread_id, initial_response)
            
            assert result == final_response
            mock_sleep.assert_called_once_with(3)
    
    def test_wait_for_completion_timeout(self, chat_service):
        """測試等待完成超時"""
        thread_id = "test_thread"
        response = {'id': 'run_123', 'status': 'in_progress'}
        
        with patch('time.time', side_effect=[0, 130]):  # 超過 120 秒
            with pytest.raises(OpenAIError, match="Request timeout"):
                chat_service._wait_for_completion(thread_id, response)
    
    def test_wait_for_completion_queued_status(self, chat_service):
        """測試等待完成時排隊狀態"""
        thread_id = "test_thread"
        initial_response = {'id': 'run_123', 'status': 'queued'}
        final_response = {'id': 'run_123', 'status': 'completed'}
        
        chat_service.model.retrieve_thread_run.return_value = (True, final_response, None)
        
        with patch('time.sleep') as mock_sleep:
            result = chat_service._wait_for_completion(thread_id, initial_response)
            
            assert result == final_response
            mock_sleep.assert_called_once_with(10)  # 排隊時等待 10 秒
    
    def test_wait_for_completion_failed_status(self, chat_service):
        """測試等待完成時失敗狀態"""
        thread_id = "test_thread"
        response = {'id': 'run_123', 'status': 'failed'}
        
        result = chat_service._wait_for_completion(thread_id, response)
        
        assert result == response
    
    def test_wait_for_completion_retrieve_error(self, chat_service):
        """測試等待完成時檢索錯誤"""
        thread_id = "test_thread"
        response = {'id': 'run_123', 'status': 'in_progress'}
        
        chat_service.model.retrieve_thread_run.return_value = (False, None, "Retrieve failed")
        
        with patch('time.sleep'):
            with pytest.raises(OpenAIError, match="Failed to retrieve run status: Retrieve failed"):
                chat_service._wait_for_completion(thread_id, response)


class TestEdgeCases:
    """測試邊界情況"""
    
    @pytest.fixture
    def chat_service(self):
        """創建聊天服務實例"""
        mock_model = Mock(spec=FullLLMInterface)
        mock_model.get_provider.return_value = ModelProvider.OPENAI
        mock_database = Mock(spec=Database)
        mock_config = {}
        return CoreChatService(mock_model, mock_database, mock_config)
    
    @pytest.fixture
    def mock_user(self):
        """模擬用戶"""
        return PlatformUser(
            user_id="test_user_123",
            platform=PlatformType.LINE,
            display_name="Test User"
        )
    
    def test_empty_message_content(self, chat_service, mock_user):
        """測試空訊息內容"""
        message = PlatformMessage(
            user=mock_user,
            content="",
            message_type="text"
        )
        
        with patch.object(chat_service, '_handle_text_message', return_value=Mock()) as mock_handle:
            chat_service.process_message(message)
            
            mock_handle.assert_called_once_with(mock_user, "", "line")
    
    def test_very_long_message_content(self, chat_service, mock_user):
        """測試非常長的訊息內容"""
        long_content = "A" * 10000
        message = PlatformMessage(
            user=mock_user,
            content=long_content,
            message_type="text"
        )
        
        with patch.object(chat_service, '_handle_text_message', return_value=Mock()) as mock_handle:
            chat_service.process_message(message)
            
            mock_handle.assert_called_once_with(mock_user, long_content, "line")
    
    def test_special_characters_in_message(self, chat_service, mock_user):
        """測試訊息中的特殊字元"""
        special_content = "Hello! 你好 🎵 @#$%^&*()_+"
        message = PlatformMessage(
            user=mock_user,
            content=special_content,
            message_type="text"
        )
        
        with patch.object(chat_service, '_handle_text_message', return_value=Mock()) as mock_handle:
            chat_service.process_message(message)
            
            mock_handle.assert_called_once_with(mock_user, special_content, "line")
    
    def test_different_platform_types(self, chat_service):
        """測試不同平台類型"""
        for platform_type in [PlatformType.LINE, PlatformType.DISCORD, PlatformType.TELEGRAM]:
            user = PlatformUser(
                user_id="test_user",
                platform=platform_type,
                display_name="Test User"
            )
            
            message = PlatformMessage(
                user=user,
                content="Hello",
                message_type="text"
            )
            
            with patch.object(chat_service, '_handle_text_message', return_value=Mock()) as mock_handle:
                chat_service.process_message(message)
                
                mock_handle.assert_called_once_with(user, "Hello", platform_type.value)


if __name__ == "__main__":
    pytest.main([__file__])