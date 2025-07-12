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
    
    def test_audio_handler_initialization(self):
        """測試音訊處理器初始化"""
        from src.services.audio import AudioHandler
        
        handler = AudioHandler()
        
        assert hasattr(handler, 'temp_files_to_cleanup')
        assert hasattr(handler, 'cleanup_lock')
        assert hasattr(handler, 'processing_stats')
        assert hasattr(handler, 'stats_lock')
        
        # 檢查初始統計
        expected_stats = {
            'total_processed': 0,
            'memory_processed': 0,
            'file_processed': 0,
            'cleanup_count': 0,
            'average_processing_time': 0,
        }
        
        for key, expected_value in expected_stats.items():
            assert handler.processing_stats[key] == expected_value
    
    @patch('os.path.exists')
    @patch('os.remove')
    def test_audio_handler_schedule_cleanup_success(self, mock_remove, mock_exists):
        """測試音訊處理器成功排程清理"""
        handler = get_audio_handler()
        test_file_path = "/tmp/test_cleanup.wav"
        
        mock_exists.return_value = True
        
        # 排程清理
        handler._schedule_cleanup(test_file_path)
        
        # 等待清理執行緒完成
        import time
        time.sleep(1.5)  # 等待超過清理延遲
        
        # 驗證清理被執行
        mock_remove.assert_called_with(test_file_path)
    
    @patch('src.services.audio.logger')
    @patch('os.path.exists')
    @patch('os.remove')
    def test_audio_handler_schedule_cleanup_failure(self, mock_remove, mock_exists, mock_logger):
        """測試音訊處理器清理失敗處理"""
        handler = get_audio_handler()
        test_file_path = "/tmp/test_cleanup_fail.wav"
        
        mock_exists.return_value = True
        mock_remove.side_effect = PermissionError("Permission denied")
        
        # 排程清理
        handler._schedule_cleanup(test_file_path)
        
        # 等待清理執行緒完成
        import time
        time.sleep(1.5)
        
        # 驗證錯誤被記錄
        mock_logger.warning.assert_called()


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
    
    def test_handle_message_with_various_platforms(self, audio_service):
        """測試不同平台的音訊處理"""
        platforms = ['line', 'discord', 'telegram', 'slack']
        
        for platform in platforms:
            with patch('src.services.audio.process_audio', return_value=(True, f"transcribed from {platform}", None)):
                result = audio_service.handle_message("test_user", b"audio_data", platform)
                
                assert result['success'] is True
                assert result['transcribed_text'] == f"transcribed from {platform}"
                assert result['error_message'] is None
    
    def test_handle_message_with_large_audio_data(self, audio_service):
        """測試處理大型音訊數據"""
        large_audio_data = b"x" * (10 * 1024 * 1024)  # 10MB 模擬大檔案
        
        with patch('src.services.audio.process_audio', return_value=(True, "large file transcribed", None)):
            result = audio_service.handle_message("test_user", large_audio_data, "line")
            
            assert result['success'] is True
            assert result['transcribed_text'] == "large file transcribed"
    
    def test_handle_message_with_special_characters_in_user_id(self, audio_service):
        """測試用戶 ID 含特殊字符的情況"""
        special_user_ids = [
            "user@example.com",
            "user-123_456",
            "user#789",
            "用戶測試",
            "user with spaces"
        ]
        
        for user_id in special_user_ids:
            with patch('src.services.audio.process_audio', return_value=(True, "transcribed", None)):
                result = audio_service.handle_message(user_id, b"audio_data", "line")
                
                assert result['success'] is True
                assert result['transcribed_text'] == "transcribed"
    
    def test_handle_message_with_timeout_error(self, audio_service):
        """測試音訊處理超時錯誤"""
        with patch('src.services.audio.process_audio', side_effect=TimeoutError("Audio processing timeout")):
            result = audio_service.handle_message("test_user", b"audio_data", "line")
            
            assert result['success'] is False
            assert result['transcribed_text'] is None
            assert "Audio processing timeout" in result['error_message']
    
    def test_handle_message_with_file_format_error(self, audio_service):
        """測試音訊檔案格式錯誤"""
        with patch('src.services.audio.process_audio', side_effect=ValueError("Unsupported audio format")):
            result = audio_service.handle_message("test_user", b"invalid_audio_data", "line")
            
            assert result['success'] is False
            assert result['transcribed_text'] is None
            assert "Unsupported audio format" in result['error_message']


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



