"""
安全性模組：提供安全配置、輸入驗證、清理和安全檢查功能
整合原始 security.py 和 optimized_security.py 的功能
包含預編譯正則表達式、優化的速率限制器和高效能安全檢查

此模組整合了所有安全相關功能：
- SecurityConfig: 安全配置管理
- InputValidator: 優化的輸入驗證和清理
- RateLimiter: O(1) 複雜度速率限制
- SecurityMiddleware: 安全中間件
- 各種安全工具函數

架構說明：
- 統一管理所有安全相關功能，避免分散
- 提供完整的安全防護層
- 支援開發和生產環境的不同安全策略
- 使用預編譯正則表達式提升效能
"""

import re
import html
import json
import hashlib
import hmac
import time
import os
import threading
from collections import defaultdict
from typing import Dict, Any, Optional, List, Union, Pattern, Tuple
from functools import wraps
from flask import request, abort, current_app
from .logger import get_logger

logger = get_logger(__name__)


class SecurityConfig:
    """安全配置管理類 - 統一管理所有安全相關配置"""
    
    def __init__(self):
        self.config = self._load_security_config()
    
    def _load_security_config(self) -> Dict[str, Any]:
        """載入安全配置"""
        return {
            # 測試端點配置
            'enable_test_endpoints': os.getenv('ENABLE_TEST_ENDPOINTS', 'true').lower() == 'true',
            'test_endpoint_rate_limit': int(os.getenv('TEST_ENDPOINT_RATE_LIMIT', '10')),  # 每分鐘請求數
            
            # 一般速率限制
            'general_rate_limit': int(os.getenv('GENERAL_RATE_LIMIT', '60')),  # 每分鐘請求數
            'webhook_rate_limit': int(os.getenv('WEBHOOK_RATE_LIMIT', '300')),  # Line webhook 每分鐘請求數
            
            # 內容限制
            'max_message_length': int(os.getenv('MAX_MESSAGE_LENGTH', '5000')),
            'max_test_message_length': int(os.getenv('MAX_TEST_MESSAGE_LENGTH', '1000')),
            
            # 安全標頭
            'enable_security_headers': os.getenv('ENABLE_SECURITY_HEADERS', 'true').lower() == 'true',
            'enable_cors': os.getenv('ENABLE_CORS', 'false').lower() == 'true',
            
            # 監控和日誌
            'log_security_events': os.getenv('LOG_SECURITY_EVENTS', 'true').lower() == 'true',
            'enable_request_logging': os.getenv('ENABLE_REQUEST_LOGGING', 'true').lower() == 'true',
            
            # 環境檢測
            'environment': os.getenv('FLASK_ENV', os.getenv('ENVIRONMENT', 'production')),
            'debug_mode': os.getenv('FLASK_DEBUG', 'false').lower() == 'true',
        }
    
    def is_development(self) -> bool:
        """檢查是否為開發環境"""
        return self.config['environment'] in ['development', 'dev', 'local']
    
    def is_production(self) -> bool:
        """檢查是否為生產環境"""
        return self.config['environment'] in ['production', 'prod']
    
    def should_enable_test_endpoints(self) -> bool:
        """檢查是否應該啟用測試端點"""
        # 在生產環境中，除非明確設定，否則不啟用測試端點
        if self.is_production():
            return self.config['enable_test_endpoints'] and self.config['debug_mode']
        return self.config['enable_test_endpoints']
    
    def get_rate_limit(self, endpoint_type: str = 'general') -> int:
        """獲取特定端點類型的速率限制"""
        rate_limits = {
            'general': self.config['general_rate_limit'],
            'webhook': self.config['webhook_rate_limit'],
            'test': self.config['test_endpoint_rate_limit'],
        }
        return rate_limits.get(endpoint_type, self.config['general_rate_limit'])
    
    def get_max_message_length(self, is_test: bool = False) -> int:
        """獲取訊息長度限制"""
        if is_test:
            return self.config['max_test_message_length']
        return self.config['max_message_length']
    
    def should_log_security_events(self) -> bool:
        """檢查是否應該記錄安全事件"""
        return self.config['log_security_events']
    
    def get_security_headers(self) -> Dict[str, str]:
        """獲取安全標頭"""
        if not self.config['enable_security_headers']:
            return {}
        
        headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
        }
        
        # 在 HTTPS 環境中添加 HSTS
        if not self.is_development():
            headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
        
        # CSP 政策
        csp_policy = "default-src 'self'; "
        if self.is_development():
            # 開發環境較寬鬆的 CSP，允許CDN和內聯樣式
            csp_policy += "script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; font-src 'self' https://cdnjs.cloudflare.com; img-src 'self' data:;"
        else:
            # 生產環境稍微寬鬆的 CSP，允許必要的CDN
            csp_policy += "script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; font-src 'self' https://cdnjs.cloudflare.com; img-src 'self' data:;"
        
        headers['Content-Security-Policy'] = csp_policy
        
        return headers


