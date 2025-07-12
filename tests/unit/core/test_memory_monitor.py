"""
測試記憶體監控模組的單元測試
"""
import pytest
import time
from unittest.mock import Mock, patch

from src.core.memory_monitor import MemoryMonitor, SmartGarbageCollector, get_memory_monitor, get_smart_gc, setup_memory_monitoring


class TestMemoryMonitor:
    """測試 MemoryMonitor 的功能"""
    
    def test_initialization(self):
        """測試 MemoryMonitor 初始化"""
        monitor = MemoryMonitor(warning_threshold=2.5, critical_threshold=5.0)
        assert monitor.warning_threshold == 2.5
        assert monitor.critical_threshold == 5.0
        assert monitor.warning_count == 0
        assert monitor.critical_count == 0
        assert monitor.gc_trigger_count == 0
        assert monitor.last_check_time > 0
    
    def test_initialization_default_values(self):
        """測試 MemoryMonitor 預設初始化值"""
        monitor = MemoryMonitor()
        assert monitor.warning_threshold == 2.0
        assert monitor.critical_threshold == 4.0

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
    
    @patch('psutil.Process')
    def test_get_memory_stats_success(self, mock_process):
        """測試成功取得記憶體統計"""
        mock_memory_info = Mock()
        mock_memory_info.rss = 100 * 1024 * 1024
        mock_memory_info.vms = 200 * 1024 * 1024
        mock_memory_info.shared = 10 * 1024 * 1024
        mock_memory_info.text = 5 * 1024 * 1024
        mock_memory_info.lib = 3 * 1024 * 1024
        mock_memory_info.data = 15 * 1024 * 1024
        mock_memory_info.dirty = 2 * 1024 * 1024
        
        mock_process.return_value.memory_info.return_value = mock_memory_info
        mock_process.return_value.memory_percent.return_value = 1.5
        
        with patch('psutil.virtual_memory') as mock_virtual_memory:
            mock_virtual_memory.return_value.percent = 15.0
            mock_virtual_memory.return_value.available = 8 * (1024**3)
            mock_virtual_memory.return_value.total = 16 * (1024**3)
            
            monitor = MemoryMonitor()
            stats = monitor.get_memory_stats()
            
            assert 'process_memory_mb' in stats
            assert 'process_memory_percent' in stats
            assert 'system_memory_percent' in stats
            assert 'available_memory_gb' in stats
            assert 'total_memory_gb' in stats
            assert 'timestamp' in stats
            assert 'memory_info' in stats
            assert 'monitor_stats' in stats
            assert stats['process_memory_mb'] == 100.0
            assert stats['process_memory_percent'] == 1.5
            assert stats['system_memory_percent'] == 15.0
    
    @patch('src.core.memory_monitor.logger')
    @patch('psutil.Process')
    def test_get_memory_stats_error(self, mock_process, mock_logger):
        """測試記憶體統計取得錯誤"""
        mock_process.side_effect = Exception("Process error")
        
        monitor = MemoryMonitor()
        stats = monitor.get_memory_stats()
        
        assert 'error' in stats
        assert 'timestamp' in stats
        assert stats['error'] == "Process error"
        mock_logger.error.assert_called_once()
    
    @patch('src.core.memory_monitor.logger')
    @patch('psutil.Process')
    def test_check_memory_usage_with_error(self, mock_process, mock_logger):
        """測試記憶體檢查出錯時的處理"""
        mock_process.side_effect = Exception("Memory check error")
        
        monitor = MemoryMonitor()
        result = monitor.check_memory_usage()
        
        assert result is True  # 出錯時假設正常
        mock_logger.error.assert_called_with("Error getting memory stats: Memory check error")
    
    @patch('src.core.memory_monitor.logger')
    @patch('gc.collect')
    @patch('psutil.Process')
    def test_trigger_emergency_gc(self, mock_process, mock_gc_collect, mock_logger):
        """測試緊急垃圾回收"""
        # 設置前後記憶體使用
        mock_memory_info_before = Mock()
        mock_memory_info_before.rss = 200 * 1024 * 1024  # 200MB
        
        mock_memory_info_after = Mock()
        mock_memory_info_after.rss = 180 * 1024 * 1024  # 180MB
        
        mock_process.return_value.memory_info.side_effect = [mock_memory_info_before, mock_memory_info_after]
        mock_gc_collect.return_value = 1500  # 收集的對象數量
        
        monitor = MemoryMonitor()
        monitor._trigger_emergency_gc()
        
        assert monitor.gc_trigger_count == 1
        mock_gc_collect.assert_called_once()
        mock_logger.warning.assert_called_once()
        
        # 檢查日誌內容
        log_args = mock_logger.warning.call_args[0][0]
        assert "Emergency GC" in log_args
        assert "collected 1500 objects" in log_args
        assert "freed 20.0MB" in log_args
    
    @patch('src.core.memory_monitor.logger')
    @patch('gc.collect')
    def test_trigger_gentle_gc(self, mock_gc_collect, mock_logger):
        """測試溫和垃圾回收"""
        mock_gc_collect.return_value = 500
        
        monitor = MemoryMonitor()
        monitor._trigger_gentle_gc()
        
        mock_gc_collect.assert_called_once()
        # 檢查包含特定調用
        mock_logger.info.assert_any_call("🧹 Gentle GC: collected 500 objects")
    
    @patch('src.core.memory_monitor.logger')
    @patch('gc.collect')
    @patch('psutil.Process')
    def test_trigger_emergency_gc_error(self, mock_process, mock_gc_collect, mock_logger):
        """測試緊急垃圾回收錯誤處理"""
        mock_process.side_effect = Exception("Memory info error")
        
        monitor = MemoryMonitor()
        monitor._trigger_emergency_gc()
        
        mock_logger.error.assert_called_once_with("Error in emergency GC: Memory info error")
    
    def test_get_cache_stats(self):
        """測試快取統計取得"""
        monitor = MemoryMonitor()
        cache_stats = monitor.get_cache_stats()
        
        assert isinstance(cache_stats, dict)
        # 應該包含 cache_types_available 或 import_error
        assert 'cache_types_available' in cache_stats or 'import_error' in cache_stats
    
    def test_get_detailed_report(self):
        """測試詳細報告取得"""
        with patch.object(MemoryMonitor, 'get_memory_stats') as mock_memory_stats, \
             patch.object(MemoryMonitor, 'get_cache_stats') as mock_cache_stats:
            
            mock_memory_stats.return_value = {'memory': 'stats'}
            mock_cache_stats.return_value = {'cache': 'stats'}
            
            monitor = MemoryMonitor(warning_threshold=2.0, critical_threshold=4.0)
            report = monitor.get_detailed_report()
            
            assert 'memory' in report
            assert 'cache' in report
            assert 'thresholds' in report
            assert 'report_time' in report
            assert report['thresholds']['warning'] == 2.0
            assert report['thresholds']['critical'] == 4.0
    
    @patch('src.core.memory_monitor.logger')
    @patch('psutil.virtual_memory')
    @patch('psutil.Process')
    def test_warning_trigger_gentle_gc(self, mock_process, mock_virtual_memory, mock_logger):
        """測試警告觸發溫和垃圾回收"""
        mock_process.return_value.memory_percent.return_value = 2.5  # 觸發警告
        mock_process.return_value.memory_info.return_value.rss = 250 * 1024 * 1024
        mock_virtual_memory.return_value.percent = 25.0
        mock_virtual_memory.return_value.available = 6 * (1024**3)
        mock_virtual_memory.return_value.total = 16 * (1024**3)
        
        monitor = MemoryMonitor(warning_threshold=0.02, critical_threshold=0.04)
        
        with patch.object(monitor, '_trigger_gentle_gc') as mock_gentle_gc:
            # 觸發5次警告以觸發 GC
            for i in range(5):
                monitor.check_memory_usage()
            
            # 第5次警告應該觸發溫和垃圾回收
            mock_gentle_gc.assert_called_once()
    
    @patch('src.core.memory_monitor.logger')
    @patch('psutil.virtual_memory')
    @patch('psutil.Process')
    def test_memory_normalization_logging(self, mock_process, mock_virtual_memory, mock_logger):
        """測試記憶體正常化日誌記錄"""
        monitor = MemoryMonitor(warning_threshold=0.02, critical_threshold=0.04)
        
        # 先觸發警告
        mock_process.return_value.memory_percent.return_value = 2.5
        mock_process.return_value.memory_info.return_value.rss = 250 * 1024 * 1024
        mock_virtual_memory.return_value.percent = 25.0
        mock_virtual_memory.return_value.available = 6 * (1024**3)
        mock_virtual_memory.return_value.total = 16 * (1024**3)
        
        monitor.check_memory_usage()  # 觸發警告
        assert monitor.warning_count > 0
        
        # 然後記憶體恢復正常
        mock_process.return_value.memory_percent.return_value = 1.0
        mock_process.return_value.memory_info.return_value.rss = 100 * 1024 * 1024
        mock_virtual_memory.return_value.percent = 10.0
        
        with patch('src.core.memory_monitor.logger') as mock_normalized_logger:
            monitor.check_memory_usage()  # 記憶體正常化
            mock_normalized_logger.info.assert_called_once()
            log_args = mock_normalized_logger.info.call_args[0][0]
            assert "Memory usage normalized" in log_args


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


