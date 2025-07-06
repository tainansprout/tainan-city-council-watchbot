"""
測試音訊服務模組的單元測試
"""
import pytest
import os
import tempfile
from unittest.mock import Mock, patch, mock_open
from linebot.v3.messaging import TextMessage

from src.services.audio import AudioService
from src.core.exceptions import OpenAIError
from src.core.error_handler import ErrorHandler
from src.models.base import FullLLMInterface
from src.services.chat import CoreChatService


class TestAudioService:
    """測試音訊服務主要功能"""
    
    @pytest.fixture
    def mock_model(self):
        """模擬 AI 模型"""
        model = Mock(spec=FullLLMInterface)
        return model
    
    @pytest.fixture
    def mock_chat_service(self):
        """模擬聊天服務"""
        service = Mock()
        service.handle_message = Mock()
        return service
    
    @pytest.fixture
    def audio_service(self, mock_model, mock_chat_service):
        """創建音訊服務實例"""
        return AudioService(mock_model, mock_chat_service)
    
    def test_audio_service_initialization(self, mock_model, mock_chat_service):
        """測試音訊服務初始化"""
        service = AudioService(mock_model, mock_chat_service)
        
        assert service.model == mock_model
        assert service.chat_service == mock_chat_service
        assert isinstance(service.error_handler, ErrorHandler)
    
    def test_handle_audio_message_success(self, audio_service, mock_model, mock_chat_service):
        """測試成功處理音訊訊息"""
        # 準備測試資料
        user_id = "test_user"
        audio_content = b"fake_audio_data"
        platform = "line"
        expected_text = "Hello, this is transcribed text"
        expected_response = Mock(spec=TextMessage)
        
        # 設定 mock 行為
        mock_model.transcribe_audio.return_value = (True, expected_text, None)
        mock_chat_service.handle_message.return_value = expected_response
        
        with patch.object(audio_service, '_save_audio_file', return_value='test_audio.m4a') as mock_save, \
             patch('os.path.exists', return_value=True), \
             patch('os.remove') as mock_remove:
            
            result = audio_service.handle_audio_message(user_id, audio_content, platform)
            
            # 驗證結果
            assert result == expected_response
            
            # 驗證方法呼叫
            mock_save.assert_called_once_with(audio_content)
            mock_model.transcribe_audio.assert_called_once_with('test_audio.m4a')
            mock_chat_service.handle_message.assert_called_once_with(user_id, expected_text, platform)
            mock_remove.assert_called_once_with('test_audio.m4a')
    
    def test_handle_audio_message_transcription_failure(self, audio_service, mock_model):
        """測試音訊轉錄失敗的情況"""
        user_id = "test_user"
        audio_content = b"fake_audio_data"
        
        # 設定轉錄失敗
        mock_model.transcribe_audio.return_value = (False, None, "Transcription failed")
        
        with patch.object(audio_service, '_save_audio_file', return_value='test_audio.m4a'), \
             patch('os.path.exists', return_value=True), \
             patch('os.remove'), \
             patch.object(audio_service.error_handler, 'handle_error') as mock_error_handler:
            
            mock_error_response = Mock(spec=TextMessage)
            mock_error_handler.return_value = mock_error_response
            
            result = audio_service.handle_audio_message(user_id, audio_content)
            
            # 驗證錯誤處理被呼叫
            mock_error_handler.assert_called_once()
            assert result == mock_error_response
    
    def test_handle_audio_message_save_file_failure(self, audio_service):
        """測試儲存音訊檔案失敗的情況"""
        user_id = "test_user"
        audio_content = b"fake_audio_data"
        
        with patch.object(audio_service, '_save_audio_file', side_effect=OpenAIError("Save failed")), \
             patch.object(audio_service.error_handler, 'handle_error') as mock_error_handler:
            
            mock_error_response = Mock(spec=TextMessage)
            mock_error_handler.return_value = mock_error_response
            
            result = audio_service.handle_audio_message(user_id, audio_content)
            
            # 驗證錯誤處理被呼叫
            mock_error_handler.assert_called_once()
            assert result == mock_error_response
    
    def test_handle_audio_message_cleanup_failure(self, audio_service, mock_model, mock_chat_service):
        """測試清理檔案失敗但不影響主要流程"""
        user_id = "test_user"
        audio_content = b"fake_audio_data"
        expected_response = Mock(spec=TextMessage)
        
        # 設定正常的轉錄和處理
        mock_model.transcribe_audio.return_value = (True, "transcribed text", None)
        mock_chat_service.handle_message.return_value = expected_response
        
        with patch.object(audio_service, '_save_audio_file', return_value='test_audio.m4a'), \
             patch('os.path.exists', return_value=True), \
             patch('os.remove', side_effect=OSError("Permission denied")) as mock_remove, \
             patch('src.services.audio.logger') as mock_logger:
            
            result = audio_service.handle_audio_message(user_id, audio_content)
            
            # 主要流程應該成功
            assert result == expected_response
            
            # 清理失敗應該被記錄為警告
            mock_remove.assert_called_once_with('test_audio.m4a')
            mock_logger.warning.assert_called_once()
    
    def test_handle_audio_message_no_cleanup_if_file_not_exists(self, audio_service, mock_model, mock_chat_service):
        """測試當檔案不存在時不進行清理"""
        user_id = "test_user"
        audio_content = b"fake_audio_data"
        expected_response = Mock(spec=TextMessage)
        
        mock_model.transcribe_audio.return_value = (True, "transcribed text", None)
        mock_chat_service.handle_message.return_value = expected_response
        
        with patch.object(audio_service, '_save_audio_file', return_value='test_audio.m4a'), \
             patch('os.path.exists', return_value=False), \
             patch('os.remove') as mock_remove:
            
            result = audio_service.handle_audio_message(user_id, audio_content)
            
            # 檔案不存在時不應該嘗試刪除
            mock_remove.assert_not_called()
            assert result == expected_response
    
    def test_handle_audio_message_default_platform(self, audio_service, mock_model, mock_chat_service):
        """測試預設平台參數"""
        user_id = "test_user"
        audio_content = b"fake_audio_data"
        expected_response = Mock(spec=TextMessage)
        
        mock_model.transcribe_audio.return_value = (True, "transcribed text", None)
        mock_chat_service.handle_message.return_value = expected_response
        
        with patch.object(audio_service, '_save_audio_file', return_value='test_audio.m4a'), \
             patch('os.path.exists', return_value=True), \
             patch('os.remove'):
            
            # 不提供 platform 參數，應該使用預設值 'line'
            result = audio_service.handle_audio_message(user_id, audio_content)
            
            mock_chat_service.handle_message.assert_called_once_with(user_id, "transcribed text", 'line')
            assert result == expected_response