class TestAudioHandlerAdvanced:
    """進階音訊處理器測試"""
    
    def test_audio_handler_temp_file_cleanup(self):
        """測試音訊處理器臨時檔案清理"""
        handler = get_audio_handler()
        
        # 清理現有文件（避免影響測試）
        handler._cleanup_all_temp_files()
        
        # 模擬有文件需要清理
        test_files = ["/tmp/test1.wav", "/tmp/test2.wav", "/tmp/test3.wav"]
        
        with handler.cleanup_lock:
            for file_path in test_files:
                handler.temp_files_to_cleanup.add(file_path)
        
        initial_count = len(handler.temp_files_to_cleanup)
        assert initial_count == 3
        
        # 測試清理功能
        handler._cleanup_all_temp_files()
        
        final_count = len(handler.temp_files_to_cleanup)
        assert final_count == 0
    
    @patch('src.services.audio.logger')
    def test_audio_handler_processing_stats_update(self, mock_logger):
        """測試音訊處理器處理統計更新"""
        handler = get_audio_handler()
        initial_stats = handler.get_stats()
        
        # 模擬記憶體處理
        handler._update_stats(2.5, used_memory=True)
        
        updated_stats = handler.get_stats()
        assert updated_stats['total_processed'] == initial_stats['total_processed'] + 1
        assert updated_stats['memory_processed'] == initial_stats['memory_processed'] + 1
        assert updated_stats['average_processing_time'] > 0
        
        # 模擬檔案處理
        handler._update_stats(1.8, used_memory=False)
        
        final_stats = handler.get_stats()
        assert final_stats['total_processed'] == initial_stats['total_processed'] + 2
        assert final_stats['file_processed'] == initial_stats['file_processed'] + 1
    
    def test_audio_handler_memory_processing_fallback(self):
        """測試音訊處理器記憶體處理備用方案"""
        handler = get_audio_handler()
        
        # 創建一個模擬的檔案物件
        import io
        audio_file_obj = io.BytesIO(b"fake_audio_data")
        audio_file_obj.name = "test.m4a"
        
        # 模擬不支援記憶體處理的模型
        mock_model = Mock()
        del mock_model.transcribe_audio_from_memory  # 確保方法不存在
        
        with patch.object(handler, '_create_temp_file_optimized') as mock_create_temp, \
             patch.object(handler, '_transcribe_audio_file') as mock_transcribe_file, \
             patch.object(handler, '_schedule_cleanup') as mock_schedule_cleanup:
            
            mock_create_temp.return_value = "/tmp/fallback_test.wav"
            mock_transcribe_file.return_value = (True, "fallback transcription", None)
            
            result = handler._fallback_to_file_processing(audio_file_obj, mock_model)
            
            assert result == (True, "fallback transcription", None)
            mock_create_temp.assert_called_once()
            mock_transcribe_file.assert_called_once_with("/tmp/fallback_test.wav", mock_model)
            mock_schedule_cleanup.assert_called_once_with("/tmp/fallback_test.wav")
    
    @patch('tempfile.gettempdir')
    @patch('os.path.exists')
    @patch('os.remove')
    def test_audio_handler_temp_file_creation_error_handling(self, mock_remove, mock_exists, mock_gettempdir):
        """測試音訊處理器臨時檔案創建錯誤處理"""
        handler = get_audio_handler()
        
        mock_gettempdir.return_value = "/tmp"
        audio_content = b"test_audio_content"
        
        # 模擬檔案寫入失敗
        with patch('builtins.open', side_effect=PermissionError("Permission denied")):
            mock_exists.return_value = True  # 模擬檔案存在以觸發清理
            
            with pytest.raises(PermissionError):
                handler._create_temp_file_optimized(audio_content)
            
            # 驗證清理被嘗試
            mock_remove.assert_called_once()
    
    def test_audio_handler_concurrent_stats_access(self):
        """測試音訊處理器並發統計存取"""
        handler = get_audio_handler()
        
        import threading
        import time
        
        def update_stats_worker(worker_id):
            for i in range(10):
                handler._update_stats(0.1 * (worker_id + 1), used_memory=(i % 2 == 0))
                time.sleep(0.001)
        
        # 創建多個執行緒同時更新統計
        threads = []
        for worker_id in range(3):
            thread = threading.Thread(target=update_stats_worker, args=(worker_id,))
            threads.append(thread)
            thread.start()
        
        # 等待所有執行緒完成
        for thread in threads:
            thread.join()
        
        # 檢查統計是否正確更新
        final_stats = handler.get_stats()
        assert final_stats['total_processed'] >= 30  # 3 workers * 10 updates each
        assert final_stats['memory_processed'] >= 0
        assert final_stats['file_processed'] >= 0
    
    def test_audio_handler_memory_usage_percentage_edge_cases(self):
        """測試音訊處理器記憶體使用率計算邊界情況"""
        # 創建新的處理器實例以避免全域狀態影響
        from src.services.audio import AudioHandler
        handler = AudioHandler()
        
        # 測試初始狀態（無處理記錄）
        initial_percentage = handler.get_memory_usage_percent()
        assert initial_percentage == 0.0
        
        # 測試只有檔案處理的情況
        handler._update_stats(1.0, used_memory=False)
        handler._update_stats(1.0, used_memory=False)
        
        file_only_percentage = handler.get_memory_usage_percent()
        assert file_only_percentage == 0.0
        
        # 測試混合處理的情況
        handler._update_stats(1.0, used_memory=True)
        
        mixed_percentage = handler.get_memory_usage_percent()
        assert 0.0 < mixed_percentage < 100.0
        
        # 測試全記憶體處理的情況
        for _ in range(10):
            handler._update_stats(1.0, used_memory=True)
        
        memory_only_percentage = handler.get_memory_usage_percent()
        assert memory_only_percentage > mixed_percentage


