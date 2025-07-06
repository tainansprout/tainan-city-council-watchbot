"""
測試 ConfigManager 單例模式和配置管理功能
"""
import pytest
import os
import threading
import time
from unittest.mock import patch, mock_open, MagicMock
from src.core.config import (
    ConfigManager, load_config, get_config, get_value, 
    _get_env_value, _merge_env_config, get_config_value,
    get_cached_config, clear_config_cache, reload_config
)


class TestConfigManager:
    """測試 ConfigManager 類"""

    def test_singleton_pattern(self):
        """測試單例模式"""
        # 創建多個實例
        config1 = ConfigManager()
        config2 = ConfigManager()
        
        # 應該是同一個實例
        assert config1 is config2
        assert id(config1) == id(config2)

    def test_thread_safety(self):
        """測試線程安全"""
        instances = []
        
        def create_instance():
            instances.append(ConfigManager())
        
        # 創建多個線程同時創建實例
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=create_instance)
            threads.append(thread)
            thread.start()
        
        # 等待所有線程完成
        for thread in threads:
            thread.join()
        
        # 所有實例應該是同一個
        first_instance = instances[0]
        for instance in instances:
            assert instance is first_instance

    @patch('builtins.open', new_callable=mock_open, read_data="""
app:
  name: 測試應用
  version: 1.0.0
auth:
  method: simple_password
  password: test123
""")
    @patch('src.core.config.print')
    def test_config_loading_once(self, mock_print, mock_file):
        """測試配置只載入一次"""
        # 清理任何現有的配置管理器狀態
        ConfigManager._instance = None
        
        manager = ConfigManager()
        
        # 多次調用 get_config
        config1 = manager.get_config('test_config.yml')
        config2 = manager.get_config('test_config.yml')
        config3 = manager.get_config('test_config.yml')
        
        # 應該是相同的配置
        assert config1 == config2 == config3
        
        # 文件只應該被讀取一次
        assert mock_file.call_count == 1
        
        # 只應該打印一次載入訊息
        success_calls = [call for call in mock_print.call_args_list 
                        if '✅ 成功載入配置文件' in str(call)]
        assert len(success_calls) == 1

    @patch('builtins.open', new_callable=mock_open, read_data="""
test:
  nested:
    value: 123
    string: "hello"
""")
    def test_get_value_method(self, mock_file):
        """測試 get_value 方法"""
        # 清理任何現有的配置管理器狀態
        ConfigManager._instance = None
        
        manager = ConfigManager()
        
        # 測試獲取嵌套值
        assert manager.get_value('test.nested.value') == 123
        assert manager.get_value('test.nested.string') == "hello"
        
        # 測試不存在的值
        assert manager.get_value('test.nonexistent') is None
        assert manager.get_value('test.nonexistent', 'default') == 'default'

    def test_force_reload(self):
        """測試強制重載配置"""
        # 清理任何現有的配置管理器狀態
        ConfigManager._instance = None
        
        manager = ConfigManager()
        
        # 第一次載入的內容
        first_content = """
original: value1
"""
        
        # 第二次載入的內容
        second_content = """
original: value2
new: value3
"""
        
        # 創建一個可以改變返回值的 mock
        call_count = 0
        def mock_open_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_open(read_data=first_content)()
            else:
                return mock_open(read_data=second_content)()
        
        with patch('builtins.open', side_effect=mock_open_side_effect):
            # 第一次載入
            config1 = manager.get_config('test_config.yml')
            assert config1['original'] == 'value1'
            
            # 強制重載
            config2 = manager.get_config('test_config.yml', force_reload=True)
            assert config2['original'] == 'value2'
            assert config2['new'] == 'value3'


class TestConfigFunctions:
    """測試配置相關的便利函數"""

    @patch('src.core.config._config_manager')
    def test_load_config_function(self, mock_manager):
        """測試 load_config 函數"""
        mock_config = {'test': 'value'}
        mock_manager.get_config.return_value = mock_config
        
        result = load_config('test.yml')
        
        mock_manager.get_config.assert_called_once_with('test.yml', False)
        assert result == mock_config

    @patch('src.core.config._config_manager')
    def test_get_config_function(self, mock_manager):
        """測試 get_config 便利函數"""
        mock_config = {'test': 'value'}
        mock_manager.get_config.return_value = mock_config
        
        result = get_config('test.yml')
        
        mock_manager.get_config.assert_called_once_with('test.yml')
        assert result == mock_config

    @patch('src.core.config._config_manager')
    def test_get_value_function(self, mock_manager):
        """測試 get_value 便利函數"""
        mock_manager.get_value.return_value = 'test_value'
        
        result = get_value('test.path', 'default')
        
        mock_manager.get_value.assert_called_once_with('test.path', 'default')
        assert result == 'test_value'

    def teardown_method(self):
        """清理測試環境"""
        # 重置 ConfigManager 實例
        ConfigManager._instance = None


