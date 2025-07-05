"""
測試核心安全模組的單元測試
"""
import pytest
import os
import time
import hashlib
import hmac
from unittest.mock import Mock, patch, MagicMock
from flask import Flask, request, abort
from src.core.security import (
    SecurityConfig, InputValidator, RateLimiter, SecurityMiddleware,
    verify_line_signature, require_json_input, sanitize_output,
    security_config, security_middleware, init_security
)


class TestSecurityConfig:
    """測試 SecurityConfig 類"""
    
    def test_security_config_initialization(self):
        """測試 SecurityConfig 初始化"""
        config = SecurityConfig()
        
        assert isinstance(config.config, dict)
        assert 'enable_test_endpoints' in config.config
        assert 'general_rate_limit' in config.config
        assert 'max_message_length' in config.config
    
    def test_load_security_config_with_env_vars(self):
        """測試從環境變數載入配置"""
        with patch.dict(os.environ, {
            'ENABLE_TEST_ENDPOINTS': 'false',
            'GENERAL_RATE_LIMIT': '120',
            'MAX_MESSAGE_LENGTH': '8000',
            'FLASK_ENV': 'development'
        }):
            config = SecurityConfig()
            
            assert config.config['enable_test_endpoints'] is False
            assert config.config['general_rate_limit'] == 120
            assert config.config['max_message_length'] == 8000
            assert config.config['environment'] == 'development'
    
    def test_is_development(self):
        """測試開發環境檢測"""
        with patch.dict(os.environ, {'FLASK_ENV': 'development'}):
            config = SecurityConfig()
            assert config.is_development() is True
        
        with patch.dict(os.environ, {'FLASK_ENV': 'dev'}):
            config = SecurityConfig()
            assert config.is_development() is True
        
        with patch.dict(os.environ, {'FLASK_ENV': 'production'}):
            config = SecurityConfig()
            assert config.is_development() is False
    
    def test_is_production(self):
        """測試生產環境檢測"""
        with patch.dict(os.environ, {'FLASK_ENV': 'production'}):
            config = SecurityConfig()
            assert config.is_production() is True
        
        with patch.dict(os.environ, {'FLASK_ENV': 'prod'}):
            config = SecurityConfig()
            assert config.is_production() is True
        
        with patch.dict(os.environ, {'FLASK_ENV': 'development'}):
            config = SecurityConfig()
            assert config.is_production() is False
    
    def test_should_enable_test_endpoints_development(self):
        """測試開發環境的測試端點啟用邏輯"""
        with patch.dict(os.environ, {
            'FLASK_ENV': 'development',
            'ENABLE_TEST_ENDPOINTS': 'true'
        }):
            config = SecurityConfig()
            assert config.should_enable_test_endpoints() is True
        
        with patch.dict(os.environ, {
            'FLASK_ENV': 'development',
            'ENABLE_TEST_ENDPOINTS': 'false'
        }):
            config = SecurityConfig()
            assert config.should_enable_test_endpoints() is False
    
    def test_should_enable_test_endpoints_production(self):
        """測試生產環境的測試端點啟用邏輯"""
        with patch.dict(os.environ, {
            'FLASK_ENV': 'production',
            'ENABLE_TEST_ENDPOINTS': 'true',
            'FLASK_DEBUG': 'true'
        }):
            config = SecurityConfig()
            assert config.should_enable_test_endpoints() is True
        
        with patch.dict(os.environ, {
            'FLASK_ENV': 'production',
            'ENABLE_TEST_ENDPOINTS': 'true',
            'FLASK_DEBUG': 'false'
        }):
            config = SecurityConfig()
            assert config.should_enable_test_endpoints() is False
    
    def test_get_rate_limit(self):
        """測試獲取速率限制"""
        config = SecurityConfig()
        
        assert config.get_rate_limit('general') == config.config['general_rate_limit']
        assert config.get_rate_limit('webhook') == config.config['webhook_rate_limit']
        assert config.get_rate_limit('test') == config.config['test_endpoint_rate_limit']
        assert config.get_rate_limit('unknown') == config.config['general_rate_limit']
    
    def test_get_max_message_length(self):
        """測試獲取訊息長度限制"""
        config = SecurityConfig()
        
        assert config.get_max_message_length(is_test=False) == config.config['max_message_length']
        assert config.get_max_message_length(is_test=True) == config.config['max_test_message_length']
    
    def test_should_log_security_events(self):
        """測試是否記錄安全事件"""
        with patch.dict(os.environ, {'LOG_SECURITY_EVENTS': 'true'}):
            config = SecurityConfig()
            assert config.should_log_security_events() is True
        
        with patch.dict(os.environ, {'LOG_SECURITY_EVENTS': 'false'}):
            config = SecurityConfig()
            assert config.should_log_security_events() is False
    
    def test_get_security_headers_disabled(self):
        """測試禁用安全標頭"""
        with patch.dict(os.environ, {'ENABLE_SECURITY_HEADERS': 'false'}):
            config = SecurityConfig()
            headers = config.get_security_headers()
            assert headers == {}
    
    def test_get_security_headers_development(self):
        """測試開發環境的安全標頭"""
        with patch.dict(os.environ, {
            'FLASK_ENV': 'development',
            'ENABLE_SECURITY_HEADERS': 'true'
        }):
            config = SecurityConfig()
            headers = config.get_security_headers()
            
            assert 'X-Content-Type-Options' in headers
            assert 'X-Frame-Options' in headers
            assert 'Content-Security-Policy' in headers
            assert 'Strict-Transport-Security' not in headers  # 開發環境不包含
    
    def test_get_security_headers_production(self):
        """測試生產環境的安全標頭"""
        with patch.dict(os.environ, {
            'FLASK_ENV': 'production',
            'ENABLE_SECURITY_HEADERS': 'true'
        }):
            config = SecurityConfig()
            headers = config.get_security_headers()
            
            assert 'X-Content-Type-Options' in headers
            assert 'X-Frame-Options' in headers
            assert 'Content-Security-Policy' in headers
            assert 'Strict-Transport-Security' in headers  # 生產環境包含


