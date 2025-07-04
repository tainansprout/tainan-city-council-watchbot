"""
健康檢查端點測試 - 修復版
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from flask import Flask


class TestHealthEndpoint:
    """健康檢查端點測試"""
    
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
                },
                'app': {
                    'name': 'Test Bot',
                    'version': '2.0.0'
                }
            }
            
            # Mock all dependencies
            with patch('src.database.connection.Database.__init__', return_value=None), \
                 patch('src.models.factory.ModelFactory.create_from_config') as mock_model_factory, \
                 patch('src.app.MultiPlatformChatBot._initialize_database'), \
                 patch('src.app.MultiPlatformChatBot._initialize_model'), \
                 patch('src.app.MultiPlatformChatBot._initialize_core_service'), \
                 patch('src.app.MultiPlatformChatBot._initialize_platforms'), \
                 patch('src.app.MultiPlatformChatBot._register_cleanup'):
                
                # Setup mocks
                mock_model = Mock()
                mock_model.check_connection.return_value = (True, None)
                mock_model.get_provider.return_value = Mock(value='openai')
                mock_model_factory.return_value = mock_model
                
                from main import create_app
                app = create_app()
                app.config['TESTING'] = True
                
                # Mock the bot instance attributes
                app.extensions['bot'] = Mock()
                app.extensions['bot'].database = Mock()
                app.extensions['bot'].model = mock_model
                app.extensions['bot'].platform_manager = Mock()
                app.extensions['bot'].platform_manager.get_enabled_platforms.return_value = ['line']
                
                return app
    
    def test_health_check_all_healthy(self, app):
        """測試所有組件健康時的健康檢查"""
        with app.test_client() as client:
            # Setup mocks for healthy state
            bot = app.extensions['bot']
            bot.database.get_session.return_value.__enter__ = Mock()
            bot.database.get_session.return_value.__exit__ = Mock()
            bot.database.get_connection_info.return_value = {
                'pool_size': 10,
                'checked_out': 1
            }
            
            response = client.get('/health')
            assert response.status_code == 200
            
            data = response.get_json()
            assert data['status'] == 'healthy'
            assert 'checks' in data
            assert data['checks']['database']['status'] == 'healthy'
            assert data['checks']['model']['status'] == 'healthy'
    
    def test_health_check_database_error(self, app):
        """測試資料庫錯誤時的健康檢查"""
        with app.test_client() as client:
            # Setup database error
            bot = app.extensions['bot']
            bot.database.get_session.side_effect = Exception("Database connection failed")
            
            response = client.get('/health')
            assert response.status_code == 503
            
            data = response.get_json()
            assert data['status'] == 'unhealthy'
            assert data['checks']['database']['status'] == 'unhealthy'
    
    def test_health_check_model_error(self, app):
        """測試模型錯誤時的健康檢查"""
        with app.test_client() as client:
            # Setup model error
            bot = app.extensions['bot']
            bot.database.get_session.return_value.__enter__ = Mock()
            bot.database.get_session.return_value.__exit__ = Mock()
            bot.model.check_connection.return_value = (False, "API key invalid")
            
            response = client.get('/health')
            assert response.status_code == 503
            
            data = response.get_json()
            assert data['status'] == 'unhealthy'
            assert data['checks']['model']['status'] == 'unhealthy'
    
    def test_health_check_no_platforms(self, app):
        """測試沒有啟用平台時的健康檢查"""
        with app.test_client() as client:
            # Setup no platforms
            bot = app.extensions['bot']
            bot.database.get_session.return_value.__enter__ = Mock()
            bot.database.get_session.return_value.__exit__ = Mock()
            bot.platform_manager.get_enabled_platforms.return_value = []
            
            response = client.get('/health')
            # Should still be healthy even with no platforms
            assert response.status_code == 200


class TestMetricsEndpoint:
    """指標端點測試"""
    
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
                
                # Mock bot instance
                app.extensions['bot'] = Mock()
                app.extensions['bot'].database = Mock()
                app.extensions['bot'].platform_manager = Mock()
                
                return app
    
    def test_metrics_basic_structure(self, app):
        """測試指標的基本結構"""
        with app.test_client() as client:
            # Setup mocks
            bot = app.extensions['bot']
            bot.database.get_connection_info.return_value = {
                'pool_size': 10,
                'checked_out': 1
            }
            bot.platform_manager.get_platform_stats.return_value = {
                'line': {'messages_processed': 100}
            }
            
            response = client.get('/metrics')
            assert response.status_code == 200
            
            data = response.get_json()
            assert 'database' in data
            assert 'platforms' in data
    
    def test_metrics_error_handling(self, app):
        """測試指標錯誤處理"""
        with app.test_client() as client:
            # Setup error
            bot = app.extensions['bot']
            bot.database.get_connection_info.side_effect = Exception("Metrics error")
            
            response = client.get('/metrics')
            assert response.status_code == 500
            
            data = response.get_json()
            assert 'error' in data


class TestRootEndpoint:
    """根端點測試"""
    
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
                },
                'app': {
                    'name': 'Multi-Platform Chat Bot',
                    'version': '2.0.0'
                }
            }
            
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
                
                # Mock bot instance
                app.extensions['bot'] = Mock()
                app.extensions['bot'].platform_manager = Mock()
                app.extensions['bot'].platform_manager.get_enabled_platforms.return_value = ['line']
                
                return app
    
    def test_root_endpoint_structure(self, app):
        """測試根端點結構"""
        with app.test_client() as client:
            response = client.get('/')
            assert response.status_code == 200
            
            data = response.get_json()
            assert 'name' in data
            assert 'version' in data
            assert 'status' in data
            assert data['status'] == 'running'
    
    def test_root_endpoint_default_values(self, app):
        """測試根端點預設值"""
        with app.test_client() as client:
            response = client.get('/')
            data = response.get_json()
            
            assert data['name'] == 'Multi-Platform Chat Bot'
            assert data['version'] == '2.0.0'
            assert 'endpoints' in data
            assert isinstance(data['endpoints'], list)
