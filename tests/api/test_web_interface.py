"""
測試 Web 介面端點
包含聊天介面、認證和 API 測試
"""
import pytest
import json
from unittest.mock import Mock, patch


class TestWebInterface:
    """測試 Web 介面功能"""
    
    @pytest.fixture
    def client(self):
        """測試客戶端"""
        with patch('src.core.config.load_config') as mock_config:
            mock_config.return_value = {
                'app': {'name': '台南議會觀測機器人', 'version': '2.0.0'},
                'platforms': {
                    'line': {
                        'enabled': True,
                        'channel_access_token': 'test_token',
                        'channel_secret': 'test_secret'
                    }
                },
                'llm': {'provider': 'openai'},
                'openai': {'api_key': 'test_key', 'assistant_id': 'test_id'},
                'db': {'host': 'localhost', 'port': 5432, 'user': 'test', 'password': 'test', 'db_name': 'test'},
                'auth': {'method': 'simple_password', 'password': 'test123'}
            }
            
            from main import create_app
            app = create_app()
            app.config['TESTING'] = True
            
            return app.test_client()
    
    def test_chat_interface_requires_auth(self, client):
        """測試聊天介面需要認證"""
        response = client.get('/chat')
        
        assert response.status_code == 200
        response_text = response.get_data(as_text=True)
        assert 'login' in response_text.lower()
        assert '台南議會觀測機器人' in response_text
        assert '登入' in response_text
    
    def test_chat_interface_successful_login(self, client):
        """測試聊天介面成功登入"""
        response = client.post('/chat', data={'password': 'test123'})
        
        assert response.status_code == 200
        response_text = response.get_data(as_text=True)
        assert 'chat-container' in response_text
        assert '台南議會觀測機器人' in response_text
        assert '歡迎使用' in response_text
    
    def test_chat_interface_wrong_password(self, client):
        """測試聊天介面錯誤密碼"""
        response = client.post('/chat', data={'password': 'wrong_password'})
        
        assert response.status_code == 401
        response_text = response.get_data(as_text=True)
        assert '密碼錯誤' in response_text
        assert 'login' in response_text.lower()
    
    def test_ask_api_requires_auth(self, client):
        """測試 Ask API 需要認證"""
        response = client.post('/ask', 
                              json={'message': '你好'},
                              headers={'Content-Type': 'application/json'})
        
        # 未登入應該返回認證頁面或錯誤
        assert response.status_code in [401, 200]  # 200 是因為會返回登入頁面
    
    def test_ask_api_successful_request(self, client):
        """測試 Ask API 成功請求"""
        # 先登入
        login_response = client.post('/chat', data={'password': 'test123'})
        assert login_response.status_code == 200
        
        # 模擬成功的聊天服務回應
        with patch('src.services.chat.CoreChatService.process_message') as mock_process:
            mock_response = Mock()
            mock_response.content = "您好！我是台南議會觀測機器人。"
            mock_process.return_value = mock_response
            
            response = client.post('/ask', 
                                  json={'message': '你好'},
                                  headers={'Content-Type': 'application/json'})
            
            assert response.status_code == 200
            data = response.get_json()
            assert 'message' in data
            assert '台南議會觀測機器人' in data['message']
    
    def test_ask_api_invalid_message(self, client):
        """測試 Ask API 無效訊息"""
        # 先登入
        client.post('/chat', data={'password': 'test123'})
        
        # 測試空訊息
        response = client.post('/ask', 
                              json={'message': ''},
                              headers={'Content-Type': 'application/json'})
        
        # 應該要有適當的錯誤處理
        assert response.status_code in [400, 422]
    
    def test_ask_api_message_too_long(self, client):
        """測試 Ask API 訊息過長"""
        # 先登入
        client.post('/chat', data={'password': 'test123'})
        
        # 測試過長訊息
        long_message = 'a' * 2000  # 超過限制的長度
        response = client.post('/ask', 
                              json={'message': long_message},
                              headers={'Content-Type': 'application/json'})
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert '長度' in data['error']
    
    def test_ask_api_missing_json(self, client):
        """測試 Ask API 缺少 JSON 資料"""
        # 先登入
        client.post('/chat', data={'password': 'test123'})
        
        # 測試無 JSON 資料
        response = client.post('/ask')
        
        assert response.status_code in [400, 422]
    
    def test_ask_api_invalid_json(self, client):
        """測試 Ask API 無效 JSON 格式"""
        # 先登入
        client.post('/chat', data={'password': 'test123'})
        
        # 測試無效 JSON
        response = client.post('/ask', 
                              data='invalid json',
                              headers={'Content-Type': 'application/json'})
        
        assert response.status_code in [400, 422]