class TestInputValidator:
    """測試 InputValidator 類"""
    
    def test_sanitize_text_basic(self):
        """測試基本文字清理"""
        text = "Hello World!"
        result = InputValidator.sanitize_text(text)
        assert result == "Hello World!"
    
    def test_sanitize_text_html_escape(self):
        """測試 HTML 轉義"""
        text = "<script>alert('xss')</script>"
        result = InputValidator.sanitize_text(text)
        assert '<script>' not in result
        assert '&lt;' in result or result == ""  # 要么轉義要么移除
    
    def test_sanitize_text_length_limit(self):
        """測試長度限制"""
        long_text = "A" * 5000
        result = InputValidator.sanitize_text(long_text, max_length=100)
        assert len(result) <= 100
    
    def test_sanitize_text_dangerous_patterns(self):
        """測試危險模式移除"""
        dangerous_inputs = [
            "javascript:alert('test')",
            "onclick='malicious()'",
            "eval('code')",
            "../../../etc/passwd",
            "<iframe src='evil'></iframe>"
        ]
        
        for dangerous_input in dangerous_inputs:
            result = InputValidator.sanitize_text(dangerous_input)
            # 危險內容應該被移除或轉義
            assert len(result) < len(dangerous_input) or '&lt;' in result or '&#x27;' in result
    
    def test_sanitize_text_control_characters(self):
        """測試控制字符移除"""
        text_with_control = "Hello\x00\x01World\n\tTest"
        result = InputValidator.sanitize_text(text_with_control)
        assert '\x00' not in result
        assert '\x01' not in result
        assert '\n' in result  # 保留換行
        assert '\t' in result  # 保留製表符
    
    def test_sanitize_text_non_string_input(self):
        """測試非字符串輸入"""
        assert InputValidator.sanitize_text(None) == ""
        assert InputValidator.sanitize_text(123) == ""
        assert InputValidator.sanitize_text([]) == ""
    
    def test_validate_user_id_valid(self):
        """測試有效的用戶 ID"""
        valid_user_ids = [
            "U" + "a" * 32,
            "U" + "0" * 32,
            "U" + "f" * 32,
            "U1234567890abcdef1234567890abcdef"
        ]
        
        for user_id in valid_user_ids:
            assert InputValidator.validate_user_id(user_id) is True
    
    def test_validate_user_id_invalid(self):
        """測試無效的用戶 ID"""
        invalid_user_ids = [
            "invalid",
            "U123",  # 太短
            "u" + "a" * 32,  # 小寫 u
            "U" + "g" * 32,  # 包含無效字符
            "U" + "a" * 31,  # 長度不足
            "U" + "a" * 33,  # 長度過長
            None,
            123
        ]
        
        for user_id in invalid_user_ids:
            assert InputValidator.validate_user_id(user_id) is False
    
    def test_validate_message_content_valid(self):
        """測試有效的訊息內容"""
        content = "Hello, this is a valid message!"
        result = InputValidator.validate_message_content(content)
        
        assert result['is_valid'] is True
        assert result['errors'] == []
        assert result['cleaned_content'] == content
    
    def test_validate_message_content_empty(self):
        """測試空訊息內容"""
        result = InputValidator.validate_message_content("")
        
        assert result['is_valid'] is False
        assert "訊息不能為空" in result['errors']
    
    def test_validate_message_content_too_long(self):
        """測試過長的訊息內容"""
        long_content = "A" * 6000
        result = InputValidator.validate_message_content(long_content)
        
        assert result['is_valid'] is False
        assert "訊息長度不能超過 5000 字符" in result['errors']
    
    def test_validate_message_content_dangerous(self):
        """測試包含危險內容的訊息"""
        dangerous_content = "<script>alert('xss')</script>"
        result = InputValidator.validate_message_content(dangerous_content)
        
        assert result['is_valid'] is False
        assert "訊息包含不安全的內容" in result['errors']
    
    def test_validate_message_content_non_string(self):
        """測試非字符串訊息內容"""
        result = InputValidator.validate_message_content(123)
        
        assert result['is_valid'] is False
        assert "訊息必須是字符串格式" in result['errors']
    
    def test_validate_json_input_valid(self):
        """測試有效的 JSON 輸入"""
        data = {"name": "John", "message": "Hello"}
        required_fields = ["name", "message"]
        result = InputValidator.validate_json_input(data, required_fields)
        
        assert result['is_valid'] is True
        assert result['errors'] == []
        assert result['cleaned_data']['name'] == "John"
        assert result['cleaned_data']['message'] == "Hello"
    
    def test_validate_json_input_missing_fields(self):
        """測試缺少必要欄位的 JSON 輸入"""
        data = {"name": "John"}
        required_fields = ["name", "message"]
        result = InputValidator.validate_json_input(data, required_fields)
        
        assert result['is_valid'] is False
        assert "缺少必要欄位: message" in result['errors']
    
    def test_validate_json_input_string_cleaning(self):
        """測試 JSON 輸入的字符串清理"""
        data = {"message": "<script>alert('test')</script>"}
        required_fields = ["message"]
        result = InputValidator.validate_json_input(data, required_fields)
        
        # 字符串應該被清理
        assert '<script>' not in result['cleaned_data']['message']


