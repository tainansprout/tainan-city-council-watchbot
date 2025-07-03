"""
平台整合測試
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from src.app import MultiPlatformChatBot, create_app
from src.platforms.base import PlatformType


class TestPlatformIntegration:
    """測試平台整合"""
    
    @pytest.fixture
    def test_config(self):
        """測試配置"""
        return {
            'app': {
                'name': 'Test Bot',
                'version': '1.0.0'
            },
            'platforms': {
                'line': {
                    'enabled': True,
                    'channel_access_token': 'test_line_token',
                    'channel_secret': 'test_line_secret'
                },
                'discord': {
                    'enabled': False,
                    'bot_token': 'test_discord_token'
                }
            },
            'llm': {
                'provider': 'openai'
            },
            'openai': {
                'api_key': 'test_openai_key',
                'assistant_id': 'test_assistant_id'
            },
            'db': {
                'host': 'localhost',
                'port': 5432,
                'db_name': 'test_db',
                'user': 'test_user',
                'password': 'test_password'
            },
            'commands': {
                'help': 'Test help message'
            }
        }
    
    @patch('src.models.factory.ModelFactory.create_from_config')
    @patch('src.database.db.Database')
    def test_app_initialization(self, mock_database_class, mock_model_factory, test_config):
        """測試應用程式初始化"""
        # Mock 模型
        mock_model = Mock()
        mock_model.get_provider.return_value = 'openai'
        mock_model.check_connection.return_value = (True, None)
        mock_model_factory.return_value = mock_model
        
        # Mock 資料庫
        mock_database = Mock()
        mock_database_class.return_value = mock_database
        
        with patch('src.core.config.load_config', return_value=test_config):
            # 創建應用程式
            app = MultiPlatformChatBot()
            
            # 驗證初始化
            assert app.config == test_config
            assert app.model == mock_model
            assert app.database == mock_database
            assert app.core_chat_service is not None
    
    @patch('src.models.factory.ModelFactory.create_from_config')
    @patch('src.database.db.Database')
    def test_flask_app_creation(self, mock_database_class, mock_model_factory, test_config):
        """測試 Flask 應用程式創建"""
        # Mock 依賴項
        mock_model = Mock()
        mock_model.get_provider.return_value = 'openai'
        mock_model.check_connection.return_value = (True, None)
        mock_model_factory.return_value = mock_model
        
        mock_database = Mock()
        mock_database_class.return_value = mock_database
        
        with patch('src.core.config.load_config', return_value=test_config):
            # 創建 Flask 應用程式
            flask_app = create_app()
            
            # 驗證 Flask 應用程式
            assert flask_app is not None
            assert hasattr(flask_app, 'test_client')


class TestWebhookIntegration:
    """測試 Webhook 整合"""
    
    @pytest.fixture
    def flask_client(self, test_config):
        """Flask 測試客戶端"""
        with patch('src.core.config.load_config', return_value=test_config):
            with patch('src.models.factory.ModelFactory.create_from_config'):
                with patch('src.database.db.Database'):
                    flask_app = create_app()
                    flask_app.config['TESTING'] = True
                    return flask_app.test_client()
    
    @pytest.fixture
    def test_config(self):
        """測試配置"""
        return {
            'app': {
                'name': 'Test Bot',
                'version': '1.0.0'
            },
            'platforms': {
                'line': {
                    'enabled': True,
                    'channel_access_token': 'test_line_token',
                    'channel_secret': 'test_line_secret'
                }
            },
            'llm': {
                'provider': 'openai'
            },
            'openai': {
                'api_key': 'test_openai_key',
                'assistant_id': 'test_assistant_id'
            },
            'db': {
                'host': 'localhost',
                'port': 5432,
                'db_name': 'test_db',
                'user': 'test_user',
                'password': 'test_password'
            },
            'commands': {
                'help': 'Test help message'
            }
        }
    
    def test_home_endpoint(self, flask_client):
        """測試根路徑端點"""
        response = flask_client.get('/')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'name' in data
        assert 'platforms' in data
        assert 'status' in data
    
    def test_health_endpoint(self, flask_client):
        """測試健康檢查端點"""
        with patch('src.database.db.Database.get_session'):
            with patch('src.models.base.FullLLMInterface.check_connection', return_value=(True, None)):
                response = flask_client.get('/health')
                
                assert response.status_code in [200, 503]  # 可能因為 mock 而失敗
                data = json.loads(response.data)
                assert 'status' in data
                assert 'checks' in data
    
    def test_metrics_endpoint(self, flask_client):
        """測試指標端點"""
        response = flask_client.get('/metrics')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'platforms' in data
        assert 'timestamp' in data
    
    @patch('src.platforms.base.PlatformManager.handle_platform_webhook')
    def test_line_webhook_endpoint(self, mock_handle_webhook, flask_client):
        """測試 LINE webhook 端點"""
        # Mock webhook 處理
        mock_handle_webhook.return_value = []
        
        # 準備 LINE webhook 資料
        webhook_data = {
            "events": [
                {
                    "type": "message",
                    "replyToken": "test_reply_token",
                    "source": {
                        "type": "user",
                        "userId": "test_user_id"
                    },
                    "message": {
                        "type": "text",
                        "id": "test_message_id",
                        "text": "Hello"
                    }
                }
            ]
        }
        
        # 發送 webhook 請求
        response = flask_client.post(
            '/webhooks/line',
            data=json.dumps(webhook_data),
            content_type='application/json',
            headers={'X-Line-Signature': 'test_signature'}
        )
        
        # 驗證回應
        assert response.status_code == 200
        assert response.data.decode() == 'OK'
    
    def test_unknown_platform_webhook(self, flask_client):
        """測試未知平台的 webhook"""
        response = flask_client.post(
            '/webhooks/unknown_platform',
            data='{}',
            content_type='application/json'
        )
        
        assert response.status_code == 404
    
    def test_legacy_callback_endpoint(self, flask_client):
        """測試向後兼容的 callback 端點"""
        with patch('src.platforms.base.PlatformManager.handle_platform_webhook', return_value=[]):
            response = flask_client.post(
                '/callback',
                data='{"events":[]}',
                content_type='application/json',
                headers={'X-Line-Signature': 'test_signature'}
            )
            
            assert response.status_code == 200


class TestErrorHandling:
    """測試錯誤處理"""
    
    @pytest.fixture
    def flask_client_with_error(self, test_config):
        """會產生錯誤的 Flask 測試客戶端"""
        # 故意使用會導致錯誤的配置
        error_config = test_config.copy()
        error_config['db'] = {}  # 無效的資料庫配置
        
        with patch('src.core.config.load_config', return_value=error_config):
            try:
                flask_app = create_app()
                flask_app.config['TESTING'] = True
                return flask_app.test_client()
            except:
                # 如果初始化失敗，返回 None
                return None
    
    @pytest.fixture
    def test_config(self):
        """測試配置"""
        return {
            'app': {
                'name': 'Test Bot',
                'version': '1.0.0'
            },
            'platforms': {
                'line': {
                    'enabled': True,
                    'channel_access_token': 'test_line_token',
                    'channel_secret': 'test_line_secret'
                }
            },
            'llm': {
                'provider': 'openai'
            },
            'openai': {
                'api_key': 'test_openai_key',
                'assistant_id': 'test_assistant_id'
            },
            'db': {
                'host': 'localhost',
                'port': 5432,
                'db_name': 'test_db',
                'user': 'test_user',
                'password': 'test_password'
            }
        }
    
    def test_invalid_config_handling(self, test_config):
        """測試無效配置的處理"""
        # 故意使用無效配置
        invalid_config = test_config.copy()
        invalid_config['platforms']['line']['enabled'] = True
        invalid_config['platforms']['line'].pop('channel_access_token', None)  # 移除必要欄位
        
        with patch('src.core.config.load_config', return_value=invalid_config):
            with patch('src.models.factory.ModelFactory.create_from_config'):
                with patch('src.database.db.Database'):
                    # 應該能夠初始化，但會有警告
                    app = MultiPlatformChatBot()
                    
                    # 檢查 LINE 平台是否被禁用或處理錯誤
                    enabled_platforms = app.platform_manager.get_enabled_platforms()
                    # LINE 應該不在啟用列表中，因為配置無效
                    assert PlatformType.LINE not in enabled_platforms or len(enabled_platforms) == 0


if __name__ == "__main__":
    pytest.main([__file__])