class TestGetEnvValue:
    """測試 _get_env_value 函數"""
    
    def test_get_env_value_boolean_true(self):
        """測試布爾值轉換 - True 情況"""
        with patch.dict(os.environ, {'TEST_BOOL': 'true'}):
            result = _get_env_value('TEST_BOOL', False)
            assert result is True
            
        with patch.dict(os.environ, {'TEST_BOOL': '1'}):
            result = _get_env_value('TEST_BOOL', False)
            assert result is True
            
        with patch.dict(os.environ, {'TEST_BOOL': 'yes'}):
            result = _get_env_value('TEST_BOOL', False)
            assert result is True
            
        with patch.dict(os.environ, {'TEST_BOOL': 'on'}):
            result = _get_env_value('TEST_BOOL', False)
            assert result is True
    
    def test_get_env_value_boolean_false(self):
        """測試布爾值轉換 - False 情況"""
        with patch.dict(os.environ, {'TEST_BOOL': 'false'}):
            result = _get_env_value('TEST_BOOL', True)
            assert result is False
            
        with patch.dict(os.environ, {'TEST_BOOL': 'no'}):
            result = _get_env_value('TEST_BOOL', True)
            assert result is False
    
    def test_get_env_value_int_valid(self):
        """測試整數轉換 - 有效值"""
        with patch.dict(os.environ, {'TEST_INT': '123'}):
            result = _get_env_value('TEST_INT', 0)
            assert result == 123
    
    def test_get_env_value_int_invalid(self):
        """測試整數轉換 - 無效值"""
        with patch.dict(os.environ, {'TEST_INT': 'invalid'}):
            result = _get_env_value('TEST_INT', 42)
            assert result == 42  # 應該返回默認值
    
    def test_get_env_value_float_valid(self):
        """測試浮點數轉換 - 有效值"""
        with patch.dict(os.environ, {'TEST_FLOAT': '3.14'}):
            result = _get_env_value('TEST_FLOAT', 0.0)
            assert result == 3.14
    
    def test_get_env_value_float_invalid(self):
        """測試浮點數轉換 - 無效值"""
        with patch.dict(os.environ, {'TEST_FLOAT': 'invalid'}):
            result = _get_env_value('TEST_FLOAT', 2.0)
            assert result == 2.0  # 應該返回默認值
    
    def test_get_env_value_string(self):
        """測試字符串值"""
        with patch.dict(os.environ, {'TEST_STRING': 'hello world'}):
            result = _get_env_value('TEST_STRING', 'default')
            assert result == 'hello world'
    
    def test_get_env_value_none(self):
        """測試環境變數不存在的情況"""
        # 確保環境變數不存在
        if 'NON_EXISTENT_VAR' in os.environ:
            del os.environ['NON_EXISTENT_VAR']
        
        result = _get_env_value('NON_EXISTENT_VAR', 'default')
        assert result == 'default'


class TestMergeEnvConfig:
    """測試 _merge_env_config 函數"""
    
    def test_merge_env_config_empty(self):
        """測試空配置的合併"""
        config = {}
        result = _merge_env_config(config)
        
        # 檢查是否創建了必要的配置節點
        assert 'platforms' in result
        assert 'line' in result['platforms']
        assert 'openai' in result
        assert 'db' in result
        assert 'auth' in result
    
    def test_merge_env_config_with_env_vars(self):
        """測試環境變數覆蓋配置"""
        config = {
            'platforms': {'line': {'channel_access_token': 'old_token'}},
            'openai': {'api_key': 'old_key'},
            'db': {'host': 'old_host'}
        }
        
        env_vars = {
            'LINE_CHANNEL_ACCESS_TOKEN': 'new_token',
            'OPENAI_API_KEY': 'new_key',
            'DB_HOST': 'new_host'
        }
        
        with patch.dict(os.environ, env_vars):
            result = _merge_env_config(config)
            
            assert result['platforms']['line']['channel_access_token'] == 'new_token'
            assert result['openai']['api_key'] == 'new_key'
            assert result['db']['host'] == 'new_host'


