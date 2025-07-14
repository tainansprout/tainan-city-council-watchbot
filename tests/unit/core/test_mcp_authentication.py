"""
MCP 認證流程測試
"""

import pytest
import asyncio
import json
import base64
import hashlib
import urllib.parse
from unittest.mock import AsyncMock, Mock, patch
from src.core.mcp_client import MCPClient, MCPClientError
from src.services.mcp_service import MCPService


class TestMCPAuthentication:
    """測試 MCP 認證功能"""
    
    def setup_method(self):
        """設定測試環境"""
        self.server_config = {
            "base_url": "http://localhost:3000/api/mcp",
            "timeout": 30,
            "authorization": {
                "type": "oauth2",
                "client_id": "test_client_id",
                "client_secret": "test_client_secret",
                "scope": "read write",
                "authorization_server": "https://auth.example.com",
                "token_endpoint": "https://auth.example.com/oauth/token"
            }
        }
        self.client = MCPClient(self.server_config)
    
    def test_auth_config_initialization(self):
        """測試認證配置初始化"""
        assert self.client.auth_config is not None
        assert self.client.auth_config["client_id"] == "test_client_id"
        assert self.client.auth_config["client_secret"] == "test_client_secret"
        assert self.client.auth_config["scope"] == "read write"
        assert self.client.access_token is None
    
    def test_auth_config_with_api_key(self):
        """測試 API Key 認證配置"""
        config_with_api_key = {
            **self.server_config,
            "authorization": {
                "type": "api_key",
                "api_key": "test_api_key"
            }
        }
        
        client = MCPClient(config_with_api_key)
        assert client.auth_config["api_key"] == "test_api_key"
    
    @pytest.mark.asyncio
    async def test_get_auth_headers_no_auth(self):
        """測試無認證的標頭生成"""
        client = MCPClient({"base_url": "http://localhost:3000"})
        headers = await client._get_auth_headers()
        assert headers == {}
    
    @pytest.mark.asyncio
    async def test_get_auth_headers_with_access_token(self):
        """測試帶 access token 的標頭生成"""
        self.client.access_token = "test_access_token"
        headers = await self.client._get_auth_headers()
        assert headers["Authorization"] == "Bearer test_access_token"
    
    @pytest.mark.asyncio
    async def test_get_auth_headers_with_api_key(self):
        """測試帶 API key 的標頭生成"""
        self.client.auth_config["api_key"] = "test_api_key"
        headers = await self.client._get_auth_headers()
        assert headers["Authorization"] == "Bearer test_api_key"
    
    @pytest.mark.asyncio
    async def test_get_auth_headers_priority(self):
        """測試認證標頭優先權"""
        # access_token 優先於 api_key
        self.client.access_token = "access_token"
        self.client.auth_config["api_key"] = "api_key"
        
        headers = await self.client._get_auth_headers()
        assert headers["Authorization"] == "Bearer access_token"
    
    @pytest.mark.asyncio
    async def test_oauth_flow_initiation_success(self):
        """測試 OAuth 流程啟動成功"""
        authorization_url = "https://auth.example.com/authorize"
        redirect_uri = "https://callback.example.com/callback"
        
        success, auth_url = await self.client.authenticate_oauth(
            authorization_url, redirect_uri
        )
        
        assert success is True
        assert auth_url.startswith(authorization_url)
        
        # 解析 URL 參數
        parsed_url = urllib.parse.urlparse(auth_url)
        params = urllib.parse.parse_qs(parsed_url.query)
        
        assert params["response_type"][0] == "code"
        assert params["client_id"][0] == "test_client_id"
        assert params["redirect_uri"][0] == redirect_uri
        assert params["code_challenge_method"][0] == "S256"
        assert "code_challenge" in params
        assert params["scope"][0] == "read write"
        
        # 驗證 code_verifier 已儲存
        assert "_code_verifier" in self.client.auth_config
    
    @pytest.mark.asyncio
    async def test_oauth_flow_initiation_no_client_id(self):
        """測試 OAuth 流程啟動缺少 client_id"""
        client = MCPClient({"base_url": "http://localhost:3000"})
        
        success, error = await client.authenticate_oauth(
            "https://auth.example.com/authorize",
            "https://callback.example.com/callback"
        )
        
        assert success is False
        assert "OAuth client_id not configured" in error
    
    def test_pkce_code_challenge_generation(self):
        """測試 PKCE code challenge 生成"""
        # 測試 code_verifier 和 code_challenge 的生成
        import secrets
        
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('utf-8')).digest()
        ).decode('utf-8').rstrip('=')\n        \n        # 驗證格式\n        assert len(code_verifier) >= 43  # Base64 編碼後至少 43 字符\n        assert len(code_challenge) == 43  # SHA256 Base64 編碼後為 43 字符\n        assert code_verifier != code_challenge\n    \n    @pytest.mark.asyncio\n    async def test_oauth_flow_completion_success(self):\n        \"\"\"測試 OAuth 流程完成成功\"\"\"\n        # 先設定 OAuth 狀態\n        self.client.auth_config[\"_code_verifier\"] = \"test_code_verifier\"\n        \n        # 模擬成功的 token 回應\n        token_response = {\n            \"access_token\": \"test_access_token\",\n            \"token_type\": \"Bearer\",\n            \"expires_in\": 3600,\n            \"refresh_token\": \"test_refresh_token\",\n            \"scope\": \"read write\"\n        }\n        \n        with patch('aiohttp.ClientSession') as mock_session_class:\n            mock_session = Mock()\n            mock_session.closed = False\n            mock_session_class.return_value = mock_session\n            \n            mock_response = Mock()\n            mock_response.status = 200\n            mock_response.text = AsyncMock(return_value=json.dumps(token_response))\n            mock_session.post = AsyncMock(return_value=mock_response)\n            \n            success, error = await self.client.complete_oauth_flow(\n                \"authorization_code\",\n                \"https://callback.example.com/callback\",\n                \"https://auth.example.com/token\"\n            )\n            \n            assert success is True\n            assert error is None\n            assert self.client.access_token == \"test_access_token\"\n            \n            # 驗證請求參數\n            call_args = mock_session.post.call_args\n            assert call_args[0][0] == \"https://auth.example.com/token\"\n            \n            form_data = call_args[1]['data']\n            assert form_data['grant_type'] == 'authorization_code'\n            assert form_data['client_id'] == 'test_client_id'\n            assert form_data['code'] == 'authorization_code'\n            assert form_data['redirect_uri'] == 'https://callback.example.com/callback'\n            assert form_data['code_verifier'] == 'test_code_verifier'\n    \n    @pytest.mark.asyncio\n    async def test_oauth_flow_completion_no_verifier(self):\n        \"\"\"測試 OAuth 流程完成缺少 code_verifier\"\"\"\n        success, error = await self.client.complete_oauth_flow(\n            \"authorization_code\",\n            \"https://callback.example.com/callback\",\n            \"https://auth.example.com/token\"\n        )\n        \n        assert success is False\n        assert \"OAuth flow not properly initialized\" in error\n    \n    @pytest.mark.asyncio\n    async def test_oauth_flow_completion_token_error(self):\n        \"\"\"測試 OAuth 流程完成 token 錯誤\"\"\"\n        self.client.auth_config[\"_code_verifier\"] = \"test_code_verifier\"\n        \n        with patch('aiohttp.ClientSession') as mock_session_class:\n            mock_session = Mock()\n            mock_session.closed = False\n            mock_session_class.return_value = mock_session\n            \n            # 模擬 token 請求失敗\n            mock_response = Mock()\n            mock_response.status = 400\n            mock_response.text = AsyncMock(return_value=json.dumps({\n                \"error\": \"invalid_grant\",\n                \"error_description\": \"Invalid authorization code\"\n            }))\n            mock_session.post = AsyncMock(return_value=mock_response)\n            \n            success, error = await self.client.complete_oauth_flow(\n                \"invalid_code\",\n                \"https://callback.example.com/callback\",\n                \"https://auth.example.com/token\"\n            )\n            \n            assert success is False\n            assert \"Token request failed\" in error\n    \n    @pytest.mark.asyncio\n    async def test_oauth_flow_completion_invalid_token_response(self):\n        \"\"\"測試 OAuth 流程完成無效 token 回應\"\"\"\n        self.client.auth_config[\"_code_verifier\"] = \"test_code_verifier\"\n        \n        with patch('aiohttp.ClientSession') as mock_session_class:\n            mock_session = Mock()\n            mock_session.closed = False\n            mock_session_class.return_value = mock_session\n            \n            # 模擬無效的 token 回應（沒有 access_token）\n            invalid_response = {\n                \"token_type\": \"Bearer\",\n                \"expires_in\": 3600\n            }\n            \n            mock_response = Mock()\n            mock_response.status = 200\n            mock_response.text = AsyncMock(return_value=json.dumps(invalid_response))\n            mock_session.post = AsyncMock(return_value=mock_response)\n            \n            success, error = await self.client.complete_oauth_flow(\n                \"authorization_code\",\n                \"https://callback.example.com/callback\",\n                \"https://auth.example.com/token\"\n            )\n            \n            assert success is False\n            assert \"No access token in response\" in error\n    \n    @pytest.mark.asyncio\n    async def test_oauth_flow_completion_json_error(self):\n        \"\"\"測試 OAuth 流程完成 JSON 解析錯誤\"\"\"\n        self.client.auth_config[\"_code_verifier\"] = \"test_code_verifier\"\n        \n        with patch('aiohttp.ClientSession') as mock_session_class:\n            mock_session = Mock()\n            mock_session.closed = False\n            mock_session_class.return_value = mock_session\n            \n            # 模擬無效 JSON 回應\n            mock_response = Mock()\n            mock_response.status = 200\n            mock_response.text = AsyncMock(return_value=\"invalid json response\")\n            mock_session.post = AsyncMock(return_value=mock_response)\n            \n            success, error = await self.client.complete_oauth_flow(\n                \"authorization_code\",\n                \"https://callback.example.com/callback\",\n                \"https://auth.example.com/token\"\n            )\n            \n            assert success is False\n            assert \"Invalid JSON token response\" in error\n    \n    @pytest.mark.asyncio\n    async def test_authenticated_requests(self):\n        \"\"\"測試認證請求\"\"\"\n        self.client.access_token = \"test_access_token\"\n        \n        with patch('aiohttp.ClientSession') as mock_session_class:\n            mock_session = Mock()\n            mock_session.closed = False\n            mock_session_class.return_value = mock_session\n            \n            # 模擬成功的認證請求\n            success_response = {\n                \"jsonrpc\": \"2.0\",\n                \"id\": 123,\n                \"result\": {\n                    \"content\": [{\"type\": \"text\", \"text\": \"Authenticated response\"}]\n                }\n            }\n            \n            mock_response = Mock()\n            mock_response.status = 200\n            mock_response.text = AsyncMock(return_value=json.dumps(success_response))\n            mock_session.post = AsyncMock(return_value=mock_response)\n            \n            result = await self.client.call_tool(\"test_tool\", {\"query\": \"test\"})\n            \n            assert result[\"success\"] is True\n            assert result[\"data\"] == \"Authenticated response\"\n            \n            # 驗證認證標頭\n            call_args = mock_session.post.call_args\n            headers = call_args[1]['headers']\n            assert headers[\"Authorization\"] == \"Bearer test_access_token\"\n    \n    @pytest.mark.asyncio\n    async def test_authentication_failure_handling(self):\n        \"\"\"測試認證失敗處理\"\"\"\n        self.client.access_token = \"invalid_token\"\n        \n        with patch('aiohttp.ClientSession') as mock_session_class:\n            mock_session = Mock()\n            mock_session.closed = False\n            mock_session_class.return_value = mock_session\n            \n            # 模擬認證失敗\n            mock_response = Mock()\n            mock_response.status = 401\n            mock_response.text = AsyncMock(return_value=\"Unauthorized\")\n            mock_session.post = AsyncMock(return_value=mock_response)\n            \n            with pytest.raises(MCPClientError, match=\"client error\"):\n                await self.client.call_tool(\"test_tool\", {\"query\": \"test\"})\n    \n    @pytest.mark.asyncio\n    async def test_capabilities_initialization_with_auth(self):\n        \"\"\"測試帶認證的能力初始化\"\"\"\n        self.client.access_token = \"test_access_token\"\n        \n        with patch('aiohttp.ClientSession') as mock_session_class:\n            mock_session = Mock()\n            mock_session.closed = False\n            mock_session_class.return_value = mock_session\n            \n            # 模擬成功的初始化回應\n            init_response = {\n                \"jsonrpc\": \"2.0\",\n                \"id\": 123,\n                \"result\": {\n                    \"capabilities\": {\n                        \"tools\": {\"listChanged\": True},\n                        \"resources\": {\"subscribe\": True}\n                    },\n                    \"serverInfo\": {\n                        \"name\": \"Test MCP Server\",\n                        \"version\": \"1.0.0\"\n                    }\n                }\n            }\n            \n            mock_response = Mock()\n            mock_response.status = 200\n            mock_response.text = AsyncMock(return_value=json.dumps(init_response))\n            mock_session.post = AsyncMock(return_value=mock_response)\n            \n            success, error = await self.client.initialize_capabilities()\n            \n            assert success is True\n            assert error is None\n            \n            # 驗證請求包含認證標頭\n            call_args = mock_session.post.call_args\n            headers = call_args[1]['headers']\n            assert headers[\"Authorization\"] == \"Bearer test_access_token\"\n            \n            # 驗證初始化請求內容\n            request_data = call_args[1]['json']\n            assert request_data[\"method\"] == \"initialize\"\n            assert request_data[\"params\"][\"protocolVersion\"] == \"2025-06-18\"\n            assert \"capabilities\" in request_data[\"params\"]\n    \n    @pytest.mark.asyncio\n    async def test_tools_list_with_auth(self):\n        \"\"\"測試帶認證的工具列表\"\"\"\n        self.client.access_token = \"test_access_token\"\n        \n        with patch('aiohttp.ClientSession') as mock_session_class:\n            mock_session = Mock()\n            mock_session.closed = False\n            mock_session_class.return_value = mock_session\n            \n            # 模擬成功的工具列表回應\n            tools_response = {\n                \"jsonrpc\": \"2.0\",\n                \"id\": 123,\n                \"result\": {\n                    \"tools\": [\n                        {\"name\": \"protected_tool\", \"description\": \"Protected tool\"},\n                        {\"name\": \"admin_tool\", \"description\": \"Admin tool\"}\n                    ]\n                }\n            }\n            \n            mock_response = Mock()\n            mock_response.status = 200\n            mock_response.text = AsyncMock(return_value=json.dumps(tools_response))\n            mock_session.post = AsyncMock(return_value=mock_response)\n            \n            success, tools, next_cursor, error = await self.client.list_tools()\n            \n            assert success is True\n            assert len(tools) == 2\n            assert tools[0][\"name\"] == \"protected_tool\"\n            assert tools[1][\"name\"] == \"admin_tool\"\n            assert next_cursor is None\n            assert error is None\n            \n            # 驗證請求包含認證標頭\n            call_args = mock_session.post.call_args\n            headers = call_args[1]['headers']\n            assert headers[\"Authorization\"] == \"Bearer test_access_token\"\n    \n    def test_service_oauth_integration(self):\n        \"\"\"測試服務層 OAuth 整合\"\"\"\n        import tempfile\n        import os\n        \n        # 創建帶認證的配置\n        temp_dir = tempfile.mkdtemp()\n        auth_config = {\n            \"mcp_server\": {\n                \"base_url\": \"http://localhost:3000/api/mcp\",\n                \"timeout\": 30,\n                \"authorization\": {\n                    \"type\": \"oauth2\",\n                    \"client_id\": \"test_client\",\n                    \"client_secret\": \"test_secret\"\n                }\n            },\n            \"functions\": [],\n            \"tools\": {}\n        }\n        \n        config_file = os.path.join(temp_dir, \"auth_config.json\")\n        with open(config_file, 'w') as f:\n            json.dump(auth_config, f)\n        \n        try:\n            with patch('src.services.mcp_service.MCPClient') as mock_client:\n                mock_client_instance = Mock()\n                mock_client_instance.auth_config = auth_config[\"mcp_server\"][\"authorization\"]\n                mock_client_instance.access_token = None\n                mock_client.return_value = mock_client_instance\n                \n                service = MCPService(temp_dir, \"auth_config.json\")\n                \n                # 驗證服務資訊包含認證狀態\n                info = service.get_service_info()\n                assert info[\"auth_configured\"] is True\n                assert info[\"has_access_token\"] is False\n                \n                # 設定 access token\n                mock_client_instance.access_token = \"test_token\"\n                info = service.get_service_info()\n                assert info[\"has_access_token\"] is True\n        \n        finally:\n            import shutil\n            shutil.rmtree(temp_dir)\n    \n    @pytest.mark.asyncio\n    async def test_service_oauth_methods(self):\n        \"\"\"測試服務層 OAuth 方法\"\"\"\n        import tempfile\n        import os\n        \n        # 創建帶認證的配置\n        temp_dir = tempfile.mkdtemp()\n        auth_config = {\n            \"mcp_server\": {\n                \"base_url\": \"http://localhost:3000/api/mcp\",\n                \"authorization\": {\n                    \"type\": \"oauth2\",\n                    \"client_id\": \"test_client\"\n                }\n            },\n            \"functions\": [],\n            \"tools\": {}\n        }\n        \n        config_file = os.path.join(temp_dir, \"auth_config.json\")\n        with open(config_file, 'w') as f:\n            json.dump(auth_config, f)\n        \n        try:\n            mock_client = Mock()\n            mock_client.authenticate_oauth = AsyncMock(return_value=(\n                True, \"https://auth.example.com/authorize?...\"\n            ))\n            mock_client.complete_oauth_flow = AsyncMock(return_value=(True, None))\n            mock_client.__aenter__ = AsyncMock(return_value=mock_client)\n            mock_client.__aexit__ = AsyncMock(return_value=None)\n            \n            with patch('src.services.mcp_service.MCPClient', return_value=mock_client):\n                service = MCPService(temp_dir, \"auth_config.json\")\n                \n                # 測試 OAuth 設定\n                success, auth_url = await service.setup_oauth_authentication(\n                    \"https://auth.example.com/authorize\",\n                    \"https://callback.example.com\"\n                )\n                \n                assert success is True\n                assert auth_url.startswith(\"https://auth.example.com/authorize\")\n                \n                # 測試 OAuth 完成\n                success, error = await service.complete_oauth_authentication(\n                    \"auth_code\",\n                    \"https://callback.example.com\",\n                    \"https://token.example.com\"\n                )\n                \n                assert success is True\n                assert error is None\n        \n        finally:\n            import shutil\n            shutil.rmtree(temp_dir)\n    \n    @pytest.mark.asyncio\n    async def test_token_refresh_scenario(self):\n        \"\"\"測試 token 刷新場景\"\"\"\n        # 模擬 token 過期和刷新\n        self.client.access_token = \"expired_token\"\n        \n        with patch('aiohttp.ClientSession') as mock_session_class:\n            mock_session = Mock()\n            mock_session.closed = False\n            mock_session_class.return_value = mock_session\n            \n            # 第一次請求返回 401（token 過期）\n            expired_response = Mock()\n            expired_response.status = 401\n            expired_response.text = AsyncMock(return_value=\"Token expired\")\n            \n            # 第二次請求（刷新 token 後）成功\n            success_response = {\n                \"jsonrpc\": \"2.0\",\n                \"id\": 123,\n                \"result\": {\n                    \"content\": [{\"type\": \"text\", \"text\": \"Success with new token\"}]\n                }\n            }\n            success_mock = Mock()\n            success_mock.status = 200\n            success_mock.text = AsyncMock(return_value=json.dumps(success_response))\n            \n            mock_session.post = AsyncMock(side_effect=[expired_response, success_mock])\n            \n            # 第一次請求應該失敗\n            with pytest.raises(MCPClientError, match=\"client error\"):\n                await self.client.call_tool(\"test_tool\", {\"query\": \"test\"})\n            \n            # 模擬手動刷新 token\n            self.client.access_token = \"new_token\"\n            \n            # 第二次請求應該成功\n            result = await self.client.call_tool(\"test_tool\", {\"query\": \"test\"})\n            assert result[\"success\"] is True\n            assert result[\"data\"] == \"Success with new token\"\n    \n    @pytest.mark.asyncio\n    async def test_multiple_auth_methods(self):\n        \"\"\"測試多種認證方法\"\"\"\n        # 測試不同認證方法的優先權和互操作性\n        \n        # 1. 僅 API key\n        config_api_key = {\n            \"base_url\": \"http://localhost:3000\",\n            \"authorization\": {\"api_key\": \"test_api_key\"}\n        }\n        client_api = MCPClient(config_api_key)\n        headers = await client_api._get_auth_headers()\n        assert headers[\"Authorization\"] == \"Bearer test_api_key\"\n        \n        # 2. OAuth 配置但無 token\n        config_oauth = {\n            \"base_url\": \"http://localhost:3000\",\n            \"authorization\": {\"client_id\": \"test_client\"}\n        }\n        client_oauth = MCPClient(config_oauth)\n        headers = await client_oauth._get_auth_headers()\n        assert headers == {}\n        \n        # 3. OAuth 配置且有 token\n        client_oauth.access_token = \"oauth_token\"\n        headers = await client_oauth._get_auth_headers()\n        assert headers[\"Authorization\"] == \"Bearer oauth_token\"\n        \n        # 4. 同時有 API key 和 OAuth token（OAuth 優先）\n        config_both = {\n            \"base_url\": \"http://localhost:3000\",\n            \"authorization\": {\"api_key\": \"api_key\", \"client_id\": \"client\"}\n        }\n        client_both = MCPClient(config_both)\n        client_both.access_token = \"oauth_token\"\n        headers = await client_both._get_auth_headers()\n        assert headers[\"Authorization\"] == \"Bearer oauth_token\"\n        \n        # 5. 只有 API key（無 OAuth token）\n        client_both.access_token = None\n        headers = await client_both._get_auth_headers()\n        assert headers[\"Authorization\"] == \"Bearer api_key\""