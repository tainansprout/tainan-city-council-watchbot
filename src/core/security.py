"""
安全性模組：提供安全配置、輸入驗證、清理和安全檢查功能

此模組整合了所有安全相關功能：
- SecurityConfig: 安全配置管理
- InputValidator: 輸入驗證和清理
- RateLimiter: 速率限制
- SecurityMiddleware: 安全中間件
- 各種安全工具函數

架構說明：
- 統一管理所有安全相關功能，避免分散
- 提供完整的安全防護層
- 支援開發和生產環境的不同安全策略
"""

import re
import html
import json
import hashlib
import hmac
import time
import os
from typing import Dict, Any, Optional, List, Union
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
    """輸入驗證器"""
    
    # 常見的危險模式
    DANGEROUS_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # XSS 腳本
        r'javascript:',               # JavaScript 協議
        r'on\w+\s*=',                # 事件處理器
        r'eval\s*\(',                # eval 函數
        r'exec\s*\(',                # exec 函數
        r'import\s+',                # Python import
        r'__\w+__',                  # Python 魔法方法
        r'\.\./',                    # 路徑遍歷
        r'<iframe[^>]*>',           # iframe 標籤
        r'<object[^>]*>',           # object 標籤
        r'<embed[^>]*>',            # embed 標籤
    ]
    
    @staticmethod
    def sanitize_text(text: str, max_length: int = 4000) -> str:
        """清理文本輸入"""
        if not isinstance(text, str):
            return ""
        
        # 長度限制
        if len(text) > max_length:
            text = text[:max_length]
        
        # HTML 編碼
        text = html.escape(text)
        
        # 移除危險模式
        for pattern in InputValidator.DANGEROUS_PATTERNS:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
        
        # 移除控制字符（但保留換行和製表符）
        text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t')
        
        return text.strip()
    
    @staticmethod
    def validate_user_id(user_id: str) -> bool:
        """驗證用戶 ID 格式"""
        if not isinstance(user_id, str):
            return False
        
        # Line 用戶 ID 格式驗證
        pattern = r'^U[0-9a-f]{32}$'
        return bool(re.match(pattern, user_id))
    
    @staticmethod
    def validate_message_content(content: str) -> Dict[str, Any]:
        """驗證訊息內容"""
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
        result['cleaned_content'] = InputValidator.sanitize_text(content)
        
        # 檢查是否包含危險內容
        for pattern in InputValidator.DANGEROUS_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                result['is_valid'] = False
                result['errors'].append('訊息包含不安全的內容')
                break
        
        return result
    
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


class RateLimiter:
    """請求頻率限制器"""
    
    def __init__(self):
        self._requests = {}  # {client_id: [timestamp, ...]}
        self._cleanup_interval = 3600  # 1 小時清理一次
        self._last_cleanup = time.time()
    
    def is_allowed(self, client_id: str, max_requests: int = 60, window_seconds: int = 60) -> bool:
        """檢查是否允許請求"""
        now = time.time()
        
        # 定期清理過期記錄
        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup_old_requests(now - window_seconds * 2)
            self._last_cleanup = now
        
        # 初始化客戶端記錄
        if client_id not in self._requests:
            self._requests[client_id] = []
        
        # 移除過期請求
        window_start = now - window_seconds
        self._requests[client_id] = [
            timestamp for timestamp in self._requests[client_id]
            if timestamp > window_start
        ]
        
        # 檢查頻率限制
        if len(self._requests[client_id]) >= max_requests:
            return False
        
        # 記錄新請求
        self._requests[client_id].append(now)
        return True
    
    def _cleanup_old_requests(self, cutoff_time: float):
        """清理過期的請求記錄"""
        for client_id in list(self._requests.keys()):
            self._requests[client_id] = [
                timestamp for timestamp in self._requests[client_id]
                if timestamp > cutoff_time
            ]
            if not self._requests[client_id]:
                del self._requests[client_id]


class SecurityMiddleware:
    """安全中間件"""
    
    def __init__(self, app=None, config=None):
        self.app = app
        self.config = config or {}
        self.rate_limiter = RateLimiter()
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """初始化 Flask 應用"""
        app.before_request(self._before_request)
        app.after_request(self._after_request)
    
    def _before_request(self):
        """請求前處理"""
        # 在測試環境中跳過某些檢查
        if request.environ.get('FLASK_ENV') == 'testing':
            return
            
        # 使用模組內的 security_config 實例
        
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
            
        # 使用模組內的 security_config 實例
        
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


def init_security(app, config=None):
    """初始化安全性配置"""
    security_middleware.init_app(app)
    logger.info("安全性中間件已初始化")