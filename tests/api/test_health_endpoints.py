"""
測試新架構的健康檢查和指標端點
"""
import pytest
import json
from unittest.mock import Mock, patch


class TestHealthEndpoint:
    """測試健康檢查端點"""
    
    @pytest.fixture
    def client(self):
        """測試客戶端"""
        with patch('src.core.config.load_config') as mock_config:
            mock_config.return_value = {
                'app': {'name': 'Test Bot', 'version': '2.0.0'},
                'platforms': {
                    'line': {
                        'enabled': True,
                        'channel_access_token': 'test_token',
                        'channel_secret': 'test_secret'
                    }
                },
                'llm': {'provider': 'openai'},
                'openai': {'api_key': 'test_key', 'assistant_id': 'test_id'},
                'db': {'host': 'localhost', 'user': 'test', 'password': 'test', 'db_name': 'test'}
            }
            
            from main import create_app
            app = create_app()
            app.config['TESTING'] = True
            
            return app.test_client()
    
    def test_health_check_all_healthy(self, client):
        """測試所有組件都健康的情況"""
        with patch('src.app.MultiPlatformChatBot.database') as mock_db, \
             patch('src.app.MultiPlatformChatBot.model') as mock_model:
            
            # 模擬資料庫健康
            mock_session = Mock()
            mock_db.get_session.return_value.__enter__ = Mock(return_value=mock_session)
            mock_db.get_session.return_value.__exit__ = Mock(return_value=None)
            mock_session.execute.return_value = None
            
            # 模擬模型健康
            mock_model.check_connection.return_value = (True, None)
            
            response = client.get('/health')
            
            assert response.status_code == 200
            data = response.get_json()
            
            # 檢查基本結構
            assert data['status'] == 'healthy'
            assert 'checks' in data
            assert 'timestamp' in data
            assert 'version' in data
            
            # 檢查各項檢查結果
            checks = data['checks']
            assert checks['database']['status'] == 'healthy'
            assert checks['model']['status'] == 'healthy'
            assert checks['platforms']['status'] == 'healthy'
            assert checks['platforms']['enabled_count'] >= 1
            assert 'line' in checks['platforms']['platforms']
            assert 'auth' in checks
    
    def test_health_check_database_error(self, client):
        """測試資料庫錯誤"""
        with patch('src.app.MultiPlatformChatBot.database') as mock_db, \
             patch('src.app.MultiPlatformChatBot.model') as mock_model:
            
            # 模擬資料庫錯誤
            mock_session = Mock()
            mock_db.get_session.return_value.__enter__ = Mock(return_value=mock_session)
            mock_db.get_session.return_value.__exit__ = Mock(return_value=None)
            mock_session.execute.side_effect = Exception("Database connection failed")
            
            # 模型正常
            mock_model.check_connection.return_value = (True, None)
            
            response = client.get('/health')
            
            assert response.status_code == 503
            data = response.get_json()
            assert data['status'] == 'unhealthy'
            assert data['checks']['database']['status'] == 'unhealthy'
            assert 'Database connection failed' in data['checks']['database']['error']
    
    def test_health_check_model_error(self, client):
        """測試模型錯誤"""
        with patch('src.app.MultiPlatformChatBot.database') as mock_db, \
             patch('src.app.MultiPlatformChatBot.model') as mock_model:
            
            # 資料庫正常
            mock_session = Mock()
            mock_db.get_session.return_value.__enter__ = Mock(return_value=mock_session)
            mock_db.get_session.return_value.__exit__ = Mock(return_value=None)
            mock_session.execute.return_value = None
            
            # 模型錯誤
            mock_model.check_connection.return_value = (False, "API key invalid")
            
            response = client.get('/health')
            
            assert response.status_code == 503
            data = response.get_json()
            assert data['status'] == 'unhealthy'
            assert data['checks']['model']['status'] == 'unhealthy'
            assert 'API key invalid' in data['checks']['model']['error']
    
    def test_health_check_no_platforms(self, client):
        """測試沒有啟用平台的情況"""
        with patch('src.core.config.load_config') as mock_config, \
             patch('src.app.MultiPlatformChatBot.database') as mock_db, \
             patch('src.app.MultiPlatformChatBot.model') as mock_model:
            
            # 配置無啟用平台
            mock_config.return_value = {
                'platforms': {},  # 空的平台配置
                'llm': {'provider': 'openai'},
                'openai': {'api_key': 'test', 'assistant_id': 'test'},
                'db': {'host': 'localhost', 'user': 'test', 'password': 'test', 'db_name': 'test'}
            }
            
            # 其他組件正常
            mock_session = Mock()
            mock_db.get_session.return_value.__enter__ = Mock(return_value=mock_session)
            mock_db.get_session.return_value.__exit__ = Mock(return_value=None)
            mock_session.execute.return_value = None
            mock_model.check_connection.return_value = (True, None)
            
            response = client.get('/health')
            
            data = response.get_json()
            assert data['checks']['platforms']['status'] == 'no_platforms'
            assert data['checks']['platforms']['enabled_count'] == 0