class TestAudioServiceSaveFile:
    """測試音訊檔案儲存功能"""
    
    @pytest.fixture
    def audio_service(self):
        """創建音訊服務實例"""
        mock_model = Mock(spec=FullLLMInterface)
        mock_chat_service = Mock()
        mock_chat_service.handle_message = Mock()
        return AudioService(mock_model, mock_chat_service)
    
    def test_save_audio_file_success(self, audio_service):
        """測試成功儲存音訊檔案"""
        audio_content = b"test_audio_content"
        
        mock_uuid = Mock()
        mock_uuid.__str__ = Mock(return_value='test-uuid')
        
        with patch('builtins.open', mock_open()) as mock_file, \
             patch('uuid.uuid4', return_value=mock_uuid), \
             patch('src.services.audio.logger') as mock_logger:
            
            result = audio_service._save_audio_file(audio_content)
            
            # 驗證檔案路徑格式
            assert result == 'test-uuid.m4a'
            
            # 驗證檔案寫入
            mock_file.assert_called_once_with('test-uuid.m4a', 'wb')
            mock_file().write.assert_called_once_with(audio_content)
            
            # 驗證除錯日誌
            mock_logger.debug.assert_called_once()
    
    def test_save_audio_file_write_failure(self, audio_service):
        """測試寫入檔案失敗的情況"""
        audio_content = b"test_audio_content"
        
        mock_uuid = Mock()
        mock_uuid.__str__ = Mock(return_value='test-uuid')
        
        with patch('builtins.open', side_effect=IOError("Disk full")), \
             patch('uuid.uuid4', return_value=mock_uuid):
            
            with pytest.raises(OpenAIError, match="Failed to save audio file.*Disk full"):
                audio_service._save_audio_file(audio_content)
    
    def test_save_audio_file_uuid_generation(self, audio_service):
        """測試 UUID 生成和檔案名稱格式"""
        audio_content = b"test_audio_content"
        
        # 模擬 UUID
        mock_uuid = Mock()
        mock_uuid.__str__ = Mock(return_value='12345678-1234-5678-9012-123456789abc')
        
        with patch('builtins.open', mock_open()), \
             patch('uuid.uuid4', return_value=mock_uuid):
            
            result = audio_service._save_audio_file(audio_content)
            
            assert result == '12345678-1234-5678-9012-123456789abc.m4a'


