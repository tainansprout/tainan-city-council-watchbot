"""
測試 Web 認證機制的單元測試
"""
import pytest
import os
import time
from unittest.mock import Mock, patch, MagicMock
from src.core.auth import TestAuth, require_test_auth, init_test_auth_with_config


class TestTestAuthClass:
    """測試 TestAuth 類別的功能"""
    
    def test_init_with_default_config(self):
        """測試使用預設配置初始化"""
        auth = TestAuth()
        
        assert auth.auth_method == 'simple_password'
        assert auth.password == 'test123'
        assert auth.username == 'admin'
        assert auth.token_expiry == 3600
    
    def test_init_with_custom_config(self):
        """測試使用自訂配置初始化"""
        config = {
            'auth': {
                'method': 'token',
                'password': 'custom_password',
                'username': 'custom_user',
                'api_token': 'custom_token',
                'token_expiry': 7200
            }
        }
        
        auth = TestAuth(config)
        
        assert auth.auth_method == 'token'
        assert auth.password == 'custom_password'
        assert auth.username == 'custom_user'
        assert auth.api_token == 'custom_token'
        assert auth.token_expiry == 7200
    
    def test_init_with_environment_variables(self):
        """測試使用環境變數初始化"""
        with patch.dict(os.environ, {
            'TEST_AUTH_METHOD': 'basic_auth',
            'TEST_PASSWORD': 'env_password',
            'TEST_USERNAME': 'env_user',
            'TEST_API_TOKEN': 'env_token'
        }):
            auth = TestAuth()
            
            assert auth.auth_method == 'basic_auth'
            assert auth.password == 'env_password'
            assert auth.username == 'env_user'
            assert auth.api_token == 'env_token'
    
    def test_verify_password(self):
        """測試密碼驗證"""
        auth = TestAuth({'auth': {'password': 'test_password'}})
        
        assert auth.verify_password('test_password') is True
        assert auth.verify_password('wrong_password') is False
    
    def test_verify_basic_auth(self):
        """測試基本認證驗證"""
        auth = TestAuth({
            'auth': {
                'username': 'test_user',
                'password': 'test_password'
            }
        })
        
        assert auth.verify_basic_auth('test_user', 'test_password') is True
        assert auth.verify_basic_auth('wrong_user', 'test_password') is False
        assert auth.verify_basic_auth('test_user', 'wrong_password') is False
    
    def test_create_and_verify_session_token(self):
        """測試建立和驗證 session token"""
        auth = TestAuth()
        
        token = auth.create_session_token()
        
        assert isinstance(token, str)
        assert len(token) > 0
        assert auth.verify_session_token(token) is True
        assert auth.verify_session_token('invalid_token') is False
    
    def test_session_token_expiry(self):
        """測試 session token 過期"""
        auth = TestAuth({'auth': {'token_expiry': 1}})  # 1 秒過期
        
        token = auth.create_session_token()
        assert auth.verify_session_token(token) is True
        
        # 等待過期
        time.sleep(1.1)
        assert auth.verify_session_token(token) is False
    
    def test_verify_api_token(self):
        """測試 API token 驗證"""
        auth = TestAuth({'auth': {'api_token': 'valid_api_token'}})
        
        assert auth.verify_api_token('valid_api_token') is True
        assert auth.verify_api_token('invalid_api_token') is False
    
    def test_cleanup_expired_tokens(self):
        """測試清理過期 token"""
        auth = TestAuth({'auth': {'token_expiry': 1}})
        
        # 建立多個 token
        token1 = auth.create_session_token()
        token2 = auth.create_session_token()
        
        assert len(auth._active_tokens) == 2
        
        # 等待過期
        time.sleep(1.1)
        
        # 建立新 token 會觸發清理
        token3 = auth.create_session_token()
        
        # 應該只剩下新 token
        assert len(auth._active_tokens) == 1
        assert auth.verify_session_token(token3) is True
        assert auth.verify_session_token(token1) is False
        assert auth.verify_session_token(token2) is False
    
    def test_generate_login_form(self):
        """測試生成登入表單"""
        auth = TestAuth({'app': {'name': '測試應用程式'}})
        
        with patch('src.core.auth.render_template') as mock_render:
            mock_render.return_value = '<html>登入表單</html>'
            
            result = auth.generate_login_form('錯誤訊息')
            
            mock_render.assert_called_once_with(
                'login.html',
                error_message='錯誤訊息',
                app_name='測試應用程式'
            )
            assert result == '<html>登入表單</html>'
    
    def test_get_auth_info(self):
        """測試取得認證資訊"""
        # 測試簡單密碼認證
        auth = TestAuth({'auth': {'method': 'simple_password', 'password': 'test123'}})
        info = auth.get_auth_info()
        
        assert info['method'] == 'simple_password'
        assert '登入頁面' in info['description']
        
        # 測試基本認證
        auth = TestAuth({'auth': {'method': 'basic_auth'}})
        info = auth.get_auth_info()
        
        assert info['method'] == 'basic_auth'
        assert 'Basic Authentication' in info['description']
        
        # 測試 token 認證
        auth = TestAuth({'auth': {'method': 'token'}})
        info = auth.get_auth_info()
        
        assert info['method'] == 'token'
        assert 'Bearer token' in info['description']


