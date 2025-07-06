"""
高效能日誌系統
包含異步處理、預編譯正則表達式敏感資料過濾和優化的格式化器
"""

import logging
import json
import re
import threading
import queue
import time
import copy
from typing import Dict, Any, Optional, Pattern, List
from datetime import datetime
from .logger import get_logger

# 取得基礎 logger 用於自身的日誌記錄
base_logger = get_logger(__name__)


class OptimizedSensitiveDataFilter:
    """優化的敏感資料過濾器"""
    
    # 🔥 關鍵優化：預編譯正則表達式
    _COMPILED_PATTERNS: List[Pattern] = [
        re.compile(r'(api_key["\']?\s*[:=]\s*["\']?)([^"\'>\s]+)', re.IGNORECASE),
        re.compile(r'(token["\']?\s*[:=]\s*["\']?)([^"\'>\s]+)', re.IGNORECASE),
        re.compile(r'(password["\']?\s*[:=]\s*["\']?)([^"\'>\s]+)', re.IGNORECASE),
        re.compile(r'(secret["\']?\s*[:=]\s*["\']?)([^"\'>\s]+)', re.IGNORECASE),
        re.compile(r'(Bearer\s+)([A-Za-z0-9\-_]+)', re.IGNORECASE),
        re.compile(r'(Authorization:\s*Bearer\s+)([A-Za-z0-9\-_]+)', re.IGNORECASE),
        # 信用卡號碼
        re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
        # 電話號碼
        re.compile(r'\b09\d{8}\b'),
        # Email 部分遮蔽
        re.compile(r'([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'),
    ]
    
    # 🔥 性能優化：快取常見的清理結果
    _cache: Dict[str, str] = {}
    _cache_lock = threading.Lock()
    _max_cache_size = 500  # 較小的快取避免記憶體過度使用
    
    @classmethod
    def sanitize_fast(cls, text: str) -> str:
        """
        快速敏感資料清理
        
        Args:
            text: 要清理的文本
            
        Returns:
            清理後的文本
        """
        if not text or not isinstance(text, str):
            return str(text)
        
        # 🔥 快取檢查（只快取短文本）
        if len(text) < 500:
            with cls._cache_lock:
                if text in cls._cache:
                    return cls._cache[text]
        
        # 長度限制，避免處理超大字串
        if len(text) > 10000:
            text = text[:10000] + "...[truncated]"
        
        # 使用預編譯正則快速處理
        sanitized = text
        for pattern in cls._COMPILED_PATTERNS:
            if pattern.pattern.startswith('([a-zA-Z0-9._%+-]+)@'):  # Email 特殊處理
                sanitized = pattern.sub(r'\1***@\2', sanitized)
            else:
                sanitized = pattern.sub(r'\1***', sanitized)
        
        # 🔥 結果快取（控制快取大小）
        if len(text) < 500:
            with cls._cache_lock:
                if len(cls._cache) >= cls._max_cache_size:
                    # 簡單的 LRU：清除一半最舊的項目
                    items = list(cls._cache.items())
                    cls._cache = dict(items[len(items)//2:])
                cls._cache[text] = sanitized
        
        return sanitized
    
    @classmethod
    def get_cache_stats(cls) -> Dict[str, int]:
        """取得快取統計資訊"""
        with cls._cache_lock:
            return {
                'cache_size': len(cls._cache),
                'max_cache_size': cls._max_cache_size,
                'cache_usage_percent': int((len(cls._cache) / cls._max_cache_size) * 100)
            }
    
    @classmethod
    def clear_cache(cls):
        """清空快取"""
        with cls._cache_lock:
            cls._cache.clear()


class HighPerformanceFormatter(logging.Formatter):
    """高效能日誌格式化器"""
    
    def __init__(self, enable_json: bool = False, enable_colors: bool = True):
        super().__init__()
        self.enable_json = enable_json
        self.enable_colors = enable_colors
        
        # 🔥 預建立顏色映射，避免重複計算
        if enable_colors:
            self.color_map = {
                'DEBUG': '\033[36m',    # 青色
                'INFO': '\033[32m',     # 綠色  
                'WARNING': '\033[33m',  # 黃色
                'ERROR': '\033[31m',    # 紅色
                'CRITICAL': '\033[35m', # 紫色
            }
            self.reset_color = '\033[0m'
        
        # 🔥 預建立時間格式，避免重複 strftime 調用
        self._last_time_cache = {}
        self._time_cache_lock = threading.Lock()
        
    def format(self, record: logging.LogRecord) -> str:
        """優化的格式化方法"""
        # 🔥 避免 copy.copy，直接處理
        
        # 快速敏感資料清理
        try:
            message = OptimizedSensitiveDataFilter.sanitize_fast(record.getMessage())
        except Exception:
            # 如果清理失敗，使用原始訊息但記錄警告
            message = record.getMessage()
            base_logger.warning("敏感資料清理失敗，使用原始訊息")
        
        if self.enable_json:
            return self._format_json(record, message)
        else:
            return self._format_simple(record, message)
    
    def _format_json(self, record: logging.LogRecord, message: str) -> str:
        """JSON 格式化"""
        log_data = {
            'time': self._get_formatted_time(),
            'level': record.levelname,
            'msg': message,
            'module': record.module,
        }
        
        # 🔥 只有錯誤時才加入額外資訊，減少 JSON 大小
        if record.levelno >= logging.ERROR:
            log_data.update({
                'filename': record.filename,
                'lineno': record.lineno,
                'funcName': record.funcName,
            })
        
        # 🔥 使用最緊湊的 JSON 格式
        return json.dumps(log_data, ensure_ascii=False, separators=(',', ':'))
    
    def _format_simple(self, record: logging.LogRecord, message: str) -> str:
        """簡單格式化"""
        timestamp = self._get_formatted_time(simple=True)
        level = record.levelname
        
        if self.enable_colors and level in self.color_map:
            level_colored = f"{self.color_map[level]}{level}{self.reset_color}"
            return f"{timestamp} [{level_colored}] {message}"
        else:
            return f"{timestamp} [{level}] {message}"
    
    def _get_formatted_time(self, simple: bool = False) -> str:
        """優化的時間格式化"""
        current_time = time.time()
        
        # 使用簡單的快取機制，快取到秒級別
        cache_key = int(current_time)
        format_key = 'simple' if simple else 'full'
        
        with self._time_cache_lock:
            if cache_key in self._last_time_cache:
                cached_times = self._last_time_cache[cache_key]
                if format_key in cached_times:
                    return cached_times[format_key]
            else:
                self._last_time_cache[cache_key] = {}
            
            # 格式化時間
            dt = datetime.fromtimestamp(current_time)
            if simple:
                formatted = dt.strftime('%H:%M:%S')
            else:
                formatted = dt.isoformat()
            
            # 快取結果
            self._last_time_cache[cache_key][format_key] = formatted
            
            # 清理舊的快取項目（保留最近10秒）
            cutoff = cache_key - 10
            old_keys = [k for k in self._last_time_cache.keys() if k < cutoff]
            for old_key in old_keys:
                del self._last_time_cache[old_key]
            
            return formatted


class AsyncLogHandler(logging.Handler):
    """異步日誌處理器 - 避免 I/O 阻塞"""
    
    def __init__(self, target_handler: logging.Handler, queue_size: int = 1000):
        super().__init__()
        self.target_handler = target_handler
        self.log_queue = queue.Queue(maxsize=queue_size)
        self.worker_thread = None
        self.stop_event = threading.Event()
        self.dropped_logs = 0
        self._start_worker()
    
    def _start_worker(self):
        """啟動背景工作執行緒"""
        def worker():
            while not self.stop_event.is_set():
                try:
                    record = self.log_queue.get(timeout=1)
                    if record is None:  # 停止信號
                        break
                    
                    # 發送到目標處理器
                    self.target_handler.emit(record)
                    self.log_queue.task_done()
                    
                except queue.Empty:
                    continue
                except Exception as e:
                    # 避免日誌錯誤影響主程式
                    # 使用 print 避免遞迴日誌錯誤
                    print(f"異步日誌處理錯誤: {e}")
        
        self.worker_thread = threading.Thread(target=worker, daemon=True, name='AsyncLogWorker')
        self.worker_thread.start()
    
    def emit(self, record: logging.LogRecord):
        """非阻塞的日誌發送"""
        try:
            # 🔥 複製 record 避免線程間數據競爭
            record_copy = copy.copy(record)
            self.log_queue.put_nowait(record_copy)
        except queue.Full:
            # 佇列滿時丟棄日誌，避免阻塞主程式
            self.dropped_logs += 1
            # 每100個丟棄的日誌報告一次
            if self.dropped_logs % 100 == 0:
                print(f"警告：已丟棄 {self.dropped_logs} 條日誌訊息")
    
    def get_stats(self) -> Dict[str, int]:
        """取得統計資訊"""
        return {
            'queue_size': self.log_queue.qsize(),
            'dropped_logs': self.dropped_logs,
            'worker_alive': self.worker_thread.is_alive() if self.worker_thread else False
        }
    
    def close(self):
        """關閉處理器"""
        self.stop_event.set()
        
        # 發送停止信號
        try:
            self.log_queue.put_nowait(None)
        except queue.Full:
            pass
        
        # 等待工作執行緒結束
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2)
        
        super().close()


def setup_optimized_logger(name: str = 'chatbot', enable_async: bool = True) -> logging.Logger:
    """
    設置優化的日誌記錄器
    
    Args:
        name: Logger 名稱
        enable_async: 是否啟用異步處理
        
    Returns:
        優化的 Logger 實例
    """
    logger = logging.getLogger(name)
    
    # 避免重複設置
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)
    
    # 🔥 Console Handler - 彩色輸出
    console_handler = logging.StreamHandler()
    console_formatter = HighPerformanceFormatter(enable_json=False, enable_colors=True)
    console_handler.setFormatter(console_formatter)
    
    # 🔥 File Handler - JSON 格式
    try:
        import os
        os.makedirs('logs', exist_ok=True)
        file_handler = logging.FileHandler('logs/app.log', encoding='utf-8')
        file_formatter = HighPerformanceFormatter(enable_json=True, enable_colors=False)
        file_handler.setFormatter(file_formatter)
    except Exception as e:
        # 如果檔案處理器創建失敗，只使用 console
        base_logger.warning(f"無法創建檔案日誌處理器: {e}")
        file_handler = None
    
    # 使用異步處理器包裝（如果啟用）
    if enable_async:
        async_console = AsyncLogHandler(console_handler, queue_size=500)
        logger.addHandler(async_console)
        
        if file_handler:
            async_file = AsyncLogHandler(file_handler, queue_size=1000)
            logger.addHandler(async_file)
    else:
        logger.addHandler(console_handler)
        if file_handler:
            logger.addHandler(async_file)
    
    return logger