class TestAudioServiceTranscribe:
    """測試音訊轉錄功能"""
    
    @pytest.fixture
    def audio_service(self):
        """創建音訊服務實例"""
        mock_model = Mock(spec=FullLLMInterface)
        mock_chat_service = Mock()
        mock_chat_service.handle_message = Mock()
        return AudioService(mock_model, mock_chat_service)
    
    def test_transcribe_audio_success(self, audio_service):
        """測試成功轉錄音訊"""
        audio_path = "test_audio.m4a"
        expected_text = "Hello, this is transcribed text"
        
        # 設定模型返回成功結果
        audio_service.model.transcribe_audio.return_value = (True, expected_text, None)
        
        result = audio_service._transcribe_audio(audio_path)
        
        assert result == expected_text
        audio_service.model.transcribe_audio.assert_called_once_with(audio_path)
    
    def test_transcribe_audio_model_failure(self, audio_service):
        """測試模型轉錄失敗"""
        audio_path = "test_audio.m4a"
        error_message = "Model API error"
        
        # 設定模型返回失敗結果
        audio_service.model.transcribe_audio.return_value = (False, None, error_message)
        
        with pytest.raises(OpenAIError, match=f"Audio transcription failed: {error_message}"):
            audio_service._transcribe_audio(audio_path)
    
    def test_transcribe_audio_model_exception(self, audio_service):
        """測試模型拋出異常"""
        audio_path = "test_audio.m4a"
        
        # 設定模型拋出異常
        audio_service.model.transcribe_audio.side_effect = ValueError("Invalid audio format")
        
        with pytest.raises(OpenAIError, match="Audio transcription error.*Invalid audio format"):
            audio_service._transcribe_audio(audio_path)
    
    def test_transcribe_audio_openai_error_passthrough(self, audio_service):
        """測試 OpenAIError 異常的直接傳遞"""
        audio_path = "test_audio.m4a"
        original_error = OpenAIError("Original error")
        
        # 設定模型拋出 OpenAIError
        audio_service.model.transcribe_audio.side_effect = original_error
        
        with pytest.raises(OpenAIError, match="Original error"):
            audio_service._transcribe_audio(audio_path)
    
    def test_transcribe_audio_model_parameters(self, audio_service):
        """測試轉錄時傳遞正確的模型參數"""
        audio_path = "test_audio.m4a"
        
        audio_service.model.transcribe_audio.return_value = (True, "text", None)
        
        audio_service._transcribe_audio(audio_path)
        
        # 驗證傳遞了正確的模型參數
        audio_service.model.transcribe_audio.assert_called_once_with(
            audio_path
        )


class TestAudioServiceLogging:
    """測試音訊服務的日誌功能"""
    
    @pytest.fixture
    def audio_service(self):
        """創建音訊服務實例"""
        mock_model = Mock(spec=FullLLMInterface)
        mock_chat_service = Mock()
        mock_chat_service.handle_message = Mock()
        return AudioService(mock_model, mock_chat_service)
    
    def test_successful_transcription_logging(self, audio_service):
        """測試成功轉錄的日誌記錄"""
        user_id = "test_user"
        audio_content = b"fake_audio_data"
        transcribed_text = "Hello world"
        
        audio_service.model.transcribe_audio.return_value = (True, transcribed_text, None)
        audio_service.chat_service.handle_message.return_value = Mock()
        
        with patch.object(audio_service, '_save_audio_file', return_value='test_audio.m4a'), \
             patch('os.path.exists', return_value=True), \
             patch('os.remove'), \
             patch('src.services.audio.logger') as mock_logger:
            
            audio_service.handle_audio_message(user_id, audio_content)
            
            # 驗證轉錄成功的日誌
            mock_logger.info.assert_called_with(f"Audio transcribed for user {user_id}: {transcribed_text}")
    
    def test_error_logging(self, audio_service):
        """測試錯誤情況的日誌記錄"""
        user_id = "test_user"
        audio_content = b"fake_audio_data"
        
        with patch.object(audio_service, '_save_audio_file', side_effect=Exception("Test error")), \
             patch.object(audio_service.error_handler, 'handle_error', return_value=Mock()), \
             patch('src.services.audio.logger') as mock_logger:
            
            audio_service.handle_audio_message(user_id, audio_content)
            
            # 驗證錯誤日誌
            mock_logger.error.assert_called_with(f"Error processing audio for user {user_id}: Test error")
    
    def test_cleanup_success_logging(self, audio_service):
        """測試清理成功的日誌記錄"""
        user_id = "test_user"
        audio_content = b"fake_audio_data"
        audio_path = 'test_audio.m4a'
        
        audio_service.model.transcribe_audio.return_value = (True, "text", None)
        audio_service.chat_service.handle_message.return_value = Mock()
        
        with patch.object(audio_service, '_save_audio_file', return_value=audio_path), \
             patch('os.path.exists', return_value=True), \
             patch('os.remove'), \
             patch('src.services.audio.logger') as mock_logger:
            
            audio_service.handle_audio_message(user_id, audio_content)
            
            # 驗證清理成功的日誌
            mock_logger.debug.assert_any_call(f"Cleaned up audio file: {audio_path}")
    
    def test_cleanup_failure_logging(self, audio_service):
        """測試清理失敗的日誌記錄"""
        user_id = "test_user"
        audio_content = b"fake_audio_data"
        audio_path = 'test_audio.m4a'
        
        audio_service.model.transcribe_audio.return_value = (True, "text", None)
        audio_service.chat_service.handle_message.return_value = Mock()
        
        with patch.object(audio_service, '_save_audio_file', return_value=audio_path), \
             patch('os.path.exists', return_value=True), \
             patch('os.remove', side_effect=OSError("Permission denied")), \
             patch('src.services.audio.logger') as mock_logger:
            
            audio_service.handle_audio_message(user_id, audio_content)
            
            # 驗證清理失敗的警告日誌
            mock_logger.warning.assert_called_with(f"Failed to clean up audio file {audio_path}: Permission denied")


