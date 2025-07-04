"""
測試 ConfigManager 單例模式和配置管理功能
"""
import pytest
import threading
import time
from unittest.mock import patch, mock_open
from src.core.config import ConfigManager, load_config, get_config, get_value


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

    @patch('builtins.open', new_callable=mock_open, read_data="""
original: value1
""")
    def test_force_reload(self, mock_file):
        """測試強制重載配置"""
        # 清理任何現有的配置管理器狀態
        ConfigManager._instance = None
        
        manager = ConfigManager()
        
        # 第一次載入
        config1 = manager.get_config('test_config.yml')
        assert config1['original'] == 'value1'
        
        # 模擬文件內容變更
        mock_file.return_value.read.return_value = """
original: value2
new: value3
"""
        
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