class LoggerPerformanceMonitor:
    """日誌效能監控器"""
    
    def __init__(self):
        self.start_time = time.time()
        self.log_counts = {
            'DEBUG': 0,
            'INFO': 0,
            'WARNING': 0,
            'ERROR': 0,
            'CRITICAL': 0
        }
        self.total_logs = 0
        self._lock = threading.Lock()
    
    def record_log(self, level: str):
        """記錄日誌"""
        with self._lock:
            if level in self.log_counts:
                self.log_counts[level] += 1
            self.total_logs += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """取得統計資訊"""
        uptime = time.time() - self.start_time
        with self._lock:
            return {
                'uptime_seconds': round(uptime, 1),
                'total_logs': self.total_logs,
                'logs_per_second': round(self.total_logs / max(uptime, 1), 2),
                'log_levels': dict(self.log_counts),
                'sensitive_data_filter': OptimizedSensitiveDataFilter.get_cache_stats()
            }


# 全域效能監控器
_performance_monitor = LoggerPerformanceMonitor()

def get_logger_stats() -> Dict[str, Any]:
    """取得日誌系統統計資訊"""
    return _performance_monitor.get_stats()


# 建立優化的預設 logger
optimized_logger = setup_optimized_logger('optimized_chatbot', enable_async=True)

# 提供便捷的日誌函數
def log_info(message: str, *args, **kwargs):
    """高效能 INFO 日誌"""
    _performance_monitor.record_log('INFO')
    optimized_logger.info(message, *args, **kwargs)

def log_error(message: str, *args, **kwargs):
    """高效能 ERROR 日誌"""
    _performance_monitor.record_log('ERROR')
    optimized_logger.error(message, *args, **kwargs)

def log_warning(message: str, *args, **kwargs):
    """高效能 WARNING 日誌"""
    _performance_monitor.record_log('WARNING')
    optimized_logger.warning(message, *args, **kwargs)

def log_debug(message: str, *args, **kwargs):
    """高效能 DEBUG 日誌"""
    _performance_monitor.record_log('DEBUG')
    optimized_logger.debug(message, *args, **kwargs)