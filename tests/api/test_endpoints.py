import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from flask import Flask

# 需要先設定環境變數避免 import 錯誤
import os
os.environ.setdefault('FLASK_ENV', 'testing')

from main import create_app
from src.services.core_chat_service import CoreChatService


class TestHealthEndpoint:
    """健康檢查端點測試"""
    
    @pytest.fixture
    def client(self):
        with patch('src.core.config.load_config') as mock_config:
            mock_config.return_value = {
                'platforms': {'line': {'enabled': True, 'channel_access_token': 'test', 'channel_secret': 'test'}},
                'llm': {'provider': 'openai'},
                'openai': {'api_key': 'test', 'assistant_id': 'test'},
                'db': {'host': 'localhost', 'user': 'test', 'password': 'test', 'db_name': 'test'}
            }
            app = create_app()
            app.config['TESTING'] = True
            with app.test_client() as client:
                yield client
    
    def test_health_check_success(self, client):
        """測試健康檢查成功"""
        with patch('src.app.MultiPlatformChatBot.database') as mock_database, \
             patch('src.app.MultiPlatformChatBot.model') as mock_model:
            
            # 設定模擬回應
            mock_database.get_connection_info.return_value = {
                'pool_size': 10,
                'checked_in': 2,
                'checked_out': 1,
                'overflow': 0,
                'invalid': 0
            }
            mock_model.check_connection.return_value = (True, None)
            
            response = client.get('/health')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['status'] == 'healthy'
            assert 'checks' in data
            assert 'database' in data['checks']
            assert 'model' in data['checks']
            assert 'platforms' in data['checks']
            assert data['checks']['database']['status'] == 'healthy'
            assert data['checks']['model']['status'] == 'healthy'
    
    def test_health_check_database_error(self, client):
        """測試資料庫連線錯誤"""
        with patch('main.database') as mock_db, \
             patch('main.model') as mock_model:
            
            # 模擬資料庫錯誤 - context manager
            mock_session = Mock()
            mock_db.get_session.return_value.__enter__ = Mock(return_value=mock_session)
            mock_db.get_session.return_value.__exit__ = Mock(return_value=None)
            mock_session.execute.side_effect = Exception("Database error")
            mock_model.check_connection.return_value = (True, None)
            
            response = client.get('/health')
            
            assert response.status_code == 503
            data = json.loads(response.data)
            assert data['status'] == 'unhealthy'
            assert data['database']['status'] == 'error'
    
    def test_health_check_model_error(self, client):
        """測試模型連線錯誤"""
        with patch('main.database') as mock_db, \
             patch('main.model') as mock_model:
            
            # 設定模擬 - context manager
            mock_session = Mock()
            mock_db.get_session.return_value.__enter__ = Mock(return_value=mock_session)
            mock_db.get_session.return_value.__exit__ = Mock(return_value=None)
            mock_session.execute.return_value = None
            mock_model.check_connection.return_value = (False, "API key invalid")
            
            response = client.get('/health')
            
            assert response.status_code == 503
            data = json.loads(response.data)
            assert data['status'] == 'unhealthy'
            assert data['model']['status'] == 'error'
            assert 'API key invalid' in data['model']['error']


class TestLineWebhookEndpoint:
    """Line Webhook 端點測試"""
    
    @pytest.fixture
    def client(self):
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    @pytest.fixture
    def line_webhook_headers(self):
        return {
            'Content-Type': 'application/json',
            'X-Line-Signature': 'test_signature'
        }
    
    def test_webhook_text_message(self, client, line_webhook_headers):
        """測試文字訊息 webhook"""
        webhook_data = {
            'events': [
                {
                    'type': 'message',
                    'message': {
                        'type': 'text',
                        'text': 'Hello'
                    },
                    'source': {
                        'type': 'user',
                        'userId': 'U' + '0' * 32
                    },
                    'replyToken': 'test_reply_token'
                }
            ]
        }
        
        with patch('main.verify_line_signature', return_value=True) as mock_verify, \
             patch('main.handler.handle') as mock_handler:
            
            # 設定模擬 - handler 處理成功
            mock_handler.return_value = None
            
            response = client.post(
                '/callback',
                data=json.dumps(webhook_data),
                headers=line_webhook_headers
            )
            
            assert response.status_code == 200
            mock_handler.assert_called_once()
    
    def test_webhook_audio_message(self, client, line_webhook_headers):
        """測試語音訊息 webhook"""
        webhook_data = {
            'events': [
                {
                    'type': 'message',
                    'message': {
                        'type': 'audio',
                        'id': 'audio_message_id_123'
                    },
                    'source': {
                        'type': 'user',
                        'userId': 'U' + '1' * 32
                    },
                    'replyToken': 'test_reply_token_audio'
                }
            ]
        }
        
        with patch('main.verify_line_signature', return_value=True) as mock_verify, \
             patch('main.handler.handle') as mock_handler:
            
            # 設定模擬 - handler 處理成功
            mock_handler.return_value = None
            
            response = client.post(
                '/callback',
                data=json.dumps(webhook_data),
                headers=line_webhook_headers
            )
            
            assert response.status_code == 200
            mock_handler.assert_called_once()
    
    def test_webhook_invalid_signature(self, client):
        """測試無效簽章"""
        webhook_data = {'events': []}
        headers = {
            'Content-Type': 'application/json',
            'X-Line-Signature': 'invalid_signature'
        }
        
        with patch('main.verify_line_signature', return_value=False) as mock_verify:
            
            response = client.post(
                '/callback',
                data=json.dumps(webhook_data),
                headers=headers
            )
            
            assert response.status_code == 400
    
    def test_webhook_unsupported_event_type(self, client, line_webhook_headers):
        """測試不支援的事件類型"""
        webhook_data = {
            'events': [
                {
                    'type': 'follow',  # 不支援的事件類型
                    'source': {
                        'type': 'user',
                        'userId': 'U' + '2' * 32
                    }
                }
            ]
        }
        
        with patch('main.verify_line_signature', return_value=True) as mock_verify, \
             patch('main.handler.handle') as mock_handler:
            
            # 設定模擬 - handler 處理成功
            mock_handler.return_value = None
            
            response = client.post(
                '/callback',
                data=json.dumps(webhook_data),
                headers=line_webhook_headers
            )
            
            assert response.status_code == 200  # 應該正常處理但不回應


