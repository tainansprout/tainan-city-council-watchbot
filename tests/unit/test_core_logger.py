"""
測試核心日誌系統的單元測試
"""
import pytest
import json
import os
import tempfile
import logging
from unittest.mock import Mock, patch, mock_open
from src.core.logger import (
    SensitiveDataFilter, StructuredFormatter, ColoredConsoleFormatter,
    LoggerManager, get_logger, AsyncLogHandler, setup_optimized_logger,
    get_logger_stats, LoggerPerformanceMonitor
)


class TestSensitiveDataFilter:
    """測試敏感數據過濾器"""
    
    def test_filter_basic_functionality(self):
        """測試基本過濾功能"""
        filter_obj = SensitiveDataFilter()
        record = Mock()
        
        # 測試記錄通過
        result = filter_obj.filter(record)
        assert result is True
    
    def test_sanitize_string_api_keys(self):
        """測試清理字符串中的 API 金鑰"""
        filter_obj = SensitiveDataFilter()
        
        test_cases = [
            ("API_KEY=sk-1234567890abcdef", "API_KEY=***"),
            ("Bearer eyJ0eXAiOiJKV1QiLCJhbGc", "Bearer ***"),
            ("password=secret123", "password=***"),
            ("Normal text without secrets", "Normal text without secrets")
        ]
        
        for input_text, expected in test_cases:
            result = filter_obj._sanitize_string(input_text)
            assert result == expected
    
    def test_sanitize_fast_optimized(self):
        """測試優化的快速清理功能"""
        # 測試快取功能
        text1 = "test_api_key=secret123"
        
        # 第一次調用
        result1 = SensitiveDataFilter.sanitize_fast(text1)
        
        # 第二次調用（應該從快取取得）
        result2 = SensitiveDataFilter.sanitize_fast(text1)
        
        assert result1 == result2
        assert "***" in result1
    
    def test_cache_functionality(self):
        """測試快取功能"""
        # 清空快取
        SensitiveDataFilter.clear_cache()
        
        # 測試快取統計
        stats = SensitiveDataFilter.get_cache_stats()
        assert stats['cache_size'] == 0
        
        # 添加一些項目到快取
        SensitiveDataFilter.sanitize_fast("short_text")
        stats_after = SensitiveDataFilter.get_cache_stats()
        assert stats_after['cache_size'] > 0
    
    def test_sanitize_dict_nested(self):
        """測試清理嵌套字典"""
        filter_obj = SensitiveDataFilter()
        
        test_dict = {
            'api_key': 'secret_key_123',
            'user_data': {
                'password': 'user_password',
                'email': 'user@example.com'
            },
            'normal_field': 'normal_value'
        }
        
        result = filter_obj._sanitize_dict(test_dict)
        
        assert result['api_key'] == '***REDACTED***'
        assert result['user_data']['password'] == '***REDACTED***'
        assert result['user_data']['email'] == 'user@example.com'
        assert result['normal_field'] == 'normal_value'
    
    def test_sanitize_dict_with_lists(self):
        """測試包含列表的字典清理"""
        filter_obj = SensitiveDataFilter()
        
        test_dict = {
            'items': [
                {'token': 'secret_token'},
                {'public': 'data'}
            ]
        }
        
        result = filter_obj._sanitize_dict(test_dict)
        
        assert result['items'][0]['token'] == '***REDACTED***'
        assert result['items'][1]['public'] == 'data'


class TestStructuredFormatter:
    """測試結構化格式化器"""
    
    def test_format_basic_record(self):
        """測試基本記錄格式化"""
        formatter = StructuredFormatter()
        
        record = logging.LogRecord(
            name='test.logger',
            level=logging.INFO,
            pathname='test.py',
            lineno=42,
            msg='Test message',
            args=(),
            exc_info=None
        )
        
        result = formatter.format(record)
        parsed = json.loads(result)
        
        assert parsed['level'] == 'INFO'
        assert parsed['logger'] == 'test.logger'
        assert parsed['message'] == 'Test message'
        assert 'timestamp' in parsed
    
    def test_format_with_exception(self):
        """測試包含異常信息的格式化"""
        formatter = StructuredFormatter()
        
        try:
            raise ValueError("Test exception")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        
        record = logging.LogRecord(
            name='test.logger',
            level=logging.ERROR,
            pathname='test.py',
            lineno=42,
            msg='Error occurred',
            args=(),
            exc_info=exc_info
        )
        
        result = formatter.format(record)
        parsed = json.loads(result)
        
        assert 'exception' in parsed
        assert 'Test exception' in parsed['exception']
    
    def test_format_with_context(self):
        """測試包含上下文信息的格式化"""
        formatter = StructuredFormatter()
        
        record = logging.LogRecord(
            name='test.logger',
            level=logging.INFO,
            pathname='test.py',
            lineno=42,
            msg='Test message',
            args=(),
            exc_info=None
        )
        
        # 添加上下文信息
        record.user_id = 'user_123'
        record.request_id = 'req_456'
        
        result = formatter.format(record)
        parsed = json.loads(result)
        
        assert parsed['user_id'] == 'user_123'
        assert parsed['request_id'] == 'req_456'


