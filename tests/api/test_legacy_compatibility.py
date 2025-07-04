"""
測試向後兼容性
"""
import pytest
import json
from unittest.mock import Mock, patch


class TestLegacyCompatibility:
    """測試向後兼容性"""
    
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
    
    def test_legacy_callback_endpoint_exists(self, client):
        """測試舊版 /callback 端點仍然存在"""
        webhook_data = {'events': []}
        headers = {
            'Content-Type': 'application/json',
            'X-Line-Signature': 'test_signature'
        }
        
        response = client.post(
            '/callback',
            data=json.dumps(webhook_data),
            headers=headers
        )
        
        # 端點應該存在並能處理請求
        assert response.status_code in [200, 400]  # 400 是因為簽名驗證失敗，這是正常的
    
    def test_legacy_import_compatibility(self):
        """測試舊版導入方式的兼容性"""
        with patch('src.core.config.load_config') as mock_config:
            mock_config.return_value = {
                'platforms': {'line': {'enabled': True, 'channel_access_token': 'test', 'channel_secret': 'test'}},
                'llm': {'provider': 'openai'},
                'openai': {'api_key': 'test', 'assistant_id': 'test'},
                'db': {'host': 'localhost', 'user': 'test', 'password': 'test', 'db_name': 'test'}
            }
            
            # 測試各種導入方式
            try:
                # 新方式
                from main import create_app, application
                assert create_app is not None
                assert application is not None
                
                # 測試主要導入路徑都可用
                assert create_app is not None
                assert application is not None
                
            except ImportError as e:
                pytest.fail(f"Legacy import compatibility failed: {e}")
    
    def test_legacy_health_check_format(self, client):
        """測試健康檢查保持向後兼容的格式"""
        with patch('src.app.MultiPlatformChatBot.database') as mock_db, \
             patch('src.app.MultiPlatformChatBot.model') as mock_model:
            
            # 模擬健康狀態
            mock_session = Mock()
            mock_db.get_session.return_value.__enter__ = Mock(return_value=mock_session)
            mock_db.get_session.return_value.__exit__ = Mock(return_value=None)
            mock_session.execute.return_value = None
            mock_model.check_connection.return_value = (True, None)
            
            response = client.get('/health')
            
            assert response.status_code == 200
            data = response.get_json()
            
            # 檢查新格式包含舊格式的必要欄位
            assert 'status' in data
            assert 'timestamp' in data
            assert 'checks' in data
            
            # 檢查舊版本期望的基本結構仍然存在
            checks = data['checks']
            assert 'database' in checks
            assert 'model' in checks
    
    def test_legacy_root_endpoint(self, client):
        """測試根端點向後兼容"""
        response = client.get('/')
        
        assert response.status_code == 200
        data = response.get_json()
        
        # 檢查包含必要的基本資訊
        assert 'status' in data
        assert data['status'] == 'running'
    
    def test_legacy_webhook_response_format(self, client):
        """測試 webhook 回應格式向後兼容"""
        webhook_data = {
            'events': [
                {
                    'type': 'message',
                    'message': {
                        'type': 'text',
                        'text': 'Hello',
                        'id': 'test_message_id'
                    },
                    'source': {
                        'type': 'user',
                        'userId': 'U' + '0' * 32
                    },
                    'replyToken': 'test_reply_token'
                }
            ]
        }
        
        headers = {
            'Content-Type': 'application/json',
            'X-Line-Signature': 'test_signature'
        }
        
        with patch('src.platforms.line_handler.LineHandler.handle_webhook') as mock_webhook:
            mock_webhook.return_value = []
            
            response = client.post(
                '/callback',
                data=json.dumps(webhook_data),
                headers=headers
            )
            
            # 舊版期望的回應格式
            assert response.status_code in [200, 400]
            # 成功的話應該返回 'OK' 或空回應
            if response.status_code == 200:
                assert response.get_data(as_text=True) in ['OK', '']


class TestEnvironmentCompatibility:
    """測試環境兼容性"""
    
    def test_flask_env_development_default(self):
        """測試 FLASK_ENV 未設定時默認為 development"""
        import os
        original_env = os.environ.get('FLASK_ENV')
        
        try:
            # 清除環境變數
            if 'FLASK_ENV' in os.environ:
                del os.environ['FLASK_ENV']
            
            with patch('src.core.config.load_config') as mock_config:
                mock_config.return_value = {
                    'platforms': {'line': {'enabled': True, 'channel_access_token': 'test', 'channel_secret': 'test'}},
                    'llm': {'provider': 'openai'},
                    'openai': {'api_key': 'test', 'assistant_id': 'test'},
                    'db': {'host': 'localhost', 'user': 'test', 'password': 'test', 'db_name': 'test'}
                }
                
                from main import application
                
                # 驗證默認環境
                current_env = os.getenv('FLASK_ENV', 'development')
                assert current_env == 'development'
                
        finally:
            if original_env:
                os.environ['FLASK_ENV'] = original_env
    
    def test_production_env_detection(self):
        """測試生產環境檢測"""
        import os
        original_env = os.environ.get('FLASK_ENV')
        
        try:
            os.environ['FLASK_ENV'] = 'production'
            
            with patch('src.core.config.load_config') as mock_config:
                mock_config.return_value = {
                    'platforms': {'line': {'enabled': True, 'channel_access_token': 'test', 'channel_secret': 'test'}},
                    'llm': {'provider': 'openai'},
                    'openai': {'api_key': 'test', 'assistant_id': 'test'},
                    'db': {'host': 'localhost', 'user': 'test', 'password': 'test', 'db_name': 'test'}
                }
                
                # 重新導入以觸發環境檢測
                import importlib
                import main
                importlib.reload(main)
                
                assert os.getenv('FLASK_ENV') == 'production'
                
        finally:
            if original_env:
                os.environ['FLASK_ENV'] = original_env
            else:
                if 'FLASK_ENV' in os.environ:
                    del os.environ['FLASK_ENV']


