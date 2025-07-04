import pytest
from unittest.mock import Mock, patch, MagicMock
from linebot.v3.messaging import TextMessage

from src.services.chat_service import ChatService
from src.services.audio_service import AudioService
from src.core.exceptions import OpenAIError, DatabaseError, ThreadError
from src.models.base import ChatResponse, RAGResponse


class TestChatService:
    """聊天服務單元測試 - 重構後版本"""
    
    @pytest.fixture
    def chat_service(self, mock_openai_model, mock_database, mock_config):
        return ChatService(mock_openai_model, mock_database, mock_config)
    
    def test_handle_help_command(self, chat_service):
        response = chat_service.handle_message('test_user', '/help')
        
        assert isinstance(response, TextMessage)
        assert 'Test help message' in response.text
    
    def test_handle_reset_command_with_existing_thread(self, chat_service, mock_database, mock_openai_model):
        # 設定模擬清除對話歷史成功
        mock_openai_model.clear_user_history.return_value = (True, None)
        
        response = chat_service.handle_message('test_user', '/reset')
        
        assert isinstance(response, TextMessage)
        assert 'Reset The Chatbot' in response.text
        mock_openai_model.clear_user_history.assert_called_once_with('test_user', 'line')
    
    def test_handle_reset_command_without_thread(self, chat_service, mock_database, mock_openai_model):
        # 設定模擬清除對話歷史失敗
        mock_openai_model.clear_user_history.return_value = (False, 'Error')

        response = chat_service.handle_message('test_user', '/reset')

        assert isinstance(response, TextMessage)
        assert 'Reset completed (with warnings).' in response.text
    
    def test_handle_unknown_command(self, chat_service):
        response = chat_service.handle_message('test_user', '/unknown')
        
        assert isinstance(response, TextMessage)
        assert 'Command not found' in response.text
    
    @patch('src.services.chat_service.preprocess_text')
    @patch('src.services.chat_service.postprocess_text')
    def test_handle_chat_message_success(self, mock_postprocess, mock_preprocess, chat_service, mock_openai_model, mock_database):
        # 設定模擬
        mock_preprocess.return_value = 'processed text'
        mock_postprocess.return_value = 'final response'
        # 設定模擬聊天接口
        mock_openai_model.chat_with_user.return_value = (True, RAGResponse(answer='Test response', sources=[], metadata={}), None)

        response = chat_service.handle_message('test_user', 'Hello')
        
        assert isinstance(response, TextMessage)
        mock_preprocess.assert_called_once()
        mock_postprocess.assert_called_once()
    
    def test_handle_chat_message_with_database_error(self, chat_service, mock_database, mock_openai_model):
        # 模擬資料庫錯誤
        mock_openai_model.chat_with_user.side_effect = DatabaseError("Database connection failed")
        # 應丟出例外
        with pytest.raises(OpenAIError):
            chat_service.handle_message('test_user', 'Hello')
    
    def test_response_formatter_initialization(self, chat_service):
        """測試 ResponseFormatter 是否正確初始化"""
        assert chat_service.response_formatter is not None
        assert hasattr(chat_service.response_formatter, 'format_rag_response')
    
    @patch('src.services.chat_service.preprocess_text')
    @patch('src.services.chat_service.postprocess_text')
    def test_unified_rag_interface_usage(self, mock_postprocess, mock_preprocess, chat_service, mock_database, mock_openai_model):
        """測試統一的 RAG 接口使用"""
        # 設定模擬
        mock_preprocess.return_value = 'processed text'
        mock_postprocess.side_effect = lambda x, config: x
        # 設定模擬聊天接口
        rag_response = RAGResponse(
            answer='Test response with sources',
            sources=[{'filename': 'test.txt', 'type': 'file_citation'}],
            metadata={'thread_id': 'test_thread'}
        )
        mock_openai_model.chat_with_user.return_value = (True, rag_response, None)

        # 呼叫處理方法
        response = chat_service.handle_message('test_user', '測試消息')

        # 驗證統一接口被調用
        mock_openai_model.chat_with_user.assert_called_once()
        assert isinstance(response, TextMessage)


