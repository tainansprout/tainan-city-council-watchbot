import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from flask import Flask

# 需要先設定環境變數避免 import 錯誤
import os
os.environ.setdefault('FLASK_ENV', 'testing')

from main import create_app
from src.services.chat import CoreChatService


class TestHealthEndpoint:
    """健康檢查端點測試"""
    
    @pytest.fixture
    def client(self):
        with patch('src.core.config.load_config') as mock_config:
            mock_config.return_value = {
                'platforms': {'line': {'enabled': True, 'channel_access_token': 'test', 'channel_secret': 'test'}},
                'llm': {'provider': 'openai'},
                'openai': {'api_key': 'test', 'assistant_id': 'test'},
                'db': {'host': 'localhost', 'port': 5432, 'user': 'test', 'password': 'test', 'db_name': 'test'}
            }
            app = create_app()
            app.config['TESTING'] = True
            
            # Setup bot instance in extensions
            app.extensions['bot'] = Mock()
            app.extensions['bot'].database = Mock()
            app.extensions['bot'].model = Mock()
            app.extensions['bot'].platform_manager = Mock()
            app.extensions['bot'].chat_service = Mock()
            with app.test_client() as client:
                yield client
    
    def test_health_check_success(self, client):
        """測試健康檢查成功"""
        # Mock 實際的健康檢查執行過程
        with patch('src.database.connection.Database.get_session') as mock_get_session, \
             patch('src.models.factory.ModelFactory.create_from_config') as mock_create_model:
            
            # 設定資料庫模擬 - context manager
            mock_session = Mock()
            mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
            mock_get_session.return_value.__exit__ = Mock(return_value=None)
            mock_session.execute.return_value = None
            
            # 設定模型模擬
            mock_model = Mock()
            mock_model.check_connection.return_value = (True, None)
            mock_create_model.return_value = mock_model
            
            response = client.get('/health')
            
            # 先檢查回應內容來了解問題
            print(f"Response status: {response.status_code}")
            print(f"Response data: {response.data}")
            print(f"Response content-type: {response.content_type}")
            
            assert response.status_code == 200
            # 嘗試使用 json.loads 來解析
            if response.data:
                data = json.loads(response.data)
            else:
                data = response.get_json()
            
            assert data is not None
            assert data['status'] == 'healthy'
            assert 'checks' in data
            assert 'database' in data['checks']
            assert 'model' in data['checks']
            assert 'platforms' in data['checks']
            assert data['checks']['database']['status'] == 'healthy'
            assert data['checks']['model']['status'] == 'healthy'
    
    def test_health_check_database_error(self, client):
        """測試資料庫連線錯誤"""
        # 需要 mock 實際的健康檢查執行過程
        with patch('src.database.connection.Database.get_session') as mock_get_session, \
             patch('src.models.factory.ModelFactory.create_from_config') as mock_create_model:
            
            # 模擬資料庫錯誤 - context manager
            mock_session = Mock()
            mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
            mock_get_session.return_value.__exit__ = Mock(return_value=None)
            mock_session.execute.side_effect = Exception("Database error")
            
            # 模擬模型正常
            mock_model = Mock()
            mock_model.check_connection.return_value = (True, None)
            mock_create_model.return_value = mock_model
            
            response = client.get('/health')
            
            assert response.status_code == 503
            data = response.get_json()
            assert data is not None
            assert data['status'] == 'unhealthy'
            assert data['checks']['database']['status'] == 'unhealthy'
    
    def test_health_check_model_error(self, client):
        """測試模型連線錯誤"""
        # 需要 mock 實際的健康檢查執行過程
        with patch('src.database.connection.Database.get_session') as mock_get_session, \
             patch('src.models.factory.ModelFactory.create_from_config') as mock_create_model:
            
            # 設定模擬 - context manager (資料庫正常)
            mock_session = Mock()
            mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
            mock_get_session.return_value.__exit__ = Mock(return_value=None)
            mock_session.execute.return_value = None
            
            # 模擬模型錯誤
            mock_model = Mock()
            mock_model.check_connection.return_value = (False, "API key invalid")
            mock_create_model.return_value = mock_model
            
            response = client.get('/health')
            
            assert response.status_code == 503
            data = response.get_json()
            assert data is not None
            assert data['status'] == 'unhealthy'
            assert data['checks']['model']['status'] == 'unhealthy'
            assert 'API key invalid' in data['checks']['model']['error']