class TestWebInterfaceLoginLogout:
    """測試登入登出流程"""
    
    @pytest.fixture
    def client(self):
        """測試客戶端"""
        with patch('src.core.config.load_config') as mock_config:
            mock_config.return_value = {
                'app': {'name': '台南議會觀測機器人', 'version': '2.0.0'},
                'platforms': {
                    'line': {
                        'enabled': True,
                        'channel_access_token': 'test_token',
                        'channel_secret': 'test_secret'
                    }
                },
                'llm': {'provider': 'openai'},
                'openai': {'api_key': 'test_key', 'assistant_id': 'test_id'},
                'db': {'host': 'localhost', 'port': 5432, 'user': 'test', 'password': 'test', 'db_name': 'test'},
                'auth': {'method': 'simple_password', 'password': 'test123'}
            }
            
            from main import create_app
            app = create_app()
            app.config['TESTING'] = True
            
            return app.test_client()
    
    def test_login_redirect_flow(self, client):
        """測試登入重定向流程"""
        # 未登入訪問 /chat 應該重定向到 /login
        response = client.get('/chat')
        assert response.status_code == 302
        assert '/login' in response.location
    
    def test_login_page_display(self, client):
        """測試登入頁面顯示"""
        response = client.get('/login')
        assert response.status_code == 200
        response_text = response.get_data(as_text=True)
        assert 'login' in response_text.lower()
        assert '台南議會觀測機器人' in response_text
        assert '密碼' in response_text
    
    def test_json_login_success(self, client):
        """測試 JSON 格式登入成功"""
        response = client.post('/login', 
                              json={'password': 'test123'},
                              headers={'Content-Type': 'application/json'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert '登入成功' in data['message']
    
    def test_json_login_failure(self, client):
        """測試 JSON 格式登入失敗"""
        response = client.post('/login', 
                              json={'password': 'wrong_password'},
                              headers={'Content-Type': 'application/json'})
        assert response.status_code == 401
        data = response.get_json()
        assert data['success'] is False
        assert '密碼錯誤' in data['error']
    
    def test_login_missing_password(self, client):
        """測試缺少密碼的登入請求"""
        response = client.post('/login', 
                              json={},
                              headers={'Content-Type': 'application/json'})
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert '缺少密碼欄位' in data['error']
    
    def test_login_non_json_request(self, client):
        """測試非 JSON 格式的登入請求"""
        response = client.post('/login', data={'password': 'test123'})
        assert response.status_code == 400
    
    def test_chat_interface_after_login(self, client):
        """測試登入後的聊天介面"""
        # 先登入
        login_response = client.post('/login', json={'password': 'test123'})
        assert login_response.status_code == 200
        
        # 再訪問聊天介面
        response = client.get('/chat')
        assert response.status_code == 200
        response_text = response.get_data(as_text=True)
        assert 'chat-container' in response_text
        assert '登出' in response_text
        assert '台南議會觀測機器人' in response_text
    
    def test_logout_functionality(self, client):
        """測試登出功能"""
        # 先登入
        login_response = client.post('/login', json={'password': 'test123'})
        assert login_response.status_code == 200
        
        # 登出
        logout_response = client.post('/logout', json={})
        assert logout_response.status_code == 200
        data = logout_response.get_json()
        assert data['success'] is True
        assert '已成功登出' in data['message']
        
        # 登出後訪問 /chat 應該重定向到 /login
        response = client.get('/chat')
        assert response.status_code == 302
        assert '/login' in response.location
    
    def test_session_persistence(self, client):
        """測試 session 持續性"""
        # 先登入
        login_response = client.post('/login', json={'password': 'test123'})
        assert login_response.status_code == 200
        
        # 多次訪問聊天介面，應該不需要重新登入
        for _ in range(3):
            response = client.get('/chat')
            assert response.status_code == 200
            response_text = response.get_data(as_text=True)
            assert 'chat-container' in response_text
    
    def test_ask_api_after_logout(self, client):
        """測試登出後的 API 訪問"""
        # 先登入
        client.post('/login', json={'password': 'test123'})
        
        # 登出
        client.post('/logout', json={})
        
        # 嘗試訪問需要認證的 API
        response = client.post('/ask', 
                              json={'message': '測試'},
                              headers={'Content-Type': 'application/json'})
        assert response.status_code == 401


class TestWebInterfaceAuthentication:
    """測試 Web 介面認證機制"""
    
    @pytest.fixture
    def client_with_different_auth(self):
        """使用不同認證方式的測試客戶端"""
        with patch('src.core.config.load_config') as mock_config:
            mock_config.return_value = {
                'app': {'name': '台南議會觀測機器人', 'version': '2.0.0'},
                'platforms': {
                    'line': {
                        'enabled': True,
                        'channel_access_token': 'test_token',
                        'channel_secret': 'test_secret'
                    }
                },
                'llm': {'provider': 'openai'},
                'openai': {'api_key': 'test_key', 'assistant_id': 'test_id'},
                'db': {'host': 'localhost', 'port': 5432, 'user': 'test', 'password': 'test', 'db_name': 'test'},
                'auth': {'method': 'token', 'api_token': 'test_api_token'}
            }
            
            from main import create_app
            app = create_app()
            app.config['TESTING'] = True
            
            return app.test_client()
    
    def test_session_persistence(self, client):
        """測試 session 持續性"""
        # 先登入
        login_response = client.post('/chat', data={'password': 'test123'})
        assert login_response.status_code == 200
        
        # 再次訪問聊天介面，應該不需要重新登入
        response = client.get('/chat')
        assert response.status_code == 200
        response_text = response.get_data(as_text=True)
        assert 'chat-container' in response_text  # 直接顯示聊天介面，不是登入頁面
    
    def test_multiple_wrong_passwords(self, client):
        """測試多次錯誤密碼"""
        for i in range(3):
            response = client.post('/chat', data={'password': f'wrong_{i}'})
            assert response.status_code == 401
            response_text = response.get_data(as_text=True)
            assert '密碼錯誤' in response_text


class TestWebInterfaceErrorHandling:
    """測試 Web 介面錯誤處理"""
    
    @pytest.fixture
    def client(self):
        """測試客戶端"""
        with patch('src.core.config.load_config') as mock_config:
            mock_config.return_value = {
                'app': {'name': '台南議會觀測機器人', 'version': '2.0.0'},
                'platforms': {
                    'line': {
                        'enabled': True,
                        'channel_access_token': 'test_token',
                        'channel_secret': 'test_secret'
                    }
                },
                'llm': {'provider': 'openai'},
                'openai': {'api_key': 'test_key', 'assistant_id': 'test_id'},
                'db': {'host': 'localhost', 'port': 5432, 'user': 'test', 'password': 'test', 'db_name': 'test'},
                'auth': {'method': 'simple_password', 'password': 'test123'}
            }
            
            from main import create_app
            app = create_app()
            app.config['TESTING'] = True
            
            return app.test_client()
    
    def test_ask_api_chat_service_error(self, client):
        """測試 Ask API 聊天服務錯誤"""
        # 先登入
        client.post('/chat', data={'password': 'test123'})
        
        # 模擬聊天服務錯誤
        with patch('src.services.chat.CoreChatService.process_message') as mock_process:
            mock_process.side_effect = Exception("聊天服務錯誤")
            
            response = client.post('/ask', 
                                  json={'message': '你好'},
                                  headers={'Content-Type': 'application/json'})
            
            assert response.status_code == 500
            data = response.get_json()
            assert data.get('success') is False
            assert data.get('error_type') == 'INTERNAL_ERROR'
            assert data.get('message') == '伺服器內部錯誤，請稍後再試'
    
    def test_template_rendering_error(self, client):
        """測試模板渲染錯誤"""
        # 模擬模板錯誤
        with patch('flask.render_template') as mock_render:
            mock_render.side_effect = Exception("模板錯誤")
            
            response = client.get('/chat')
            
            # 應該有適當的錯誤處理，不會讓應用程式崩潰
            assert response.status_code in [500, 200]  # 可能有錯誤處理機制


class TestWebInterfaceSecurityFeatures:
    """測試 Web 介面安全功能"""
    
    @pytest.fixture  
    def client(self):
        """測試客戶端"""
        with patch('src.core.config.load_config') as mock_config:
            mock_config.return_value = {
                'app': {'name': '台南議會觀測機器人', 'version': '2.0.0'},
                'platforms': {
                    'line': {
                        'enabled': True,
                        'channel_access_token': 'test_token',
                        'channel_secret': 'test_secret'
                    }
                },
                'llm': {'provider': 'openai'},
                'openai': {'api_key': 'test_key', 'assistant_id': 'test_id'},
                'db': {'host': 'localhost', 'port': 5432, 'user': 'test', 'password': 'test', 'db_name': 'test'},
                'auth': {'method': 'simple_password', 'password': 'test123'}
            }
            
            from main import create_app
            app = create_app()
            app.config['TESTING'] = True
            
            return app.test_client()
    
    def test_xss_protection_in_ask_api(self, client):
        """測試 Ask API 的 XSS 防護"""
        # 先登入
        client.post('/chat', data={'password': 'test123'})
        
        # 模擬惡意輸入
        malicious_input = '<script>alert("xss")</script>'
        
        with patch('src.services.chat.CoreChatService.process_message') as mock_process:
            mock_response = Mock()
            mock_response.content = f"您輸入了: {malicious_input}"
            mock_process.return_value = mock_response
            
            response = client.post('/ask', 
                                  json={'message': malicious_input},
                                  headers={'Content-Type': 'application/json'})
            
            assert response.status_code == 200
            data = response.get_json()
            
            # 檢查回應是否已經清理過
            assert '<script>' not in data['message']
    
    def test_input_validation_in_ask_api(self, client):
        """測試 Ask API 的輸入驗證"""
        # 先登入
        client.post('/chat', data={'password': 'test123'})
        
        # 測試各種無效輸入
        invalid_inputs = [
            None,
            123,  # 非字串
            {'nested': 'object'},  # 物件
            ['array'],  # 陣列
        ]
        
        for invalid_input in invalid_inputs:
            response = client.post('/ask', 
                                  json={'message': invalid_input},
                                  headers={'Content-Type': 'application/json'})
            
            # 應該要有適當的驗證錯誤
            assert response.status_code in [400, 422, 500]