class TestAudioService:
    """音訊服務單元測試 - 重構後版本"""
    
    @pytest.fixture
    def audio_service(self, mock_openai_model, mock_chat_service):
        return AudioService(mock_openai_model, mock_chat_service)
    
    @patch('os.path.exists')
    @patch('os.remove')
    @patch('builtins.open', create=True)
    def test_handle_audio_message_success(self, mock_open, mock_remove, mock_exists, 
                                        audio_service, mock_openai_model, mock_chat_service):
        # 設定模擬
        mock_exists.return_value = True
        # 使用重構後的新方法
        mock_openai_model.transcribe_audio.return_value = (True, 'Transcribed text', None)
        mock_chat_service.handle_message.return_value = TextMessage(text='Chat response')
        
        audio_content = b'fake audio data'
        
        response = audio_service.handle_audio_message('test_user', audio_content)
        
        assert isinstance(response, TextMessage)
        assert response.text == 'Chat response'
        mock_chat_service.handle_message.assert_called_once_with('test_user', 'Transcribed text', 'line')
        mock_remove.assert_called_once()  # 確保清理臨時檔案
    
    @patch('os.path.exists')
    @patch('os.remove')
    @patch('builtins.open', create=True)
    def test_handle_audio_message_transcription_error(self, mock_open, mock_remove, mock_exists,
                                                    audio_service, mock_openai_model):
        # 設定模擬：轉錄失敗
        mock_exists.return_value = True
        # 使用重構後的新方法
        mock_openai_model.transcribe_audio.return_value = (False, None, 'Transcription failed')
        
        audio_content = b'fake audio data'
        
        response = audio_service.handle_audio_message('test_user', audio_content)
        
        assert isinstance(response, TextMessage)
        # 應該返回錯誤訊息（中文）
        assert 'OpenAI' in response.text or 'API' in response.text or '錯誤' in response.text
        mock_remove.assert_called_once()  # 即使失敗也要清理檔案
    
    @patch('uuid.uuid4')
    @patch('builtins.open', create=True)
    def test_save_audio_file(self, mock_open, mock_uuid, audio_service):
        mock_uuid.return_value = Mock()
        mock_uuid.return_value.__str__ = Mock(return_value='test-uuid')
        
        audio_content = b'test audio data'
        
        file_path = audio_service._save_audio_file(audio_content)
        
        assert file_path.endswith('.m4a')
        mock_open.assert_called_once()
    
    def test_save_audio_file_error(self, audio_service):
        # 模擬檔案寫入錯誤
        with patch('builtins.open', side_effect=IOError("Disk full")):
            with pytest.raises(OpenAIError, match="Failed to save audio file"):
                audio_service._save_audio_file(b'test data')
    
    def test_transcribe_audio_success(self, audio_service, mock_openai_model):
        # 使用重構後的新方法
        mock_openai_model.transcribe_audio.return_value = (
            True, 
            'Hello world', 
            None
        )
        
        result = audio_service._transcribe_audio('test_file.m4a')
        
        assert result == 'Hello world'
    
    def test_transcribe_audio_failure(self, audio_service, mock_openai_model):
        # 使用重構後的新方法
        mock_openai_model.transcribe_audio.return_value = (
            False, 
            None, 
            'Transcription service unavailable'
        )
        
        with pytest.raises(OpenAIError, match="Audio transcription failed"):
            audio_service._transcribe_audio('test_file.m4a')
    
    @patch('os.path.exists')
    @patch('os.remove')
    def test_cleanup_on_exception(self, mock_remove, mock_exists, audio_service, mock_openai_model):
        # 模擬轉錄過程中發生異常
        # 使用重構後的新方法
        mock_openai_model.transcribe_audio.side_effect = Exception("Unexpected error")
        mock_exists.return_value = True
        
        with patch.object(audio_service, '_save_audio_file', return_value='test_file.m4a'):
            response = audio_service.handle_audio_message('test_user', b'audio_data')
            
            # 確保即使發生異常也會清理檔案
            mock_remove.assert_called_once_with('test_file.m4a')
            assert isinstance(response, TextMessage)


class TestServiceIntegration:
    """服務整合測試 - 重構後版本"""
    
    def test_chat_and_audio_service_integration(self, mock_openai_model, mock_database, mock_config):
        # 建立服務實例
        chat_service = ChatService(mock_openai_model, mock_database, mock_config)
        audio_service = AudioService(mock_openai_model, chat_service)
        
        # 設定模擬
        # 使用重構後的新方法
        mock_openai_model.transcribe_audio.return_value = (True, 'Hello', None)
        
        mock_rag_response = Mock()
        mock_rag_response.answer = 'Hi there!'
        mock_rag_response.sources = []
        mock_openai_model.chat_with_user.return_value = (True, mock_rag_response, None)
        
        with patch('os.path.exists', return_value=True), \
             patch('os.remove'), \
             patch('builtins.open', create=True):
            
            response = audio_service.handle_audio_message('test_user', b'audio_data')
            
            assert isinstance(response, TextMessage)
            # 驗證使用統一的音訊轉錄接口
            mock_openai_model.transcribe_audio.assert_called_once()
            mock_openai_model.chat_with_user.assert_called_once()