"""
測試記憶體監控模組的單元測試
"""
import pytest
import time
from unittest.mock import Mock, patch

from src.core.memory_monitor import MemoryMonitor, SmartGarbageCollector, get_memory_monitor, get_smart_gc, setup_memory_monitoring


class TestMemoryMonitor:
    """測試 MemoryMonitor 的功能"""

    @patch('src.core.memory_monitor.logger')
    @patch('psutil.virtual_memory')
    @patch('psutil.Process')
    def test_check_memory_usage_normal(self, mock_process, mock_virtual_memory, mock_logger):
        mock_process.return_value.memory_percent.return_value = 1.0
        mock_process.return_value.memory_info.return_value.rss = 100 * 1024 * 1024 # 100MB
        mock_virtual_memory.return_value.percent = 10.0
        mock_virtual_memory.return_value.available = 10 * (1024**3) # 10GB
        mock_virtual_memory.return_value.total = 16 * (1024**3) # 16GB
        monitor = MemoryMonitor(warning_threshold=0.02, critical_threshold=0.04)
        assert monitor.check_memory_usage() is True
        mock_logger.info.assert_called_once()

    @patch('src.core.memory_monitor.logger')
    @patch('psutil.virtual_memory')
    @patch('psutil.Process')
    def test_check_memory_usage_warning(self, mock_process, mock_virtual_memory, mock_logger):
        mock_process.return_value.memory_percent.return_value = 2.0  # 2% of system memory
        mock_process.return_value.memory_info.return_value.rss = 200 * 1024 * 1024 # 200MB
        mock_virtual_memory.return_value.percent = 20.0
        mock_virtual_memory.return_value.available = 8 * (1024**3)
        mock_virtual_memory.return_value.total = 16 * (1024**3)
        monitor = MemoryMonitor(warning_threshold=0.02, critical_threshold=0.04)
        monitor.check_memory_usage()
        mock_logger.warning.assert_called_once()

    @patch('src.core.memory_monitor.logger')
    @patch('psutil.virtual_memory')
    @patch('psutil.Process')
    def test_check_memory_usage_critical(self, mock_process, mock_virtual_memory, mock_logger):
        mock_process.return_value.memory_percent.return_value = 4.0  # 4% of system memory
        mock_process.return_value.memory_info.return_value.rss = 400 * 1024 * 1024 # 400MB
        mock_virtual_memory.return_value.percent = 40.0
        mock_virtual_memory.return_value.available = 4 * (1024**3)
        mock_virtual_memory.return_value.total = 16 * (1024**3)
        monitor = MemoryMonitor(warning_threshold=0.02, critical_threshold=0.04)
        with patch.object(monitor, '_trigger_emergency_gc') as mock_gc:
            assert monitor.check_memory_usage() is False
            mock_gc.assert_called_once()
            mock_logger.critical.assert_called_once()


class TestSmartGarbageCollector:
    """測試 SmartGarbageCollector 的功能"""

    def test_should_run_gc_false_not_idle(self):
        collector = SmartGarbageCollector(idle_threshold=300, check_interval=600)
        collector.update_activity()
        assert collector.should_run_gc() is False

    def test_should_run_gc_false_not_time(self):
        collector = SmartGarbageCollector(idle_threshold=10, check_interval=600)
        time.sleep(0.1)
        assert collector.should_run_gc() is False

    def test_should_run_gc_true(self):
        collector = SmartGarbageCollector(idle_threshold=0.1, check_interval=0.1)
        time.sleep(0.2)
        assert collector.should_run_gc() is True

    @patch('gc.collect')
    def test_run_smart_gc(self, mock_collect):
        collector = SmartGarbageCollector(idle_threshold=0.1, check_interval=0.1)
        time.sleep(0.2)
        result = collector.run_smart_gc()
        assert result['executed'] is True
        mock_collect.assert_called_once()


class TestModuleFunctions:
    """測試模組級別的函數"""

    def test_get_memory_monitor_singleton(self):
        m1 = get_memory_monitor()
        m2 = get_memory_monitor()
        assert m1 is m2

    def test_get_smart_gc_singleton(self):
        gc1 = get_smart_gc()
        gc2 = get_smart_gc()
        assert gc1 is gc2

    def test_setup_memory_monitoring(self):
        mock_app = Mock()
        mock_app.before_request = Mock()
        mock_app.after_request = Mock()
        setup_memory_monitoring(mock_app)
        mock_app.before_request.assert_called_once()
        mock_app.after_request.assert_called_once()