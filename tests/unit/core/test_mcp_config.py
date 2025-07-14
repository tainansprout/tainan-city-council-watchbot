"""
測試 MCP 配置管理器
"""

import pytest
import json
import tempfile
import os
from unittest.mock import patch, mock_open, MagicMock
from src.core.mcp_config import MCPConfigManager


class TestMCPConfigManager:
    """測試 MCP 配置管理器"""
    
    def setup_method(self):
        """設定測試環境"""
        # 創建臨時目錄
        self.temp_dir = tempfile.mkdtemp()
        self.config_manager = MCPConfigManager(self.temp_dir)
        
        # 測試配置資料
        self.test_config = {
            "mcp_server": {
                "base_url": "http://localhost:3000/api/mcp",
                "timeout": 30,
                "retry_attempts": 3
            },
            "functions": [
                {
                    "name": "test_function",
                    "description": "測試函數",
                    "mcp_tool": "test_tool",
                    "enabled": True,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"}
                        },
                        "required": ["query"]
                    }
                }
            ],
            "tools": {
                "test_function": {
                    "validation": {
                        "required_fields": ["query"],
                        "field_limits": {
                            "query": {"max_length": 100}
                        }
                    }
                }
            }
        }
    
    def teardown_method(self):
        """清理測試環境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_init(self):
        """測試初始化"""
        config_manager = MCPConfigManager("test_dir")
        assert config_manager.config_dir == "test_dir"
        assert config_manager._config_cache == {}
        assert config_manager._last_modified == {}
    
    def test_load_mcp_config_success(self):
        """測試成功載入配置"""
        config_file = os.path.join(self.temp_dir, "test.json")
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_config, f)
        
        config = self.config_manager.load_mcp_config("test.json")
        assert config == self.test_config
        assert "test.json" in self.config_manager._config_cache
    
    def test_load_mcp_config_file_not_found(self):
        """測試文件不存在錯誤"""
        with pytest.raises(FileNotFoundError):
            self.config_manager.load_mcp_config("nonexistent.json")
    
    def test_load_mcp_config_invalid_json(self):
        """測試無效 JSON 格式"""
        config_file = os.path.join(self.temp_dir, "invalid.json")
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write("invalid json content")
        
        with pytest.raises(json.JSONDecodeError):
            self.config_manager.load_mcp_config("invalid.json")
    
    def test_validate_config_success(self):
        """測試配置驗證成功"""
        # 不應該拋出異常
        self.config_manager._validate_config(self.test_config)
    
    def test_validate_config_missing_sections(self):
        """測試缺少必要配置段"""
        invalid_config = {"mcp_server": {}}
        
        with pytest.raises(ValueError, match="Missing required section"):
            self.config_manager._validate_config(invalid_config)
    
    def test_validate_config_missing_base_url(self):
        """測試缺少 base_url"""
        invalid_config = {
            "mcp_server": {},
            "functions": [],
            "tools": {}
        }
        
        with pytest.raises(ValueError, match="Missing 'base_url'"):
            self.config_manager._validate_config(invalid_config)
    
    def test_validate_config_invalid_functions(self):
        """測試無效的函數配置"""
        invalid_config = {
            "mcp_server": {"base_url": "http://test"},
            "functions": [{"name": "test"}],  # 缺少 mcp_tool
            "tools": {}
        }
        
        with pytest.raises(ValueError, match="must have 'name' and 'mcp_tool'"):
            self.config_manager._validate_config(invalid_config)
    
    def test_get_server_config(self):
        """測試取得服務器配置"""
        config_file = os.path.join(self.temp_dir, "test.json")
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_config, f)
        
        server_config = self.config_manager.get_server_config("test.json")
        assert server_config == self.test_config["mcp_server"]
    
    def test_get_function_schemas_for_openai(self):
        """測試取得 OpenAI 函數模式"""
        config_file = os.path.join(self.temp_dir, "test.json")
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_config, f)
        
        schemas = self.config_manager.get_function_schemas_for_openai("test.json")
        assert len(schemas) == 1
        assert schemas[0]["type"] == "function"
        assert schemas[0]["function"]["name"] == "test_function"
    
    def test_get_function_schemas_for_anthropic(self):
        """測試取得 Anthropic 函數模式"""
        config_file = os.path.join(self.temp_dir, "test.json")
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_config, f)
        
        prompt = self.config_manager.get_function_schemas_for_anthropic("test.json")
        assert "Available tools:" in prompt
        assert "test_function" in prompt
        assert "測試函數" in prompt
    
    def test_get_function_by_name(self):
        """測試根據名稱取得函數"""
        config_file = os.path.join(self.temp_dir, "test.json")
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_config, f)
        
        func = self.config_manager.get_function_by_name("test_function", "test.json")
        assert func is not None
        assert func["name"] == "test_function"
        
        # 測試不存在的函數
        func = self.config_manager.get_function_by_name("nonexistent", "test.json")
        assert func is None
    
    def test_validate_function_arguments_success(self):
        """測試函數參數驗證成功"""
        config_file = os.path.join(self.temp_dir, "test.json")
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_config, f)
        
        valid, error = self.config_manager.validate_function_arguments(
            "test_function", {"query": "test"}, "test.json"
        )
        assert valid is True
        assert error is None
    
    def test_validate_function_arguments_missing_required(self):
        """測試缺少必要參數"""
        config_file = os.path.join(self.temp_dir, "test.json")
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_config, f)
        
        valid, error = self.config_manager.validate_function_arguments(
            "test_function", {}, "test.json"
        )
        assert valid is False
        assert "Missing required field: query" in error
    
    def test_validate_function_arguments_exceed_limit(self):
        """測試參數超出限制"""
        config_file = os.path.join(self.temp_dir, "test.json")
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_config, f)
        
        valid, error = self.config_manager.validate_function_arguments(
            "test_function", {"query": "x" * 101}, "test.json"
        )
        assert valid is False
        assert "exceeds max length" in error
    
    def test_validate_function_arguments_unknown_function(self):
        """測試未知函數"""
        config_file = os.path.join(self.temp_dir, "test.json")
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_config, f)
        
        valid, error = self.config_manager.validate_function_arguments(
            "unknown_function", {"query": "test"}, "test.json"
        )
        assert valid is False
        assert "Unknown function: unknown_function" in error
    
    def test_list_available_configs(self):
        """測試列出可用配置"""
        # 創建測試配置文件
        config_file = os.path.join(self.temp_dir, "test.json")
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_config, f)
        
        # 創建範例文件（應該被忽略）
        example_file = os.path.join(self.temp_dir, "example.json.example")
        with open(example_file, 'w', encoding='utf-8') as f:
            f.write("{}")
        
        configs = self.config_manager.list_available_configs()
        assert "test.json" in configs
        assert "example.json.example" not in configs
    
    def test_is_mcp_enabled_true(self):
        """測試 MCP 啟用檢查 - 啟用"""
        config_file = os.path.join(self.temp_dir, "test.json")
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_config, f)
        
        with patch('src.core.config.get_value') as mock_get_value:
            mock_get_value.side_effect = lambda key, default: True if 'mcp' in key else default
            
            enabled = self.config_manager.is_mcp_enabled()
            assert enabled is True
    
    def test_is_mcp_enabled_false_no_configs(self):
        """測試 MCP 啟用檢查 - 沒有配置文件"""
        with patch('src.core.config.get_value') as mock_get_value:
            mock_get_value.side_effect = lambda key, default: True if 'mcp' in key else default
            
            enabled = self.config_manager.is_mcp_enabled()
            assert enabled is False
    
    def test_reload_config(self):
        """測試重新載入配置"""
        config_file = os.path.join(self.temp_dir, "test.json")
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_config, f)
        
        # 載入配置
        self.config_manager.load_mcp_config("test.json")
        assert "test.json" in self.config_manager._config_cache
        
        # 重新載入
        self.config_manager.reload_config("test.json")
        assert "test.json" not in self.config_manager._config_cache
    
    def test_should_reload_new_file(self):
        """測試是否需要重新載入 - 新文件"""
        config_file = os.path.join(self.temp_dir, "test.json")
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_config, f)
        
        should_reload = self.config_manager._should_reload(config_file)
        assert should_reload is True
    
    def test_should_reload_modified_file(self):
        """測試是否需要重新載入 - 修改過的文件"""
        config_file = os.path.join(self.temp_dir, "test.json")
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_config, f)
        
        # 記錄初始修改時間
        initial_mtime = os.path.getmtime(config_file)
        self.config_manager._last_modified[config_file] = initial_mtime
        
        # 修改文件
        import time
        time.sleep(0.1)  # 確保修改時間不同
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_config, f)
        
        should_reload = self.config_manager._should_reload(config_file)
        assert should_reload is True
    
    def test_find_available_config_success(self):
        """測試尋找可用配置成功"""
        config_file = os.path.join(self.temp_dir, "test.json")
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_config, f)
        
        config_name = self.config_manager._find_available_config()
        assert config_name == "test.json"
    
    def test_find_available_config_no_configs(self):
        """測試尋找可用配置失敗"""
        with pytest.raises(FileNotFoundError, match="No MCP config files found"):
            self.config_manager._find_available_config()
    
    def test_find_available_config_no_directory(self):
        """測試配置目錄不存在"""
        config_manager = MCPConfigManager("/nonexistent/directory")
        with pytest.raises(FileNotFoundError, match="MCP config directory not found"):
            config_manager._find_available_config()
    
    def test_get_error_messages(self):
        """測試取得錯誤訊息"""
        config_with_errors = {
            **self.test_config,
            "error_handling": {
                "fallback_messages": {
                    "connection_error": "連線失敗",
                    "timeout_error": "請求超時"
                }
            }
        }
        
        config_file = os.path.join(self.temp_dir, "test.json")
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_with_errors, f)
        
        error_messages = self.config_manager.get_error_messages("test.json")
        assert error_messages["connection_error"] == "連線失敗"
        assert error_messages["timeout_error"] == "請求超時"
    
    def test_get_default_params(self):
        """測試取得預設參數"""
        config_with_defaults = {
            **self.test_config,
            "default_search_params": {
                "max_results": 20,
                "timeout": 30
            }
        }
        
        config_file = os.path.join(self.temp_dir, "test.json")
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_with_defaults, f)
        
        default_params = self.config_manager.get_default_params("test.json")
        assert default_params["max_results"] == 20
        assert default_params["timeout"] == 30