class TestRateLimiter:
    """測試 RateLimiter 類"""
    
    def test_rate_limiter_initialization(self):
        """測試 RateLimiter 初始化"""
        limiter = RateLimiter()
        
        assert limiter._requests == {}
        assert limiter._cleanup_interval == 3600
        assert isinstance(limiter._last_cleanup, float)
    
    def test_is_allowed_first_request(self):
        """測試第一次請求"""
        with patch('time.time', return_value=1000.0):
            limiter = RateLimiter()
            
            assert limiter.is_allowed("client_1", max_requests=10) is True
            assert "client_1" in limiter._requests
            assert len(limiter._requests["client_1"]) == 1
    
    def test_is_allowed_within_limit(self):
        """測試在限制內的請求"""
        with patch('time.time', return_value=1000.0):
            limiter = RateLimiter()
            
            # 發送 5 個請求（限制為 10）
            for i in range(5):
                assert limiter.is_allowed("client_1", max_requests=10) is True
            
            assert len(limiter._requests["client_1"]) == 5
    
    def test_is_allowed_exceeds_limit(self):
        """測試超過限制的請求"""
        with patch('time.time', return_value=1000.0):
            limiter = RateLimiter()
            
            # 發送到達限制的請求
            for i in range(3):
                assert limiter.is_allowed("client_1", max_requests=3) is True
            
            # 第 4 個請求應該被拒絕
            assert limiter.is_allowed("client_1", max_requests=3) is False
    
    def test_is_allowed_window_expiry(self):
        """測試時間窗口過期"""
        # 使用非常短的時間窗口進行測試
        with patch('time.time') as mock_time:
            # 第一個請求在時間 0
            mock_time.return_value = 0
            limiter = RateLimiter()
            assert limiter.is_allowed("client_1", max_requests=1, window_seconds=1) is True
            
            # 第二個請求在時間 0.5（仍在窗口內）
            mock_time.return_value = 0.5
            assert limiter.is_allowed("client_1", max_requests=1, window_seconds=1) is False
            
            # 第三個請求在時間 2（窗口外）
            mock_time.return_value = 2
            assert limiter.is_allowed("client_1", max_requests=1, window_seconds=1) is True
    
    def test_cleanup_old_requests(self):
        """測試清理過期請求"""
        limiter = RateLimiter()
        
        # 添加一些請求記錄
        limiter._requests["client_1"] = [1000, 2000, 3000]
        limiter._requests["client_2"] = [500, 1500]
        
        # 清理 2500 之前的請求
        limiter._cleanup_old_requests(2500)
        
        assert limiter._requests["client_1"] == [3000]
        assert "client_2" not in limiter._requests  # 所有請求都被清理，客戶端被移除
    
    def test_automatic_cleanup(self):
        """測試自動清理機制"""
        with patch('time.time') as mock_time:
            # 設定初始時間
            mock_time.return_value = 1000
            limiter = RateLimiter()
            limiter._last_cleanup = 1000
            
            # 第一個請求
            assert limiter.is_allowed("client_1", max_requests=10) is True
            
            # 時間超過清理間隔
            mock_time.return_value = 1000 + 3601  # 超過 1 小時
            
            with patch.object(limiter, '_cleanup_old_requests') as mock_cleanup:
                limiter.is_allowed("client_1", max_requests=10)
                mock_cleanup.assert_called_once()