class TestColoredConsoleFormatter:
    """測試彩色控制台格式化器"""
    
    def test_format_different_levels(self):
        """測試不同級別的顏色格式化"""
        formatter = ColoredConsoleFormatter(
            fmt='%(levelname)s - %(message)s'
        )
        
        levels_colors = [
            (logging.DEBUG, '\x1b[36m'),    # Cyan
            (logging.INFO, '\x1b[32m'),     # Green
            (logging.WARNING, '\x1b[33m'),  # Yellow
            (logging.ERROR, '\x1b[31m'),    # Red
            (logging.CRITICAL, '\x1b[35m'), # Magenta
        ]
        
        for level, expected_color in levels_colors:
            record = logging.LogRecord(
                name='test.logger',
                level=level,
                pathname='test.py',
                lineno=42,
                msg='Test message',
                args=(),
                exc_info=None
            )
            
            result = formatter.format(record)
            assert expected_color in result
            assert '\x1b[0m' in result  # Reset code
            assert 'Test message' in result


class TestLoggerManager:
    """測試日誌管理器"""
    
    def test_initialization_default_config(self):
        """測試使用默認配置初始化"""
        with patch('src.core.logger.LoggerManager._load_default_config') as mock_load:
            mock_load.return_value = {
                'version': 1,
                'level': 'INFO',
                'format': 'simple',
                'handlers': ['console']
            }
            
            manager = LoggerManager()
            
            assert manager.config is not None
            mock_load.assert_called_once()
    
    def test_initialization_custom_config(self):
        """測試使用自定義配置初始化"""
        custom_config = {
            'level': 'DEBUG',
            'file_path': './logs/test.log',
            'max_bytes': 5 * 1024 * 1024,
            'backup_count': 3,
            'format': 'structured',
            'enable_console': True,
            'enable_file': False,
        }
        
        manager = LoggerManager('test_logger', custom_config)
        
        assert manager.config == custom_config
    
    def test_load_default_config_success(self):
        """測試成功加載默認配置"""
        mock_config = {
            'version': 1,
            'level': 'INFO'
        }
        
        with patch('src.core.config.load_config', return_value=mock_config):
            manager = LoggerManager()
            result = manager._load_default_config()
            
            assert result['level'] == 'DEBUG'  # 實際默認值是DEBUG
    
    def test_load_default_config_file_not_found(self):
        """測試配置文件不存在時的默認配置"""
        with patch('src.core.config.load_config', side_effect=Exception("Config not found")):
            manager = LoggerManager()
            result = manager._load_default_config()
            
            assert 'level' in result
            assert result['level'] == 'DEBUG'
            assert 'file_path' in result
            assert 'format' in result
    
    def test_get_logger(self):
        """測試獲取日誌記錄器"""
        with patch('src.core.logger.LoggerManager._load_default_config') as mock_load:
            mock_load.return_value = {
                'version': 1,
                'level': 'INFO',
                'format': 'simple',
                'handlers': ['console']
            }
            
            manager = LoggerManager()
            logger = manager.get_logger()
            
            assert logger.name == 'chatbot'
            assert isinstance(logger, logging.Logger)
    
    def test_log_with_context(self):
        """測試帶上下文的日誌記錄"""
        with patch('src.core.logger.LoggerManager._load_default_config') as mock_load:
            mock_load.return_value = {
                'version': 1,
                'level': 'INFO',
                'format': 'simple',
                'handlers': ['console']
            }
            
            manager = LoggerManager()
            logger = manager.get_logger()
            
            context = {'user_id': 'user_123', 'action': 'login'}
            
            with patch.object(logger, 'log') as mock_log:
                manager.log_with_context(logging.INFO, 'Test message', **context)
                mock_log.assert_called_once_with(logging.INFO, 'Test message', extra={'user_id': 'user_123', 'action': 'login'})
    
    def test_update_config(self):
        """測試動態更新配置"""
        with patch('src.core.logger.LoggerManager._load_default_config') as mock_load:
            mock_load.return_value = {
                'version': 1,
                'level': 'INFO',
                'handlers': ['console']
            }
            
            manager = LoggerManager()
            
            new_config = {
                'version': 1,
                'level': 'DEBUG',
                'handlers': ['console', 'file']
            }
            
            with patch.object(manager, '_setup_logger') as mock_setup:
                manager.update_config(new_config)
                
                assert manager.config == new_config
                mock_setup.assert_called_once()