class TestErrorHandling:
    """錯誤處理測試"""
    
    @pytest.fixture
    def client(self):
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    def test_404_error(self, client):
        """測試 404 錯誤"""
        response = client.get('/nonexistent-endpoint')
        assert response.status_code == 404
    
    def test_500_error_in_webhook(self, client):
        """測試 webhook 中的 500 錯誤"""
        webhook_data = {
            'events': [
                {
                    'type': 'message',
                    'message': {
                        'type': 'text',
                        'text': 'test'
                    },
                    'source': {
                        'type': 'user',
                        'userId': 'U' + '3' * 32
                    },
                    'replyToken': 'test_token'
                }
            ]
        }
        
        headers = {
            'Content-Type': 'application/json',
            'X-Line-Signature': 'test_signature'
        }
        
        with patch('main.verify_line_signature', return_value=True) as mock_verify, \
             patch('main.handler.handle') as mock_handler:
            
            # 模擬解析成功但服務失敗
            mock_handler.side_effect = Exception("Service error")
            
            response = client.post(
                '/callback',
                data=json.dumps(webhook_data),
                headers=headers
            )
            
            # 錯誤應該被捕獲並記錄，返回 500
            assert response.status_code == 500


class TestConfigurationEndpoints:
    """配置相關端點測試"""
    
    @pytest.fixture
    def client(self):
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    def test_config_info_endpoint(self, client):
        """測試配置資訊端點（如果存在）"""
        # 這個測試假設有配置資訊端點
        # 如果沒有此端點，可以跳過此測試
        with patch('main.config') as mock_config:
            mock_config.get.return_value = 'test_value'
            
            # 嘗試訪問配置端點
            response = client.get('/config')
            
            # 如果端點不存在，應該返回 404
            assert response.status_code in [200, 404]
    
    def test_model_info_endpoint(self, client):
        """測試模型資訊端點（如果存在）"""
        with patch('main.model') as mock_model:
            mock_model.get_provider.return_value = 'openai'
            
            response = client.get('/model/info')
            
            # 如果端點不存在，應該返回 404
            assert response.status_code in [200, 404]


class TestPerformanceEndpoints:
    """效能測試端點"""

    def test_concurrent_webhook_requests(self):
        """測試並發 webhook 請求"""
        import threading
        import json
        from unittest.mock import patch
        from main import app

        webhook_data = {
            'events': [
                {
                    'type': 'message',
                    'message': {
                        'type': 'text',
                        'text': 'concurrent test'
                    },
                    'source': {
                        'type': 'user',
                        'userId': 'U' + '4' * 32
                    },
                    'replyToken': 'concurrent_token'
                }
            ]
        }
        
        headers = {
            'Content-Type': 'application/json',
            'X-Line-Signature': 'a_valid_signature'
        }
        
        results = []
        
        def make_request():
            try:
                with app.test_client() as thread_client:
                    with patch('main._handle_line_webhook', return_value='OK'):
                        response = thread_client.post(
                            '/callback',
                            data=json.dumps(webhook_data),
                            headers=headers
                        )
                        results.append(response.status_code)
            except Exception as e:
                results.append(str(e))
        
        threads = []
        for _ in range(5):
            t = threading.Thread(target=make_request)
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        assert len(results) == 5
        success_count = sum(1 for r in results if r == 200)
        assert success_count == 5, f"Expected 5 successful requests, but got {success_count}. Results: {results}"