class TestSmartGarbageCollectorAdvanced:
    """進階智慧垃圾回收測試"""
    
    def test_initialization(self):
        """測試 SmartGarbageCollector 初始化"""
        collector = SmartGarbageCollector(idle_threshold=600, check_interval=1200)
        assert collector.idle_threshold == 600
        assert collector.check_interval == 1200
        assert collector.gc_runs == 0
        assert collector.total_collected == 0
        assert collector.last_activity_time > 0
        assert collector.last_gc_time > 0
    
    def test_initialization_default_values(self):
        """測試 SmartGarbageCollector 預設初始化值"""
        collector = SmartGarbageCollector()
        assert collector.idle_threshold == 300  # 5分鐘
        assert collector.check_interval == 1800  # 30分鐘
    
    def test_update_activity(self):
        """測試活動時間更新"""
        collector = SmartGarbageCollector()
        old_time = collector.last_activity_time
        time.sleep(0.01)
        collector.update_activity()
        assert collector.last_activity_time > old_time
    
    def test_should_run_gc_conditions_not_met(self):
        """測試不滿足條件時的 GC 判斷"""
        collector = SmartGarbageCollector(idle_threshold=300, check_interval=1800)
        
        # 剛初始化，不滿足時間間隔
        assert collector.should_run_gc() is False
        
        # 更新活動時間，不滿足空閑時間
        collector.last_gc_time = time.time() - 2000  # 讓時間間隔滿足
        collector.update_activity()  # 更新活動時間
        assert collector.should_run_gc() is False
    
    def test_run_smart_gc_conditions_not_met(self):
        """測試不滿足條件時的 GC 執行"""
        collector = SmartGarbageCollector(idle_threshold=300, check_interval=1800)
        
        result = collector.run_smart_gc()
        
        assert result['skipped'] is True
        assert result['reason'] == 'conditions not met'
    
    @patch('src.core.memory_monitor.logger')
    @patch('gc.collect')
    @patch('psutil.Process')
    def test_run_smart_gc_success(self, mock_process, mock_gc_collect, mock_logger):
        """測試成功執行智慧垃圾回收"""
        # 設置前後記憶體使用
        mock_memory_info_before = Mock()
        mock_memory_info_before.rss = 200 * 1024 * 1024  # 200MB
        
        mock_memory_info_after = Mock()
        mock_memory_info_after.rss = 180 * 1024 * 1024  # 180MB
        
        mock_process.return_value.memory_info.side_effect = [mock_memory_info_before, mock_memory_info_after]
        mock_gc_collect.return_value = 1000
        
        collector = SmartGarbageCollector(idle_threshold=0.1, check_interval=0.1)
        time.sleep(0.2)  # 確保滿足條件
        
        result = collector.run_smart_gc()
        
        assert result['executed'] is True
        assert result['collected_objects'] == 1000
        assert result['memory_freed_mb'] == 20.0
        assert 'duration_seconds' in result
        assert 'before_memory_mb' in result
        assert 'after_memory_mb' in result
        assert result['total_runs'] == 1
        assert result['total_collected'] == 1000
        
        # 檢查統計更新
        assert collector.gc_runs == 1
        assert collector.total_collected == 1000
        
        # 檢查包含特定調用
        mock_logger.info.assert_any_call(f"SmartGarbageCollector initialized: idle=0.1s, interval=0.1s")
        log_args = mock_logger.info.call_args[0][0]
        assert "Smart GC completed" in log_args
    
    @patch('src.core.memory_monitor.logger')
    def test_run_smart_gc_error(self, mock_logger):
        """測試智慧垃圾回收錯誤處理"""
        collector = SmartGarbageCollector(idle_threshold=0.1, check_interval=0.1)
        time.sleep(0.2)
        
        with patch('gc.collect', side_effect=Exception("GC error")):
            result = collector.run_smart_gc()
            
            assert 'error' in result
            assert result['error'] == "GC error"
            mock_logger.error.assert_called_once_with("Error in smart GC: GC error")
    
    @patch('src.core.memory_monitor.logger')
    def test_multiple_gc_runs_statistics(self, mock_logger):
        """測試多次 GC 執行統計"""
        collector = SmartGarbageCollector(idle_threshold=0.1, check_interval=0.1)
        
        with patch('gc.collect', return_value=100) as mock_gc_collect, \
             patch('psutil.Process') as mock_process:
            
            # 設置固定的記憶體減少
            mock_process.return_value.memory_info.return_value.rss = 100 * 1024 * 1024
            
            # 連續執行多次 GC
            for i in range(3):
                time.sleep(0.2)
                result = collector.run_smart_gc()
                assert result['executed'] is True
            
            assert collector.gc_runs == 3
            assert collector.total_collected == 300  # 3 * 100
            assert mock_gc_collect.call_count == 3