class TestSecurityMiddleware:
    """測試 SecurityMiddleware 類"""
    
    @pytest.fixture
    def app(self):
        """創建測試 Flask 應用"""
        app = Flask(__name__)
        app.config['TESTING'] = True
        
        @app.route('/test', methods=['GET', 'POST'])
        def test_endpoint():
            return 'OK'
        
        @app.route('/callback', methods=['POST'])
        def callback():
            return 'Webhook OK'
        
        return app
    
    def test_security_middleware_initialization(self):
        """測試 SecurityMiddleware 初始化"""
        middleware = SecurityMiddleware()
        
        assert middleware.app is None
        assert middleware.config == {}
        assert isinstance(middleware.rate_limiter, RateLimiter)
    
    def test_init_app(self, app):
        """測試初始化 Flask 應用"""
        middleware = SecurityMiddleware()
        middleware.init_app(app)
        
        # 檢查是否註冊了請求處理器
        assert len(app.before_request_funcs[None]) > 0
        assert len(app.after_request_funcs[None]) > 0
    
    def test_get_client_id(self, app):
        """測試獲取客戶端 ID"""
        middleware = SecurityMiddleware()
        
        with app.test_request_context('/', headers={
            'X-Forwarded-For': '192.168.1.1',
            'User-Agent': 'TestAgent'
        }):
            client_id = middleware._get_client_id()
            assert isinstance(client_id, str)
            assert len(client_id) == 16
    
    def test_get_client_id_multiple_forwarded_ips(self, app):
        """測試多個轉發 IP 的處理"""
        middleware = SecurityMiddleware()
        
        with app.test_request_context('/', headers={
            'X-Forwarded-For': '192.168.1.1, 10.0.0.1, 172.16.0.1',
            'User-Agent': 'TestAgent'
        }):
            client_id = middleware._get_client_id()
            assert isinstance(client_id, str)
            # 應該使用第一個 IP
            expected_hash = hashlib.sha256("192.168.1.1:TestAgent".encode()).hexdigest()[:16]
            assert client_id == expected_hash
    
    def test_before_request_testing_env(self, app):
        """測試在測試環境中跳過檢查"""
        middleware = SecurityMiddleware()
        middleware.init_app(app)
        
        with app.test_client() as client:
            with app.test_request_context('/', environ_base={'FLASK_ENV': 'testing'}):
                # 在測試環境中，before_request 應該返回 None（跳過檢查）
                # 由於 Flask 的測試環境會自動設定，我們需要驗證方法被調用但不拋出異常
                try:
                    result = middleware._before_request()
                    # 如果沒有拋出異常，就算通過
                    assert True
                except Exception:
                    # 如果拋出異常則失敗
                    assert False, "Should not raise exception in testing environment"
    
    def test_before_request_large_payload(self, app):
        """測試大型載荷檢查"""
        middleware = SecurityMiddleware()
        middleware.init_app(app)
        
        with app.test_client() as client:
            with app.test_request_context('/', content_length=20*1024*1024, environ_base={'FLASK_ENV': 'production'}):  # 20MB
                with pytest.raises(Exception):  # 應該拋出 413 錯誤
                    middleware._before_request()
    
    def test_before_request_non_json_post(self, app):
        """測試非 JSON POST 請求檢查"""
        middleware = SecurityMiddleware()
        middleware.init_app(app)
        
        with app.test_client() as client:
            with app.test_request_context('/test', method='POST', 
                                        content_type='text/plain', 
                                        data='not json',
                                        environ_base={'FLASK_ENV': 'production'}):
                with pytest.raises(Exception):  # 應該拋出 400 錯誤
                    middleware._before_request()
    
    def test_before_request_webhook_allows_non_json(self, app):
        """測試 webhook 端點允許非 JSON"""
        middleware = SecurityMiddleware()
        middleware.init_app(app)
        
        with app.test_client() as client:
            with app.test_request_context('/callback', method='POST', 
                                        content_type='text/plain',
                                        data='webhook data'):
                # webhook 端點應該允許非 JSON 內容
                result = middleware._before_request()
                # 不應該拋出異常
    
    def test_after_request_testing_env(self, app):
        """測試在測試環境中跳過安全標頭"""
        middleware = SecurityMiddleware()
        
        with app.test_request_context('/', environ_base={'FLASK_ENV': 'testing'}):
            response = Mock()
            response.headers = {}
            
            result = middleware._after_request(response)
            assert result == response
            assert len(response.headers) == 0
    
    def test_after_request_adds_security_headers(self, app):
        """測試添加安全標頭"""
        middleware = SecurityMiddleware()
        
        with app.test_request_context('/'):
            response = Mock()
            response.headers = {}
            
            with patch('src.core.security.security_config') as mock_config:
                mock_config.get_security_headers.return_value = {
                    'X-Frame-Options': 'DENY',
                    'X-Content-Type-Options': 'nosniff'
                }
                
                result = middleware._after_request(response)
                
                assert result == response
                assert response.headers['X-Frame-Options'] == 'DENY'
                assert response.headers['X-Content-Type-Options'] == 'nosniff'


