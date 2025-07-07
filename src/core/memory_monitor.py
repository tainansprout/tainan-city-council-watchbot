"""
記憶體使用監控系統
針對 RAG 應用優化，支援實時監控和警報
"""
import psutil
import gc
import time
import threading
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from ..core.logger import get_logger

logger = get_logger(__name__)


class MemoryMonitor:
    """
    記憶體使用監控和警報系統
    
    特色功能：
    - 實時記憶體使用監控
    - 可配置警告和緊急閾值
    - 自動垃圾回收觸發
    - 詳細的記憶體統計
    """
    
    def __init__(self, warning_threshold: float = 2.0, critical_threshold: float = 4.0):
        """
        初始化記憶體監控
        
        Args:
            warning_threshold: 警告閾值（2.0 = 2% 系統記憶體）
            critical_threshold: 緊急閾值（4.0 = 4% 系統記憶體）
        """
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.logger = logger
        
        # 統計資訊
        self.last_check_time = time.time()
        self.warning_count = 0
        self.critical_count = 0
        self.gc_trigger_count = 0
        
        logger.info(f"MemoryMonitor initialized: warning={warning_threshold:.1%}, critical={critical_threshold:.1%}")
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """取得當前記憶體統計"""
        try:
            # 進程記憶體資訊
            process = psutil.Process()
            memory_info = process.memory_info()
            
            # 系統記憶體資訊
            system_memory = psutil.virtual_memory()
            
            return {
                'process_memory_mb': memory_info.rss / 1024 / 1024,
                'process_memory_percent': process.memory_percent(),
                'system_memory_percent': system_memory.percent,
                'available_memory_gb': system_memory.available / 1024 / 1024 / 1024,
                'total_memory_gb': system_memory.total / 1024 / 1024 / 1024,
                'timestamp': datetime.utcnow().isoformat(),
                
                # 詳細統計
                'memory_info': {
                    'rss': memory_info.rss,  # 實際物理記憶體
                    'vms': memory_info.vms,  # 虛擬記憶體
                    'shared': getattr(memory_info, 'shared', 0),
                    'text': getattr(memory_info, 'text', 0),
                    'lib': getattr(memory_info, 'lib', 0),
                    'data': getattr(memory_info, 'data', 0),
                    'dirty': getattr(memory_info, 'dirty', 0)
                },
                
                # 監控統計
                'monitor_stats': {
                    'warning_count': self.warning_count,
                    'critical_count': self.critical_count,
                    'gc_trigger_count': self.gc_trigger_count,
                    'uptime_seconds': time.time() - self.last_check_time
                }
            }
        except Exception as e:
            logger.error(f"Error getting memory stats: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def check_memory_usage(self) -> bool:
        """
        檢查記憶體使用並發出警報
        
        Returns:
            bool: True 如果記憶體使用正常，False 如果達到緊急閾值
        """
        try:
            stats = self.get_memory_stats()
            
            if 'error' in stats:
                return True  # 無法取得統計時假設正常
            
            # 只使用進程記憶體百分比作為警告依據
            # 系統記憶體使用率不應影響應用程式警告
            process_percent = stats['process_memory_percent']
            system_percent = stats['system_memory_percent'] 
            
            # 使用進程記憶體百分比來決定警告
            alert_percent = process_percent / 100
            
            if alert_percent >= self.critical_threshold:
                self.critical_count += 1
                self.logger.critical(
                    f"🚨 Critical memory usage: {alert_percent:.1%} "
                    f"(Process: {process_percent:.1%}, System: {system_percent:.1%}) "
                    f"RSS: {stats['process_memory_mb']:.1f}MB"
                )
                
                # 觸發緊急垃圾回收
                self._trigger_emergency_gc()
                return False
                
            elif alert_percent >= self.warning_threshold:
                self.warning_count += 1
                self.logger.warning(
                    f"⚠️ High memory usage: {alert_percent:.1%} "
                    f"(Process: {process_percent:.1%}, System: {system_percent:.1%}) "
                    f"RSS: {stats['process_memory_mb']:.1f}MB"
                )
                
                # 可選：觸發溫和的垃圾回收
                if self.warning_count % 5 == 0:  # 每5次警告觸發一次GC
                    self._trigger_gentle_gc()
            
            else:
                # 記憶體使用正常
                if self.warning_count > 0 or self.critical_count > 0:
                    logger.info(f"✅ Memory usage normalized: {alert_percent:.1%}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking memory usage: {e}")
            return True  # 出錯時假設正常，避免誤報
    
    def _trigger_emergency_gc(self):
        """觸發緊急垃圾回收"""
        try:
            before_memory = psutil.Process().memory_info().rss / 1024 / 1024
            
            # 執行垃圾回收
            collected = gc.collect()
            
            after_memory = psutil.Process().memory_info().rss / 1024 / 1024
            freed_mb = before_memory - after_memory
            
            self.gc_trigger_count += 1
            
            logger.warning(
                f"🧹 Emergency GC: collected {collected} objects, "
                f"freed {freed_mb:.1f}MB (before: {before_memory:.1f}MB, after: {after_memory:.1f}MB)"
            )
            
        except Exception as e:
            logger.error(f"Error in emergency GC: {e}")
    
    def _trigger_gentle_gc(self):
        """觸發溫和的垃圾回收"""
        try:
            collected = gc.collect()
            logger.info(f"🧹 Gentle GC: collected {collected} objects")
            
        except Exception as e:
            logger.error(f"Error in gentle GC: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """取得應用程式快取統計（如果可用）"""
        cache_stats = {}
        
        try:
            # 嘗試從各個模組取得快取統計
            from ..models.anthropic_model import AnthropicModel
            from ..models.gemini_model import GeminiModel
            from ..core.bounded_cache import BoundedCache
            
            # 這裡可以添加對快取統計的收集
            # 注意：需要模型實例才能取得具體統計
            cache_stats['cache_types_available'] = ['anthropic', 'gemini', 'bounded_cache']
            
        except ImportError as e:
            cache_stats['import_error'] = str(e)
        
        return cache_stats
    
    def get_detailed_report(self) -> Dict[str, Any]:
        """取得詳細的記憶體報告"""
        memory_stats = self.get_memory_stats()
        cache_stats = self.get_cache_stats()
        
        return {
            'memory': memory_stats,
            'cache': cache_stats,
            'thresholds': {
                'warning': self.warning_threshold,
                'critical': self.critical_threshold
            },
            'report_time': datetime.utcnow().isoformat()
        }


class SmartGarbageCollector:
    """
    智慧垃圾回收管理
    
    特色功能：
    - 基於空閒時間的智慧回收
    - 避免高峰時段的GC
    - 可配置的檢查間隔
    """
    
    def __init__(self, idle_threshold: int = 300, check_interval: int = 1800):
        """
        初始化智慧垃圾回收
        
        Args:
            idle_threshold: 空閒閾值（秒），預設5分鐘
            check_interval: 檢查間隔（秒），預設30分鐘
        """
        self.idle_threshold = idle_threshold
        self.check_interval = check_interval
        self.last_activity_time = time.time()
        self.last_gc_time = time.time()
        
        # 統計
        self.gc_runs = 0
        self.total_collected = 0
        
        logger.info(f"SmartGarbageCollector initialized: idle={idle_threshold}s, interval={check_interval}s")
    
    def update_activity(self):
        """更新最後活動時間（在請求處理時調用）"""
        self.last_activity_time = time.time()
    
    def should_run_gc(self) -> bool:
        """判斷是否應該執行垃圾回收"""
        current_time = time.time()
        
        # 檢查是否到了檢查時間
        if current_time - self.last_gc_time < self.check_interval:
            return False
        
        # 檢查是否空閒足夠時間
        idle_time = current_time - self.last_activity_time
        if idle_time < self.idle_threshold:
            logger.debug(f"Not idle enough for GC: {idle_time:.1f}s < {self.idle_threshold}s")
            return False
        
        return True
    
    def run_smart_gc(self) -> Dict[str, Any]:
        """執行智慧垃圾回收"""
        if not self.should_run_gc():
            return {'skipped': True, 'reason': 'conditions not met'}
        
        try:
            before_memory = psutil.Process().memory_info().rss / 1024 / 1024
            start_time = time.time()
            
            # 執行垃圾回收
            collected = gc.collect()
            
            end_time = time.time()
            after_memory = psutil.Process().memory_info().rss / 1024 / 1024
            
            # 更新統計
            self.gc_runs += 1
            self.total_collected += collected
            self.last_gc_time = time.time()
            
            gc_duration = end_time - start_time
            freed_mb = before_memory - after_memory
            
            result = {
                'executed': True,
                'collected_objects': collected,
                'memory_freed_mb': freed_mb,
                'duration_seconds': gc_duration,
                'before_memory_mb': before_memory,
                'after_memory_mb': after_memory,
                'total_runs': self.gc_runs,
                'total_collected': self.total_collected
            }
            
            logger.info(
                f"🧹 Smart GC completed: collected {collected} objects, "
                f"freed {freed_mb:.1f}MB in {gc_duration:.3f}s"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error in smart GC: {e}")
            return {'error': str(e)}


# 全局實例
_memory_monitor = None
_smart_gc = None

def get_memory_monitor() -> MemoryMonitor:
    """取得全局記憶體監控實例"""
    global _memory_monitor
    if _memory_monitor is None:
        _memory_monitor = MemoryMonitor()
    return _memory_monitor

def get_smart_gc() -> SmartGarbageCollector:
    """取得全局智慧垃圾回收實例"""
    global _smart_gc
    if _smart_gc is None:
        _smart_gc = SmartGarbageCollector()
    return _smart_gc


# Flask 整合用的便利函數
def setup_memory_monitoring(app):
    """
    設置 Flask 應用的記憶體監控
    
    Args:
        app: Flask 應用實例
    """
    memory_monitor = get_memory_monitor()
    smart_gc = get_smart_gc()
    
    @app.before_request
    def before_request():
        # 更新活動時間
        smart_gc.update_activity()
        
        # 檢查記憶體使用
        if not memory_monitor.check_memory_usage():
            # 記憶體使用過高時的處理
            logger.warning("High memory usage detected during request")
    
    @app.after_request
    def after_request(response):
        # 執行智慧垃圾回收（如果條件滿足）
        smart_gc.run_smart_gc()
        return response
    
    logger.info("Memory monitoring setup completed for Flask app")
    return memory_monitor, smart_gc
