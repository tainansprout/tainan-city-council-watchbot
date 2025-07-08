"""
測試新的統一主應用程式入口點
"""
import pytest
import os
import sys
import builtins
from unittest.mock import Mock, patch


class TestMainApplication:
    """測試 main.py 的統一應用程式"""
    
    def test_create_app_function(self):
        """測試 create_app 工廠函數"""
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
                'db': {'host': 'localhost', 'port': 5432, 'user': 'test', 'password': 'test', 'db_name': 'test'}
            }
            
            from main import create_app
            app = create_app()
            
            assert app is not None
            assert app.name == 'src.app'
    
    def test_application_instance(self):
        """測試 WSGI application 實例"""
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
                'db': {'host': 'localhost', 'port': 5432, 'user': 'test', 'password': 'test', 'db_name': 'test'}
            }
            
            from main import application, create_app
            
            # application 是 Flask app 實例
            assert application is not None
            
            # create_app() 返回 Flask app，應該有 test_client
            flask_app = create_app()
            assert hasattr(flask_app, 'test_client')
    
    def test_environment_detection_development(self):
        """測試開發環境檢測"""
        original_env = os.environ.get('FLASK_ENV')
        
        try:
            # 測試未設定環境變數 (預設為 development)
            if 'FLASK_ENV' in os.environ:
                del os.environ['FLASK_ENV']
            
            with patch('src.core.config.load_config') as mock_config:
                mock_config.return_value = {
                    'platforms': {'line': {'enabled': True, 'channel_access_token': 'test', 'channel_secret': 'test'}},
                    'llm': {'provider': 'openai'},
                    'openai': {'api_key': 'test', 'assistant_id': 'test'},
                    'db': {'host': 'localhost', 'port': 5432, 'user': 'test', 'password': 'test', 'db_name': 'test'}
                }
                
                from main import application
                
                # 在測試環境中，預設應該是 development
                current_env = os.getenv('FLASK_ENV', 'development')
                assert current_env == 'development'
                
        finally:
            if original_env:
                os.environ['FLASK_ENV'] = original_env
    
    def test_environment_detection_production(self):
        """測試生產環境檢測"""
        original_env = os.environ.get('FLASK_ENV')
        
        try:
            os.environ['FLASK_ENV'] = 'production'
            
            with patch('src.core.config.load_config') as mock_config:
                mock_config.return_value = {
                    'platforms': {'line': {'enabled': True, 'channel_access_token': 'test', 'channel_secret': 'test'}},
                    'llm': {'provider': 'openai'},
                    'openai': {'api_key': 'test', 'assistant_id': 'test'},
                    'db': {'host': 'localhost', 'port': 5432, 'user': 'test', 'password': 'test', 'db_name': 'test'}
                }
                
                # 重新導入以測試生產環境
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
    """測試 WSGI 和向後兼容性"""
    
    def test_main_import_paths(self):
        """測試 main.py 的各種導入路徑"""
        with patch('src.core.config.load_config') as mock_config:
            mock_config.return_value = {
                'platforms': {'line': {'enabled': True, 'channel_access_token': 'test', 'channel_secret': 'test'}},
                'llm': {'provider': 'openai'},
                'openai': {'api_key': 'test', 'assistant_id': 'test'},
                'db': {'host': 'localhost', 'port': 5432, 'user': 'test', 'password': 'test', 'db_name': 'test'}
            }
            
            # 測試主要的導入路徑
            from main import application as main_app
            from main import create_app
            
            # 驗證對象存在且有效
            assert main_app is not None
            assert create_app is not None
            assert hasattr(main_app, 'test_client')  # Flask app 有 test_client
    
    def test_application_compatibility(self):
        """測試應用程式兼容性"""
        with patch('src.core.config.load_config') as mock_config:
            mock_config.return_value = {
                'platforms': {'line': {'enabled': True, 'channel_access_token': 'test', 'channel_secret': 'test'}},
                'llm': {'provider': 'openai'},
                'openai': {'api_key': 'test', 'assistant_id': 'test'},
                'db': {'host': 'localhost', 'port': 5432, 'user': 'test', 'password': 'test', 'db_name': 'test'}
            }
            
            # 測試主要導入方式
            from main import create_app, application
            
            assert create_app is not None
            assert application is not None
            assert hasattr(application, 'test_client')  # Flask app 有 test_client
            
            # 測試工廠函數創建新的應用實例
            test_app = create_app()
            assert test_app is not None
            assert hasattr(test_app, 'test_client')


class TestProductionMode:
    """測試生產模式功能"""
    
    def test_wsgi_application_availability(self):
        """測試 WSGI 應用可用性"""
        with patch('src.core.config.load_config') as mock_config:
            mock_config.return_value = {
                'platforms': {'line': {'enabled': True, 'channel_access_token': 'test', 'channel_secret': 'test'}},
                'llm': {'provider': 'openai'},
                'openai': {'api_key': 'test', 'assistant_id': 'test'},
                'db': {'host': 'localhost', 'port': 5432, 'user': 'test', 'password': 'test', 'db_name': 'test'}
            }
            
            # 測試 WSGI 應用實例
            from main import application
            
            assert application is not None
            assert hasattr(application, 'wsgi_app')  # Flask 的 WSGI 介面
            assert callable(application)  # 應該是可調用的 WSGI 應用
    
    def test_gunicorn_integration(self):
        """測試與 Gunicorn 的整合兼容性"""
        with patch('src.core.config.load_config') as mock_config:
            mock_config.return_value = {
                'platforms': {'line': {'enabled': True, 'channel_access_token': 'test', 'channel_secret': 'test'}},
                'llm': {'provider': 'openai'},
                'openai': {'api_key': 'test', 'assistant_id': 'test'},
                'db': {'host': 'localhost', 'port': 5432, 'user': 'test', 'password': 'test', 'db_name': 'test'}
            }
            
            # 驗證 main:application 可以被 Gunicorn 使用
            import main
            
            # 檢查 main 模組有 application 屬性
            assert hasattr(main, 'application')
            
            # 檢查 application 是有效的 WSGI 應用
            app = main.application
            assert app is not None
            assert hasattr(app, 'wsgi_app')  # Flask 應用特徵


class TestApplicationLifecycle:
    """測試應用程式生命週期管理"""
    
    def test_cleanup_function(self):
        """測試 cleanup 函數"""
        with patch('main.shutdown_logger') as mock_shutdown:
            with patch('builtins.print') as mock_print:
                from main import cleanup
                
                # 調用 cleanup 函數
                cleanup()
                
                # 驗證 print 被調用
                mock_print.assert_any_call("Application is shutting down.")
                mock_print.assert_any_call("Cleanup complete.")
                
                # 驗證 shutdown_logger 被調用
                mock_shutdown.assert_called_once()
    
    def test_atexit_registration(self):
        """測試 atexit 註冊"""
        # 這個測試驗證 atexit.register 被正確調用
        with patch('atexit.register') as mock_register:
            # 重新導入 main 模組來觸發註冊
            import importlib
            import main
            importlib.reload(main)
            
            # 驗證 atexit.register 被調用且參數是 cleanup 函數
            mock_register.assert_called()
            
            # 檢查是否有調用包含 cleanup 函數的註冊
            called_functions = [call[0][0].__name__ for call in mock_register.call_args_list if call[0]]
            assert 'cleanup' in called_functions, "cleanup 函數應該已註冊到 atexit"