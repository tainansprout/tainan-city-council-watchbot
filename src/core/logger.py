import os
import logging
import logging.handlers
import json
from datetime import datetime
from typing import Dict, Any, Optional


class SensitiveDataFilter(logging.Filter):
    """過濾敏感資料的日誌過濾器"""
    
    SENSITIVE_KEYS = {
        'api_key', 'password', 'token', 'secret', 'auth', 'credential',
        'openai_api_key', 'line_channel_access_token', 'line_channel_secret'
    }
    
    def filter(self, record):
        """過濾日誌記錄中的敏感資料"""
        if hasattr(record, 'msg'):
            # 如果是字典格式，遞迴清理
            if isinstance(record.msg, dict):
                record.msg = self._sanitize_dict(record.msg)
            # 如果是字符串格式，使用正則表達式清理
            elif isinstance(record.msg, str):
                record.msg = self._sanitize_string(record.msg)
        
        return True
    
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
        """清理字符串中的敏感資料"""
        import re
        
        # 常見的敏感資料模式
        patterns = [
            r'(api_key["\']?\s*[:=]\s*["\']?)([^"\'\s]+)',
            r'(token["\']?\s*[:=]\s*["\']?)([^"\'\s]+)',
            r'(password["\']?\s*[:=]\s*["\']?)([^"\'\s]+)',
            r'(Bearer\s+)([A-Za-z0-9\-._~+/]+=*)',
            r'(sk-[A-Za-z0-9]{20,})',  # OpenAI API keys
        ]
        
        for pattern in patterns:
            text = re.sub(pattern, r'\1***REDACTED***', text, flags=re.IGNORECASE)
        
        return text


class StructuredFormatter(logging.Formatter):
    """結構化日誌格式器"""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'message': record.getMessage(),
        }
        
        # 添加異常資訊
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # 添加額外的上下文資訊
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id
        
        return json.dumps(log_entry, ensure_ascii=False)


class ColoredConsoleFormatter(logging.Formatter):
    """彩色控制台格式器"""
    
    LEVEL_COLORS = {
        logging.DEBUG: '\x1b[36m',     # Cyan
        logging.INFO: '\x1b[32m',      # Green
        logging.WARNING: '\x1b[33m',   # Yellow
        logging.ERROR: '\x1b[31m',     # Red
        logging.CRITICAL: '\x1b[35m',  # Magenta
    }
    
    RESET = '\x1b[0m'
    
    def format(self, record):
        color = self.LEVEL_COLORS.get(record.levelno, '')
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


class LoggerManager:
    """日誌管理器"""
    
    def __init__(self, name: str = 'chatbot', config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = config or self._load_default_config()
        self.logger = None
        self._setup_logger()
    
    def _load_default_config(self) -> Dict[str, Any]:
        """載入預設配置"""
        try:
            from .config import load_config
            config = load_config()
            return {
                'level': config.get('log_level', 'INFO'),
                'file_path': config.get('logfile', './logs/chatbot.log'),
                'max_bytes': 10 * 1024 * 1024,  # 10MB
                'backup_count': 5,
                'format': config.get('log_format', 'structured'),  # 'structured' or 'simple'
                'enable_console': True,
                'enable_file': True,
            }
        except:
            return {
                'level': 'INFO',
                'file_path': './logs/chatbot.log',
                'max_bytes': 10 * 1024 * 1024,
                'backup_count': 5,
                'format': 'simple',
                'enable_console': True,
                'enable_file': True,
            }
    
    def _setup_logger(self):
        """設定日誌記錄器"""
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(getattr(logging, self.config['level'].upper()))
        
        # 避免重複添加 handler
        if self.logger.handlers:
            return
        
        # 添加敏感資料過濾器
        sensitive_filter = SensitiveDataFilter()
        
        # 控制台處理器
        if self.config['enable_console']:
            console_handler = logging.StreamHandler()
            if self.config['format'] == 'structured':
                console_formatter = StructuredFormatter()
            else:
                console_formatter = ColoredConsoleFormatter(
                    fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
            console_handler.setFormatter(console_formatter)
            console_handler.addFilter(sensitive_filter)
            self.logger.addHandler(console_handler)
        
        # 檔案處理器
        if self.config['enable_file']:
            log_dir = os.path.dirname(self.config['file_path'])
            os.makedirs(log_dir, exist_ok=True)
            
            file_handler = logging.handlers.RotatingFileHandler(
                self.config['file_path'],
                maxBytes=self.config['max_bytes'],
                backupCount=self.config['backup_count'],
                encoding='utf-8'
            )
            
            if self.config['format'] == 'structured':
                file_formatter = StructuredFormatter()
            else:
                file_formatter = logging.Formatter(
                    fmt='%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
            
            file_handler.setFormatter(file_formatter)
            file_handler.addFilter(sensitive_filter)
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


# 全域日誌管理器實例
_logger_manager = LoggerManager()
logger = _logger_manager.get_logger()


def get_logger(name: str = None) -> logging.Logger:
    """取得日誌記錄器"""
    if name:
        return logging.getLogger(name)
    return logger


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
        logger.info(
            "Response sent",
            extra={
                'status_code': response.status_code,
                'content_length': response.content_length
            }
        )
        return response


# 向後相容
CustomFormatter = ColoredConsoleFormatter
LoggerFactory = LoggerManager
FileHandler = logging.handlers.RotatingFileHandler
ConsoleHandler = logging.StreamHandler