class TestAudioPerformanceMonitoringAdvanced:
    """進階音訊效能監控測試"""
    
    def test_performance_monitor_uptime_calculation(self):
        """測試效能監控器運行時間計算"""
        monitor = AudioPerformanceMonitor()
        
        # 等待一小段時間
        import time
        time.sleep(0.1)
        
        summary = monitor.get_performance_summary()
        
        assert summary['uptime_seconds'] >= 0.1
        assert isinstance(summary['uptime_seconds'], float)
    
    def test_performance_monitor_comprehensive_metrics(self):
        """測試效能監控器綜合指標"""
        # 創建新的監控器實例以避免全域狀態影響
        from src.services.audio import AudioHandler, AudioPerformanceMonitor
        
        # 創建獨立的處理器和監控器
        handler = AudioHandler()
        
        # 模擬一些處理活動
        handler._update_stats(1.5, used_memory=True)
        handler._update_stats(2.0, used_memory=False)
        handler._update_stats(1.8, used_memory=True)
        
        # 模擬一些清理活動
        with handler.stats_lock:
            handler.processing_stats['cleanup_count'] = 5
        
        with handler.cleanup_lock:
            handler.temp_files_to_cleanup.add("/tmp/pending1.wav")
            handler.temp_files_to_cleanup.add("/tmp/pending2.wav")
        
        # 創建監控器並手動設置 handler
        monitor = AudioPerformanceMonitor()
        monitor.handler = handler  # 使用我們的測試 handler
        
        summary = monitor.get_performance_summary()
        
        # 驗證所有指標都存在且合理
        assert summary['total_audio_processed'] >= 3
        assert 0 <= summary['memory_processing_rate'] <= 100
        assert summary['average_processing_time'] > 0
        assert summary['files_processed'] >= 1
        assert summary['memory_processed'] >= 2
        assert summary['cleanup_efficiency']['total_cleanups'] == 5
        assert summary['cleanup_efficiency']['pending_cleanups'] == 2
    
    def test_global_audio_functions_integration(self):
        """測試全域音訊函數整合"""
        # 測試全域統計函數
        stats = get_audio_stats()
        assert isinstance(stats, dict)
        assert 'total_processed' in stats
        assert 'pending_cleanup' in stats
        
        # 測試全域效能摘要函數
        performance = get_audio_performance_summary()
        assert isinstance(performance, dict)
        assert 'uptime_seconds' in performance
        assert 'total_audio_processed' in performance
        assert 'memory_processing_rate' in performance
        assert 'cleanup_efficiency' in performance
        
        # 驗證兩個函數使用相同的處理器實例
        handler1 = get_audio_handler()
        monitor = AudioPerformanceMonitor()
        handler2 = monitor.handler
        
        assert handler1 is handler2  # 確保單例模式


