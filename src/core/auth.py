"""
測試端點認證模組
提供多種認證方式保護測試介面
"""

import os
import hashlib
import secrets
import time
from functools import wraps
from typing import Optional, Dict, Any
from flask import request, abort, session, jsonify, render_template, current_app


class TestAuth:
    """測試端點認證類"""
    
    def __init__(self, config=None):
        # 優先從 config.yml 讀取設定，其次從環境變數，最後使用預設值
        self.config = config
        auth_config = config.get('auth', {}) if config else {}
        
        self.auth_method = (
            auth_config.get('method') or 
            os.getenv('TEST_AUTH_METHOD', 'simple_password')
        )
        
        self.password = (
            auth_config.get('password') or 
            os.getenv('TEST_PASSWORD', 'test123')
        )
        
        self.username = (
            auth_config.get('username') or 
            os.getenv('TEST_USERNAME', 'admin')
        )
        
        self.secret_key = (
            auth_config.get('secret_key') or 
            os.getenv('TEST_SECRET_KEY', secrets.token_urlsafe(32))
        )
        
        self.api_token = (
            auth_config.get('api_token') or 
            os.getenv('TEST_API_TOKEN', secrets.token_urlsafe(16))
        )
        
        # Token 有效期（秒）
        self.token_expiry = int(
            auth_config.get('token_expiry', 3600) or 
            os.getenv('TEST_TOKEN_EXPIRY', '3600')
        )
        
        # 儲存活躍的 tokens {token: expiry_time}
        self._active_tokens = {}
    
    def generate_login_form(self, error_message: str = "") -> str:
        """生成登入表單"""
        app_name = self.config.get('app', {}).get('name', '聊天機器人') if self.config else '聊天機器人'
        return render_template('login.html', error_message=error_message, app_name=app_name)
    
    def verify_password(self, password: str) -> bool:
        """驗證密碼"""
        return password == self.password
    
    def verify_basic_auth(self, username: str, password: str) -> bool:
        """驗證基本認證"""
        return username == self.username and password == self.password
    
    def create_session_token(self) -> str:
        """創建 session token"""
        token = secrets.token_urlsafe(32)
        expiry = time.time() + self.token_expiry
        self._active_tokens[token] = expiry
        
        # 清理過期 tokens
        self._cleanup_expired_tokens()
        
        return token
    
    def verify_session_token(self, token: str) -> bool:
        """驗證 session token"""
        if not token or token not in self._active_tokens:
            return False
        
        # 檢查是否過期
        if time.time() > self._active_tokens[token]:
            del self._active_tokens[token]
            return False
        
        return True
    
    def verify_api_token(self, token: str) -> bool:
        """驗證 API token"""
        return token == self.api_token
    
    def _cleanup_expired_tokens(self):
        """清理過期的 tokens"""
        current_time = time.time()
        expired_tokens = [
            token for token, expiry in self._active_tokens.items()
            if current_time > expiry
        ]
        for token in expired_tokens:
            del self._active_tokens[token]
    
    def get_auth_info(self) -> Dict[str, Any]:
        """獲取認證資訊（用於文檔說明）"""
        info = {
            'method': self.auth_method,
            'description': '',
            'example': ''
        }
        
        if self.auth_method == 'simple_password':
            info['description'] = '在登入頁面輸入密碼'
            info['example'] = f'密碼: {self.password if os.getenv("FLASK_ENV") == "development" else "請查看環境變數"}'
        elif self.auth_method == 'basic_auth':
            info['description'] = 'HTTP Basic Authentication'
            info['example'] = f'用戶名: {self.username}, 密碼: {self.password if os.getenv("FLASK_ENV") == "development" else "請查看環境變數"}'
        elif self.auth_method == 'token':
            info['description'] = '在 Authorization 標頭中提供 Bearer token'
            info['example'] = f'Authorization: Bearer {self.api_token if os.getenv("FLASK_ENV") == "development" else "請查看環境變數"}'
        
        return info


# 全域認證實例 - 延遲初始化
test_auth = None

def init_test_auth_with_config(config):
    """使用配置初始化全域認證實例"""
    global test_auth
    test_auth = TestAuth(config)
    return test_auth


def require_test_auth(f):
    """
    測試端點認證裝飾器
    支援多種認證方式：
    1. simple_password: 簡單密碼 + session
    2. basic_auth: HTTP Basic Authentication  
    3. token: API Token (Bearer)
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_method = test_auth.auth_method
        
        if auth_method == 'simple_password':
            return _handle_simple_password_auth(f, *args, **kwargs)
        elif auth_method == 'basic_auth':
            return _handle_basic_auth(f, *args, **kwargs)
        elif auth_method == 'token':
            return _handle_token_auth(f, *args, **kwargs)
        else:
            # 預設為簡單密碼認證
            return _handle_simple_password_auth(f, *args, **kwargs)
    
    return decorated_function


def _handle_simple_password_auth(f, *args, **kwargs):
    """處理簡單密碼認證"""
    # 在測試環境中跳過認證
    if (request.environ.get('FLASK_ENV') == 'testing' or current_app.config.get('TESTING', False)):
        return f(*args, **kwargs)
        
    # 檢查是否已登入（session）
    if 'test_authenticated' in session and session['test_authenticated']:
        return f(*args, **kwargs)
    
    # 處理登入請求
    if request.method == 'POST':
        password = request.form.get('password', '')
        if test_auth.verify_password(password):
            session['test_authenticated'] = True
            session.permanent = True
            return f(*args, **kwargs)
        else:
            return test_auth.generate_login_form("密碼錯誤，請重試"), 401
    
    # 顯示登入表單
    return test_auth.generate_login_form()


def _handle_basic_auth(f, *args, **kwargs):
    """處理 HTTP Basic 認證"""
    # 在測試環境中跳過認證
    if (request.environ.get('FLASK_ENV') == 'testing' or current_app.config.get('TESTING', False)):
        return f(*args, **kwargs)
        
    auth = request.authorization
    if not auth or not test_auth.verify_basic_auth(auth.username, auth.password):
        return jsonify({'error': '需要認證'}), 401, {
            'WWW-Authenticate': 'Basic realm="Test Interface"'
        }
    return f(*args, **kwargs)


def _handle_token_auth(f, *args, **kwargs):
    """處理 Token 認證"""
    # 在測試環境中跳過認證
    if (request.environ.get('FLASK_ENV') == 'testing' or current_app.config.get('TESTING', False)):
        return f(*args, **kwargs)
        
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'error': '需要 Bearer token 認證'}), 401
    
    token = auth_header[7:]  # 移除 'Bearer ' 前綴
    if not test_auth.verify_api_token(token):
        return jsonify({'error': 'Invalid token'}), 401
    
    return f(*args, **kwargs)


def init_test_auth(app):
    """初始化測試認證"""
    app.secret_key = test_auth.secret_key
    
    # 設定 session 配置
    app.config.update(
        PERMANENT_SESSION_LIFETIME=test_auth.token_expiry,
        SESSION_COOKIE_SECURE=False,  # 允許 HTTP 連接（開發環境）
        SESSION_COOKIE_HTTPONLY=True,  # 防止 XSS
        SESSION_COOKIE_SAMESITE='Lax'  # CSRF 保護
    )
    
    from .logger import get_logger
    logger = get_logger(__name__)
    logger.info(f"測試認證已初始化，方式: {test_auth.auth_method}")


def get_auth_status_info():
    """獲取認證狀態資訊（用於健康檢查等）"""
    return {
        'auth_method': test_auth.auth_method,
        'active_sessions': len(test_auth._active_tokens),
        'auth_required': True
    }