class TestMetricsEndpoint:
    """測試指標端點"""
    
    @pytest.fixture
    def client(self):
        """測試客戶端"""
        with patch('src.core.config.load_config') as mock_config:
            mock_config.return_value = {
                'platforms': {
                    'line': {
                        'enabled': True,
                        'channel_access_token': 'test_token',
                        'channel_secret': 'test_secret'
                    }
                },
                'llm': {'provider': 'openai'},
                'openai': {'api_key': 'test_key', 'assistant_id': 'test_id'},
                'db': {'host': 'localhost', 'user': 'test', 'password': 'test', 'db_name': 'test'}
            }
            
            from main import create_app
            app = create_app()
            app.config['TESTING'] = True
            
            return app.test_client()
    
    def test_metrics_basic_structure(self, client):
        """測試指標端點的基本結構"""
        with patch('src.app.MultiPlatformChatBot.database') as mock_db, \
             patch('src.app.MultiPlatformChatBot.model') as mock_model:
            
            # 模擬資料庫連接資訊
            mock_db.get_connection_info.return_value = {
                'pool_size': 10,
                'checked_in': 2,
                'checked_out': 1,
                'overflow': 0,
                'invalid': 0
            }
            
            # 模擬模型提供商
            mock_model.get_provider.return_value = Mock(value='openai')
            
            response = client.get('/metrics')
            
            assert response.status_code == 200
            data = response.get_json()
            
            # 檢查基本結構
            assert 'timestamp' in data
            assert 'platforms' in data
            assert 'model' in data
            assert 'database' in data
            
            # 檢查平台指標
            platforms = data['platforms']
            assert 'enabled' in platforms
            assert 'count' in platforms
            assert platforms['count'] >= 1
            assert 'line' in platforms['enabled']
            
            # 檢查模型指標
            model = data['model']
            assert model['provider'] == 'openai'
            
            # 檢查資料庫指標
            database = data['database']
            assert 'pool_size' in database
            assert database['pool_size'] == 10
    
    def test_metrics_error_handling(self, client):
        """測試指標端點的錯誤處理"""
        with patch('src.app.MultiPlatformChatBot.database') as mock_db:
            # 模擬資料庫錯誤
            mock_db.get_connection_info.side_effect = Exception("Database error")
            
            response = client.get('/metrics')
            
            assert response.status_code == 500
            data = response.get_json()
            assert 'error' in data


class TestRootEndpoint:
    """測試根端點"""
    
    @pytest.fixture
    def client(self):
        """測試客戶端"""
        with patch('src.core.config.load_config') as mock_config:
            mock_config.return_value = {
                'app': {'name': 'Test Bot', 'version': '2.0.0'},
                'platforms': {
                    'line': {
                        'enabled': True,
                        'channel_access_token': 'test_token',
                        'channel_secret': 'test_secret'
                    }
                },
                'llm': {'provider': 'openai'},
                'openai': {'api_key': 'test_key', 'assistant_id': 'test_id'},
                'db': {'host': 'localhost', 'user': 'test', 'password': 'test', 'db_name': 'test'}
            }
            
            from main import create_app
            app = create_app()
            app.config['TESTING'] = True
            
            return app.test_client()
    
    def test_root_endpoint_structure(self, client):
        """測試根端點的結構"""
        response = client.get('/')
        
        assert response.status_code == 200
        data = response.get_json()
        
        # 檢查基本資訊
        assert 'name' in data
        assert 'version' in data
        assert 'platforms' in data
        assert 'status' in data
        
        # 檢查值
        assert data['status'] == 'running'
        assert data['version'] == '2.0.0'
        assert 'line' in data['platforms']
    
    def test_root_endpoint_default_values(self, client):
        """測試根端點的默認值"""
        with patch('src.core.config.load_config') as mock_config:
            # 配置沒有 app 資訊
            mock_config.return_value = {
                'platforms': {'line': {'enabled': True, 'channel_access_token': 'test', 'channel_secret': 'test'}},
                'llm': {'provider': 'openai'},
                'openai': {'api_key': 'test', 'assistant_id': 'test'},
                'db': {'host': 'localhost', 'user': 'test', 'password': 'test', 'db_name': 'test'}
            }
            
            from main import create_app
            app = create_app()
            app.config['TESTING'] = True
            
            client = app.test_client()
            response = client.get('/')
            
            data = response.get_json()
            
            # 檢查默認值
            assert data['name'] == 'Multi-Platform Chat Bot'  # 默認名稱
            assert data['version'] == '2.0.0'  # 默認版本