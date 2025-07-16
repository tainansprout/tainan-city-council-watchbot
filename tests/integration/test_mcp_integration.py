"""
MCP 集成測試
"""

import pytest
import asyncio
import json
import tempfile
import os
from unittest.mock import AsyncMock, Mock, patch
from src.core.mcp_config import MCPConfigManager
from src.core.mcp_client import MCPClient
from src.services.mcp_service import MCPService


class TestMCPIntegration:
    """測試 MCP 完整集成流程"""
    
    def setup_method(self):
        """設定測試環境"""
        # 創建臨時目錄
        self.temp_dir = tempfile.mkdtemp()
        
        # 測試配置
        self.test_config = {
            "mcp_server": {
                "base_url": "http://localhost:3000/api/mcp",
                "timeout": 30,
                "retry_attempts": 3,
                "authorization": {
                    "type": "oauth2",
                    "client_id": "test_client",
                    "client_secret": "test_secret"
                },
                "capabilities": {
                    "roots": {"listChanged": True},
                    "sampling": {},
                    "elicitation": {}
                }
            },
            "functions": [
                {
                    "name": "search_data",
                    "description": "搜尋資料",
                    "mcp_tool": "search_tool",
                    "enabled": True,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "max_results": {"type": "integer", "default": 10}
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "get_info",
                    "description": "取得資訊",
                    "mcp_tool": "info_tool",
                    "enabled": False
                }
            ],
            "tools": {
                "search_data": {
                    "validation": {
                        "required_fields": ["query"],
                        "field_limits": {
                            "query": {"max_length": 200},
                            "max_results": {"min": 1, "max": 100}
                        }
                    }
                }
            },
            "error_handling": {
                "fallback_messages": {
                    "connection_error": "無法連接到伺服器",
                    "timeout_error": "請求超時",
                    "no_results": "查無結果"
                }
            }
        }
        
        # 創建配置文件
        self.config_file = os.path.join(self.temp_dir, "test_config.json")
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_config, f, ensure_ascii=False, indent=2)
    
    def teardown_method(self):
        """清理測試環境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_config_to_client_integration(self):
        """測試配置管理器到客戶端的集成"""
        config_manager = MCPConfigManager(self.temp_dir)
        
        # 載入配置
        config = config_manager.load_mcp_config("test_config.json")
        assert config == self.test_config
        
        # 取得服務器配置
        server_config = config_manager.get_server_config("test_config.json")
        assert server_config["base_url"] == "http://localhost:3000/api/mcp"
        assert server_config["timeout"] == 30
        
        # 創建客戶端
        client = MCPClient(server_config)
        assert client.base_url == "http://localhost:3000/api/mcp"
        assert client.timeout == 30
        assert client.auth_config["client_id"] == "test_client"
        assert client.capabilities["roots"]["listChanged"] is True
    
    def test_config_to_service_integration(self):
        """測試配置管理器到服務的集成"""
        with patch('src.services.mcp_service.MCPClient') as mock_client:
            mock_client_instance = Mock()
            mock_client.return_value = mock_client_instance
            
            service = MCPService(self.temp_dir, "test_config.json")
            
            assert service.is_enabled is True
            assert service.config_dir == self.temp_dir
            assert service.config_name == "test_config.json"
            
            # 測試函數 schemas
            openai_schemas = service.get_function_schemas_for_openai()
            assert len(openai_schemas) == 1  # 只有 enabled 的函數
            assert openai_schemas[0]["function"]["name"] == "search_data"
            
            anthropic_prompt = service.get_function_schemas_for_anthropic()
            assert "search_data" in anthropic_prompt
            assert "搜尋資料" in anthropic_prompt
            
            gemini_schemas = service.get_function_schemas_for_gemini()
            assert len(gemini_schemas) == 1
            assert gemini_schemas[0]["name"] == "search_data"
    
    @pytest.mark.asyncio
    async def test_full_function_call_flow(self):
        """測試完整的函數呼叫流程"""
        # 模擬 MCP 客戶端成功回應
        mock_client = Mock()
        mock_client.call_tool = AsyncMock(return_value={
            "success": True,
            "data": "搜尋結果：找到 3 筆資料",
            "content_type": "text",
            "metadata": {
                "sources": [
                    {"url": "http://example.com/1", "title": "結果 1"},
                    {"url": "http://example.com/2", "title": "結果 2"}
                ]
            }
        })
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch('src.services.mcp_service.MCPClient', return_value=mock_client):
            service = MCPService(self.temp_dir, "test_config.json")
            
            # 執行函數呼叫
            result = await service.handle_function_call("search_data", {
                "query": "測試查詢",
                "max_results": 5
            })
            
            # 驗證結果
            assert result["success"] is True
            assert result["data"] == "搜尋結果：找到 3 筆資料"
            assert result["content_type"] == "text"
            assert result["metadata"]["function_name"] == "search_data"
            assert result["metadata"]["mcp_tool"] == "search_tool"
            assert len(result["metadata"]["sources"]) == 2
            assert "execution_time" in result["metadata"]
    
    @pytest.mark.asyncio
    async def test_function_call_with_validation_error(self):
        """測試函數呼叫參數驗證錯誤"""
        mock_client = Mock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch('src.services.mcp_service.MCPClient', return_value=mock_client):
            service = MCPService(self.temp_dir, "test_config.json")
            
            # 測試缺少必要參數
            result = await service.handle_function_call("search_data", {})
            
            assert result["success"] is False
            assert "Parameter validation failed" in result["error"]
            assert "Missing required field: query" in result["error"]
    
    @pytest.mark.asyncio
    async def test_function_call_with_field_limits(self):
        """測試函數呼叫欄位限制"""
        mock_client = Mock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch('src.services.mcp_service.MCPClient', return_value=mock_client):
            service = MCPService(self.temp_dir, "test_config.json")
            
            # 測試超過字串長度限制
            result = await service.handle_function_call("search_data", {
                "query": "x" * 201  # 超過 200 字符限制
            })
            
            assert result["success"] is False
            assert "exceeds max length" in result["error"]
            
            # 測試超過數值限制
            result = await service.handle_function_call("search_data", {
                "query": "測試",
                "max_results": 150  # 超過 100 限制
            })
            
            assert result["success"] is False
            assert "above maximum" in result["error"]
    
    @pytest.mark.asyncio
    async def test_disabled_function_call(self):
        """測試禁用函數呼叫"""
        mock_client = Mock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch('src.services.mcp_service.MCPClient', return_value=mock_client):
            service = MCPService(self.temp_dir, "test_config.json")
            
            # 嘗試呼叫禁用的函數
            result = await service.handle_function_call("get_info", {"query": "test"})
            
            assert result["success"] is False
            assert "Function execution error" in result["error"]
    
    @pytest.mark.asyncio
    async def test_pagination_workflow(self):
        """測試分頁工作流程"""
        mock_client = Mock()
        
        # 第一頁回應
        mock_client.list_tools = AsyncMock(side_effect=[
            (True, [{"name": "tool1"}, {"name": "tool2"}], "cursor_123", None),
            (True, [{"name": "tool3"}], None, None)
        ])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch('src.services.mcp_service.MCPClient', return_value=mock_client):
            service = MCPService(self.temp_dir, "test_config.json")
            
            # 第一頁
            success, tools, next_cursor, error = await service.list_available_tools()
            assert success is True
            assert len(tools) == 2
            assert next_cursor == "cursor_123"
            
            # 第二頁
            success, tools, next_cursor, error = await service.list_available_tools("cursor_123")
            assert success is True
            assert len(tools) == 1
            assert next_cursor is None
            
            # 驗證呼叫次數
            assert mock_client.list_tools.call_count == 2
    
    @pytest.mark.asyncio
    async def test_authentication_workflow(self):
        """測試認證工作流程"""
        mock_client = Mock()
        
        # OAuth 認證流程
        mock_client.authenticate_oauth = AsyncMock(return_value=(
            True, "https://auth.example.com/authorize?code_challenge=..."
        ))
        mock_client.complete_oauth_flow = AsyncMock(return_value=(True, None))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch('src.services.mcp_service.MCPClient', return_value=mock_client):
            service = MCPService(self.temp_dir, "test_config.json")
            
            # 設定 OAuth 認證
            success, auth_url = await service.setup_oauth_authentication(
                "https://auth.example.com/authorize",
                "https://callback.example.com"
            )
            assert success is True
            assert auth_url.startswith("https://auth.example.com/authorize")
            
            # 完成認證流程
            success, error = await service.complete_oauth_authentication(
                "auth_code_123",
                "https://callback.example.com",
                "https://auth.example.com/token"
            )
            assert success is True
            assert error is None
    
    @pytest.mark.asyncio
    async def test_error_handling_workflow(self):
        """測試錯誤處理工作流程"""
        mock_client = Mock()
        
        # 模擬不同類型的錯誤
        mock_client.call_tool = AsyncMock(return_value={
            "success": False,
            "error": "Connection failed",
            "error_code": "CONN_ERROR"
        })
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch('src.services.mcp_service.MCPClient', return_value=mock_client):
            service = MCPService(self.temp_dir, "test_config.json")
            
            result = await service.handle_function_call("search_data", {
                "query": "測試查詢"
            })
            
            assert result["success"] is False
            assert result["error"] == "Connection failed"
            assert result["fallback_message"] == "無法連接到伺服器"
    
    @pytest.mark.asyncio
    async def test_service_initialization_and_health_check(self):
        """測試服務初始化和健康檢查"""
        mock_client = Mock()
        mock_client.initialize_capabilities = AsyncMock(return_value=(True, None))
        mock_client.health_check = AsyncMock(return_value=(True, None))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        # 新增需要的屬性
        mock_client.base_url = "http://localhost:3000/api/mcp"
        mock_client.timeout = 30
        mock_client.auth_config = {"client_id": "test_client"}
        mock_client.capabilities = {"roots": {}, "sampling": {}, "elicitation": {}}
        mock_client.access_token = None
        
        with patch('src.services.mcp_service.MCPClient', return_value=mock_client):
            service = MCPService(self.temp_dir, "test_config.json")
            
            # 初始化連線
            success, error = await service.initialize_connection()
            assert success is True
            assert error is None
            
            # 健康檢查
            healthy, error = await service.health_check()
            assert healthy is True
            assert error is None
            
            # 檢查服務資訊
            info = service.get_service_info()
            assert info["enabled"] is True
            assert info["configured_functions"] == 1
            assert info["server_url"] == "http://localhost:3000/api/mcp"
    
    def test_config_reload_workflow(self):
        """測試配置重新載入工作流程"""
        config_manager = MCPConfigManager(self.temp_dir)
        
        # 載入初始配置
        config = config_manager.load_mcp_config("test_config.json")
        assert len(config["functions"]) == 2
        
        # 修改配置文件
        modified_config = {
            **self.test_config,
            "functions": [
                {
                    "name": "new_function",
                    "description": "新函數",
                    "mcp_tool": "new_tool",
                    "enabled": True
                }
            ]
        }
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(modified_config, f, ensure_ascii=False, indent=2)
        
        # 重新載入配置
        config_manager.reload_config("test_config.json")
        config = config_manager.load_mcp_config("test_config.json")
        
        assert len(config["functions"]) == 1
        assert config["functions"][0]["name"] == "new_function"
    
    def test_multiple_configs_workflow(self):
        """測試多配置文件工作流程"""
        # 創建第二個配置文件
        config2 = {
            "mcp_server": {
                "base_url": "http://localhost:3001/api/mcp",
                "timeout": 60
            },
            "functions": [
                {
                    "name": "other_function",
                    "description": "其他函數",
                    "mcp_tool": "other_tool",
                    "enabled": True
                }
            ],
            "tools": {}
        }
        
        config_file2 = os.path.join(self.temp_dir, "config2.json")
        with open(config_file2, 'w', encoding='utf-8') as f:
            json.dump(config2, f, ensure_ascii=False, indent=2)
        
        config_manager = MCPConfigManager(self.temp_dir)
        
        # 列出可用配置
        configs = config_manager.list_available_configs()
        assert len(configs) == 2
        assert "test_config.json" in configs
        assert "config2.json" in configs
        
        # 載入不同配置
        config1 = config_manager.load_mcp_config("test_config.json")
        config2_loaded = config_manager.load_mcp_config("config2.json")
        
        assert config1["mcp_server"]["base_url"] == "http://localhost:3000/api/mcp"
        assert config2_loaded["mcp_server"]["base_url"] == "http://localhost:3001/api/mcp"
        assert config1["functions"][0]["name"] == "search_data"
        assert config2_loaded["functions"][0]["name"] == "other_function"
    
    def test_service_info_comprehensive(self):
        """測試服務資訊完整性"""
        mock_client = Mock()
        mock_client.base_url = "http://localhost:3000/api/mcp"
        mock_client.timeout = 30
        mock_client.auth_config = {"client_id": "test_client"}
        mock_client.capabilities = {"roots": {}, "sampling": {}, "elicitation": {}}
        mock_client.access_token = "test_token"
        
        with patch('src.services.mcp_service.MCPClient', return_value=mock_client):
            service = MCPService(self.temp_dir, "test_config.json")
            
            info = service.get_service_info()
            
            # 基本資訊
            assert info["enabled"] is True
            assert info["config_dir"] == self.temp_dir
            assert info["config_name"] == "test_config.json"
            assert info["configured_functions"] == 1
            
            # 客戶端資訊
            assert info["server_url"] == "http://localhost:3000/api/mcp"
            assert info["timeout"] == 30
            assert info["auth_configured"] is True
            assert info["has_access_token"] is True
            assert len(info["capabilities"]) == 3
            
            # 可用配置
            assert "test_config.json" in info["available_configs"]