class TestSecurityFunctions:
    """測試安全相關函數"""
    
    def test_verify_line_signature_valid(self):
        """測試有效的 Line 簽名驗證"""
        channel_secret = "test_secret"
        body = "test_body"
        
        # 生成正確的簽名
        expected_signature = hmac.new(
            channel_secret.encode('utf-8'),
            body.encode('utf-8'),
            hashlib.sha256
        ).digest()
        signature = "sha256=" + expected_signature.hex()
        
        assert verify_line_signature(signature, body, channel_secret) is True
    
    def test_verify_line_signature_invalid(self):
        """測試無效的 Line 簽名驗證"""
        channel_secret = "test_secret"
        body = "test_body"
        wrong_signature = "sha256=" + "0" * 64
        
        assert verify_line_signature(wrong_signature, body, channel_secret) is False
    
    def test_verify_line_signature_wrong_format(self):
        """測試錯誤格式的簽名"""
        assert verify_line_signature("invalid_format", "body", "secret") is False
        assert verify_line_signature("md5=abc123", "body", "secret") is False
    
    def test_verify_line_signature_empty_params(self):
        """測試空參數的簽名驗證"""
        assert verify_line_signature("", "body", "secret") is False
        assert verify_line_signature("sha256=abc", "", "secret") is False
        assert verify_line_signature("sha256=abc", "body", "") is False
    
    def test_verify_line_signature_exception_handling(self):
        """測試簽名驗證異常處理"""
        with patch('src.core.security.logger') as mock_logger:
            # 提供無效的十六進制字符串
            result = verify_line_signature("sha256=invalid_hex", "body", "secret")
            
            assert result is False
            mock_logger.error.assert_called_once()
    
    def test_require_json_input_decorator_valid(self):
        """測試 require_json_input 裝飾器（有效 JSON）"""
        app = Flask(__name__)
        
        @app.route('/test', methods=['POST'])
        @require_json_input(['name'])
        def test_endpoint():
            return 'OK'
        
        with app.test_client() as client:
            response = client.post('/test', 
                                 json={'name': 'John'},
                                 content_type='application/json')
            assert response.status_code == 200
    
    def test_require_json_input_decorator_missing_field(self):
        """測試 require_json_input 裝飾器（缺少必要欄位）"""
        app = Flask(__name__)
        
        @app.route('/test', methods=['POST'])
        @require_json_input(['name', 'email'])
        def test_endpoint():
            return 'OK'
        
        with app.test_client() as client:
            response = client.post('/test',
                                 json={'name': 'John'},
                                 content_type='application/json')
            assert response.status_code == 400
    
    def test_require_json_input_decorator_non_json(self):
        """測試 require_json_input 裝飾器（非 JSON 內容）"""
        app = Flask(__name__)
        
        @app.route('/test', methods=['POST'])
        @require_json_input()
        def test_endpoint():
            return 'OK'
        
        with app.test_client() as client:
            response = client.post('/test',
                                 data='not json',
                                 content_type='text/plain')
            assert response.status_code == 400
    
    def test_sanitize_output_string(self):
        """測試字符串輸出清理"""
        input_str = "<script>alert('xss')</script>"
        result = sanitize_output(input_str)
        
        assert '&lt;script&gt;' in result
        assert '<script>' not in result
    
    def test_sanitize_output_dict(self):
        """測試字典輸出清理"""
        input_dict = {
            'safe': 'normal text',
            'dangerous': '<script>alert("xss")</script>'
        }
        result = sanitize_output(input_dict)
        
        assert result['safe'] == 'normal text'
        assert '&lt;script&gt;' in result['dangerous']
        assert '<script>' not in result['dangerous']
    
    def test_sanitize_output_list(self):
        """測試列表輸出清理"""
        input_list = ['safe text', '<script>dangerous</script>']
        result = sanitize_output(input_list)
        
        assert result[0] == 'safe text'
        assert '&lt;script&gt;' in result[1]
        assert '<script>' not in result[1]
    
    def test_sanitize_output_nested_structure(self):
        """測試嵌套結構輸出清理"""
        input_data = {
            'users': [
                {'name': 'John', 'bio': '<script>evil</script>'},
                {'name': 'Jane', 'bio': 'normal text'}
            ]
        }
        result = sanitize_output(input_data)
        
        assert result['users'][0]['name'] == 'John'
        assert '&lt;script&gt;' in result['users'][0]['bio']
        assert result['users'][1]['bio'] == 'normal text'
    
    def test_sanitize_output_non_string_types(self):
        """測試非字符串類型的輸出清理"""
        assert sanitize_output(123) == 123
        assert sanitize_output(None) is None
        assert sanitize_output(True) is True