class TestConfigValue:
    """測試 get_config_value 函數"""
    
    def test_get_config_value_nested(self):
        """測試嵌套配置值獲取"""
        config = {
            'db': {
                'host': 'localhost',
                'port': 5432
            },
            'app': {
                'name': 'Test App'
            }
        }
        
        assert get_config_value(config, 'db.host') == 'localhost'
        assert get_config_value(config, 'db.port') == 5432
        assert get_config_value(config, 'app.name') == 'Test App'
    
    def test_get_config_value_missing(self):
        """測試不存在的配置值"""
        config = {'db': {'host': 'localhost'}}
        
        assert get_config_value(config, 'db.nonexistent') is None
        assert get_config_value(config, 'db.nonexistent', 'default') == 'default'
        assert get_config_value(config, 'nonexistent.key', 'default') == 'default'
    
    def test_get_config_value_invalid_path(self):
        """測試無效路徑"""
        config = {'db': 'not_a_dict'}
        
        assert get_config_value(config, 'db.host', 'default') == 'default'


class TestConfigErrorHandling:
    """測試配置錯誤處理"""
    
    @patch('src.core.config.print')
    def test_yaml_error_handling(self, mock_print):
        """測試 YAML 格式錯誤處理"""
        # 清理任何現有的配置管理器狀態
        ConfigManager._instance = None
        
        # 模擬 YAML 錯誤
        import yaml
        with patch('builtins.open', mock_open(read_data="invalid: yaml: [")):
            with patch('yaml.safe_load', side_effect=yaml.YAMLError("YAML Error")):
                manager = ConfigManager()
                config = manager.get_config('invalid.yml')
                
                # 檢查錯誤訊息
                error_calls = [call for call in mock_print.call_args_list 
                             if '❌ 配置文件格式錯誤' in str(call)]
                assert len(error_calls) == 1
                
                # 配置應該是空的（因為 YAML 錯誤導致提早返回）
                assert config == {}
    
    @patch('src.core.config.print')
    def test_file_not_found_handling(self, mock_print):
        """測試文件不存在的處理"""
        # 清理任何現有的配置管理器狀態
        ConfigManager._instance = None
        
        with patch('builtins.open', side_effect=FileNotFoundError()):
            manager = ConfigManager()
            config = manager.get_config('nonexistent.yml')
            
            # 檢查警告消息
            warning_calls = [call for call in mock_print.call_args_list 
                           if '⚠️  配置文件不存在' in str(call)]
            assert len(warning_calls) == 1
    
    @patch('src.core.config.print')
    def test_validation_warnings(self, mock_print):
        """測試配置驗證警告"""
        # 清理任何現有的配置管理器狀態
        ConfigManager._instance = None
        
        # 創建一個缺少必要配置的配置
        incomplete_config = {'app': {'name': 'test'}}
        
        with patch('builtins.open', mock_open(read_data='app:\n  name: test')):
            manager = ConfigManager()
            config = manager.get_config('test.yml')
            
            # 檢查警告消息
            warning_calls = [call for call in mock_print.call_args_list 
                           if '⚠️  缺少必要配置' in str(call)]
            assert len(warning_calls) == 1


class TestAdditionalFunctions:
    """測試額外的便利函數"""
    
    @patch('src.core.config._config_manager')
    def test_get_cached_config(self, mock_manager):
        """測試 get_cached_config 函數"""
        mock_config = {'test': 'value'}
        mock_manager.get_config.return_value = mock_config
        
        result = get_cached_config('test.yml')
        
        mock_manager.get_config.assert_called_once_with('test.yml')
        assert result == mock_config
    
    @patch('src.core.config._config_manager')
    def test_clear_config_cache(self, mock_manager):
        """測試 clear_config_cache 函數"""
        clear_config_cache()
        
        mock_manager.reload_config.assert_called_once()
    
    @patch('src.core.config._config_manager')
    def test_reload_config_function(self, mock_manager):
        """測試 reload_config 便利函數"""
        mock_config = {'reloaded': 'value'}
        mock_manager.reload_config.return_value = mock_config
        
        result = reload_config('test.yml')
        
        mock_manager.reload_config.assert_called_once_with('test.yml')
        assert result == mock_config