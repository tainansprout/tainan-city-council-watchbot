"""
API 錯誤回應測試
測試不同 API 端點的錯誤處理和回應格式
"""
import pytest
import json
from unittest.mock import Mock, patch
from flask import Flask
from sqlalchemy.exc import ProgrammingError
import psycopg2.errors

from src.app import MultiPlatformChatBot


class TestAPIErrorResponses:
    """API 錯誤回應測試"""
    
    @pytest.fixture
    def mock_config(self):
        """模擬配置"""
        return {
            'app': {'name': '測試聊天機器人', 'version': '2.0.0'},
            'llm': {'provider': 'openai'},
            'openai': {'api_key': 'test_key', 'assistant_id': 'test_assistant'},
            'platforms': {
                'line': {
                    'enabled': True,
                    'channel_access_token': 'test_token',
                    'channel_secret': 'test_secret'
                }
            },
            'db': {
                'host': 'localhost',
                'port': 5432,
                'database': 'test_db',
                'username': 'test_user',
                'password': 'test_pass'
            },
            'auth': {
                'method': 'simple_password',
                'password': 'test_password'
            },
            'text_processing': {
                'preprocessors': [],
                'post_replacements': []
            }
        }
    
    @pytest.fixture
    def app_instance(self, mock_config):
        """創建應用實例"""
        with patch('src.app.load_config', return_value=mock_config):
            with patch('src.models.factory.ModelFactory') as mock_factory:
                with patch('src.platforms.factory.PlatformFactory') as mock_platform_factory:
                    # 模擬模型
                    mock_model = Mock()
                    mock_model.get_provider.return_value.value = "openai"
                    mock_factory.return_value.create_model.return_value = mock_model
                    
                    # 模擬平台處理器
                    mock_platform_factory.return_value.create_enabled_handlers.return_value = {}
                    
                    app = MultiPlatformChatBot()
                    return app
    
    @pytest.fixture
    def client(self, app_instance):
        """創建測試客戶端"""
        flask_app = app_instance.get_flask_app()
        flask_app.config['TESTING'] = True
        flask_app.config['SECRET_KEY'] = 'test_secret_key'
        return flask_app.test_client()
    
    @pytest.fixture
    def authenticated_client(self, client):
        """創建已認證的測試客戶端"""
        with client.session_transaction() as sess:
            sess['test_authenticated'] = True
        return client
    
    def test_ask_endpoint_database_error_response_format(self, authenticated_client, app_instance):
        """測試 /ask 端點資料庫錯誤的回應格式"""
        # 模擬資料庫錯誤
        with patch.object(app_instance.chat.model, 'chat_with_user') as mock_chat:
            mock_chat.return_value = (
                False, 
                None, 
                "Database operation failed: column 'platform' does not exist"
            )
            
            response = authenticated_client.post('/ask', 
                json={'message': '測試資料庫錯誤'},
                content_type='application/json'
            )
            
            # 驗證回應格式
            assert response.status_code == 500
            assert response.content_type == 'application/json'
            
            data = json.loads(response.data)
            assert 'error' in data
            assert isinstance(data['error'], str)
            assert '資料庫查詢失敗' in data['error']
            assert '執行 SQL 查詢時發生錯誤' in data['error']
    
    def test_ask_endpoint_openai_error_response_format(self, authenticated_client, app_instance):
        """測試 /ask 端點 OpenAI 錯誤的回應格式"""
        # 模擬 OpenAI API 錯誤
        with patch.object(app_instance.chat.model, 'chat_with_user') as mock_chat:
            mock_chat.return_value = (
                False, 
                None, 
                "Invalid API key provided"
            )
            
            response = authenticated_client.post('/ask', 
                json={'message': '測試 OpenAI 錯誤'},
                content_type='application/json'
            )
            
            # 驗證回應格式
            assert response.status_code == 500
            assert response.content_type == 'application/json'
            
            data = json.loads(response.data)
            assert 'error' in data
            assert isinstance(data['error'], str)
            # 應該顯示詳細的 OpenAI 錯誤訊息
            assert ('API' in data['error'] or '金鑰' in data['error'] or 
                    'OPENAI_API_KEY' in data['error'])
    
    def test_ask_endpoint_success_response_format(self, authenticated_client, app_instance):
        """測試 /ask 端點成功回應的格式"""
        # 模擬成功回應
        from src.models.base import RAGResponse
        mock_rag_response = RAGResponse(
            answer="這是測試回應",
            sources=[]
        )
        
        with patch.object(app_instance.chat.model, 'chat_with_user') as mock_chat:
            mock_chat.return_value = (True, mock_rag_response, None)
            
            response = authenticated_client.post('/ask', 
                json={'message': '測試成功回應'},
                content_type='application/json'
            )
            
            # 驗證回應格式
            assert response.status_code == 200
            assert response.content_type == 'application/json'
            
            data = json.loads(response.data)
            assert 'message' in data
            assert isinstance(data['message'], str)
            assert data['message'] == "這是測試回應"
    
    def test_ask_endpoint_authentication_error(self, client):
        """測試 /ask 端點認證錯誤"""
        response = client.post('/ask', 
            json={'message': '未認證請求'},
            content_type='application/json'
        )
        
        # 驗證認證錯誤回應
        assert response.status_code == 401
        assert response.content_type == 'application/json'
        
        data = json.loads(response.data)
        assert 'error' in data
        assert '需要先登入' in data['error']
    
    def test_ask_endpoint_validation_error(self, authenticated_client):
        """測試 /ask 端點輸入驗證錯誤"""
        # 測試缺少 message 欄位
        response = authenticated_client.post('/ask', 
            json={},
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_ask_endpoint_invalid_json(self, authenticated_client):
        """測試 /ask 端點無效 JSON"""
        response = authenticated_client.post('/ask', 
            data='invalid json',
            content_type='application/json'
        )
        
        assert response.status_code == 400
    
    def test_ask_endpoint_message_too_long(self, authenticated_client):
        """測試 /ask 端點訊息過長"""
        # 創建過長的訊息
        long_message = "x" * 10000  # 假設限制是更小的數字
        
        response = authenticated_client.post('/ask', 
            json={'message': long_message},
            content_type='application/json'
        )
        
        # 可能會是 400 (驗證錯誤) 或 500 (處理錯誤)
        assert response.status_code in [400, 500]
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_error_response_security(self, authenticated_client, app_instance):
        """測試錯誤回應的安全性"""
        # 模擬包含敏感資訊的錯誤
        with patch.object(app_instance.chat.model, 'chat_with_user') as mock_chat:
            mock_chat.return_value = (
                False, 
                None, 
                "Database error: password=secret123 in connection string"
            )
            
            response = authenticated_client.post('/ask', 
                json={'message': '測試敏感資訊'},
                content_type='application/json'
            )
            
            data = json.loads(response.data)
            # 確保敏感資訊不會洩漏給用戶
            assert 'password' not in data['error']
            assert 'secret123' not in data['error']
            # 但應該有適當的錯誤訊息
            assert '資料庫' in data['error']
    
    def test_health_endpoint_error_handling(self, client, app_instance):
        """測試健康檢查端點的錯誤處理"""
        # 模擬資料庫檢查失敗
        with patch.object(app_instance.database, 'get_connection_info') as mock_db:
            mock_db.side_effect = Exception("Database connection failed")
            
            response = client.get('/health')
            
            # 健康檢查應該返回錯誤狀態但不拋出異常
            assert response.status_code in [200, 503]  # 可能是 503 Service Unavailable
            data = json.loads(response.data)
            assert 'status' in data
    
    def test_error_response_headers(self, authenticated_client, app_instance):
        """測試錯誤回應的 HTTP 標頭"""
        # 模擬錯誤
        with patch.object(app_instance.chat.model, 'chat_with_user') as mock_chat:
            mock_chat.return_value = (False, None, "Test error")
            
            response = authenticated_client.post('/ask', 
                json={'message': '測試標頭'},
                content_type='application/json'
            )
            
            # 驗證 Content-Type 標頭
            assert response.content_type == 'application/json'
            # 驗證沒有暴露敏感的 Server 資訊
            assert 'X-Powered-By' not in response.headers
    
    def test_concurrent_error_handling(self, authenticated_client, app_instance):
        """測試並發錯誤處理"""
        import threading
        import time
        
        results = []
        
        def make_request():
            with patch.object(app_instance.chat.model, 'chat_with_user') as mock_chat:
                mock_chat.return_value = (False, None, "Concurrent test error")
                
                response = authenticated_client.post('/ask', 
                    json={'message': '並發測試'},
                    content_type='application/json'
                )
                results.append(response.status_code)
        
        # 創建多個並發請求
        threads = []
        for i in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        # 等待所有線程完成
        for thread in threads:
            thread.join()
        
        # 所有請求都應該正確處理錯誤
        assert len(results) == 5
        assert all(status == 500 for status in results)