class TestGlobalInstances:
    """測試全域實例和初始化函數"""
    
    def test_security_config_global_instance(self):
        """測試全域 security_config 實例"""
        from src.core.security import security_config
        
        assert isinstance(security_config, SecurityConfig)
        assert hasattr(security_config, 'config')
    
    def test_security_middleware_global_instance(self):
        """測試全域 security_middleware 實例"""
        from src.core.security import security_middleware
        
        assert isinstance(security_middleware, SecurityMiddleware)
        assert hasattr(security_middleware, 'rate_limiter')
    
    def test_init_security_function(self):
        """測試 init_security 函數"""
        app = Flask(__name__)
        
        with patch('src.core.security.security_middleware.init_app') as mock_init, \
             patch('src.core.security.logger') as mock_logger:
            
            init_security(app)
            
            mock_init.assert_called_once_with(app)
            mock_logger.info.assert_called_once_with("安全性中間件已初始化")


class TestSecurityIntegration:
    """測試安全模組整合"""
    
    def test_end_to_end_request_processing(self):
        """測試端對端請求處理"""
        app = Flask(__name__)
        
        @app.route('/api/test', methods=['POST'])
        @require_json_input(['message'])
        def api_endpoint():
            data = request.get_json()
            return {'response': f"Received: {data['message']}"}
        
        # 初始化安全中間件
        middleware = SecurityMiddleware()
        middleware.init_app(app)
        
        with app.test_client() as client:
            # 測試正常請求
            response = client.post('/api/test',
                                 json={'message': 'Hello World'},
                                 content_type='application/json')
            
            assert response.status_code == 200
            data = response.get_json()
            assert 'Received: Hello World' in data['response']
    
    def test_rate_limiting_integration(self):
        """測試速率限制整合"""
        app = Flask(__name__)
        
        @app.route('/test')
        def test_endpoint():
            return 'OK'
        
        # 創建配置低速率限制的中間件
        middleware = SecurityMiddleware()
        
        with patch.object(middleware.rate_limiter, 'is_allowed', side_effect=[True, True, False]):
            middleware.init_app(app)
            
            with app.test_client() as client:
                # 前兩個請求應該成功
                response1 = client.get('/test')
                response2 = client.get('/test')
                
                # 第三個請求應該被限制（429 錯誤）
                response3 = client.get('/test')
                assert response3.status_code == 429
    
    def test_security_headers_integration(self):
        """測試安全標頭整合"""
        app = Flask(__name__)
        
        @app.route('/test')
        def test_endpoint():
            return 'OK'
        
        middleware = SecurityMiddleware()
        middleware.init_app(app)
        
        with app.test_client() as client:
            response = client.get('/test')
            
            # 檢查是否包含安全標頭（根據環境配置）
            if security_config.config['enable_security_headers']:
                assert 'X-Content-Type-Options' in response.headers
                assert 'X-Frame-Options' in response.headers


class TestSecurityConfigReload:
    """測試安全配置重新載入"""
    
    def test_config_reload_with_new_env_vars(self):
        """測試使用新環境變數重新載入配置"""
        # 創建新的配置實例來測試環境變數變化
        with patch.dict(os.environ, {
            'GENERAL_RATE_LIMIT': '200',
            'MAX_MESSAGE_LENGTH': '10000'
        }):
            new_config = SecurityConfig()
            
            assert new_config.config['general_rate_limit'] == 200
            assert new_config.config['max_message_length'] == 10000


if __name__ == "__main__":
    pytest.main([__file__])