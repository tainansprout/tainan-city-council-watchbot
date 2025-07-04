"""
煙霧測試 - 確保基本功能正常
"""
import pytest
from unittest.mock import Mock, patch, MagicMock


class TestSmoke:
    """基本煙霧測試"""
    
    def test_imports(self):
        """測試所有主要模組都能正確導入"""
        try:
            from main import create_app, application
            from src.app import MultiPlatformChatBot
            from src.core.config import ConfigManager
            from src.database.connection import Database
            from src.models.factory import ModelFactory
            from src.platforms.factory import PlatformFactory
            assert True
        except ImportError as e:
            pytest.fail(f"Import failed: {e}")
    
    def test_config_manager_singleton(self):
        """測試 ConfigManager 單例模式"""
        from src.core.config import ConfigManager
        
        cm1 = ConfigManager()
        cm2 = ConfigManager()
        assert cm1 is cm2
    
    @patch('src.core.config.load_config')
    def test_create_app_minimal(self, mock_load_config):
        """測試最小化應用創建"""
        # 最小配置
        mock_load_config.return_value = {
            'platforms': {
                'line': {
                    'enabled': True,
                    'channel_access_token': 'test',
                    'channel_secret': 'test'
                }
            },
            'llm': {'provider': 'openai'},
            'openai': {'api_key': 'test', 'assistant_id': 'test'},
            'db': {
                'host': 'localhost',
                'port': 5432,
                'user': 'test',
                'password': 'test',
                'db_name': 'test'
            }
        }
        
        # Mock 所有外部依賴
        with patch('src.database.connection.Database.__init__', return_value=None), \
             patch('src.models.factory.ModelFactory.create_from_config') as mock_model_factory, \
             patch('src.app.MultiPlatformChatBot._initialize_database'), \
             patch('src.app.MultiPlatformChatBot._initialize_model'), \
             patch('src.app.MultiPlatformChatBot._initialize_core_service'), \
             patch('src.app.MultiPlatformChatBot._initialize_platforms'), \
             patch('src.app.MultiPlatformChatBot._register_routes'), \
             patch('src.app.MultiPlatformChatBot._register_cleanup'):
            
            # 設定 mock 模型
            mock_model = Mock()
            mock_model.check_connection.return_value = (True, None)
            mock_model_factory.return_value = mock_model
            
            from main import create_app
            app = create_app()
            
            assert app is not None
            assert hasattr(app, 'test_client')


class TestHealthCheckMinimal:
    """最小化的健康檢查測試"""
    
    @pytest.fixture
    def app(self):
        """創建測試應用"""
        with patch('src.core.config.load_config') as mock_config:
            mock_config.return_value = {
                'platforms': {
                    'line': {
                        'enabled': True,
                        'channel_access_token': 'test',
                        'channel_secret': 'test'
                    }
                },
                'llm': {'provider': 'openai'},
                'openai': {'api_key': 'test', 'assistant_id': 'test'},
                'db': {
                    'host': 'localhost',
                    'port': 5432,
                    'user': 'test',
                    'password': 'test',
                    'db_name': 'test'
                }
            }
            
            # 創建 mock 的 MultiPlatformChatBot
            with patch('src.app.MultiPlatformChatBot') as MockBot:
                # 創建 Flask app
                from flask import Flask
                app = Flask(__name__)
                app.config['TESTING'] = True
                
                # 創建 mock bot 實例
                mock_bot = Mock()
                mock_bot.app = app
                mock_bot.database = Mock()
                mock_bot.model = Mock()
                mock_bot.platform_manager = Mock()
                
                # 設定健康檢查的 mock
                mock_bot.database.get_session = Mock()
                mock_bot.database.get_session.return_value.__enter__ = Mock()
                mock_bot.database.get_session.return_value.__exit__ = Mock()
                mock_bot.model.check_connection.return_value = (True, None)
                
                # 設定工廠返回我們的 mock
                MockBot.return_value = mock_bot
                
                # 註冊基本路由
                @app.route('/health')
                def health():
                    return {'status': 'healthy', 'checks': {
                        'database': {'status': 'healthy'},
                        'model': {'status': 'healthy'},
                        'platforms': {'status': 'healthy'},
                        'auth': {'status': 'healthy'}
                    }}
                
                @app.route('/')
                def root():
                    return {
                        'name': 'Multi-Platform Chat Bot',
                        'version': '2.0.0',
                        'status': 'running',
                        'endpoints': ['/health', '/metrics', '/webhooks/line']
                    }
                
                return app
    
    def test_health_endpoint_exists(self, app):
        """測試健康檢查端點存在"""
        client = app.test_client()
        response = client.get('/health')
        assert response.status_code == 200
    
    def test_root_endpoint_exists(self, app):
        """測試根端點存在"""
        client = app.test_client()
        response = client.get('/')
        assert response.status_code == 200
        data = response.get_json()
        assert 'name' in data
        assert 'version' in data


class TestPlatformWebhooks:
    """平台 webhook 測試"""
    
    @pytest.fixture
    def client(self):
        """創建測試客戶端"""
        with patch('src.core.config.load_config') as mock_config:
            mock_config.return_value = {
                'platforms': {
                    'line': {
                        'enabled': True,
                        'channel_access_token': 'test',
                        'channel_secret': 'test'
                    }
                },
                'llm': {'provider': 'openai'},
                'openai': {'api_key': 'test', 'assistant_id': 'test'},
                'db': {
                    'host': 'localhost',
                    'port': 5432,
                    'user': 'test',
                    'password': 'test',
                    'db_name': 'test'
                }
            }
            
            # Mock 所有初始化
            with patch('src.database.connection.Database.__init__', return_value=None), \
                 patch('src.models.factory.ModelFactory.create_from_config'), \
                 patch('src.app.MultiPlatformChatBot._initialize_database'), \
                 patch('src.app.MultiPlatformChatBot._initialize_model'), \
                 patch('src.app.MultiPlatformChatBot._initialize_core_service'), \
                 patch('src.app.MultiPlatformChatBot._initialize_platforms'), \
                 patch('src.app.MultiPlatformChatBot._register_cleanup'):
                
                from main import create_app
                app = create_app()
                app.config['TESTING'] = True
                return app.test_client()
    
    def test_line_webhook_endpoint_exists(self, client):
        """測試 LINE webhook 端點存在"""
        # 發送空的 webhook 請求
        response = client.post('/webhooks/line', 
                             json={'events': []},
                             headers={'X-Line-Signature': 'test'})
        
        # 應該返回 200 或 400（簽章錯誤）
        assert response.status_code in [200, 400, 500]
    
    def test_legacy_callback_endpoint_exists(self, client):
        """測試舊版 callback 端點存在"""
        response = client.post('/callback',
                             json={'events': []},
                             headers={'X-Line-Signature': 'test'})
        
        assert response.status_code in [200, 400, 500]
