"""
測試 MCP 服務
"""

import pytest
import json
import inspect
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from src.services.mcp_service import MCPService, get_mcp_service, reload_mcp_service
from src.core.mcp_client import MCPClientError, MCPServerError


class TestMCPService:
    """測試 MCP 服務"""
    
    def setup_method(self):
        """設定測試環境"""
        # 重置全域實例
        import src.services.mcp_service as mcp_service_module
        mcp_service_module._mcp_service_instance = None
        
        # 模擬配置
        self.mock_config = {
            "mcp_server": {
                "base_url": "http://localhost:3000/api/mcp",
                "timeout": 30
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
                            "query": {
                                "type": "string",
                                "description": "Search query"
                            }
                        },
                        "required": ["query"]
                    }
                }
            ],
            "tools": {
                "test_function": {
                    "validation": {
                        "required_fields": ["query"]
                    }
                }
            }
        }
    
    def teardown_method(self):
        """清理測試環境"""
        # 重置全域實例
        import src.services.mcp_service as mcp_service_module
        mcp_service_module._mcp_service_instance = None
    
    @patch('src.services.mcp_service.MCPConfigManager')
    def test_init_enabled(self, mock_config_manager):
        """測試啟用服務初始化"""
        mock_manager = Mock()
        mock_manager.is_mcp_enabled.return_value = True
        mock_manager.get_server_config.return_value = self.mock_config["mcp_server"]
        mock_config_manager.return_value = mock_manager
        
        with patch('src.services.mcp_service.MCPClient') as mock_client:
            service = MCPService()
            
            assert service.is_enabled is True
            assert service.mcp_client is not None
            mock_client.assert_called_once()
    
    @patch('src.services.mcp_service.MCPConfigManager')
    def test_init_disabled(self, mock_config_manager):
        """測試禁用服務初始化"""
        mock_manager = Mock()
        mock_manager.is_mcp_enabled.return_value = False
        mock_config_manager.return_value = mock_manager
        
        service = MCPService()
        
        assert service.is_enabled is False
        assert service.mcp_client is None
    
    @patch('src.services.mcp_service.MCPConfigManager')
    def test_init_exception(self, mock_config_manager):
        """測試初始化異常處理"""
        mock_manager = Mock()
        mock_manager.is_mcp_enabled.return_value = True
        mock_manager.get_server_config.side_effect = Exception("Config error")
        mock_config_manager.return_value = mock_manager
        
        service = MCPService()
        
        assert service.is_enabled is False
        assert service.mcp_client is None
    
    @patch('src.services.mcp_service.MCPConfigManager')
    def test_handle_function_call_disabled(self, mock_config_manager):
        """測試禁用服務的函數呼叫"""
        mock_manager = Mock()
        mock_manager.is_mcp_enabled.return_value = False
        mock_config_manager.return_value = mock_manager
        
        service = MCPService()
        
        async def test():
            result = await service.handle_function_call("test_function", {"query": "test"})
            assert result["success"] is False
            assert "not enabled" in result["error"]
        
        import asyncio
        asyncio.run(test())
    
    @patch('src.services.mcp_service.MCPConfigManager')
    @patch('src.services.mcp_service.MCPClient')
    def test_handle_function_call_validation_error(self, mock_client, mock_config_manager):
        """測試函數呼叫參數驗證錯誤"""
        mock_manager = Mock()
        mock_manager.is_mcp_enabled.return_value = True
        mock_manager.get_server_config.return_value = self.mock_config["mcp_server"]
        mock_manager.validate_function_arguments.return_value = (False, "Missing required field")
        mock_config_manager.return_value = mock_manager
        
        service = MCPService()
        
        async def test():
            result = await service.handle_function_call("test_function", {})
            assert result["success"] is False
            assert "Parameter validation failed" in result["error"]
        
        import asyncio
        asyncio.run(test())
    
    @patch('src.services.mcp_service.MCPConfigManager')
    @patch('src.services.mcp_service.MCPClient')
    def test_handle_function_call_unknown_function(self, mock_client, mock_config_manager):
        """測試未知函數呼叫"""
        mock_manager = Mock()
        mock_manager.is_mcp_enabled.return_value = True
        mock_manager.get_server_config.return_value = self.mock_config["mcp_server"]
        mock_manager.validate_function_arguments.return_value = (True, None)
        mock_manager.get_function_by_name.return_value = None
        mock_config_manager.return_value = mock_manager
        
        service = MCPService()
        
        async def test():
            result = await service.handle_function_call("unknown_function", {"query": "test"})
            assert result["success"] is False
            assert "Unknown function" in result["error"]
        
        import asyncio
        asyncio.run(test())
    
    @patch('src.services.mcp_service.MCPConfigManager')
    @patch('src.services.mcp_service.MCPClient')
    def test_handle_function_call_success(self, mock_client, mock_config_manager):
        """測試成功的函數呼叫"""
        # 設定配置管理器
        mock_manager = Mock()
        mock_manager.is_mcp_enabled.return_value = True
        mock_manager.get_server_config.return_value = self.mock_config["mcp_server"]
        mock_manager.validate_function_arguments.return_value = (True, None)
        mock_manager.get_function_by_name.return_value = self.mock_config["functions"][0]
        mock_config_manager.return_value = mock_manager
        
        # 設定 MCP 客戶端
        mock_client_instance = Mock()
        mock_client_instance.call_tool = AsyncMock(return_value={
            "success": True,
            "data": "Test response",
            "content_type": "text",
            "metadata": {}
        })
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value = mock_client_instance
        
        service = MCPService()
        
        async def test():
            result = await service.handle_function_call("test_function", {"query": "test"})
            assert result["success"] is True
            assert result["data"] == "Test response"
            assert result["content_type"] == "text"
            assert "metadata" in result
        
        import asyncio
        asyncio.run(test())
    
    @patch('src.services.mcp_service.MCPConfigManager')
    @patch('src.services.mcp_service.MCPClient')
    def test_handle_function_call_mcp_error(self, mock_client, mock_config_manager):
        """測試 MCP 錯誤處理"""
        # 設定配置管理器
        mock_manager = Mock()
        mock_manager.is_mcp_enabled.return_value = True
        mock_manager.get_server_config.return_value = self.mock_config["mcp_server"]
        mock_manager.validate_function_arguments.return_value = (True, None)
        mock_manager.get_function_by_name.return_value = self.mock_config["functions"][0]
        mock_config_manager.return_value = mock_manager
        
        # 設定 MCP 客戶端錯誤
        mock_client_instance = Mock()
        mock_client_instance.call_tool = AsyncMock(side_effect=MCPClientError("Client error"))
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value = mock_client_instance
        
        service = MCPService()
        
        async def test():
            result = await service.handle_function_call("test_function", {"query": "test"})
            assert result["success"] is False
            assert "Client error" in result["error"]
        
        import asyncio
        asyncio.run(test())
    
    @patch('src.services.mcp_service.MCPConfigManager')
    @patch('src.services.mcp_service.MCPClient')
    def test_handle_function_call_server_error(self, mock_client, mock_config_manager):
        """測試 MCP 伺服器錯誤處理"""
        # 設定配置管理器
        mock_manager = Mock()
        mock_manager.is_mcp_enabled.return_value = True
        mock_manager.get_server_config.return_value = self.mock_config["mcp_server"]
        mock_manager.validate_function_arguments.return_value = (True, None)
        mock_manager.get_function_by_name.return_value = self.mock_config["functions"][0]
        mock_config_manager.return_value = mock_manager
        
        # 設定 MCP 客戶端錯誤
        mock_client_instance = Mock()
        mock_client_instance.call_tool = AsyncMock(side_effect=MCPServerError("Server error"))
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value = mock_client_instance
        
        service = MCPService()
        
        async def test():
            result = await service.handle_function_call("test_function", {"query": "test"})
            assert result["success"] is False
            assert "Server error" in result["error"]
        
        import asyncio
        asyncio.run(test())
    
    @patch('src.services.mcp_service.MCPConfigManager')
    def test_get_function_schemas_for_openai_disabled(self, mock_config_manager):
        """測試禁用服務的 OpenAI schemas"""
        mock_manager = Mock()
        mock_manager.is_mcp_enabled.return_value = False
        mock_config_manager.return_value = mock_manager
        
        service = MCPService()
        schemas = service.get_function_schemas_for_openai()
        
        assert schemas == []
    
    @patch('src.services.mcp_service.MCPConfigManager')
    def test_get_function_schemas_for_openai_enabled(self, mock_config_manager):
        """測試啟用服務的 OpenAI schemas"""
        mock_manager = Mock()
        mock_manager.is_mcp_enabled.return_value = True
        mock_manager.get_server_config.return_value = self.mock_config["mcp_server"]
        mock_manager.get_function_schemas_for_openai.return_value = [
            {"type": "function", "function": {"name": "test_function"}}
        ]
        mock_config_manager.return_value = mock_manager
        
        with patch('src.services.mcp_service.MCPClient'):
            service = MCPService()
            schemas = service.get_function_schemas_for_openai()
            
            assert len(schemas) == 1
            assert schemas[0]["type"] == "function"
    
    @patch('src.services.mcp_service.MCPConfigManager')
    def test_get_function_schemas_for_anthropic_disabled(self, mock_config_manager):
        """測試禁用服務的 Anthropic schemas"""
        mock_manager = Mock()
        mock_manager.is_mcp_enabled.return_value = False
        mock_config_manager.return_value = mock_manager
        
        service = MCPService()
        prompt = service.get_function_schemas_for_anthropic()
        
        assert prompt == ""
    
    @patch('src.services.mcp_service.MCPConfigManager')
    def test_get_function_schemas_for_anthropic_enabled(self, mock_config_manager):
        """測試啟用服務的 Anthropic schemas"""
        mock_manager = Mock()
        mock_manager.is_mcp_enabled.return_value = True
        mock_manager.get_server_config.return_value = self.mock_config["mcp_server"]
        mock_manager.get_function_schemas_for_anthropic.return_value = "Available tools: test_function"
        mock_config_manager.return_value = mock_manager
        
        with patch('src.services.mcp_service.MCPClient'):
            service = MCPService()
            prompt = service.get_function_schemas_for_anthropic()
            
            assert "Available tools: test_function" in prompt
    
    @patch('src.services.mcp_service.MCPConfigManager')
    def test_get_function_schemas_for_gemini_disabled(self, mock_config_manager):
        """測試禁用服務的 Gemini schemas"""
        mock_manager = Mock()
        mock_manager.is_mcp_enabled.return_value = False
        mock_config_manager.return_value = mock_manager
        
        service = MCPService()
        schemas = service.get_function_schemas_for_gemini()
        
        assert schemas == []
    
    @patch('src.services.mcp_service.MCPConfigManager')
    def test_get_function_schemas_for_gemini_enabled(self, mock_config_manager):
        """測試啟用服務的 Gemini schemas"""
        mock_manager = Mock()
        mock_manager.is_mcp_enabled.return_value = True
        mock_manager.get_server_config.return_value = self.mock_config["mcp_server"]
        mock_manager.load_mcp_config.return_value = self.mock_config
        mock_config_manager.return_value = mock_manager
        
        with patch('src.services.mcp_service.MCPClient'):
            service = MCPService()
            schemas = service.get_function_schemas_for_gemini()
            
            assert len(schemas) == 1
            assert schemas[0]["name"] == "test_function"
    
    @patch('src.services.mcp_service.MCPConfigManager')
    @patch('src.services.mcp_service.MCPClient')
    def test_list_available_tools_disabled(self, mock_client, mock_config_manager):
        """測試禁用服務的工具列表"""
        mock_manager = Mock()
        mock_manager.is_mcp_enabled.return_value = False
        mock_config_manager.return_value = mock_manager
        
        service = MCPService()
        
        async def test():
            success, tools, next_cursor, error = await service.list_available_tools()
            assert success is False
            assert tools is None
            assert next_cursor is None
            assert "not enabled" in error
        
        import asyncio
        asyncio.run(test())
    
    @patch('src.services.mcp_service.MCPConfigManager')
    @patch('src.services.mcp_service.MCPClient')
    def test_list_available_tools_enabled(self, mock_client, mock_config_manager):
        """測試啟用服務的工具列表"""
        mock_manager = Mock()
        mock_manager.is_mcp_enabled.return_value = True
        mock_manager.get_server_config.return_value = self.mock_config["mcp_server"]
        mock_config_manager.return_value = mock_manager
        
        mock_client_instance = Mock()
        mock_client_instance.list_tools = AsyncMock(return_value=(True, [{"name": "tool1"}], "cursor123", None))
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value = mock_client_instance
        
        service = MCPService()
        
        async def test():
            success, tools, next_cursor, error = await service.list_available_tools()
            assert success is True
            assert len(tools) == 1
            assert tools[0]["name"] == "tool1"
            assert next_cursor == "cursor123"
            assert error is None
        
        import asyncio
        asyncio.run(test())
    
    @patch('src.services.mcp_service.MCPConfigManager')
    @patch('src.services.mcp_service.MCPClient')
    def test_list_available_tools_with_cursor(self, mock_client, mock_config_manager):
        """測試帶 cursor 的工具列表"""
        mock_manager = Mock()
        mock_manager.is_mcp_enabled.return_value = True
        mock_manager.get_server_config.return_value = self.mock_config["mcp_server"]
        mock_config_manager.return_value = mock_manager
        
        mock_client_instance = Mock()
        mock_client_instance.list_tools = AsyncMock(return_value=(True, [{"name": "tool2"}], None, None))
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value = mock_client_instance
        
        service = MCPService()
        
        async def test():
            success, tools, next_cursor, error = await service.list_available_tools("cursor123")
            assert success is True
            assert len(tools) == 1
            assert tools[0]["name"] == "tool2"
            assert next_cursor is None
            assert error is None
            
            # 驗證 cursor 被傳遞
            mock_client_instance.list_tools.assert_called_once_with("cursor123")
        
        import asyncio
        asyncio.run(test())
    
    @patch('src.services.mcp_service.MCPConfigManager')
    @patch('src.services.mcp_service.MCPClient')
    def test_health_check_disabled(self, mock_client, mock_config_manager):
        """測試禁用服務的健康檢查"""
        mock_manager = Mock()
        mock_manager.is_mcp_enabled.return_value = False
        mock_config_manager.return_value = mock_manager
        
        service = MCPService()
        
        async def test():
            healthy, error = await service.health_check()
            assert healthy is False
            assert "not enabled" in error
        
        import asyncio
        asyncio.run(test())
    
    @patch('src.services.mcp_service.MCPConfigManager')
    @patch('src.services.mcp_service.MCPClient')
    def test_health_check_enabled(self, mock_client, mock_config_manager):
        """測試啟用服務的健康檢查"""
        mock_manager = Mock()
        mock_manager.is_mcp_enabled.return_value = True
        mock_manager.get_server_config.return_value = self.mock_config["mcp_server"]
        mock_config_manager.return_value = mock_manager
        
        mock_client_instance = Mock()
        mock_client_instance.health_check = AsyncMock(return_value=(True, None))
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value = mock_client_instance
        
        service = MCPService()
        
        async def test():
            healthy, error = await service.health_check()
            assert healthy is True
            assert error is None
        
        import asyncio
        asyncio.run(test())
    
    @patch('src.services.mcp_service.MCPConfigManager')
    @patch('src.services.mcp_service.MCPClient')
    def test_initialize_connection_success(self, mock_client, mock_config_manager):
        """測試成功初始化連線"""
        mock_manager = Mock()
        mock_manager.is_mcp_enabled.return_value = True
        mock_manager.get_server_config.return_value = self.mock_config["mcp_server"]
        mock_config_manager.return_value = mock_manager
        
        mock_client_instance = Mock()
        mock_client_instance.initialize_capabilities = AsyncMock(return_value=(True, None))
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value = mock_client_instance
        
        service = MCPService()
        
        async def test():
            success, error = await service.initialize_connection()
            assert success is True
            assert error is None
        
        import asyncio
        asyncio.run(test())
    
    @patch('src.services.mcp_service.MCPConfigManager')
    @patch('src.services.mcp_service.MCPClient')
    def test_setup_oauth_authentication_success(self, mock_client, mock_config_manager):
        """測試成功設定 OAuth 認證"""
        mock_manager = Mock()
        mock_manager.is_mcp_enabled.return_value = True
        mock_manager.get_server_config.return_value = self.mock_config["mcp_server"]
        mock_config_manager.return_value = mock_manager
        
        mock_client_instance = Mock()
        mock_client_instance.authenticate_oauth = AsyncMock(return_value=(True, "http://auth.url"))
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value = mock_client_instance
        
        service = MCPService()
        
        async def test():
            success, auth_url = await service.setup_oauth_authentication(
                "http://auth.server", "http://callback"
            )
            assert success is True
            assert auth_url == "http://auth.url"
        
        import asyncio
        asyncio.run(test())
    
    @patch('src.services.mcp_service.MCPConfigManager')
    @patch('src.services.mcp_service.MCPClient')
    def test_complete_oauth_authentication_success(self, mock_client, mock_config_manager):
        """測試成功完成 OAuth 認證"""
        mock_manager = Mock()
        mock_manager.is_mcp_enabled.return_value = True
        mock_manager.get_server_config.return_value = self.mock_config["mcp_server"]
        mock_config_manager.return_value = mock_manager
        
        mock_client_instance = Mock()
        mock_client_instance.complete_oauth_flow = AsyncMock(return_value=(True, None))
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value = mock_client_instance
        
        service = MCPService()
        
        async def test():
            success, error = await service.complete_oauth_authentication(
                "auth_code", "http://callback", "http://token.url"
            )
            assert success is True
            assert error is None
        
        import asyncio
        asyncio.run(test())
    
    @patch('src.services.mcp_service.MCPConfigManager')
    def test_get_configured_functions_disabled(self, mock_config_manager):
        """測試禁用服務的配置函數"""
        mock_manager = Mock()
        mock_manager.is_mcp_enabled.return_value = False
        mock_config_manager.return_value = mock_manager
        
        service = MCPService()
        functions = service.get_configured_functions()
        
        assert functions == []
    
    @patch('src.services.mcp_service.MCPConfigManager')
    def test_get_configured_functions_enabled(self, mock_config_manager):
        """測試啟用服務的配置函數"""
        mock_manager = Mock()
        mock_manager.is_mcp_enabled.return_value = True
        mock_manager.get_server_config.return_value = self.mock_config["mcp_server"]
        mock_manager.load_mcp_config.return_value = self.mock_config
        mock_config_manager.return_value = mock_manager
        
        with patch('src.services.mcp_service.MCPClient'):
            service = MCPService()
            functions = service.get_configured_functions()
            
            assert len(functions) == 1
            assert functions[0]["name"] == "test_function"
    
    @patch('src.services.mcp_service.MCPConfigManager')
    def test_get_service_info_disabled(self, mock_config_manager):
        """測試禁用服務的服務資訊"""
        mock_manager = Mock()
        mock_manager.is_mcp_enabled.return_value = False
        mock_manager.list_available_configs.return_value = []
        mock_config_manager.return_value = mock_manager
        
        service = MCPService()
        info = service.get_service_info()
        
        assert info["enabled"] is False
        assert info["configured_functions"] == 0
        assert "server_url" not in info
    
    @patch('src.services.mcp_service.MCPConfigManager')
    def test_get_service_info_enabled(self, mock_config_manager):
        """測試啟用服務的服務資訊"""
        mock_manager = Mock()
        mock_manager.is_mcp_enabled.return_value = True
        mock_manager.get_server_config.return_value = self.mock_config["mcp_server"]
        mock_manager.list_available_configs.return_value = ["test.json"]
        mock_manager.load_mcp_config.return_value = self.mock_config
        mock_config_manager.return_value = mock_manager
        
        with patch('src.services.mcp_service.MCPClient') as mock_client:
            mock_client_instance = Mock()
            mock_client_instance.base_url = "http://localhost:3000/api/mcp"
            mock_client_instance.timeout = 30
            mock_client_instance.auth_config = {}
            mock_client_instance.capabilities = {"roots": {}, "sampling": {}}
            mock_client_instance.access_token = None
            mock_client.return_value = mock_client_instance
            
            service = MCPService()
            info = service.get_service_info()
            
            assert info["enabled"] is True
            assert info["configured_functions"] == 1
            assert info["server_url"] == "http://localhost:3000/api/mcp"
            assert info["timeout"] == 30
            assert info["auth_configured"] is False
            assert info["has_access_token"] is False
            assert "roots" in info["capabilities"]
    
    @patch('src.services.mcp_service.MCPConfigManager')
    def test_reload_config_success(self, mock_config_manager):
        """測試成功重新載入配置"""
        mock_manager = Mock()
        mock_manager.is_mcp_enabled.return_value = True
        mock_manager.get_server_config.return_value = self.mock_config["mcp_server"]
        mock_manager.reload_config.return_value = None
        mock_config_manager.return_value = mock_manager
        
        with patch('src.services.mcp_service.MCPClient'):
            service = MCPService()
            success = service.reload_config()
            
            assert success is True
            mock_manager.reload_config.assert_called_once()
    
    @patch('src.services.mcp_service.MCPConfigManager')
    def test_reload_config_failure(self, mock_config_manager):
        """測試重新載入配置失敗"""
        mock_manager = Mock()
        mock_manager.is_mcp_enabled.return_value = True
        mock_manager.get_server_config.return_value = self.mock_config["mcp_server"]
        mock_manager.reload_config.side_effect = Exception("Reload failed")
        mock_config_manager.return_value = mock_manager
        
        with patch('src.services.mcp_service.MCPClient'):
            service = MCPService()
            success = service.reload_config()
            
            assert success is False
    
    def test_get_mcp_service_singleton(self):
        """測試單例模式"""
        with patch('src.services.mcp_service.MCPService') as mock_service:
            service1 = get_mcp_service()
            service2 = get_mcp_service()
            
            # 應該是同一個實例
            assert service1 is service2
            # 只應該創建一次
            mock_service.assert_called_once()
    
    def test_reload_mcp_service_with_instance(self):
        """測試重新載入全域服務（有實例）"""
        with patch('src.services.mcp_service.MCPService') as mock_service:
            mock_instance = Mock()
            mock_instance.reload_config.return_value = True
            mock_service.return_value = mock_instance
            
            # 創建實例
            get_mcp_service()
            
            # 重新載入
            success = reload_mcp_service()
            
            assert success is True
            mock_instance.reload_config.assert_called_once()
    
    def test_reload_mcp_service_without_instance(self):
        """測試重新載入全域服務（無實例）"""
        success = reload_mcp_service()
        assert success is False
    
    def test_format_error_response(self):
        """測試格式化錯誤回應"""
        mock_config_manager = Mock()
        mock_config_manager.is_mcp_enabled.return_value = False
        
        with patch('src.services.mcp_service.MCPConfigManager', return_value=mock_config_manager):
            service = MCPService()
            
            response = service._format_error_response("Test error")
            
            assert response["success"] is False
            assert response["error"] == "Test error"
            assert "fallback_message" in response
            assert response["metadata"]["error_type"] == "mcp_service_error"
    
    def test_get_fallback_message_connection_error(self):
        """測試取得連線錯誤的 fallback 訊息"""
        mock_config_manager = Mock()
        mock_config_manager.is_mcp_enabled.return_value = False
        mock_config_manager.get_error_messages.return_value = {
            "connection_error": "自定義連線錯誤訊息"
        }
        
        with patch('src.services.mcp_service.MCPConfigManager', return_value=mock_config_manager):
            service = MCPService()
            
            message = service._get_fallback_message("Connection failed")
            assert message == "自定義連線錯誤訊息"
    
    def test_get_fallback_message_timeout_error(self):
        """測試取得超時錯誤的 fallback 訊息"""
        mock_config_manager = Mock()
        mock_config_manager.is_mcp_enabled.return_value = False
        mock_config_manager.get_error_messages.return_value = {
            "timeout_error": "自定義超時錯誤訊息"
        }
        
        with patch('src.services.mcp_service.MCPConfigManager', return_value=mock_config_manager):
            service = MCPService()
            
            message = service._get_fallback_message("Request timeout")
            assert message == "自定義超時錯誤訊息"
    
    def test_get_fallback_message_default(self):
        """測試取得預設 fallback 訊息"""
        mock_config_manager = Mock()
        mock_config_manager.is_mcp_enabled.return_value = False
        mock_config_manager.get_error_messages.return_value = {}
        
        with patch('src.services.mcp_service.MCPConfigManager', return_value=mock_config_manager):
            service = MCPService()
            
            message = service._get_fallback_message("Unknown error")


