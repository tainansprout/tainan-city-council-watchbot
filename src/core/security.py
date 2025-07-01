"""
安全性模組：提供輸入驗證、清理和安全檢查功能
"""

import re
import html
import json
import hashlib
import hmac
import time
from typing import Dict, Any, Optional, List, Union
from functools import wraps
from flask import request, abort, current_app
from src.core.logger import logger


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
            
        from .security_config import security_config
        
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
        if request.method == 'POST' and request.endpoint not in ['callback', 'webhooks_line', 'index']:
            if not request.is_json:
                logger.warning("Non-JSON POST request rejected")
                abort(400)
    
    def _after_request(self, response):
        """請求後處理"""
        # 在測試環境中跳過某些檢查
        if request.environ.get('FLASK_ENV') == 'testing':
            return response
            
        from .security_config import security_config
        
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


# 全域安全中間件實例
security_middleware = SecurityMiddleware()


def init_security(app, config=None):
    """初始化安全性配置"""
    security_middleware.init_app(app)
    logger.info("安全性中間件已初始化")