class TestAuthDecorator:
    """測試認證裝飾器"""
    
    def setup_method(self):
        """每個測試前的設定"""
        # 重設全域認證實例
        import src.core.auth
        src.core.auth.test_auth = None
    
    def test_require_test_auth_simple_password(self):
        """測試簡單密碼認證裝飾器"""
        # 初始化認證
        config = {'auth': {'method': 'simple_password', 'password': 'test123'}}
        init_test_auth_with_config(config)
        
        @require_test_auth
        def protected_view():
            return "受保護的內容"
        
        # 模擬 Flask request
        with patch('src.core.auth.request') as mock_request, \
             patch('src.core.auth.session') as mock_session:
            
            # 測試未登入
            mock_session.__contains__ = Mock(return_value=False)
            mock_request.method = 'GET'
            
            with patch('src.core.auth.test_auth.generate_login_form') as mock_form:
                mock_form.return_value = "登入表單"
                result = protected_view()
                assert result == "登入表單"
            
            # 測試已登入
            mock_session.__contains__ = Mock(return_value=True)
            mock_session.__getitem__ = Mock(return_value=True)
            
            result = protected_view()
            assert result == "受保護的內容"
    
    def test_require_test_auth_with_post_login(self):
        """測試 POST 登入請求"""
        config = {'auth': {'method': 'simple_password', 'password': 'test123'}}
        init_test_auth_with_config(config)
        
        @require_test_auth
        def protected_view():
            return "受保護的內容"
        
        with patch('src.core.auth.request') as mock_request, \
             patch('src.core.auth.session') as mock_session:
            
            # 模擬 POST 請求
            mock_request.method = 'POST'
            mock_request.form = Mock()
            mock_session.__contains__ = Mock(return_value=False)
            
            # 測試正確密碼
            mock_request.form.get.return_value = 'test123'
            mock_session.__setitem__ = Mock()
            
            result = protected_view()
            assert result == "受保護的內容"
            
            # 測試錯誤密碼
            mock_request.form.get.return_value = 'wrong_password'
            
            with patch('src.core.auth.test_auth.generate_login_form') as mock_form:
                mock_form.return_value = ("錯誤表單", 401)
                result = protected_view()
                assert result == ("錯誤表單", 401)
    
    def test_require_test_auth_basic_auth(self):
        """測試基本認證裝飾器"""
        config = {
            'auth': {
                'method': 'basic_auth',
                'username': 'admin',
                'password': 'password'
            }
        }
        init_test_auth_with_config(config)
        
        @require_test_auth
        def protected_view():
            return "受保護的內容"
        
        with patch('src.core.auth.request') as mock_request:
            # 測試無認證
            mock_request.authorization = None
            mock_request.environ = {}
            
            result = protected_view()
            assert isinstance(result, tuple)
            assert result[1] == 401  # 狀態碼
            
            # 測試正確認證
            mock_auth = Mock()
            mock_auth.username = 'admin'
            mock_auth.password = 'password'
            mock_request.authorization = mock_auth
            
            result = protected_view()
            assert result == "受保護的內容"
    
    def test_require_test_auth_token(self):
        """測試 token 認證裝飾器"""
        config = {
            'auth': {
                'method': 'token',
                'api_token': 'valid_token'
            }
        }
        init_test_auth_with_config(config)
        
        @require_test_auth
        def protected_view():
            return "受保護的內容"
        
        with patch('src.core.auth.request') as mock_request, \
             patch('src.core.auth.jsonify') as mock_jsonify:
            
            mock_request.environ = {}
            
            # 測試無 token
            mock_request.headers = {}
            mock_jsonify.return_value = {"error": "需要認證"}
            
            result = protected_view()
            assert isinstance(result, tuple)
            assert result[1] == 401
            
            # 測試無效 token
            mock_request.headers = {'Authorization': 'Bearer invalid_token'}
            
            result = protected_view()
            assert isinstance(result, tuple)
            assert result[1] == 401
            
            # 測試有效 token
            mock_request.headers = {'Authorization': 'Bearer valid_token'}
            
            result = protected_view()
            assert result == "受保護的內容"
    
    def test_testing_environment_bypass(self):
        """測試在測試環境中繞過認證"""
        config = {'auth': {'method': 'simple_password', 'password': 'test123'}}
        init_test_auth_with_config(config)
        
        @require_test_auth
        def protected_view():
            return "受保護的內容"
        
        with patch('src.core.auth.request') as mock_request:
            # 設定測試環境
            mock_request.environ = {'FLASK_ENV': 'testing'}
            
            result = protected_view()
            assert result == "受保護的內容"


class TestAuthConfiguration:
    """測試認證配置"""
    
    def test_init_test_auth_with_config(self):
        """測試使用配置初始化認證"""
        config = {
            'auth': {
                'method': 'basic_auth',
                'username': 'test_user',
                'password': 'test_password'
            }
        }
        
        auth = init_test_auth_with_config(config)
        
        assert auth is not None
        assert auth.auth_method == 'basic_auth'
        assert auth.username == 'test_user'
        assert auth.password == 'test_password'
    
    def test_auth_status_info(self):
        """測試取得認證狀態資訊"""
        from src.core.auth import get_auth_status_info
        
        config = {'auth': {'method': 'simple_password'}}
        init_test_auth_with_config(config)
        
        status = get_auth_status_info()
        
        assert 'auth_method' in status
        assert 'active_sessions' in status
        assert 'auth_required' in status
        assert status['auth_method'] == 'simple_password'
        assert status['auth_required'] is True