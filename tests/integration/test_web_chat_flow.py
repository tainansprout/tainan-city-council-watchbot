"""
測試 Web 聊天流程的整合測試
模擬完整的用戶聊天體驗
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock


class TestWebChatFlow:
    """測試完整的 Web 聊天流程"""
    
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
    
    def test_complete_chat_flow(self, client):
        """測試完整的聊天流程"""
        # 1. 訪問聊天介面 - 應該顯示登入頁面
        response = client.get('/chat')
        assert response.status_code == 200
        assert 'login' in response.get_data(as_text=True).lower()
        
        # 2. 登入
        login_response = client.post('/chat', data={'password': 'test123'})
        assert login_response.status_code == 200
        assert 'chat-container' in login_response.get_data(as_text=True)
        
        # 3. 發送聊天訊息
        with patch('src.services.chat.CoreChatService.process_message') as mock_process:
            mock_response = Mock()
            mock_response.content = "您好！我是台南議會觀測機器人，請問有什麼可以幫助您的嗎？"
            mock_process.return_value = mock_response
            
            chat_response = client.post('/ask', 
                                      json={'message': '你好，請介紹一下你自己'},
                                      headers={'Content-Type': 'application/json'})
            
            assert chat_response.status_code == 200
            data = chat_response.get_json()
            assert 'message' in data
            assert '台南議會觀測機器人' in data['message']
        
        # 4. 繼續對話
        with patch('src.services.chat.CoreChatService.process_message') as mock_process:
            mock_response = Mock()
            mock_response.content = "我可以幫您查詢台南市議會的會議記錄、議員資訊等。"
            mock_process.return_value = mock_response
            
            follow_up_response = client.post('/ask', 
                                           json={'message': '你可以做什麼？'},
                                           headers={'Content-Type': 'application/json'})
            
            assert follow_up_response.status_code == 200
            data = follow_up_response.get_json()
            assert 'message' in data
            assert '議會' in data['message']
    
    def test_session_management_across_requests(self, client):
        """測試跨請求的 session 管理"""
        # 登入
        client.post('/chat', data={'password': 'test123'})
        
        # 模擬多次 API 調用，確保 session 持續有效
        for i in range(3):
            with patch('src.services.chat.CoreChatService.process_message') as mock_process:
                mock_response = Mock()
                mock_response.content = f"第 {i+1} 次回應"
                mock_process.return_value = mock_response
                
                response = client.post('/ask', 
                                     json={'message': f'第 {i+1} 個問題'},
                                     headers={'Content-Type': 'application/json'})
                
                assert response.status_code == 200
                data = response.get_json()
                assert f'第 {i+1} 次' in data['message']
    
    def test_chat_with_different_message_types(self, client):
        """測試不同類型的訊息"""
        # 登入
        client.post('/chat', data={'password': 'test123'})
        
        # 測試不同類型的訊息
        test_messages = [
            "簡短問題",
            "這是一個比較長的問題，想要了解台南市議會最近有哪些重要的議案討論？",
            "請問議員的聯絡方式",
            "會議時間查詢",
            "台南市政府的政策"
        ]
        
        for message in test_messages:
            with patch('src.services.chat.CoreChatService.process_message') as mock_process:
                mock_response = Mock()
                mock_response.content = f"針對「{message[:10]}...」的回應"
                mock_process.return_value = mock_response
                
                response = client.post('/ask', 
                                     json={'message': message},
                                     headers={'Content-Type': 'application/json'})
                
                assert response.status_code == 200
                data = response.get_json()
                assert 'message' in data
    
    def test_concurrent_users_simulation(self, client):
        """模擬多個用戶同時使用"""
        # 模擬多個用戶會話
        sessions = []
        
        for i in range(3):
            # 每個會話都需要登入
            session_client = client
            login_response = session_client.post('/chat', data={'password': 'test123'})
            assert login_response.status_code == 200
            sessions.append(session_client)
        
        # 每個會話發送訊息
        for i, session in enumerate(sessions):
            with patch('src.services.chat.CoreChatService.process_message') as mock_process:
                mock_response = Mock()
                mock_response.content = f"用戶 {i+1} 的回應"
                mock_process.return_value = mock_response
                
                response = session.post('/ask', 
                                      json={'message': f'用戶 {i+1} 的問題'},
                                      headers={'Content-Type': 'application/json'})
                
                assert response.status_code == 200


class TestWebChatErrorRecovery:
    """測試 Web 聊天錯誤恢復機制"""
    
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
    
    def test_recovery_after_service_error(self, client):
        """測試服務錯誤後的恢復"""
        # 登入
        client.post('/chat', data={'password': 'test123'})
        
        # 第一次請求失敗
        with patch('src.services.chat.CoreChatService.process_message') as mock_process:
            mock_process.side_effect = Exception("服務暫時不可用")
            
            response = client.post('/ask', 
                                 json={'message': '第一個問題'},
                                 headers={'Content-Type': 'application/json'})
            
            assert response.status_code == 500
        
        # 第二次請求成功
        with patch('src.services.chat.CoreChatService.process_message') as mock_process:
            mock_response = Mock()
            mock_response.content = "服務已恢復正常"
            mock_process.return_value = mock_response
            
            response = client.post('/ask', 
                                 json={'message': '第二個問題'},
                                 headers={'Content-Type': 'application/json'})
            
            assert response.status_code == 200
            data = response.get_json()
            assert '恢復正常' in data['message']
    
    def test_graceful_handling_of_timeout(self, client):
        """測試超時的優雅處理"""
        # 登入
        client.post('/chat', data={'password': 'test123'})
        
        # 模擬超時
        with patch('src.services.chat.CoreChatService.process_message') as mock_process:
            mock_process.side_effect = TimeoutError("請求超時")
            
            response = client.post('/ask', 
                                 json={'message': '這個問題可能會超時'},
                                 headers={'Content-Type': 'application/json'})
            
            # 應該返回適當的錯誤訊息
            assert response.status_code == 500
            data = response.get_json()
            assert 'error' in data


class TestWebChatIntegrationWithDatabase:
    """測試 Web 聊天與資料庫的整合"""
    
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
    
    def test_conversation_persistence(self, client):
        """測試對話持久化"""
        # 登入
        client.post('/chat', data={'password': 'test123'})
        
        # 模擬對話管理器
        with patch('src.services.chat.CoreChatService.process_message') as mock_process:
            mock_response = Mock()
            mock_response.content = "對話已保存到資料庫"
            mock_process.return_value = mock_response
            
            # 發送多個訊息
            for i in range(3):
                response = client.post('/ask', 
                                     json={'message': f'訊息 {i+1}'},
                                     headers={'Content-Type': 'application/json'})
                
                assert response.status_code == 200
            
            # 驗證 process_message 被正確調用
            assert mock_process.call_count == 3
    
    def test_database_connection_error_handling(self, client):
        """測試資料庫連接錯誤處理"""
        # 登入
        client.post('/chat', data={'password': 'test123'})
        
        # 模擬資料庫錯誤
        with patch('src.services.chat.CoreChatService.process_message') as mock_process:
            mock_process.side_effect = Exception("資料庫連接失敗")
            
            response = client.post('/ask', 
                                 json={'message': '測試資料庫錯誤'},
                                 headers={'Content-Type': 'application/json'})
            
            assert response.status_code == 500
            data = response.get_json()
            assert 'error' in data
            assert '發生錯誤' in data['error']