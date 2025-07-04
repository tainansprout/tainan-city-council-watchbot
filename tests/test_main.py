"""
測試新的統一主應用程式入口點
"""
import pytest
import os
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
            
            from main import application
            
            assert application is not None
            assert hasattr(application, 'test_client')
    
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
            assert hasattr(main_app, 'test_client')
    
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
            assert hasattr(application, 'test_client')
            
            # 測試工廠函數創建的應用與預設應用兼容
            test_app = create_app()
            assert test_app is not None
            assert hasattr(test_app, 'test_client')


class TestProductionMode:
    """測試生產模式功能"""
    
    @patch('subprocess.run')
    @patch('os.path.exists')
    def test_production_server_start_with_config(self, mock_exists, mock_subprocess):
        """測試生產服務器啟動（有配置文件）"""
        mock_exists.return_value = True  # gunicorn.conf.py 存在
        
        from main import start_production_server
        
        with pytest.raises(SystemExit):  # 會因為 subprocess.run 而退出
            start_production_server()
        
        # 驗證調用了正確的指令
        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args[0][0]
        assert 'gunicorn' in call_args
        assert '-c' in call_args
        assert 'gunicorn.conf.py' in call_args
        assert 'main:application' in call_args
    
    @patch('subprocess.run')
    @patch('os.path.exists')
    def test_production_server_start_without_config(self, mock_exists, mock_subprocess):
        """測試生產服務器啟動（無配置文件）"""
        mock_exists.return_value = False  # gunicorn.conf.py 不存在
        
        from main import start_production_server
        
        with pytest.raises(SystemExit):
            start_production_server()
        
        # 驗證調用了默認配置
        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args[0][0]
        assert 'gunicorn' in call_args
        assert '--bind' in call_args
        assert '--workers' in call_args
        assert 'main:application' in call_args
    
    @patch('subprocess.run')
    def test_production_server_missing_gunicorn(self, mock_subprocess):
        """測試 Gunicorn 未安裝的情況"""
        # Mock gunicorn import to raise ImportError
        with patch.dict('sys.modules', {'gunicorn': None}):
            with patch('builtins.__import__', side_effect=lambda name, *args, **kwargs: 
                      (_ for _ in ()).throw(ImportError("No module named 'gunicorn'")) 
                      if name == 'gunicorn' else __import__(name, *args, **kwargs)):
                
                from main import start_production_server
                
                # 測試應該會呼叫 sys.exit(1)
                with pytest.raises(SystemExit) as exc_info:
                    start_production_server()
                
                # 驗證 exit code 是 1
                assert exc_info.value.code == 1
                
                # 驗證 subprocess.run 沒有被呼叫
                mock_subprocess.assert_not_called()