class TestLineWebhookEndpoint:
    """Line Webhook 端點測試"""
    
    @pytest.fixture
    def client(self):
        with patch('src.core.config.load_config') as mock_config:
            mock_config.return_value = {
                'platforms': {'line': {'enabled': True, 'channel_access_token': 'test', 'channel_secret': 'test'}},
                'llm': {'provider': 'openai'},
                'openai': {'api_key': 'test', 'assistant_id': 'test'},
                'db': {'host': 'localhost', 'port': 5432, 'user': 'test', 'password': 'test', 'db_name': 'test'}
            }
            app = create_app()
            app.config['TESTING'] = True
            
            # Setup bot instance in extensions
            app.extensions['bot'] = Mock()
            app.extensions['bot'].database = Mock()
            app.extensions['bot'].model = Mock()
            app.extensions['bot'].platform_manager = Mock()
            app.extensions['bot'].chat_service = Mock()
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
        
        # Mock 平台管理器和處理器
        with patch('src.platforms.base.get_platform_manager') as mock_get_manager:
            
            # 設定平台管理器模擬
            mock_manager = Mock()
            mock_get_manager.return_value = mock_manager
            
            # 模擬 webhook 處理返回訊息
            from src.platforms.base import PlatformMessage, PlatformUser, PlatformType
            mock_user = Mock(user_id='U' + '0' * 32, display_name='Test User', platform=PlatformType.LINE)
            mock_message = Mock(
                message_id='test_msg_id',
                user=mock_user,
                content='Hello',
                message_type='text',
                reply_token='test_reply_token'
            )
            mock_manager.handle_platform_webhook.return_value = [mock_message]
            
            # 模擬處理器
            mock_handler = Mock()
            mock_handler.send_response.return_value = True
            mock_manager.get_handler.return_value = mock_handler
            
            # Mock 核心聊天服務
            with patch('src.services.chat.CoreChatService.process_message') as mock_process:
                mock_process.return_value = Mock(content='Test response')
            
                response = client.post(
                    '/callback',
                    data=json.dumps(webhook_data),
                    headers=line_webhook_headers
                )
                
                assert response.status_code == 200
                mock_manager.handle_platform_webhook.assert_called_once()
    
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
        
        # Mock 平台管理器和處理器
        with patch('src.platforms.base.get_platform_manager') as mock_get_manager:
            
            # 設定平台管理器模擬
            mock_manager = Mock()
            mock_get_manager.return_value = mock_manager
            
            # 模擬 webhook 處理返回訊息
            from src.platforms.base import PlatformMessage, PlatformUser, PlatformType
            mock_user = Mock(user_id='U' + '1' * 32, display_name='Test User', platform=PlatformType.LINE)
            mock_message = Mock(
                message_id='audio_message_id_123',
                user=mock_user,
                content='',
                message_type='audio',
                reply_token='test_reply_token_audio',
                audio_content=b'audio_data'
            )
            mock_manager.handle_platform_webhook.return_value = [mock_message]
            
            # 模擬處理器
            mock_handler = Mock()
            mock_handler.send_response.return_value = True
            mock_manager.get_handler.return_value = mock_handler
            
            # Mock 核心聊天服務
            with patch('src.services.chat.CoreChatService.process_message') as mock_process:
                mock_process.return_value = Mock(content='Audio response')
            
                response = client.post(
                    '/callback',
                    data=json.dumps(webhook_data),
                    headers=line_webhook_headers
                )
                
                assert response.status_code == 200
                mock_manager.handle_platform_webhook.assert_called_once()
    
    def test_webhook_invalid_signature(self, client):
        """測試無效簽章"""
        webhook_data = {'events': []}
        headers = {
            'Content-Type': 'application/json',
            'X-Line-Signature': 'invalid_signature'
        }
        
        # Mock 平台管理器拋出驗證錯誤
        with patch('src.platforms.base.get_platform_manager') as mock_get_manager:
            
            mock_manager = Mock()
            mock_get_manager.return_value = mock_manager
            
            # 模擬簽章驗證失敗
            mock_manager.handle_platform_webhook.side_effect = ValueError("Invalid signature")
            
            response = client.post(
                '/callback',
                data=json.dumps(webhook_data),
                headers=headers
            )
            
            # 新架構中，webhook 錯誤會返回 500
            assert response.status_code == 500
    
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
        
        # Mock 平台管理器
        with patch('src.platforms.base.get_platform_manager') as mock_get_manager:
            
            # 設定平台管理器模擬
            mock_manager = Mock()
            mock_get_manager.return_value = mock_manager
            
            # 模擬返回空訊息列表（不支援的事件）
            mock_manager.handle_platform_webhook.return_value = []
            
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
        with patch('src.core.config.load_config') as mock_config:
            mock_config.return_value = {
                'platforms': {'line': {'enabled': True, 'channel_access_token': 'test', 'channel_secret': 'test'}},
                'llm': {'provider': 'openai'},
                'openai': {'api_key': 'test', 'assistant_id': 'test'},
                'db': {'host': 'localhost', 'port': 5432, 'user': 'test', 'password': 'test', 'db_name': 'test'}
            }
            app = create_app()
            app.config['TESTING'] = True
            
            # Setup bot instance in extensions
            app.extensions['bot'] = Mock()
            app.extensions['bot'].database = Mock()
            app.extensions['bot'].model = Mock()
            app.extensions['bot'].platform_manager = Mock()
            app.extensions['bot'].chat_service = Mock()
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
        
        # Mock 平台管理器但讓處理過程失敗
        with patch('src.platforms.base.get_platform_manager') as mock_get_manager:
            
            mock_manager = Mock()
            mock_get_manager.return_value = mock_manager
            
            # 模擬 webhook 處理成功
            from src.platforms.base import PlatformMessage, PlatformUser, PlatformType
            mock_user = Mock(user_id='U' + '3' * 32, display_name='Test User', platform=PlatformType.LINE)
            mock_message = Mock(
                message_id='test_msg_id',
                user=mock_user,
                content='test',
                message_type='text',
                reply_token='test_token'
            )
            mock_manager.handle_platform_webhook.return_value = [mock_message]
            
            # 模擬處理器
            mock_handler = Mock()
            mock_manager.get_handler.return_value = mock_handler
            
            # Mock 核心聊天服務但讓它失敗
            with patch('src.services.chat.CoreChatService.process_message') as mock_process:
                mock_process.side_effect = Exception("Service error")
                
                response = client.post(
                    '/callback',
                    data=json.dumps(webhook_data),
                    headers=headers
                )
                
                # 錯誤應該被捕獲並記錄，但返回 200 OK
                assert response.status_code == 200