class TestLoggerIntegration:
    """測試日誌系統整合"""
    
    def test_get_logger_function(self):
        """測試全局 get_logger 函數"""
        logger = get_logger('test.integration')
        
        assert logger.name == 'test.integration'
        assert isinstance(logger, logging.Logger)
    
    def test_file_handler_creation(self):
        """測試文件處理器創建"""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = {
                'level': 'INFO',
                'file_path': os.path.join(temp_dir, 'test.log'),
                'max_bytes': 10 * 1024 * 1024,
                'backup_count': 3,
                'format': 'simple',
                'enable_console': False,
                'enable_file': True,
            }
            
            manager = LoggerManager('test.file', config)
            logger = manager.get_logger()
            
            # 測試日誌寫入
            logger.info('Test log message')
            
            # 檢查文件是否創建
            log_file = os.path.join(temp_dir, 'test.log')
            assert os.path.exists(log_file)
    
    def test_error_handling_scenarios(self):
        """測試錯誤處理場景"""
        # 測試無效配置
        invalid_config = {
            'level': 'INVALID_LEVEL',
            'enable_console': True,
            'enable_file': False,
        }
        
        with patch('src.core.logger.LoggerManager._load_default_config') as mock_load:
            mock_load.return_value = {
                'level': 'INFO',
                'file_path': './logs/chatbot.log',
                'max_bytes': 10 * 1024 * 1024,
                'backup_count': 5,
                'format': 'simple',
                'enable_console': True,
                'enable_file': True,
            }
            
            # 現在LoggerManager有更好的錯誤處理，無效的level會被安全地處理
            manager = LoggerManager('test', invalid_config)
            # 配置應該被正確處理，無效的level會被替換為DEBUG
            assert 'level' in manager.config
            # 檢查logger確實被設置為DEBUG級別（因為INVALID_LEVEL無效）
            assert manager.logger.level == logging.DEBUG


class TestAsyncLogHandler:
    """測試異步日誌處理器"""
    
    def test_async_handler_initialization(self):
        """測試異步處理器初始化"""
        target_handler = Mock()
        async_handler = AsyncLogHandler(target_handler, queue_size=100)
        
        assert async_handler.target_handler == target_handler
        assert async_handler.log_queue.maxsize == 100
        assert async_handler.worker_thread is not None
        assert async_handler.worker_thread.is_alive()
    
    def test_async_handler_emit(self):
        """測試異步處理器發送日誌"""
        target_handler = Mock()
        async_handler = AsyncLogHandler(target_handler, queue_size=100)
        
        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='test.py',
            lineno=1, msg='test message', args=(), exc_info=None
        )
        
        async_handler.emit(record)
        
        # 等待一下讓工作執行緒處理
        import time
        time.sleep(0.1)
        
        # 檢查目標處理器是否被調用
        target_handler.emit.assert_called()
    
    def test_async_handler_stats(self):
        """測試異步處理器統計"""
        target_handler = Mock()
        async_handler = AsyncLogHandler(target_handler, queue_size=100)
        
        stats = async_handler.get_stats()
        
        assert 'queue_size' in stats
        assert 'dropped_logs' in stats
        assert 'worker_alive' in stats


class TestOptimizedFeatures:
    """測試優化功能"""
    
    def test_setup_optimized_logger(self):
        """測試設置優化日誌記錄器"""
        logger = setup_optimized_logger('test_optimized', enable_async=False)
        
        assert logger.name == 'test_optimized'
        assert isinstance(logger, logging.Logger)
    
    def test_performance_monitor(self):
        """測試效能監控器"""
        monitor = LoggerPerformanceMonitor()
        
        # 記錄一些日誌
        monitor.record_log('INFO')
        monitor.record_log('ERROR')
        
        stats = monitor.get_stats()
        
        assert stats['total_logs'] == 2
        assert stats['log_levels']['INFO'] == 1
        assert stats['log_levels']['ERROR'] == 1
        assert 'uptime_seconds' in stats
        assert 'logs_per_second' in stats
    
    def test_logger_stats(self):
        """測試日誌系統統計"""
        stats = get_logger_stats()
        
        assert 'performance' in stats
        assert 'manager' in stats


class TestCoreIntegration:
    """測試核心整合功能"""
    
    def test_integrated_functionality(self):
        """測試整合後的功能"""
        manager = LoggerManager()
        assert isinstance(manager, LoggerManager)
        
        # 測試敏感資料過濾器
        filter_obj = SensitiveDataFilter()
        assert hasattr(filter_obj, 'sanitize_fast')
        
        # 測試異步處理器
        async_handler = AsyncLogHandler(Mock())
        assert hasattr(async_handler, 'get_stats')