class TestAudioServiceEdgeCases:
    """測試音訊服務的邊界情況"""
    
    @pytest.fixture
    def audio_service(self):
        """創建音訊服務實例"""
        mock_model = Mock(spec=FullLLMInterface)
        mock_chat_service = Mock()
        mock_chat_service.handle_message = Mock()
        return AudioService(mock_model, mock_chat_service)
    
    def test_empty_audio_content(self, audio_service):
        """測試空的音訊內容"""
        user_id = "test_user"
        audio_content = b""  # 空內容
        
        with patch.object(audio_service, '_save_audio_file', return_value='test_audio.m4a'), \
             patch('os.path.exists', return_value=True), \
             patch('os.remove'), \
             patch.object(audio_service.error_handler, 'handle_error') as mock_error_handler:
            
            # 設定轉錄失敗（因為空內容）
            audio_service.model.transcribe_audio.return_value = (False, None, "Empty audio")
            mock_error_handler.return_value = Mock()
            
            result = audio_service.handle_audio_message(user_id, audio_content)
            
            # 應該處理錯誤並返回錯誤訊息
            mock_error_handler.assert_called_once()
    
    def test_very_long_transcribed_text(self, audio_service):
        """測試非常長的轉錄文字"""
        user_id = "test_user"
        audio_content = b"fake_audio_data"
        long_text = "A" * 10000  # 10,000 字元的長文字
        
        audio_service.model.transcribe_audio.return_value = (True, long_text, None)
        expected_response = Mock()
        audio_service.chat_service.handle_message.return_value = expected_response
        
        with patch.object(audio_service, '_save_audio_file', return_value='test_audio.m4a'), \
             patch('os.path.exists', return_value=True), \
             patch('os.remove'):
            
            result = audio_service.handle_audio_message(user_id, audio_content)
            
            # 應該能正常處理長文字
            audio_service.chat_service.handle_message.assert_called_once_with(user_id, long_text, 'line')
            assert result == expected_response
    
    def test_special_characters_in_transcription(self, audio_service):
        """測試轉錄結果包含特殊字元"""
        user_id = "test_user"
        audio_content = b"fake_audio_data"
        special_text = "Hello! 你好 🎵 @#$%^&*()_+"
        
        audio_service.model.transcribe_audio.return_value = (True, special_text, None)
        expected_response = Mock()
        audio_service.chat_service.handle_message.return_value = expected_response
        
        with patch.object(audio_service, '_save_audio_file', return_value='test_audio.m4a'), \
             patch('os.path.exists', return_value=True), \
             patch('os.remove'):
            
            result = audio_service.handle_audio_message(user_id, audio_content)
            
            # 應該能正常處理特殊字元
            audio_service.chat_service.handle_message.assert_called_once_with(user_id, special_text, 'line')
            assert result == expected_response
    
    def test_none_audio_path_in_cleanup(self, audio_service):
        """測試音訊路徑為 None 時的清理行為"""
        user_id = "test_user"
        audio_content = b"fake_audio_data"
        
        with patch.object(audio_service, '_save_audio_file', side_effect=Exception("Save failed")), \
             patch('os.path.exists') as mock_exists, \
             patch('os.remove') as mock_remove, \
             patch.object(audio_service.error_handler, 'handle_error', return_value=Mock()):
            
            audio_service.handle_audio_message(user_id, audio_content)
            
            # 當 input_audio_path 為 None 時，不應該檢查檔案存在性或刪除檔案
            mock_exists.assert_not_called()
            mock_remove.assert_not_called()