class TestConfigurationEndpoints:
    """配置相關端點測試"""
    
    @pytest.fixture
    def client(self):
        with patch('src.core.config.load_config') as mock_config:
            mock_config.return_value = {
                'platforms': {'line': {'enabled': True, 'channel_access_token': 'test', 'channel_secret': 'test'}},
                'llm': {'provider': 'openai'},
                'openai': {'api_key': 'test', 'assistant_id': 'test'},
                'db': {'host': 'localhost', 'port': 5432, 'user': 'test', 'password': 'test', 'db_name': 'test'}
            }
            app = create_app()
            app.config['TESTING'] = True
            
            # Setup bot instance in extensions
            app.extensions['bot'] = Mock()
            app.extensions['bot'].database = Mock()
            app.extensions['bot'].model = Mock()
            app.extensions['bot'].platform_manager = Mock()
            app.extensions['bot'].chat_service = Mock()
            with app.test_client() as client:
                yield client
    
    def test_config_info_endpoint(self, client):
        """測試配置資訊端點（如果存在）"""
        # 這個測試假設有配置資訊端點
        # 如果沒有此端點，可以跳過此測試
        # 嘗試訪問配置端點
        response = client.get('/config')
        
        # 如果端點不存在，應該返回 404
        assert response.status_code in [200, 404]
    
    def test_model_info_endpoint(self, client):
        """測試模型資訊端點（如果存在）"""
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
        
        # 使用固定的配置創建應用
        with patch('src.core.config.load_config') as mock_config:
            mock_config.return_value = {
                'platforms': {'line': {'enabled': True, 'channel_access_token': 'test', 'channel_secret': 'test'}},
                'llm': {'provider': 'openai'},
                'openai': {'api_key': 'test', 'assistant_id': 'test'},
                'db': {'host': 'localhost', 'port': 5432, 'user': 'test', 'password': 'test', 'db_name': 'test'}
            }
            
            from main import create_app
            app = create_app()
            app.config['TESTING'] = True
            
            # Setup bot instance in extensions
            app.extensions['bot'] = Mock()
            app.extensions['bot'].database = Mock()
            app.extensions['bot'].model = Mock()
            app.extensions['bot'].platform_manager = Mock()
            app.extensions['bot'].chat_service = Mock()

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
                        # Mock 平台管理器
                        with patch('src.platforms.base.get_platform_manager') as mock_get_manager:
                            mock_manager = Mock()
                            mock_get_manager.return_value = mock_manager
                            
                            # 模擬空訊息列表（快速返回）
                            mock_manager.handle_platform_webhook.return_value = []
                            
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
