"""
MCP 錯誤處理和邊界情況測試
"""

import pytest
import json
import asyncio
import tempfile
import os
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from src.core.mcp_config import MCPConfigManager
from src.core.mcp_client import MCPClient, MCPClientError, MCPServerError
from src.services.mcp_service import MCPService


class TestMCPErrorHandling:
    """測試 MCP 錯誤處理"""
    
    def setup_method(self):
        """設定測試環境"""
        self.temp_dir = tempfile.mkdtemp()
        self.server_config = {
            "base_url": "http://localhost:3000/api/mcp",
            "timeout": 30,
            "retry_attempts": 3
        }
        
        # 無效配置範例
        self.invalid_configs = {
            "missing_mcp_server": {
                "functions": [],
                "tools": {}
            },
            "missing_base_url": {
                "mcp_server": {},
                "functions": [],
                "tools": {}
            },
            "invalid_functions": {
                "mcp_server": {"base_url": "http://test"},
                "functions": [{"name": "test"}],  # 缺少 mcp_tool
                "tools": {}
            },
            "functions_not_list": {
                "mcp_server": {"base_url": "http://test"},
                "functions": "not a list",
                "tools": {}
            },
            "empty_function_name": {
                "mcp_server": {"base_url": "http://test"},
                "functions": [{"mcp_tool": "test"}],  # 缺少 name
                "tools": {}
            }
        }
    
    def teardown_method(self):
        """清理測試環境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_config_validation_errors(self):
        """測試配置驗證錯誤"""
        config_manager = MCPConfigManager(self.temp_dir)
        
        for config_name, invalid_config in self.invalid_configs.items():
            with pytest.raises(ValueError):
                config_manager._validate_config(invalid_config)
    
    def test_config_file_errors(self):
        """測試配置文件錯誤"""
        config_manager = MCPConfigManager(self.temp_dir)
        
        # 測試不存在的文件
        with pytest.raises(FileNotFoundError):
            config_manager.load_mcp_config("nonexistent.json")
        
        # 測試無效 JSON
        invalid_json_file = os.path.join(self.temp_dir, "invalid.json")
        with open(invalid_json_file, 'w') as f:
            f.write("invalid json {")
        
        with pytest.raises(json.JSONDecodeError):
            config_manager.load_mcp_config("invalid.json")
    
    def test_config_directory_errors(self):
        """測試配置目錄錯誤"""
        # 不存在的目錄
        config_manager = MCPConfigManager("/nonexistent/directory")
        
        with pytest.raises(FileNotFoundError):
            config_manager._find_available_config()
        
        # 空目錄
        empty_dir = tempfile.mkdtemp()
        config_manager = MCPConfigManager(empty_dir)
        
        with pytest.raises(FileNotFoundError):
            config_manager._find_available_config()
        
        import shutil
        shutil.rmtree(empty_dir)
    
    def test_parameter_validation_edge_cases(self):
        """測試參數驗證邊界情況"""
        test_config = {
            "mcp_server": {"base_url": "http://test"},
            "functions": [
                {
                    "name": "test_function",
                    "mcp_tool": "test_tool",
                    "enabled": True
                }
            ],
            "tools": {
                "test_function": {
                    "validation": {
                        "required_fields": ["query"],
                        "field_limits": {
                            "query": {"max_length": 10},
                            "count": {"min": 1, "max": 5},
                            "items": {"max_items": 3}
                        }
                    }
                }
            }
        }
        
        config_file = os.path.join(self.temp_dir, "test.json")
        with open(config_file, 'w') as f:
            json.dump(test_config, f)
        
        config_manager = MCPConfigManager(self.temp_dir)
        
        # 測試各種參數限制
        test_cases = [
            # 字串長度限制
            ({"query": "12345678901"}, False, "exceeds max length"),
            ({"query": "1234567890"}, True, None),
            
            # 數值範圍限制
            ({"query": "test", "count": 0}, False, "below minimum"),
            ({"query": "test", "count": 6}, False, "above maximum"),
            ({"query": "test", "count": 3}, True, None),
            
            # 陣列項目限制
            ({"query": "test", "items": [1, 2, 3, 4]}, False, "exceeds max items"),
            ({"query": "test", "items": [1, 2, 3]}, True, None),
        ]
        
        for args, expected_valid, expected_error in test_cases:
            valid, error = config_manager.validate_function_arguments(
                "test_function", args, "test.json"
            )
            assert valid == expected_valid
            if expected_error:
                assert expected_error in error
    
    @pytest.mark.asyncio
    async def test_client_network_errors(self):
        """測試客戶端網路錯誤"""
        client = MCPClient(self.server_config)
        
        # 模擬各種網路錯誤
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = Mock()
            mock_session.closed = False
            mock_session_class.return_value = mock_session
            
            # 連線錯誤
            import aiohttp
            mock_session.post = AsyncMock(side_effect=aiohttp.ClientError("Connection failed"))
            
            with pytest.raises(MCPClientError, match="HTTP request failed"):
                await client.call_tool("test_tool", {"query": "test"})
            
            # 超時錯誤
            mock_session.post = AsyncMock(side_effect=asyncio.TimeoutError())
            
            with pytest.raises(MCPClientError, match="timeout"):
                await client.call_tool("test_tool", {"query": "test"})
    
    @pytest.mark.asyncio
    async def test_client_response_errors(self):
        """測試客戶端回應錯誤"""
        client = MCPClient(self.server_config)
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = Mock()
            mock_session.closed = False
            mock_session_class.return_value = mock_session
            
            # HTTP 錯誤狀態碼
            error_cases = [
                (400, MCPClientError, "client error"),
                (401, MCPClientError, "client error"),
                (403, MCPClientError, "client error"),
                (404, MCPClientError, "client error"),
                (500, MCPServerError, "server error"),
                (502, MCPServerError, "server error"),
                (503, MCPServerError, "server error")
            ]
            
            for status_code, expected_exception, expected_message in error_cases:
                mock_response = Mock()
                mock_response.status = status_code
                mock_response.text = AsyncMock(return_value=f"HTTP {status_code} Error")
                mock_session.post = AsyncMock(return_value=mock_response)
                
                with pytest.raises(expected_exception, match=expected_message):
                    await client.call_tool("test_tool", {"query": "test"})
    
    @pytest.mark.asyncio
    async def test_client_json_errors(self):
        """測試客戶端 JSON 解析錯誤"""
        client = MCPClient(self.server_config)
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = Mock()
            mock_session.closed = False
            mock_session_class.return_value = mock_session
            
            # 無效 JSON 回應
            mock_response = Mock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value="invalid json {")
            mock_session.post = AsyncMock(return_value=mock_response)
            
            with pytest.raises(MCPClientError, match="Invalid JSON response"):
                await client.call_tool("test_tool", {"query": "test"})
    
    @pytest.mark.asyncio
    async def test_client_mcp_protocol_errors(self):
        """測試 MCP 協議錯誤"""
        client = MCPClient(self.server_config)
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = Mock()
            mock_session.closed = False
            mock_session_class.return_value = mock_session
            
            # MCP 錯誤回應
            error_response = {
                "jsonrpc": "2.0",
                "id": 123,
                "error": {
                    "code": -32000,
                    "message": "Tool not found"
                }
            }
            
            mock_response = Mock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value=json.dumps(error_response))
            mock_session.post = AsyncMock(return_value=mock_response)
            
            result = await client.call_tool("test_tool", {"query": "test"})
            
            assert result["success"] is False
            assert result["error"] == "Tool not found"
            assert result["error_code"] == -32000
    
    @pytest.mark.asyncio
    async def test_client_malformed_responses(self):
        """測試畸形回應處理"""
        client = MCPClient(self.server_config)
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = Mock()
            mock_session.closed = False
            mock_session_class.return_value = mock_session
            
            # 各種畸形回應
            malformed_responses = [
                {"invalid": "response"},  # 缺少 result 或 error
                {"result": None},  # result 為 None
                {"result": {"content": None}},  # content 為 None
                {"result": {"content": []}},  # content 為空陣列
                {"result": {"content": [{"invalid": "format"}]}},  # content 格式錯誤
            ]
            
            for response in malformed_responses:
                mock_response = Mock()
                mock_response.status = 200
                mock_response.text = AsyncMock(return_value=json.dumps(response))
                mock_session.post = AsyncMock(return_value=mock_response)
                
                result = await client.call_tool("test_tool", {"query": "test"})
                
                # 應該仍然成功處理，但可能以 raw 格式回傳
                assert result["success"] is True
                assert "data" in result
    
    @pytest.mark.asyncio
    async def test_service_error_propagation(self):
        """測試服務錯誤傳播"""
        test_config = {
            "mcp_server": {"base_url": "http://test"},
            "functions": [
                {
                    "name": "test_function",
                    "mcp_tool": "test_tool",
                    "enabled": True
                }
            ],
            "tools": {},
            "error_handling": {
                "fallback_messages": {
                    "connection_error": "自定義連線錯誤",
                    "timeout_error": "自定義超時錯誤"
                }
            }
        }
        
        config_file = os.path.join(self.temp_dir, "test.json")
        with open(config_file, 'w') as f:
            json.dump(test_config, f)
        
        # 測試不同錯誤類型的 fallback 訊息
        error_cases = [
            ("Connection failed", "自定義連線錯誤"),
            ("Network timeout", "自定義超時錯誤"),
            ("Unknown error", "處理請求時發生錯誤，請稍後再試"),
        ]
        
        for error_message, expected_fallback in error_cases:
            mock_client = Mock()
            mock_client.call_tool = AsyncMock(side_effect=MCPClientError(error_message))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            
            with patch('src.services.mcp_service.MCPClient', return_value=mock_client):
                service = MCPService(self.temp_dir, "test.json")
                
                result = await service.handle_function_call("test_function", {"query": "test"})
                
                assert result["success"] is False
                assert result["error"] == error_message
                assert result["fallback_message"] == expected_fallback
    
    @pytest.mark.asyncio
    async def test_service_unexpected_errors(self):
        """測試服務意外錯誤處理"""
        test_config = {
            "mcp_server": {"base_url": "http://test"},
            "functions": [
                {
                    "name": "test_function",
                    "mcp_tool": "test_tool",
                    "enabled": True
                }
            ],
            "tools": {}
        }
        
        config_file = os.path.join(self.temp_dir, "test.json")
        with open(config_file, 'w') as f:
            json.dump(test_config, f)
        
        # 模擬意外異常
        mock_client = Mock()
        mock_client.call_tool = AsyncMock(side_effect=Exception("Unexpected error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch('src.services.mcp_service.MCPClient', return_value=mock_client):
            service = MCPService(self.temp_dir, "test.json")
            
            result = await service.handle_function_call("test_function", {"query": "test"})
            
            assert result["success"] is False
            assert "Function execution error" in result["error"]
            assert "Unexpected error" in result["error"]
    
    @pytest.mark.asyncio
    async def test_authentication_errors(self):
        """測試認證錯誤"""
        client = MCPClient(self.server_config)
        
        # 測試沒有 client_id 的 OAuth
        success, error = await client.authenticate_oauth(
            "https://auth.example.com", "https://callback.example.com"
        )
        assert success is False
        assert "OAuth client_id not configured" in error
        
        # 測試沒有 code_verifier 的 OAuth 完成
        success, error = await client.complete_oauth_flow(
            "auth_code", "https://callback.example.com", "https://token.example.com"
        )
        assert success is False
        assert "OAuth flow not properly initialized" in error
    
    @pytest.mark.asyncio
    async def test_oauth_token_errors(self):
        """測試 OAuth token 錯誤"""
        client = MCPClient(self.server_config)
        client.auth_config = {
            "client_id": "test_client",
            "_code_verifier": "test_verifier"
        }
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = Mock()
            mock_session.closed = False
            mock_session_class.return_value = mock_session
            
            # Token 請求失敗
            mock_response = Mock()
            mock_response.status = 400
            mock_response.text = AsyncMock(return_value="Invalid grant")
            mock_session.post = AsyncMock(return_value=mock_response)
            
            success, error = await client.complete_oauth_flow(
                "auth_code", "https://callback.example.com", "https://token.example.com"
            )
            
            assert success is False
            assert "Token request failed" in error
            
            # 無效的 token 回應
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value='{"error": "invalid_grant"}')
            
            success, error = await client.complete_oauth_flow(
                "auth_code", "https://callback.example.com", "https://token.example.com"
            )
            
            assert success is False
            assert "No access token in response" in error
    
    @pytest.mark.asyncio
    async def test_session_management_errors(self):
        """測試會話管理錯誤"""
        client = MCPClient(self.server_config)
        
        # 測試關閉已關閉的會話
        await client.close()  # 第一次關閉
        await client.close()  # 第二次關閉不應該出錯
        
        # 測試使用已關閉的會話
        await client._ensure_session()
        assert client._session is not None
        
        # 模擬會話突然關閉
        with patch.object(client._session, 'closed', True):
            await client._ensure_session()
            # 應該創建新的會話
            assert client._session is not None
    
    def test_config_edge_cases(self):
        """測試配置邊界情況"""
        config_manager = MCPConfigManager(self.temp_dir)
        
        # 測試空配置
        empty_config = {
            "mcp_server": {"base_url": "http://test"},
            "functions": [],
            "tools": {}
        }
        
        config_file = os.path.join(self.temp_dir, "empty.json")
        with open(config_file, 'w') as f:
            json.dump(empty_config, f)
        
        # 應該不會出錯
        config_manager.load_mcp_config("empty.json")
        
        # 測試各種空值情況
        functions = config_manager.get_function_schemas_for_openai("empty.json")
        assert functions == []
        
        prompt = config_manager.get_function_schemas_for_anthropic("empty.json")
        assert "Available tools:" in prompt
        
        # 測試不存在的函數
        func = config_manager.get_function_by_name("nonexistent", "empty.json")
        assert func is None
    
    def test_error_message_handling(self):
        """測試錯誤訊息處理"""
        # 測試配置管理器錯誤訊息獲取的邊界情況
        config_manager = MCPConfigManager(self.temp_dir)
        
        # 配置沒有 error_handling 段
        minimal_config = {
            "mcp_server": {"base_url": "http://test"},
            "functions": [],
            "tools": {}
        }
        
        config_file = os.path.join(self.temp_dir, "minimal.json")
        with open(config_file, 'w') as f:
            json.dump(minimal_config, f)
        
        error_messages = config_manager.get_error_messages("minimal.json")
        assert error_messages == {}
        
        default_params = config_manager.get_default_params("minimal.json")
        assert default_params == {}
    
    def test_service_initialization_edge_cases(self):
        """測試服務初始化邊界情況"""
        # 測試沒有 MCP 配置的情況
        empty_dir = tempfile.mkdtemp()
        service = MCPService(empty_dir)
        
        assert service.is_enabled is False
        assert service.mcp_client is None
        
        # 測試各種操作都應該回傳禁用錯誤
        schemas = service.get_function_schemas_for_openai()
        assert schemas == []
        
        prompt = service.get_function_schemas_for_anthropic()
        assert prompt == ""
        
        functions = service.get_configured_functions()
        assert functions == []
        
        import shutil
        shutil.rmtree(empty_dir)
    
    def test_concurrent_operations(self):
        """測試並發操作"""
        # 測試配置管理器的並發載入
        test_config = {
            "mcp_server": {"base_url": "http://test"},
            "functions": [],
            "tools": {}
        }
        
        config_file = os.path.join(self.temp_dir, "concurrent.json")
        with open(config_file, 'w') as f:
            json.dump(test_config, f)
        
        config_manager = MCPConfigManager(self.temp_dir)
        
        # 多次並發載入同一配置
        configs = []
        for _ in range(5):
            config = config_manager.load_mcp_config("concurrent.json")
            configs.append(config)
        
        # 所有配置應該相同
        for config in configs:
            assert config == test_config
    
    def test_memory_usage_edge_cases(self):
        """測試記憶體使用邊界情況"""
        config_manager = MCPConfigManager(self.temp_dir)
        
        # 創建大量配置文件
        for i in range(10):
            config = {
                "mcp_server": {"base_url": f"http://test{i}"},
                "functions": [],
                "tools": {}
            }
            
            config_file = os.path.join(self.temp_dir, f"config{i}.json")
            with open(config_file, 'w') as f:
                json.dump(config, f)
        
        # 載入所有配置
        for i in range(10):
            config_manager.load_mcp_config(f"config{i}.json")
        
        # 檢查快取
        assert len(config_manager._config_cache) == 10
        
        # 清除快取
        config_manager.reload_config()
        assert len(config_manager._config_cache) == 0