class InputValidator:
    """優化的輸入驗證器 - 使用預編譯正則表達式"""
    
    # 🔥 關鍵優化：預編譯所有正則表達式
    _COMPILED_PATTERNS: List[Pattern] = [
        re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL),
        re.compile(r'javascript:', re.IGNORECASE),
        re.compile(r'on\w+\s*=', re.IGNORECASE),
        re.compile(r'<iframe[^>]*>.*?</iframe>', re.IGNORECASE | re.DOTALL),
        re.compile(r'<object[^>]*>.*?</object>', re.IGNORECASE | re.DOTALL),
        re.compile(r'<embed[^>]*>', re.IGNORECASE),
        re.compile(r'<link[^>]*>', re.IGNORECASE),
        re.compile(r'<meta[^>]*>', re.IGNORECASE),
        re.compile(r'<style[^>]*>.*?</style>', re.IGNORECASE | re.DOTALL),
        re.compile(r'expression\s*\(', re.IGNORECASE),
        re.compile(r'@import', re.IGNORECASE),
        re.compile(r'vbscript:', re.IGNORECASE),
        re.compile(r'<!\[CDATA\[.*?\]\]>', re.DOTALL),
        re.compile(r'eval\s*\(', re.IGNORECASE),
        re.compile(r'exec\s*\(', re.IGNORECASE),
        re.compile(r'import\s+', re.IGNORECASE),
        re.compile(r'__\w+__'),  # Python 魔法方法
        re.compile(r'\.\./', re.IGNORECASE),  # 路徑遍歷
    ]
    
    # 🔥 效能優化：用戶 ID 格式驗證預編譯
    _USER_ID_PATTERN = re.compile(r'^U[0-9a-f]{32}$')
    
    # 🔥 快取機制：常見輸入的清理結果
    _sanitize_cache: Dict[str, str] = {}
    _cache_lock = threading.Lock()
    _max_cache_size = 1000
    
    @classmethod
    def sanitize_text(cls, text: str, max_length: int = 4000) -> str:
        """
        優化的文本清理 - 使用預編譯正則表達式
        
        Args:
            text: 要清理的文本
            max_length: 最大長度限制
            
        Returns:
            清理後的文本
        """
        if not text or not isinstance(text, str):
            return ""
        
        # 🔥 快取檢查（對於常見的短文本）
        cache_key = None
        if len(text) < 200:  # 只快取短文本
            cache_key = f"{text}:{max_length}"
            with cls._cache_lock:
                if cache_key in cls._sanitize_cache:
                    return cls._sanitize_cache[cache_key]
        
        # 長度限制
        if len(text) > max_length:
            text = text[:max_length]
        
        # HTML 編碼
        text = html.escape(text)
        
        # 🔥 效能提升：使用預編譯的正則，避免重複編譯
        for pattern in cls._COMPILED_PATTERNS:
            text = pattern.sub('', text)
        
        # 移除控制字符（但保留換行和製表符）
        text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t')
        
        sanitized = text.strip()
        
        # 🔥 結果快取（控制快取大小）
        if cache_key is not None:  # 只有當我們有有效的快取鍵時才快取
            with cls._cache_lock:
                if len(cls._sanitize_cache) >= cls._max_cache_size:
                    # 簡單的 LRU：清除一半最舊的項目
                    items = list(cls._sanitize_cache.items())
                    cls._sanitize_cache = dict(items[len(items)//2:])
                cls._sanitize_cache[cache_key] = sanitized
        
        return sanitized
    
    @classmethod
    def sanitize_text_batch(cls, texts: List[str], max_length: int = 4000) -> List[str]:
        """
        批次處理多個文本 - 更高效
        
        Args:
            texts: 文本列表
            max_length: 最大長度限制
            
        Returns:
            清理後的文本列表
        """
        return [cls.sanitize_text(text, max_length) for text in texts]
    
    @classmethod
    def validate_user_id(cls, user_id: str) -> bool:
        """
        快速驗證用戶 ID 格式
        
        Args:
            user_id: 用戶 ID
            
        Returns:
            是否有效
        """
        if not isinstance(user_id, str):
            return False
        
        # 使用預編譯的正則表達式
        return bool(cls._USER_ID_PATTERN.match(user_id))
    
    @classmethod
    def validate_message_content(cls, content: str) -> Dict[str, Any]:
        """
        優化的訊息內容驗證
        
        Args:
            content: 訊息內容
            
        Returns:
            驗證結果字典
        """
        result = {
            'is_valid': True,
            'errors': [],
            'cleaned_content': content
        }
        
        if not isinstance(content, str):
            result['is_valid'] = False
            result['errors'].append('訊息必須是字符串格式')
            return result
        
        # 長度檢查
        if len(content) == 0:
            result['is_valid'] = False
            result['errors'].append('訊息不能為空')
        elif len(content) > 5000:
            result['is_valid'] = False
            result['errors'].append('訊息長度不能超過 5000 字符')
        
        # 清理內容
        result['cleaned_content'] = cls.sanitize_text(content)
        
        # 🔥 優化：使用預編譯正則檢查危險內容
        original_content = content.lower()
        for pattern in cls._COMPILED_PATTERNS:
            if pattern.search(original_content):
                result['is_valid'] = False
                result['errors'].append('訊息包含不安全的內容')
                break  # 找到一個就停止
        
        return result
    
    @classmethod
    def is_safe_content(cls, content: str) -> bool:
        """
        快速檢查內容是否安全
        
        Args:
            content: 要檢查的內容
            
        Returns:
            是否安全
        """
        if not content or not isinstance(content, str):
            return True
        
        # 使用預編譯正則快速檢查
        content_lower = content.lower()
        for pattern in cls._COMPILED_PATTERNS:
            if pattern.search(content_lower):
                return False
        
        return True
    
    @staticmethod
    def validate_json_input(data: Dict[str, Any], required_fields: List[str]) -> Dict[str, Any]:
        """驗證 JSON 輸入"""
        result = {
            'is_valid': True,
            'errors': [],
            'cleaned_data': {}
        }
        
        # 檢查必要欄位
        for field in required_fields:
            if field not in data:
                result['is_valid'] = False
                result['errors'].append(f'缺少必要欄位: {field}')
            else:
                # 清理字符串欄位
                if isinstance(data[field], str):
                    result['cleaned_data'][field] = InputValidator.sanitize_text(data[field])
                else:
                    result['cleaned_data'][field] = data[field]
        
        return result
    
    @classmethod
    def get_cache_stats(cls) -> Dict[str, int]:
        """取得快取統計資訊"""
        with cls._cache_lock:
            return {
                'cache_size': len(cls._sanitize_cache),
                'max_cache_size': cls._max_cache_size,
                'cache_usage_percent': int((len(cls._sanitize_cache) / cls._max_cache_size) * 100)
            }
    
    @classmethod
    def clear_cache(cls):
        """清空快取"""
        with cls._cache_lock:
            cls._sanitize_cache.clear()


class RateLimiter:
    """O(1) 複雜度的 Rate Limiter"""
    
    def __init__(self, cleanup_interval: int = 300, time_func=None):  # 5分鐘清理一次
        # 🔥 使用滑動窗口計數器取代時間戳列表
        self.windows: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
        self.last_cleanup = time.time()
        self.cleanup_interval = cleanup_interval
        self.lock = threading.RLock()
        self._time_func = time_func or time.time  # 保持測試兼容性
        
        # 統計資訊
        self.total_requests = 0
        self.blocked_requests = 0
    
    def is_allowed(self, client_id: str, max_requests: int = 60, window_seconds: int = 60) -> bool:
        """
        O(1) 複雜度的速率檢查
        
        Args:
            client_id: 客戶端 ID
            max_requests: 最大請求數
            window_seconds: 時間窗口（秒）
            
        Returns:
            是否允許請求
        """
        current_time = int(self._time_func())
        
        # 轉換參數格式
        requests_per_minute = max_requests if window_seconds == 60 else int(max_requests * 60 / window_seconds)
        window_minutes = max(1, window_seconds // 60)
        current_window = current_time // 60  # 以分鐘為單位的窗口
        
        with self.lock:
            self.total_requests += 1
            
            # 🔥 定期清理過期窗口（非阻塞）
            if current_time - self.last_cleanup > self.cleanup_interval:
                self._schedule_cleanup(current_window)
                self.last_cleanup = current_time
            
            # 🔥 O(1) 操作：計算當前窗口的請求數
            client_windows = self.windows[client_id]
            
            # 計算滑動窗口內的總請求數
            total_requests = 0
            for window_time in range(current_window - window_minutes + 1, current_window + 1):
                total_requests += client_windows.get(window_time, 0)
            
            # 檢查是否超過限制
            if total_requests >= requests_per_minute:
                self.blocked_requests += 1
                logger.debug(f"Rate limit exceeded for client {client_id}: {total_requests}/{requests_per_minute}")
                return False
            
            # 🔥 O(1) 操作：增加當前窗口計數
            client_windows[current_window] += 1
            return True
    
    def _schedule_cleanup(self, current_window: int):
        """非阻塞的清理排程"""
        def cleanup_worker():
            """背景清理工作"""
            cutoff_window = current_window - 5  # 保留最近5分鐘的資料
            
            with self.lock:
                clients_to_remove = []
                
                for client_id, client_windows in self.windows.items():
                    # 移除過期窗口
                    expired_windows = [w for w in client_windows.keys() if w < cutoff_window]
                    for window in expired_windows:
                        del client_windows[window]
                    
                    # 如果客戶端沒有活動窗口，標記為移除
                    if not client_windows:
                        clients_to_remove.append(client_id)
                
                # 移除無活動的客戶端
                for client_id in clients_to_remove:
                    del self.windows[client_id]
                
                logger.debug(f"RateLimiter cleanup: removed {len(clients_to_remove)} inactive clients")
        
        # 使用背景執行緒清理，避免阻塞主請求
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
    
    def reset(self):
        """重置所有請求記錄（用於測試）"""
        with self.lock:
            self.windows.clear()
            self.total_requests = 0
            self.blocked_requests = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """取得統計資訊"""
        with self.lock:
            active_clients = len(self.windows)
            success_rate = (self.total_requests - self.blocked_requests) / max(self.total_requests, 1)
            
            return {
                'total_requests': self.total_requests,
                'blocked_requests': self.blocked_requests,
                'active_clients': active_clients,
                'success_rate_percent': round(success_rate * 100, 2),
                'current_windows': sum(len(windows) for windows in self.windows.values())
            }
    
    def get_client_status(self, client_id: str) -> Dict[str, int]:
        """取得特定客戶端狀態"""
        current_window = int(self._time_func()) // 60
        
        with self.lock:
            client_windows = self.windows.get(client_id, {})
            recent_requests = sum(
                count for window, count in client_windows.items()
                if current_window - window < 5  # 最近5分鐘
            )
            
            return {
                'recent_requests_5min': recent_requests,
                'active_windows': len(client_windows),
                'last_request_window': max(client_windows.keys()) if client_windows else 0
            }


class SecurityMiddleware:
    """安全中間件 - 整合優化的組件"""
    
    def __init__(self, app=None, config=None):
        self.app = app
        self.config = config or {}
        self.rate_limiter = RateLimiter()
        self.input_validator = InputValidator()
        
        # 不同類型用戶的不同限制
        self.rate_limits = {
            'normal': 60,      # 一般用戶：60次/分鐘
            'premium': 120,    # 高級用戶：120次/分鐘
            'internal': 300,   # 內部系統：300次/分鐘
        }
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """初始化 Flask 應用"""
        app.before_request(self._before_request)
        app.after_request(self._after_request)
    
    def check_request(self, client_id: str, user_type: str = 'normal', content: str = None) -> Tuple[bool, str]:
        """
        統一的請求檢查
        
        Args:
            client_id: 客戶端 ID
            user_type: 用戶類型
            content: 請求內容
            
        Returns:
            (是否允許, 錯誤訊息)
        """
        # 1. 速率限制檢查
        rate_limit = self.rate_limits.get(user_type, 60)
        if not self.rate_limiter.is_allowed(client_id, rate_limit):
            return False, f"速率限制：每分鐘最多 {rate_limit} 次請求"
        
        # 2. 內容安全檢查
        if content:
            if not self.input_validator.is_safe_content(content):
                return False, "請求內容包含不安全元素"
        
        return True, "OK"
    
    def get_security_stats(self) -> Dict[str, Any]:
        """取得安全統計資訊"""
        return {
            'rate_limiter': self.rate_limiter.get_stats(),
            'input_validator': self.input_validator.get_cache_stats()
        }
    
    def _before_request(self):
        """請求前處理"""
        # 在測試環境中跳過某些檢查
        if request.environ.get('FLASK_ENV') == 'testing':
            return
            
        # 檢查請求頻率
        client_id = self._get_client_id()
        
        # 根據端點類型決定速率限制
        if request.endpoint in ['callback', 'webhooks_line']:
            max_requests = security_config.get_rate_limit('webhook')
        elif request.endpoint in ['ask', 'index']:
            max_requests = security_config.get_rate_limit('test')
        else:
            max_requests = security_config.get_rate_limit('general')
        
        if not self.rate_limiter.is_allowed(client_id, max_requests=max_requests):
            if security_config.should_log_security_events():
                logger.warning(f"Rate limit exceeded for client: {client_id}, endpoint: {request.endpoint}")
            abort(429)  # Too Many Requests
        
        # 檢查請求大小
        if request.content_length and request.content_length > 10 * 1024 * 1024:  # 10MB
            logger.warning(f"Request too large: {request.content_length} bytes")
            abort(413)  # Payload Too Large
        
        # 檢查 Content-Type（對於 POST 請求）
        # 豁免清單：僅允許 webhook 端點使用非 JSON 格式
        non_json_allowed_endpoints = ['callback', 'webhooks_line']
        if request.method == 'POST' and request.endpoint not in non_json_allowed_endpoints:
            if not request.is_json:
                logger.warning(f"Non-JSON POST request rejected for endpoint: {request.endpoint}")
                abort(400)
    
    def _after_request(self, response):
        """請求後處理"""
        # 在測試環境中跳過某些檢查
        if request.environ.get('FLASK_ENV') == 'testing':
            return response
            
        # 添加安全標頭
        security_headers = security_config.get_security_headers()
        for header, value in security_headers.items():
            response.headers[header] = value
        
        return response
    
    def _get_client_id(self) -> str:
        """獲取客戶端識別"""
        # 優先使用真實 IP
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if client_ip and ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
        # 結合 User-Agent 創建更唯一的識別
        user_agent = request.headers.get('User-Agent', '')
        return hashlib.sha256(f"{client_ip}:{user_agent}".encode()).hexdigest()[:16]


def verify_line_signature(signature: str, body: str, channel_secret: str) -> bool:
    """驗證 Line Webhook 簽名"""
    try:
        if not signature or not body or not channel_secret:
            return False
            
        # Line 使用 HMAC-SHA256
        expected_signature = hmac.new(
            channel_secret.encode('utf-8'),
            body.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        # Line 簽名格式檢查
        if not signature.startswith('sha256='):
            return False
        
        # 提取簽名值
        provided_signature = bytes.fromhex(signature[7:])  # 移除 'sha256=' 前綴
        
        # 安全比較
        return hmac.compare_digest(expected_signature, provided_signature)
        
    except Exception as e:
        logger.error(f"簽名驗證失敗: {e}")
        return False


def require_json_input(required_fields: List[str] = None):
    """裝飾器：要求 JSON 輸入並驗證"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not request.is_json:
                abort(400, "Content-Type must be application/json")
            
            data = request.get_json()
            if not data:
                abort(400, "Invalid JSON data")
            
            if required_fields:
                validation_result = InputValidator.validate_json_input(data, required_fields)
                if not validation_result['is_valid']:
                    abort(400, f"Validation errors: {', '.join(validation_result['errors'])}")
                
                # 將清理後的數據傳遞給視圖函數
                request.validated_json = validation_result['cleaned_data']
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def sanitize_output(data: Union[str, Dict, List]) -> Union[str, Dict, List]:
    """清理輸出數據"""
    if isinstance(data, str):
        return html.escape(data)
    elif isinstance(data, dict):
        return {key: sanitize_output(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [sanitize_output(item) for item in data]
    else:
        return data


# 全域實例
security_config = SecurityConfig()
security_middleware = SecurityMiddleware()

# 全域安全中間件實例
_security_middleware = None
_security_lock = threading.Lock()

def get_security_middleware() -> SecurityMiddleware:
    """取得全域安全中間件實例"""
    global _security_middleware
    if _security_middleware is None:
        with _security_lock:
            if _security_middleware is None:
                _security_middleware = SecurityMiddleware()
    return _security_middleware


def init_security(app, config=None):
    """初始化安全性配置"""
    security_middleware.init_app(app)
    logger.info("安全性中間件已初始化")


