"""
測試音訊服務的單元測試
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.services.audio import (
    AudioService, process_audio, get_audio_handler, 
    AudioPerformanceMonitor, get_audio_stats, get_audio_performance_summary
)
from src.services.chat import ChatService
from src.models.base import FullLLMInterface, ModelProvider
from src.platforms.base import PlatformMessage, PlatformResponse, PlatformUser, PlatformType
from src.core.exceptions import AudioError
from src.core.error_handler import ErrorHandler


class TestAudioService:
    """測試音訊服務"""
    
    @pytest.fixture
    def mock_model(self):
        """模擬 AI 模型"""
        model = Mock(spec=FullLLMInterface)
        model.get_provider.return_value = ModelProvider.OPENAI
        return model
    
    @pytest.fixture
    def mock_chat_service(self):
        """模擬聊天服務"""
        return Mock(spec=ChatService)
    
    @pytest.fixture
    def audio_service(self, mock_model):
        """創建音訊服務實例"""
        return AudioService(mock_model)
    
    def test_audio_service_initialization(self, mock_model):
        """測試音訊服務初始化"""
        service = AudioService(mock_model)
        
        assert service.model == mock_model
        assert isinstance(service.error_handler, ErrorHandler)
    
    @patch('src.services.audio.process_audio')
    def test_handle_message_success(self, mock_process_audio, audio_service):
        """測試成功處理音訊訊息 - 僅轉錄"""
        user_id = "test_user_123"
        audio_content = b"fake_audio_data"
        transcribed_text = "Hello from audio"
        
        # 模擬音訊處理成功
        mock_process_audio.return_value = (True, transcribed_text, None)
        
        result = audio_service.handle_message(user_id, audio_content, "line")
        
        assert result['success'] is True
        assert result['transcribed_text'] == transcribed_text
        assert result['error_message'] is None
        
        # 驗證音訊處理被調用
        mock_process_audio.assert_called_once_with(audio_content, audio_service.model)
    
    @patch('src.services.audio.process_audio')
    def test_handle_message_transcription_failure(self, mock_process_audio, audio_service):
        """測試音訊轉錄失敗"""
        user_id = "test_user_123"
        audio_content = b"fake_audio_data"
        error_message = "Audio transcription failed"
        
        # 模擬音訊處理失敗
        mock_process_audio.return_value = (False, None, error_message)
        
        result = audio_service.handle_message(user_id, audio_content, "line")
        
        assert result['success'] is False
        assert result['transcribed_text'] is None
        assert "Audio transcription failed" in result['error_message']
    
    @patch('src.services.audio.process_audio')
    def test_handle_message_exception(self, mock_process_audio, audio_service):
        """測試音訊處理異常"""
        user_id = "test_user_123"
        audio_content = b"fake_audio_data"
        
        # 模擬異常
        mock_process_audio.side_effect = Exception("Unexpected error")
        
        result = audio_service.handle_message(user_id, audio_content, "line")
        
        assert result['success'] is False
        assert result['transcribed_text'] is None
        assert "Unexpected error" in result['error_message']
    
    @patch('src.services.audio.process_audio')
    def test_handle_message_logging(self, mock_process_audio, audio_service):
        """測試音訊處理的日誌記錄"""
        user_id = "test_user_123"
        audio_content = b"fake_audio_data"
        transcribed_text = "Hello from audio"
        
        mock_process_audio.return_value = (True, transcribed_text, None)
        
        with patch('src.services.audio.logger') as mock_logger:
            audio_service.handle_message(user_id, audio_content, "line")
            
            # 檢查日誌記錄
            mock_logger.info.assert_called_once_with(
                f"Audio transcribed for user {user_id}: {transcribed_text[:50]}{'...' if len(transcribed_text) > 50 else ''}"
            )


class TestProcessAudio:
    """測試音訊處理函數"""
    
    @patch('src.services.audio.get_audio_handler')
    def test_process_audio_success(self, mock_get_handler):
        """測試成功處理音訊"""
        audio_content = b"fake_audio_data"
        model_handler = Mock()
        
        # 模擬音訊處理器
        mock_handler = Mock()
        mock_handler.process_audio.return_value = (True, "transcribed text", None)
        mock_get_handler.return_value = mock_handler
        
        result = process_audio(audio_content, model_handler)
        
        assert result == (True, "transcribed text", None)
        mock_handler.process_audio.assert_called_once_with(audio_content, model_handler)
    
    @patch('src.services.audio.get_audio_handler')
    def test_process_audio_failure(self, mock_get_handler):
        """測試音訊處理失敗"""
        audio_content = b"fake_audio_data"
        model_handler = Mock()
        
        # 模擬音訊處理器失敗
        mock_handler = Mock()
        mock_handler.process_audio.return_value = (False, "", "Processing failed")
        mock_get_handler.return_value = mock_handler
        
        result = process_audio(audio_content, model_handler)
        
        assert result == (False, "", "Processing failed")


class TestOptimizedAudioHandler:
    """測試優化音訊處理器"""
    
    def test_get_audio_handler_singleton(self):
        """測試音訊處理器單例模式"""
        handler1 = get_audio_handler()
        handler2 = get_audio_handler()
        
        assert handler1 is handler2  # 確保是同一個實例
    
    def test_audio_handler_stats(self):
        """測試音訊處理器統計功能"""
        handler = get_audio_handler()
        stats = handler.get_stats()
        
        assert isinstance(stats, dict)
        assert 'total_processed' in stats
        assert 'memory_processed' in stats
        assert 'file_processed' in stats
        assert 'cleanup_count' in stats
        assert 'average_processing_time' in stats


class TestAudioHandlerIntegration:
    """測試音訊處理器整合功能"""
    
    def test_audio_handler_process_audio(self):
        """測試音訊處理器的優化處理功能"""
        handler = get_audio_handler()
        mock_model = Mock()
        mock_model.transcribe_audio.return_value = (True, "transcribed text", None)
        
        # 測試檔案處理模式
        audio_content = b"fake_audio_data"
        success, text, error = handler.process_audio(audio_content, mock_model)
        
        assert success is True
        assert text == "transcribed text"
        assert error is None
    
    def test_audio_handler_memory_processing_capability(self):
        """測試音訊處理器記憶體處理能力檢查"""
        handler = get_audio_handler()
        
        # 測試不支援記憶體處理的模型
        mock_model_no_memory = Mock()
        del mock_model_no_memory.supports_memory_audio  # 確保屬性不存在
        assert handler._can_use_memory_processing(mock_model_no_memory) is False
        
        # 測試支援記憶體處理的模型
        mock_model_with_memory = Mock()
        mock_model_with_memory.supports_memory_audio = True
        assert handler._can_use_memory_processing(mock_model_with_memory) is True
    
    def test_audio_handler_stats_tracking(self):
        """測試音訊處理器統計追蹤"""
        handler = get_audio_handler()
        initial_stats = handler.get_stats()
        
        # 更新統計
        handler._update_stats(1.5, used_memory=True)
        updated_stats = handler.get_stats()
        
        assert updated_stats['total_processed'] == initial_stats['total_processed'] + 1
        assert updated_stats['memory_processed'] == initial_stats['memory_processed'] + 1
        assert updated_stats['average_processing_time'] > 0


class TestAudioServiceErrorHandling:
    """測試音訊服務錯誤處理"""
    
    @pytest.fixture
    def audio_service_with_failing_model(self):
        """創建有故障模型的音訊服務"""
        mock_model = Mock(spec=FullLLMInterface)
        mock_model.transcribe_audio.side_effect = Exception("Model failure")
        return AudioService(mock_model)
    
    def test_audio_service_model_failure_handling(self, audio_service_with_failing_model):
        """測試音訊服務模型故障處理"""
        user_id = "test_user_456"
        audio_content = b"test_audio"
        
        with patch('src.services.audio.process_audio', side_effect=Exception("Model failure")):
            result = audio_service_with_failing_model.handle_message(user_id, audio_content)
        
        assert result['success'] is False
        assert result['transcribed_text'] is None
        assert 'Model failure' in result['error_message']
    
    def test_audio_service_empty_transcription_handling(self):
        """測試音訊服務空轉錄處理"""
        mock_model = Mock(spec=FullLLMInterface)
        audio_service = AudioService(mock_model)
        
        # 模擬空轉錄結果
        with patch('src.services.audio.process_audio', return_value=(True, "", None)):
            result = audio_service.handle_message("test_user", b"audio_data")
            
            # 空轉錄應該被處理為失敗
            assert result['success'] is False
            assert result['transcribed_text'] is None
            assert "無法識別音訊內容" in result['error_message']


class TestAudioServicePlatformSupport:
    """測試音訊服務平台支援"""
    
    @pytest.fixture
    def audio_service(self):
        """創建音訊服務實例"""
        mock_model = Mock(spec=FullLLMInterface)
        return AudioService(mock_model)
    
    def test_different_platform_support(self, audio_service):
        """測試不同平台支援"""
        platforms = ['line', 'discord', 'telegram']
        
        for platform in platforms:
            with patch('src.services.audio.process_audio', return_value=(True, "test text", None)):
                result = audio_service.handle_message("test_user", b"audio", platform)
                
                assert result['success'] is True
                assert result['transcribed_text'] == "test text"


class TestAudioProcessingFunctions:
    """測試音訊處理相關函數"""
    
    @patch('src.services.audio.get_audio_handler')
    def test_process_audio_exception_handling(self, mock_get_handler):
        """測試音訊處理異常處理"""
        audio_content = b"test_audio_data"
        model_handler = Mock()
        
        # 模擬處理器拋出異常
        mock_handler = Mock()
        mock_handler.process_audio.side_effect = Exception("Processing error")
        mock_get_handler.return_value = mock_handler
        
        # process_audio 函數會直接調用處理器並傳播異常
        try:
            result = process_audio(audio_content, model_handler)
            assert False, "Expected exception to be raised"
        except Exception as e:
            assert "Processing error" in str(e)
    
    def test_audio_handler_memory_processing_edge_cases(self):
        """測試音訊處理器記憶體處理邊界情況"""
        handler = get_audio_handler()
        
        # 測試 None 模型
        assert handler._can_use_memory_processing(None) is False
        
        # 測試模型沒有 supports_memory_audio 屬性
        mock_model_no_attr = Mock()
        del mock_model_no_attr.supports_memory_audio
        assert handler._can_use_memory_processing(mock_model_no_attr) is False
        
        # 測試模型屬性為 False
        mock_model_false = Mock()
        mock_model_false.supports_memory_audio = False
        assert handler._can_use_memory_processing(mock_model_false) is False
        
        # 測試模型屬性為 True
        mock_model_true = Mock()
        mock_model_true.supports_memory_audio = True
        assert handler._can_use_memory_processing(mock_model_true) is True
    
    def test_audio_handler_schedule_cleanup(self):
        """測試音訊處理器檔案排程清理功能"""
        handler = get_audio_handler()
        
        # 測試排程清理方法
        test_file_path = "/tmp/test_audio.wav"
        handler._schedule_cleanup(test_file_path)
        
        # 驗證檔案被加入清理佇列（由於是異步的，我們檢查內部狀態）
        assert hasattr(handler, 'temp_files_to_cleanup')
    
    def test_audio_handler_stats_tracking(self):
        """測試音訊處理器統計追蹤"""
        handler = get_audio_handler()
        initial_stats = handler.get_stats()
        
        # 更新統計
        handler._update_stats(1.5, used_memory=True)
        updated_stats = handler.get_stats()
        
        assert updated_stats['total_processed'] >= initial_stats['total_processed']
        assert updated_stats['memory_processed'] >= initial_stats['memory_processed']
    
    def test_audio_handler_memory_usage_calculation(self):
        """測試音訊處理器記憶體使用率計算"""
        handler = get_audio_handler()
        
        # 測試記憶體使用率方法
        memory_percent = handler.get_memory_usage_percent()
        
        # 應該回傳一個介於 0-100 之間的數值
        assert isinstance(memory_percent, float)
        assert 0 <= memory_percent <= 100


class TestAudioServiceEdgeCases:
    """測試音訊服務邊界情況"""
    
    @pytest.fixture
    def audio_service(self):
        """創建音訊服務實例"""
        mock_model = Mock(spec=FullLLMInterface)
        return AudioService(mock_model)
    
    def test_handle_message_with_none_audio_content(self, audio_service):
        """測試處理 None 音訊內容"""
        with patch('src.services.audio.process_audio', side_effect=TypeError("a bytes-like object is required, not 'NoneType'")):
            result = audio_service.handle_message("test_user", None, "line")
            
            assert result['success'] is False
            assert result['transcribed_text'] is None
            assert "a bytes-like object is required" in result['error_message']
    
    def test_handle_message_with_empty_audio_content(self, audio_service):
        """測試處理空音訊內容"""
        with patch('src.services.audio.process_audio', return_value=(True, "", None)):
            result = audio_service.handle_message("test_user", b"", "line")
            
            # 空轉錄應該被處理為失敗
            assert result['success'] is False
            assert result['transcribed_text'] is None
            assert "無法識別音訊內容" in result['error_message']
    
    def test_handle_message_with_invalid_user_id(self, audio_service):
        """測試處理無效用戶 ID"""
        with patch('src.services.audio.process_audio', return_value=(True, "test", None)):
            result = audio_service.handle_message("", b"audio_data", "line")
            
            # 應該仍然正常處理
            assert result['success'] is True
            assert result['transcribed_text'] == "test"
    
    def test_handle_message_logging_with_long_transcription(self, audio_service):
        """測試長轉錄文字的日誌記錄"""
        long_text = "A" * 100  # 超過 50 字符的文字
        
        with patch('src.services.audio.process_audio', return_value=(True, long_text, None)), \
             patch('src.services.audio.logger') as mock_logger:
            
            result = audio_service.handle_message("test_user", b"audio_data", "line")
            
            # 驗證日誌記錄被截斷
            assert result['success'] is True
            mock_logger.info.assert_called_once()
            log_message = mock_logger.info.call_args[0][0]
            assert "..." in log_message  # 確認有截斷標記
    
    def test_handle_message_with_whitespace_only_transcription(self, audio_service):
        """測試只有空白字符的轉錄結果"""
        with patch('src.services.audio.process_audio', return_value=(True, "   \n\t  ", None)):
            result = audio_service.handle_message("test_user", b"audio_data", "line")
            
            # 空白字符應該被處理為失敗
            assert result['success'] is False
            assert result['transcribed_text'] is None
            assert "無法識別音訊內容" in result['error_message']
    
    def test_handle_message_error_handler_integration(self, audio_service):
        """測試錯誤處理器整合"""
        mock_error = Exception("Test error")
        
        with patch('src.services.audio.process_audio', side_effect=mock_error):
            result = audio_service.handle_message("test_user", b"audio_data", "line")
            
            # 驗證錯誤被捕獲並處理
            assert result['success'] is False
            assert result['transcribed_text'] is None
            assert "Test error" in result['error_message']


class TestAudioPerformanceMonitoring:
    """測試音訊性能監控"""
    
    def test_performance_monitor_initialization(self):
        """測試性能監控器初始化"""
        monitor = AudioPerformanceMonitor()
        summary = monitor.get_performance_summary()
        
        assert 'uptime_seconds' in summary
        assert 'total_audio_processed' in summary
        assert 'memory_processing_rate' in summary
        assert 'average_processing_time' in summary
        assert 'cleanup_efficiency' in summary
    
    def test_audio_stats_global_functions(self):
        """測試全域音訊統計函數"""
        stats = get_audio_stats()
        performance = get_audio_performance_summary()
        
        assert isinstance(stats, dict)
        assert isinstance(performance, dict)
        assert 'total_processed' in stats
        assert 'uptime_seconds' in performance


if __name__ == "__main__":
    pytest.main([__file__])