class TestMCPServiceAsyncIntegration:
    """測試 MCP 服務的 async 集成功能"""

    def setup_method(self):
        """設定測試環境"""
        # 重置全域實例
        import src.services.mcp_service as mcp_service_module
        mcp_service_module._mcp_service_instance = None

    def test_sync_wrapper_methods_exist(self):
        """測試 sync 包裝器方法是否存在"""
        mock_config_manager = Mock()
        mock_config_manager.is_mcp_enabled.return_value = False
        
        with patch('src.services.mcp_service.MCPConfigManager', return_value=mock_config_manager):
            service = MCPService()
            
            # 檢查方法存在
            assert hasattr(service, 'handle_function_call_sync')
            assert hasattr(service, 'handle_function_call_async')
            assert hasattr(service, 'handle_function_call')
            
            # 檢查方法類型
            assert not inspect.iscoroutinefunction(service.handle_function_call_sync)
            assert inspect.iscoroutinefunction(service.handle_function_call_async)
            assert inspect.iscoroutinefunction(service.handle_function_call)

    def test_sync_wrapper_disabled_service(self):
        """測試 sync 包裝器在服務未啟用時的行為"""
        mock_config_manager = Mock()
        mock_config_manager.is_mcp_enabled.return_value = False
        
        with patch('src.services.mcp_service.MCPConfigManager', return_value=mock_config_manager):
            service = MCPService()
            service.is_enabled = False
            
            result = service.handle_function_call_sync("test_function", {"arg1": "value1"})
            
            # 應該返回錯誤結果而不是拋出異常
            assert isinstance(result, dict)
            assert "success" in result
            assert result["success"] is False

    def test_sync_wrapper_with_async_mock(self):
        """測試 sync 包裝器調用 async 方法"""
        mock_config_manager = Mock()
        mock_config_manager.is_mcp_enabled.return_value = True
        
        with patch('src.services.mcp_service.MCPConfigManager', return_value=mock_config_manager):
            service = MCPService()
            
            # 模擬成功的 async 結果
            mock_result = {
                "success": True,
                "data": "測試結果",
                "content": "MCP sync wrapper 成功"
            }
            
            async def mock_async_call(function_name, arguments):
                return mock_result
            
            # 修補 async 方法
            with patch.object(service, 'handle_function_call_async', side_effect=mock_async_call):
                result = service.handle_function_call_sync("test_function", {"arg1": "value1"})
                assert result["success"] is True

    def test_backward_compatibility(self):
        """測試向後兼容性 - handle_function_call 仍然是 async"""
        mock_config_manager = Mock()
        mock_config_manager.is_mcp_enabled.return_value = False
        
        with patch('src.services.mcp_service.MCPConfigManager', return_value=mock_config_manager):
            service = MCPService()
            
            # handle_function_call 應該指向 async 版本
            assert inspect.iscoroutinefunction(service.handle_function_call)
            
            # 檢查程式碼中的實作
            source = inspect.getsource(service.handle_function_call)
            assert "handle_function_call_async" in source

    def test_error_handling_in_sync_wrapper(self):
        """測試 sync 包裝器的錯誤處理"""
        mock_config_manager = Mock()
        mock_config_manager.is_mcp_enabled.return_value = True
        
        with patch('src.services.mcp_service.MCPConfigManager', return_value=mock_config_manager):
            service = MCPService()
            
            # 模擬 async 方法拋出異常
            async def mock_async_call_with_error(function_name, arguments):
                raise Exception("測試錯誤")
            
            with patch.object(service, 'handle_function_call_async', side_effect=mock_async_call_with_error):
                result = service.handle_function_call_sync("test_function", {"arg1": "value1"})
                
                # 應該返回錯誤結果而不是拋出異常
                assert isinstance(result, dict)
                assert result["success"] is False
                assert "error" in result
                assert "測試錯誤" in result["error"]