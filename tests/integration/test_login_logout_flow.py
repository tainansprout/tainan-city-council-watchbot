"""
測試完整的登入登出流程 - 整合測試
"""
import pytest
from unittest.mock import patch


class TestCompleteLoginLogoutFlow:
    """測試完整的登入登出流程"""

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

    def test_complete_user_journey(self, client):
        """測試完整的用戶使用流程"""
        
        # 1. 未登入用戶訪問 /chat，應該被重定向到 /login
        response = client.get('/chat')
        assert response.status_code == 302
        assert '/login' in response.location
        
        # 2. 訪問登入頁面
        response = client.get('/login')
        assert response.status_code == 200
        response_text = response.get_data(as_text=True)
        assert 'login' in response_text.lower()
        assert '台南議會觀測機器人' in response_text
        
        # 3. 嘗試錯誤密碼登入
        response = client.post('/login', json={'password': 'wrong_password'})
        assert response.status_code == 401
        data = response.get_json()
        assert data['success'] is False
        assert '密碼錯誤' in data['error']
        
        # 4. 使用正確密碼登入
        response = client.post('/login', json={'password': 'test123'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert '登入成功' in data['message']
        
        # 5. 登入後訪問 /chat，應該顯示聊天介面
        response = client.get('/chat')
        assert response.status_code == 200
        response_text = response.get_data(as_text=True)
        assert 'chat-container' in response_text
        assert '登出' in response_text
        assert '台南議會觀測機器人' in response_text
        
        # 6. 使用聊天功能
        with patch('src.services.chat.CoreChatService.process_message') as mock_process:
            from unittest.mock import Mock
            mock_response = Mock()
            mock_response.content = "這是測試回應"
            mock_process.return_value = mock_response
            
            response = client.post('/ask', json={'message': '你好'})
            assert response.status_code == 200
            data = response.get_json()
            assert 'message' in data
            assert '這是測試回應' in data['message']
        
        # 7. 登出
        response = client.post('/logout', json={})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert '已成功登出' in data['message']
        
        # 8. 登出後再次訪問 /chat，應該被重定向到 /login
        response = client.get('/chat')
        assert response.status_code == 302
        assert '/login' in response.location
        
        # 9. 登出後嘗試使用需要認證的 API，應該被拒絕
        response = client.post('/ask', json={'message': '你好'})
        assert response.status_code == 401

    def test_concurrent_login_sessions(self, client):
        """測試併發登入會話"""
        # 模擬多個用戶同時登入
        responses = []
        
        for i in range(5):
            response = client.post('/login', json={'password': 'test123'})
            responses.append(response)
            
            # 每個登入都應該成功
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
        
        # 登入後所有用戶都應該能訪問聊天介面
        for i in range(5):
            response = client.get('/chat')
            assert response.status_code == 200
            response_text = response.get_data(as_text=True)
            assert 'chat-container' in response_text

    def test_session_timeout_simulation(self, client):
        """測試 Session 超時模擬"""
        # 登入
        response = client.post('/login', json={'password': 'test123'})
        assert response.status_code == 200
        
        # 正常訪問
        response = client.get('/chat')
        assert response.status_code == 200
        
        # 模擬 session 被清除（如伺服器重啟）
        with client.session_transaction() as sess:
            sess.clear()
        
        # 訪問應該被重定向到登入頁面
        response = client.get('/chat')
        assert response.status_code == 302
        assert '/login' in response.location

    def test_login_error_handling(self, client):
        """測試登入錯誤處理"""
        # 測試各種錯誤情況
        
        # 1. 缺少密碼欄位
        response = client.post('/login', json={})
        assert response.status_code == 400
        
        # 2. 密碼為空
        response = client.post('/login', json={'password': ''})
        assert response.status_code == 401
        
        # 3. 密碼為 null
        response = client.post('/login', json={'password': None})
        assert response.status_code == 401
        
        # 4. 非 JSON 請求
        response = client.post('/login', data={'password': 'test123'})
        assert response.status_code == 400
        
        # 5. 無效的 JSON
        response = client.post('/login', 
                              data='invalid json',
                              headers={'Content-Type': 'application/json'})
        assert response.status_code == 400

    def test_route_protection(self, client):
        """測試路由保護機制"""
        # 測試需要認證的端點在未登入時被保護
        
        # /ask 端點應該需要認證
        response = client.post('/ask', json={'message': '測試'})
        assert response.status_code == 401
        
        # 登入後應該可以訪問
        client.post('/login', json={'password': 'test123'})
        
        with patch('src.services.chat.CoreChatService.process_message') as mock_process:
            from unittest.mock import Mock
            mock_response = Mock()
            mock_response.content = "測試回應"
            mock_process.return_value = mock_response
            
            response = client.post('/ask', json={'message': '測試'})
            assert response.status_code == 200

    def test_logout_from_different_endpoints(self, client):
        """測試從不同端點登出"""
        # 登入
        client.post('/login', json={'password': 'test123'})
        
        # 確認登入成功
        response = client.get('/chat')
        assert response.status_code == 200
        
        # 從任何地方都可以登出
        response = client.post('/logout', json={})
        assert response.status_code == 200
        
        # 確認登出成功
        response = client.get('/chat')
        assert response.status_code == 302