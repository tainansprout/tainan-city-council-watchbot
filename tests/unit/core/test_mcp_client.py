"""
測試 MCP 客戶端
"""

import pytest
import asyncio
import json
import aiohttp
from unittest.mock import AsyncMock, Mock, patch, MagicMock, PropertyMock
from src.core.mcp_client import MCPClient, MCPClientError, MCPServerError


class TestMCPClient:
    """測試 MCP 客戶端"""
    
    def setup_method(self):
        """設定測試環境"""
        self.server_config = {
            "base_url": "http://localhost:3000/api/mcp",
            "timeout": 30,
            "retry_attempts": 3,
            "retry_delay": 1.0
        }
        self.client = MCPClient(self.server_config)
        
        # 測試回應資料
        self.success_response = {
            "jsonrpc": "2.0",
            "id": 123,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": "Test response"
                    }
                ]
            }
        }
        
        self.error_response = {
            "jsonrpc": "2.0",
            "id": 123,
            "error": {
                "code": -32000,
                "message": "Test error"
            }
        }
    
    def test_init_basic(self):
        """測試基本初始化"""
        assert self.client.base_url == "http://localhost:3000/api/mcp"
        assert self.client.timeout == 30
        assert self.client.retry_attempts == 3
        assert self.client.retry_delay == 1.0
        assert self.client.access_token is None
        assert "roots" in self.client.capabilities
        assert "sampling" in self.client.capabilities
        assert "elicitation" in self.client.capabilities
    
    def test_init_with_auth(self):
        """測試帶認證的初始化"""
        config_with_auth = {
            **self.server_config,
            "authorization": {
                "client_id": "test_client",
                "client_secret": "test_secret"
            }
        }
        
        client = MCPClient(config_with_auth)
        assert client.auth_config["client_id"] == "test_client"
        assert client.auth_config["client_secret"] == "test_secret"
    
    def test_init_with_custom_capabilities(self):
        """測試自定義能力初始化"""
        config_with_caps = {
            **self.server_config,
            "capabilities": {
                "roots": {"listChanged": True},
                "custom_capability": {"enabled": True}
            }
        }
        
        client = MCPClient(config_with_caps)
        assert client.capabilities["roots"]["listChanged"] is True
        assert client.capabilities["custom_capability"]["enabled"] is True
    
    @pytest.mark.asyncio
    async def test_ensure_session(self):
        """測試確保會話存在"""
        assert self.client._session is None
        
        await self.client._ensure_session()
        assert self.client._session is not None
        assert isinstance(self.client._session, aiohttp.ClientSession)
        
        # 測試不會重複創建
        old_session = self.client._session
        await self.client._ensure_session()
        assert self.client._session is old_session
    
    @pytest.mark.asyncio
    async def test_close(self):
        """測試關閉會話"""
        await self.client._ensure_session()
        assert self.client._session is not None
        
        await self.client.close()
        assert self.client._session is None
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """測試異步上下文管理器"""
        async with self.client as client:
            assert client._session is not None
        
        # 退出後應該關閉會話
        assert self.client._session is None
    
    def test_build_mcp_request(self):
        """測試建構 MCP 請求"""
        request = self.client._build_mcp_request("test_tool", {"query": "test"})
        
        assert request["jsonrpc"] == "2.0"
        assert "id" in request
        assert request["method"] == "tools/call"
        assert request["params"]["name"] == "test_tool"
        assert request["params"]["arguments"] == {"query": "test"}
    
    def test_parse_mcp_response_success(self):
        """測試解析成功回應"""
        result = self.client._parse_mcp_response(self.success_response)
        
        assert result["success"] is True
        assert result["data"] == "Test response"
        assert result["content_type"] == "text"
        assert "metadata" in result
    
    def test_parse_mcp_response_error(self):
        """測試解析錯誤回應"""
        result = self.client._parse_mcp_response(self.error_response)
        
        assert result["success"] is False
        assert result["error"] == "Test error"
        assert result["error_code"] == -32000
        assert "raw_response" in result
    
    def test_parse_mcp_response_no_content(self):
        """測試解析沒有 content 的回應"""
        response = {
            "jsonrpc": "2.0",
            "id": 123,
            "result": {
                "data": "direct_data"
            }
        }
        
        result = self.client._parse_mcp_response(response)
        
        assert result["success"] is True
        assert result["data"] == {"data": "direct_data"}
        assert result["content_type"] == "raw"
    
    def test_parse_mcp_response_invalid_format(self):
        """測試解析無效格式回應"""
        result = self.client._parse_mcp_response({"invalid": "format"})
        
        assert result["success"] is True
        assert result["data"] == {"invalid": "format"}
        assert result["content_type"] == "unknown"
    
    def test_parse_mcp_response_parsing_error(self):
        """測試解析過程中的錯誤"""
        # 創建一個會導致解析錯誤的回應
        response = None
        
        result = self.client._parse_mcp_response(response)
        
        assert result["success"] is False
        assert "Error parsing MCP response" in result["error"]
    
    def test_extract_sources_from_content(self):
        """測試從內容中提取來源"""
        content = [
            {
                "type": "text",
                "text": "Content 1",
                "source": {"url": "http://example.com/1"}
            },
            {
                "type": "text",
                "text": "Content 2",
                "metadata": {
                    "source": {"url": "http://example.com/2"}
                }
            },
            {
                "type": "text",
                "text": "Content 3"
            }
        ]
        
        sources = self.client._extract_sources_from_content(content)
        
        assert len(sources) == 2
        assert sources[0] == {"url": "http://example.com/1"}
        assert sources[1] == {"url": "http://example.com/2"}
    
    def test_timeout_configuration(self):
        """測試超時配置"""
        custom_timeout_config = {
            "base_url": "http://localhost:3000/api/mcp",
            "timeout": 60,
            "retry_attempts": 5,
            "retry_delay": 2.0
        }
        
        client = MCPClient(custom_timeout_config)
        
        assert client.timeout == 60
        assert client.retry_attempts == 5
        assert client.retry_delay == 2.0
        assert client.session_timeout.total == 60
    
    @pytest.mark.asyncio
    async def test_get_auth_headers_no_auth(self):
        """測試取得認證標頭 - 無認證"""
        headers = await self.client._get_auth_headers()
        assert headers == {}
    
    @pytest.mark.asyncio
    async def test_get_auth_headers_with_access_token(self):
        """測試取得認證標頭 - 有 access token"""
        self.client.access_token = "test_token"
        headers = await self.client._get_auth_headers()
        assert headers["Authorization"] == "Bearer test_token"
    
    @pytest.mark.asyncio
    async def test_get_auth_headers_with_api_key(self):
        """測試取得認證標頭 - 有 API key"""
        self.client.auth_config = {"api_key": "test_api_key"}
        headers = await self.client._get_auth_headers()
        assert headers["Authorization"] == "Bearer test_api_key"
    
    @pytest.mark.asyncio
    async def test_call_tool_success(self):
        """測試成功呼叫工具"""
        mock_response = Mock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=json.dumps(self.success_response))
        
        mock_session = Mock()
        mock_session.post = Mock()
        mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session.closed = False
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await self.client.call_tool("test_tool", {"query": "test"})
        
        assert result["success"] is True
        assert result["data"] == "Test response"
    
    @pytest.mark.asyncio
    async def test_call_tool_server_error(self):
        """測試伺服器錯誤"""
        mock_response = Mock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Server Error")
        
        mock_session = Mock()
        mock_session.post = Mock()
        mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session.closed = False
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            with pytest.raises(MCPServerError):
                await self.client.call_tool("test_tool", {"query": "test"})
    
    @pytest.mark.asyncio
    async def test_call_tool_client_error(self):
        """測試客戶端錯誤"""
        mock_response = Mock()
        mock_response.status = 400
        mock_response.text = AsyncMock(return_value="Bad Request")
        
        mock_session = Mock()
        mock_session.post = Mock()
        mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session.closed = False
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            with pytest.raises(MCPClientError):
                await self.client.call_tool("test_tool", {"query": "test"})
    
    @pytest.mark.asyncio
    async def test_call_tool_timeout(self):
        """測試超時錯誤"""
        mock_session = Mock()
        mock_session.post = Mock()
        mock_session.post.return_value.__aenter__ = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session.closed = False
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            with pytest.raises(MCPClientError, match="timeout"):
                await self.client.call_tool("test_tool", {"query": "test"})
    
    @pytest.mark.asyncio
    async def test_call_tool_connection_error(self):
        """測試連線錯誤"""
        mock_session = Mock()
        mock_session.post = Mock()
        mock_session.post.return_value.__aenter__ = AsyncMock(side_effect=aiohttp.ClientError("Connection failed"))
        mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session.closed = False
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            with pytest.raises(MCPClientError, match="HTTP request failed"):
                await self.client.call_tool("test_tool", {"query": "test"})
    
    @pytest.mark.asyncio
    async def test_call_tool_invalid_json(self):
        """測試無效 JSON 回應"""
        mock_response = Mock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="invalid json")
        
        mock_session = Mock()
        mock_session.post = Mock()
        mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session.closed = False
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            with pytest.raises(MCPClientError, match="Invalid JSON response"):
                await self.client.call_tool("test_tool", {"query": "test"})
    
    @pytest.mark.asyncio
    async def test_list_tools_success(self):
        """測試成功列出工具"""
        tools_response = {
            "jsonrpc": "2.0",
            "id": 123,
            "result": {
                "tools": [
                    {"name": "tool1", "description": "Test tool 1"},
                    {"name": "tool2", "description": "Test tool 2"}
                ]
            }
        }
        
        mock_response = Mock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=json.dumps(tools_response))
        
        mock_session = Mock()
        mock_session.post = Mock()
        mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session.closed = False
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            success, tools, next_cursor, error = await self.client.list_tools()
        
        assert success is True
        assert len(tools) == 2
        assert tools[0]["name"] == "tool1"
        assert next_cursor is None
        assert error is None
    
    @pytest.mark.asyncio
    async def test_list_tools_with_pagination(self):
        """測試帶分頁的工具列表"""
        tools_response = {
            "jsonrpc": "2.0",
            "id": 123,
            "result": {
                "tools": [
                    {"name": "tool1", "description": "Test tool 1"}
                ],
                "nextCursor": "cursor123"
            }
        }
        
        mock_response = Mock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=json.dumps(tools_response))
        
        mock_session = Mock()
        mock_session.post = Mock()
        mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session.closed = False
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            success, tools, next_cursor, error = await self.client.list_tools("prev_cursor")
        
        assert success is True
        assert len(tools) == 1
        assert next_cursor == "cursor123"
        assert error is None
    
    @pytest.mark.asyncio
    async def test_list_tools_error(self):
        """測試列出工具錯誤"""
        error_response = {
            "jsonrpc": "2.0",
            "id": 123,
            "error": {
                "code": -32000,
                "message": "Tools list error"
            }
        }
        
        mock_response = Mock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=json.dumps(error_response))
        
        mock_session = Mock()
        mock_session.post = Mock()
        mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session.closed = False
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            success, tools, next_cursor, error = await self.client.list_tools()
        
        assert success is False
        assert tools is None
        assert next_cursor is None
        assert error == "Tools list error"
    
    @pytest.mark.asyncio
    async def test_initialize_capabilities_success(self):
        """測試成功初始化能力"""
        init_response = {
            "jsonrpc": "2.0",
            "id": 123,
            "result": {
                "capabilities": {
                    "tools": {"listChanged": True},
                    "resources": {"subscribe": True}
                }
            }
        }
        
        mock_response = Mock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=json.dumps(init_response))
        
        mock_session = Mock()
        mock_session.post = Mock()
        mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session.closed = False
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            success, error = await self.client.initialize_capabilities()
        
        assert success is True
        assert error is None
    
    @pytest.mark.asyncio
    async def test_initialize_capabilities_error(self):
        """測試初始化能力錯誤"""
        mock_response = Mock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Server Error")
        
        mock_session = Mock()
        mock_session.post = Mock()
        mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session.closed = False
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            success, error = await self.client.initialize_capabilities()
        
        assert success is False
        assert "Failed to initialize" in error
    
    @pytest.mark.asyncio
    async def test_authenticate_oauth_success(self):
        """測試 OAuth 認證成功"""
        self.client.auth_config = {"client_id": "test_client"}
        
        success, auth_url = await self.client.authenticate_oauth(
            "https://auth.example.com/authorize",
            "https://callback.example.com"
        )
        
        assert success is True
        assert auth_url.startswith("https://auth.example.com/authorize")
        assert "client_id=test_client" in auth_url
        assert "code_challenge" in auth_url
        assert "code_challenge_method=S256" in auth_url
    
    @pytest.mark.asyncio
    async def test_authenticate_oauth_no_client_id(self):
        """測試 OAuth 認證缺少 client_id"""
        success, error = await self.client.authenticate_oauth(
            "https://auth.example.com/authorize",
            "https://callback.example.com"
        )
        
        assert success is False
        assert "OAuth client_id not configured" in error
    
    @pytest.mark.asyncio
    async def test_complete_oauth_flow_success(self):
        """測試完成 OAuth 流程成功"""
        # 設定 OAuth 狀態
        self.client.auth_config = {
            "client_id": "test_client",
            "_code_verifier": "test_verifier"
        }
        
        token_response = {
            "access_token": "test_access_token",
            "token_type": "Bearer",
            "expires_in": 3600
        }
        
        mock_response = Mock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=json.dumps(token_response))
        
        mock_session = Mock()
        mock_session.post = Mock()
        mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session.closed = False
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            success, error = await self.client.complete_oauth_flow(
                "auth_code",
                "https://callback.example.com",
                "https://auth.example.com/token"
            )
        
        assert success is True
        assert error is None
        assert self.client.access_token == "test_access_token"
    
    @pytest.mark.asyncio
    async def test_complete_oauth_flow_no_verifier(self):
        """測試完成 OAuth 流程缺少 verifier"""
        success, error = await self.client.complete_oauth_flow(
            "auth_code",
            "https://callback.example.com",
            "https://auth.example.com/token"
        )
        
        assert success is False
        assert "OAuth flow not properly initialized" in error
    
    @pytest.mark.asyncio
    async def test_complete_oauth_flow_token_error(self):
        """測試完成 OAuth 流程 token 錯誤"""
        self.client.auth_config = {
            "client_id": "test_client",
            "_code_verifier": "test_verifier"
        }
        
        mock_response = Mock()
        mock_response.status = 400
        mock_response.text = AsyncMock(return_value="Invalid grant")
        
        mock_session = Mock()
        mock_session.post = Mock()
        mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session.closed = False
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            success, error = await self.client.complete_oauth_flow(
                "auth_code",
                "https://callback.example.com",
                "https://auth.example.com/token"
            )
        
        assert success is False
        assert "Token request failed" in error
    
    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """測試健康檢查成功"""
        mock_response = Mock()
        mock_response.status = 200
        
        mock_session = Mock()
        mock_session.get = Mock()
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session.closed = False
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            healthy, error = await self.client.health_check()
        
        assert healthy is True
        assert error is None
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """測試健康檢查失敗"""
        mock_response = Mock()
        mock_response.status = 500
        
        mock_session = Mock()
        mock_session.get = Mock()
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session.closed = False
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            healthy, error = await self.client.health_check()
        
        assert healthy is False
        assert "health check failed" in error
    
    @pytest.mark.asyncio
    async def test_health_check_exception(self):
        """測試健康檢查異常"""
        mock_session = Mock()
        mock_session.get = Mock()
        mock_session.get.return_value.__aenter__ = AsyncMock(side_effect=Exception("Connection failed"))
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session.closed = False
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            healthy, error = await self.client.health_check()
        
        assert healthy is False
        assert "health check error" in error
    
    def test_create_mcp_client_function(self):
        """測試創建 MCP 客戶端函數"""
        from src.core.mcp_client import create_mcp_client
        
        server_config = {
            "base_url": "http://localhost:3000/api/mcp",
            "timeout": 30
        }
        
        client = create_mcp_client(server_config)
        
        assert isinstance(client, MCPClient)
        assert client.base_url == "http://localhost:3000/api/mcp"
        assert client.timeout == 30
    
    def test_mcp_client_error_classes(self):
        """測試 MCP 錯誤類別"""
        from src.core.mcp_client import MCPClientError, MCPServerError
        
        # 測試客戶端錯誤
        client_error = MCPClientError("Client error")
        assert str(client_error) == "Client error"
        assert isinstance(client_error, Exception)
        
        # 測試伺服器錯誤
        server_error = MCPServerError("Server error")
        assert str(server_error) == "Server error"
        assert isinstance(server_error, Exception)
    
    def test_parse_mcp_response_various_formats(self):
        """測試解析各種 MCP 回應格式"""
        # 測試多個內容項目
        response_multi_content = {
            "jsonrpc": "2.0",
            "id": 123,
            "result": {
                "content": [
                    {"type": "text", "text": "First content"},
                    {"type": "text", "text": "Second content"}
                ]
            }
        }
        
        result = self.client._parse_mcp_response(response_multi_content)
        assert result["success"] is True
        assert result["data"] == "First content"
        assert result["metadata"]["content_count"] == 2
        
        # 測試空內容列表
        response_empty_content = {
            "jsonrpc": "2.0",
            "id": 123,
            "result": {
                "content": []
            }
        }
        
        result = self.client._parse_mcp_response(response_empty_content)
        assert result["success"] is True
        assert result["data"] == []
        assert result["content_type"] == "raw"
    
    def test_build_mcp_request_with_complex_arguments(self):
        """測試建構複雜參數的 MCP 請求"""
        complex_args = {
            "query": "test query",
            "filters": {
                "type": "document",
                "date_range": {
                    "start": "2023-01-01",
                    "end": "2023-12-31"
                }
            },
            "options": ["verbose", "include_metadata"]
        }
        
        request = self.client._build_mcp_request("search_documents", complex_args)
        
        assert request["method"] == "tools/call"
        assert request["params"]["name"] == "search_documents"
        assert request["params"]["arguments"] == complex_args
        assert isinstance(request["id"], int)
    
    def test_extract_sources_from_content_edge_cases(self):
        """測試從內容中提取來源的邊界情況"""
        # 測試空內容
        empty_content = []
        sources = self.client._extract_sources_from_content(empty_content)
        assert sources == []
        
        # 測試非字典項目
        mixed_content = [
            "string_item",
            123,
            {"type": "text", "text": "normal content"},
            {"type": "link", "source": {"url": "http://example.com"}}
        ]
        
        sources = self.client._extract_sources_from_content(mixed_content)
        assert len(sources) == 1
        assert sources[0] == {"url": "http://example.com"}
    
    @pytest.mark.asyncio
    async def test_session_management(self):
        """測試會話管理"""
        # 測試初始狀態
        assert self.client._session is None
        
        # 測試確保會話存在
        await self.client._ensure_session()
        assert self.client._session is not None
        
        # 測試關閉已關閉的會話（使用 mock 來模擬 closed 狀態）
        old_session = self.client._session
        
        # 創建一個 MagicMock 來模擬 session，並設定 closed 屬性
        mock_session = MagicMock(spec=aiohttp.ClientSession)
        mock_session.closed = True
        
        self.client._session = mock_session
        
        await self.client._ensure_session()
        assert self.client._session is not None
        assert self.client._session is not mock_session  # 應該創建新的 session
        
        # 測試正常關閉
        await self.client.close()
        assert self.client._session is None
    
    def test_auth_config_properties(self):
        """測試認證配置屬性"""
        auth_config = {
            "type": "oauth2",
            "client_id": "test_client",
            "client_secret": "test_secret",
            "scope": "read write"
        }
        
        config_with_auth = {
            **self.server_config,
            "authorization": auth_config
        }
        
        client = MCPClient(config_with_auth)
        
        assert client.auth_config == auth_config
        assert client.auth_config["type"] == "oauth2"
        assert client.auth_config["client_id"] == "test_client"
        assert client.access_token is None
    
    def test_capabilities_configuration(self):
        """測試能力配置"""
        custom_capabilities = {
            "roots": {"listChanged": True},
            "sampling": {"enabled": True},
            "custom_feature": {"version": "1.0"}
        }
        
        config_with_caps = {
            **self.server_config,
            "capabilities": custom_capabilities
        }
        
        client = MCPClient(config_with_caps)
        
        assert client.capabilities == custom_capabilities
        assert client.capabilities["roots"]["listChanged"] is True
        assert client.capabilities["custom_feature"]["version"] == "1.0"