"""
高效能日誌系統
整合原始 logger.py 和 optimized_logger.py 的功能
包含異步處理、預編譯正則表達式敏感資料過濾和優化的格式化器
"""

import os
import logging
import logging.handlers
import json
import re
import copy
import threading
import queue
import time
from datetime import datetime
from typing import Dict, Any, Optional, Pattern, List


class SensitiveDataFilter(logging.Filter):
    """優化的敏感資料過濾器 - 使用預編譯正則表達式"""
    
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
    
    SENSITIVE_KEYS = {
        'api_key', 'password', 'token', 'secret', 'auth', 'credential',
        'openai_api_key', 'line_channel_access_token', 'line_channel_secret'
    }
    
    # 🔥 性能優化：快取常見的清理結果
    _cache: Dict[str, str] = {}
    _cache_lock = threading.Lock()
    _max_cache_size = 500
    
    def filter(self, record):
        """過濾日誌記錄中的敏感資料"""
        if hasattr(record, 'msg'):
            if isinstance(record.msg, dict):
                record.msg = self._sanitize_dict(record.msg)
            elif isinstance(record.msg, str):
                record.msg = self.sanitize_fast(record.msg)
        return True
    
    @classmethod
    def sanitize_fast(cls, text: str) -> str:
        """
        快速敏感資料清理 - 使用預編譯正則表達式
        
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
            # 根據正則表達式的群組數量決定替換策略
            if 'api_key' in pattern.pattern or 'token' in pattern.pattern or 'password' in pattern.pattern or 'secret' in pattern.pattern or 'Bearer' in pattern.pattern:
                # 這些模式有兩個捕獲群組：(前綴)(值)
                sanitized = pattern.sub(r'\1***', sanitized)
            elif pattern.pattern.startswith('([a-zA-Z0-9._%+-]+)@'):  # Email 特殊處理
                sanitized = pattern.sub(r'\1***@\2', sanitized)
            else:  # 沒有捕獲群組，直接替換
                sanitized = pattern.sub('***', sanitized)
        
        # 🔥 結果快取（控制快取大小）
        if len(text) < 500:
            with cls._cache_lock:
                if len(cls._cache) >= cls._max_cache_size:
                    # 簡單的 LRU：清除一半最舊的項目
                    items = list(cls._cache.items())
                    cls._cache = dict(items[len(items)//2:])
                cls._cache[text] = sanitized
        
        return sanitized
    
    def _sanitize_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """清理字典中的敏感資料"""
        if not isinstance(data, dict):
            return data
        
        sanitized = {}
        for key, value in data.items():
            if any(sensitive in key.lower() for sensitive in self.SENSITIVE_KEYS):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_dict(value)
            elif isinstance(value, list):
                sanitized[key] = [self._sanitize_dict(item) if isinstance(item, dict) else item for item in value]
            else:
                sanitized[key] = value
        
        return sanitized
    
    def _sanitize_string(self, text: str) -> str:
        """清理字符串中的敏感資料 - 向後兼容方法"""
        return self.sanitize_fast(text)
    
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


class StructuredFormatter(logging.Formatter):
    """高效能結構化日誌格式器"""
    
    def __init__(self, enable_colors: bool = False):
        super().__init__()
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
    
    def format(self, record):
        """優化的 JSON 格式化"""
        # 快速敏感資料清理
        try:
            message = SensitiveDataFilter.sanitize_fast(record.getMessage())
        except Exception:
            message = record.getMessage()
        
        log_entry = {
            'timestamp': self._get_formatted_time(),
            'level': record.levelname,
            'logger': record.name,
            'module': record.module,
            'message': message,
        }
        
        # 🔥 只有錯誤時才加入額外資訊，減少 JSON 大小
        if record.levelno >= logging.ERROR:
            log_entry.update({
                'function': record.funcName,
                'line': record.lineno,
            })
        
        # 添加異常資訊
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # 添加額外的上下文資訊
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id
        
        return json.dumps(log_entry, ensure_ascii=False, separators=(',', ':'))
    
    def _get_formatted_time(self) -> str:
        """優化的時間格式化"""
        current_time = time.time()
        
        # 使用簡單的快取機制，快取到秒級別
        cache_key = int(current_time)
        
        with self._time_cache_lock:
            if cache_key in self._last_time_cache:
                return self._last_time_cache[cache_key]
            
            # 格式化時間
            formatted = datetime.fromtimestamp(current_time).isoformat()
            
            # 快取結果
            self._last_time_cache[cache_key] = formatted
            
            # 清理舊的快取項目（保留最近10秒）
            cutoff = cache_key - 10
            old_keys = [k for k in self._last_time_cache.keys() if k < cutoff]
            for old_key in old_keys:
                del self._last_time_cache[old_key]
            
            return formatted


class ColoredConsoleFormatter(logging.Formatter):
    """優化的彩色控制台格式器"""
    
    LEVEL_COLORS = {
        logging.DEBUG: '\x1b[36m',     # Cyan
        logging.INFO: '\x1b[32m',      # Green
        logging.WARNING: '\x1b[33m',   # Yellow
        logging.ERROR: '\x1b[31m',     # Red
        logging.CRITICAL: '\x1b[35m',  # Magenta
    }
    
    RESET = '\x1b[0m'
    
    def __init__(self, fmt=None, datefmt=None):
        super().__init__(fmt, datefmt)
        # 🔥 預建立時間格式，避免重複 strftime 調用
        self._last_time_cache = {}
        self._time_cache_lock = threading.Lock()
    
    def format(self, record):
        """優化的彩色格式化"""
        # 快速敏感資料清理
        try:
            message = SensitiveDataFilter.sanitize_fast(record.getMessage())
        except Exception:
            message = record.getMessage()
        
        # 創建 record 的副本以避免修改原始 record
        colored_record = copy.copy(record)
        color = self.LEVEL_COLORS.get(colored_record.levelno, '')
        colored_record.levelname = f"{color}{colored_record.levelname}{self.RESET}"
        colored_record.msg = message
        
        timestamp = self._get_formatted_time()
        return f"{timestamp} - {colored_record.name} - {colored_record.levelname} - {message}"
    
    def _get_formatted_time(self) -> str:
        """優化的時間格式化"""
        current_time = time.time()
        cache_key = int(current_time)
        
        with self._time_cache_lock:
            if cache_key in self._last_time_cache:
                return self._last_time_cache[cache_key]
            
            formatted = datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S')
            self._last_time_cache[cache_key] = formatted
            
            # 清理舊的快取項目
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


class LoggerManager:
    """優化的日誌管理器"""
    
    def __init__(self, name: str = 'chatbot', config: Optional[Dict[str, Any]] = None, enable_async: bool = True):
        self.name = name
        self.config = config or self._load_default_config()
        self.enable_async = enable_async
        self.logger = None
        self._setup_logger()
    
    def _load_default_config(self) -> Dict[str, Any]:
        """載入預設配置"""
        default_config = {
            'level': 'DEBUG',
            'file_path': './logs/chatbot.log',
            'max_bytes': 10 * 1024 * 1024,  # 10MB
            'backup_count': 5,
            'format': 'simple',
            'enable_console': True,
            'enable_file': True,
        }
        
        try:
            from .config import ConfigManager
            config_manager = ConfigManager()
            config = config_manager.get_config()
            
            # 安全地合併配置
            if config:
                default_config.update({
                    'level': config.get('log_level', default_config['level']),
                    'file_path': config.get('logfile', default_config['file_path']),
                    'format': config.get('log_format', default_config['format']),
                })
        except Exception as e:
            print(f"Warning: Could not load config file, using defaults: {e}")
        
        return default_config
    
    def _setup_logger(self):
        """設定優化的日誌記錄器"""
        self.logger = logging.getLogger(self.name)
        
        # 安全地設置日誌級別
        try:
            level = self.config['level'].upper()
            log_level = getattr(logging, level)
            self.logger.setLevel(log_level)
        except (AttributeError, KeyError):
            self.logger.setLevel(logging.DEBUG)
            print(f"Warning: Invalid log level '{self.config.get('level', 'unknown')}', using DEBUG instead")
        
        # 避免重複添加 handler
        if self.logger.handlers:
            return
        
        # 添加敏感資料過濾器
        sensitive_filter = SensitiveDataFilter()
        
        # 控制台處理器
        if self.config.get('enable_console', True):
            console_handler = logging.StreamHandler()
            if self.config.get('format', 'simple') == 'structured':
                console_formatter = StructuredFormatter(enable_colors=True)
            else:
                console_formatter = ColoredConsoleFormatter(
                    fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
            console_handler.setFormatter(console_formatter)
            console_handler.addFilter(sensitive_filter)
            
            # 🔥 使用異步處理器包裝（如果啟用）
            if self.enable_async:
                async_console = AsyncLogHandler(console_handler, queue_size=500)
                self.logger.addHandler(async_console)
            else:
                self.logger.addHandler(console_handler)
        
        # 檔案處理器
        if self.config.get('enable_file', True):
            file_path = self.config.get('file_path', './logs/chatbot.log')
            log_dir = os.path.dirname(file_path)
            os.makedirs(log_dir, exist_ok=True)
            
            file_handler = logging.handlers.RotatingFileHandler(
                file_path,
                maxBytes=self.config.get('max_bytes', 10 * 1024 * 1024),
                backupCount=self.config.get('backup_count', 5),
                encoding='utf-8'
            )
            
            if self.config.get('format', 'simple') == 'structured':
                file_formatter = StructuredFormatter(enable_colors=False)
            else:
                file_formatter = logging.Formatter(
                    fmt='%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
            
            file_handler.setFormatter(file_formatter)
            file_handler.addFilter(sensitive_filter)
            
            # 🔥 使用異步處理器包裝（如果啟用）
            if self.enable_async:
                async_file = AsyncLogHandler(file_handler, queue_size=1000)
                self.logger.addHandler(async_file)
            else:
                self.logger.addHandler(file_handler)
    
    def get_logger(self) -> logging.Logger:
        """取得日誌記錄器"""
        return self.logger
    
    def log_with_context(self, level: int, msg: str, **context):
        """帶上下文的日誌記錄"""
        extra = {k: v for k, v in context.items() if k not in ['msg', 'args']}
        self.logger.log(level, msg, extra=extra)
    
    def update_config(self, new_config: Dict[str, Any]):
        """更新配置"""
        self.config.update(new_config)
        # 移除現有 handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        # 重新設定
        self._setup_logger()
    
    def get_stats(self) -> Dict[str, Any]:
        """取得日誌系統統計資訊"""
        stats = {
            'logger_name': self.name,
            'log_level': self.logger.level,
            'handler_count': len(self.logger.handlers),
            'async_enabled': self.enable_async,
            'sensitive_data_filter': SensitiveDataFilter.get_cache_stats()
        }
        
        # 收集異步 handler 統計
        async_stats = []
        for handler in self.logger.handlers:
            if isinstance(handler, AsyncLogHandler):
                async_stats.append(handler.get_stats())
        
        if async_stats:
            stats['async_handlers'] = async_stats
        
        return stats


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
                'sensitive_data_filter': SensitiveDataFilter.get_cache_stats()
            }


# 全域日誌管理器實例
_logger_manager = LoggerManager(enable_async=True)
logger = _logger_manager.get_logger()

# 全域效能監控器
_performance_monitor = LoggerPerformanceMonitor()


def get_logger(name: str = None) -> logging.Logger:
    """取得日誌記錄器"""
    if name:
        return logging.getLogger(name)
    return logger


def setup_optimized_logger(name: str = 'chatbot', enable_async: bool = True) -> logging.Logger:
    """
    設置優化的日誌記錄器
    
    Args:
        name: Logger 名稱
        enable_async: 是否啟用異步處理
        
    Returns:
        優化的 Logger 實例
    """
    manager = LoggerManager(name=name, enable_async=enable_async)
    return manager.get_logger()


def get_logger_stats() -> Dict[str, Any]:
    """取得日誌系統統計資訊"""
    return {
        'performance': _performance_monitor.get_stats(),
        'manager': _logger_manager.get_stats()
    }


def setup_request_logging(app):
    """設定 Flask 請求日誌"""
    @app.before_request
    def log_request_info():
        from flask import request
        import uuid
        
        # 生成請求 ID
        request_id = str(uuid.uuid4())[:8]
        
        # 記錄請求資訊（排除敏感 headers）
        safe_headers = {
            k: v for k, v in request.headers.items() 
            if k.lower() not in ['authorization', 'x-line-signature']
        }
        
        # 記錄請求資訊
        logger.info(
            "Incoming request",
            extra={
                'request_id': request_id,
                'method': request.method,
                'url': request.url,
                'remote_addr': request.remote_addr,
                'headers': safe_headers
            }
        )
    
    @app.after_request
    def log_response_info(response):
        # 記錄回應資訊
        logger.info(
            "Response sent",
            extra={
                'status_code': response.status_code,
                'content_length': response.content_length
            }
        )
        return response


# 提供便捷的日誌函數
def log_info(message: str, *args, **kwargs):
    """高效能 INFO 日誌"""
    _performance_monitor.record_log('INFO')
    logger.info(message, *args, **kwargs)


def log_error(message: str, *args, **kwargs):
    """高效能 ERROR 日誌"""
    _performance_monitor.record_log('ERROR')
    logger.error(message, *args, **kwargs)


def log_warning(message: str, *args, **kwargs):
    """高效能 WARNING 日誌"""
    _performance_monitor.record_log('WARNING')
    logger.warning(message, *args, **kwargs)


def log_debug(message: str, *args, **kwargs):
    """高效能 DEBUG 日誌"""
    _performance_monitor.record_log('DEBUG')
    logger.debug(message, *args, **kwargs)