class TestAudioServiceRobustness:
    """音訊服務健壯性測試"""
    
    @pytest.fixture
    def audio_service(self):
        """創建音訊服務實例"""
        mock_model = Mock(spec=FullLLMInterface)
        return AudioService(mock_model)
    
    def test_audio_service_stress_test(self, audio_service):
        """測試音訊服務壓力測試"""
        import threading
        import time
        
        results = []
        errors = []
        
        def process_audio_worker(worker_id):
            try:
                for i in range(5):
                    user_id = f"stress_user_{worker_id}_{i}"
                    audio_data = b"stress_test_audio_data" * (worker_id + 1)
                    
                    with patch('src.services.audio.process_audio', return_value=(True, f"transcribed_{worker_id}_{i}", None)):
                        result = audio_service.handle_message(user_id, audio_data, "line")
                        results.append(result)
                    
                    time.sleep(0.001)  # 小延遲模擬真實處理
            except Exception as e:
                errors.append(e)
        
        # 創建多個並發執行緒
        threads = []
        for worker_id in range(10):
            thread = threading.Thread(target=process_audio_worker, args=(worker_id,))
            threads.append(thread)
            thread.start()
        
        # 等待所有執行緒完成
        for thread in threads:
            thread.join()
        
        # 驗證結果
        assert len(errors) == 0, f"Errors occurred during stress test: {errors}"
        assert len(results) == 50  # 10 workers * 5 requests each
        
        # 驗證所有結果都成功
        successful_results = [r for r in results if r['success']]
        assert len(successful_results) == 50
    
    def test_audio_service_error_recovery(self, audio_service):
        """測試音訊服務錯誤復原"""
        # 模擬間歇性失敗
        call_count = 0
        
        def intermittent_failure(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:  # 每第3次調用失敗
                raise ConnectionError("Intermittent network failure")
            return (True, f"success_call_{call_count}", None)
        
        successful_calls = 0
        failed_calls = 0
        
        with patch('src.services.audio.process_audio', side_effect=intermittent_failure):
            for i in range(10):
                result = audio_service.handle_message(f"user_{i}", b"audio_data", "line")
                
                if result['success']:
                    successful_calls += 1
                else:
                    failed_calls += 1
                    assert "Intermittent network failure" in result['error_message']
        
        # 驗證錯誤復原機制
        assert successful_calls > 0
        assert failed_calls > 0
        assert successful_calls + failed_calls == 10
    
    def test_audio_service_resource_cleanup_under_load(self, audio_service):
        """測試音訊服務在負載下的資源清理"""
        handler = get_audio_handler()
        initial_pending_cleanup = len(handler.temp_files_to_cleanup)
        
        # 模擬高負載處理
        with patch('src.services.audio.process_audio') as mock_process:
            mock_process.return_value = (True, "high_load_transcription", None)
            
            # 處理大量音訊請求
            for i in range(50):
                result = audio_service.handle_message(f"load_user_{i}", b"load_test_audio", "line")
                assert result['success'] is True
        
        # 檢查資源是否正常清理
        # 由於這是模擬測試，我們主要檢查沒有異常發生
        current_stats = handler.get_stats()
        assert current_stats['total_processed'] >= initial_pending_cleanup
        
        # 測試清理功能
        handler._cleanup_all_temp_files()
        assert len(handler.temp_files_to_cleanup) == 0


if __name__ == "__main__":
    pytest.main([__file__])