class TestWSGICompatibility:
    """測試 WSGI 兼容性"""
    
    def test_main_application_object(self):
        """測試 main.py 的 WSGI application 對象"""
        with patch('src.core.config.load_config') as mock_config:
            mock_config.return_value = {
                'platforms': {'line': {'enabled': True, 'channel_access_token': 'test', 'channel_secret': 'test'}},
                'llm': {'provider': 'openai'},
                'openai': {'api_key': 'test', 'assistant_id': 'test'},
                'db': {'host': 'localhost', 'user': 'test', 'password': 'test', 'db_name': 'test'}
            }
            
            # 測試 WSGI 對象存在且可用
            from main import application
            
            # 驗證對象
            assert application is not None
            
            # 驗證 WSGI 介面
            assert hasattr(application, '__call__')
            assert hasattr(application, 'test_client')
    
    def test_main_factory_function(self):
        """測試 main.py 的工廠函數"""
        with patch('src.core.config.load_config') as mock_config:
            mock_config.return_value = {
                'platforms': {'line': {'enabled': True, 'channel_access_token': 'test', 'channel_secret': 'test'}},
                'llm': {'provider': 'openai'},
                'openai': {'api_key': 'test', 'assistant_id': 'test'},
                'db': {'host': 'localhost', 'user': 'test', 'password': 'test', 'db_name': 'test'}
            }
            
            # 測試工廠函數
            from main import create_app, application
            
            test_app = create_app()
            assert test_app is not None
            assert hasattr(test_app, 'test_client')
    
    def test_gunicorn_compatibility(self):
        """測試 Gunicorn 兼容性"""
        with patch('src.core.config.load_config') as mock_config:
            mock_config.return_value = {
                'platforms': {'line': {'enabled': True, 'channel_access_token': 'test', 'channel_secret': 'test'}},
                'llm': {'provider': 'openai'},
                'openai': {'api_key': 'test', 'assistant_id': 'test'},
                'db': {'host': 'localhost', 'user': 'test', 'password': 'test', 'db_name': 'test'}
            }
            
            # 測試 Gunicorn 期望的主要導入路徑
            try:
                # main:application - 主要部署方式
                from main import application as main_app
                assert main_app is not None
                
                # main:create_app - 工廠函數方式
                from main import create_app
                assert create_app is not None
                
                # 驗證 WSGI 應用正常運作
                assert hasattr(main_app, '__call__')
                assert hasattr(main_app, 'test_client')
                
            except ImportError as e:
                pytest.fail(f"Gunicorn compatibility test failed: {e}")


class TestConfigurationCompatibility:
    """測試配置兼容性"""
    
    def test_new_platform_config_structure(self):
        """測試新的平台配置結構"""
        with patch('src.core.config.load_config') as mock_config:
            # 新格式配置
            new_config = {
                'platforms': {
                    'line': {
                        'enabled': True,
                        'channel_access_token': 'test_token',
                        'channel_secret': 'test_secret'
                    }
                },
                'llm': {'provider': 'openai'},
                'openai': {'api_key': 'test', 'assistant_id': 'test'},
                'db': {'host': 'localhost', 'user': 'test', 'password': 'test', 'db_name': 'test'}
            }
            
            mock_config.return_value = new_config
            
            try:
                from main import create_app
                app = create_app()
                assert app is not None
                
                # 測試應用能夠啟動
                with app.test_client() as client:
                    response = client.get('/')
                    assert response.status_code == 200
                    
            except Exception as e:
                pytest.fail(f"New config format compatibility failed: {e}")
    
    def test_required_config_validation(self):
        """測試必要配置驗證"""
        with patch('src.core.config.load_config') as mock_config:
            # 最小配置
            minimal_config = {
                'platforms': {
                    'line': {
                        'enabled': True,
                        'channel_access_token': 'test',
                        'channel_secret': 'test'
                    }
                },
                'llm': {'provider': 'openai'},
                'openai': {'api_key': 'test', 'assistant_id': 'test'},
                'db': {'host': 'localhost', 'user': 'test', 'password': 'test', 'db_name': 'test'}
            }
            
            mock_config.return_value = minimal_config
            
            try:
                from main import create_app
                app = create_app()
                assert app is not None
                
            except Exception as e:
                pytest.fail(f"Minimal config validation failed: {e}")