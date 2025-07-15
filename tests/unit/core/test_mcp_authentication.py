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
        ).decode('utf-8').rstrip('=')
        
        # 驗證格式
        assert len(code_verifier) >= 43  # Base64 編碼後至少 43 字符
        assert len(code_challenge) == 43  # SHA256 Base64 編碼後為 43 字符
        assert code_verifier != code_challenge
    
    @pytest.mark.asyncio
    async def test_oauth_flow_completion_success(self):
        """測試 OAuth 流程完成成功"""
        # 先設定 OAuth 狀態
        self.client.auth_config["_code_verifier"] = "test_code_verifier"
        
        # 模擬成功的 token 回應
        token_response = {
            "access_token": "test_access_token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "test_refresh_token",
            "scope": "read write"
        }
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = Mock()
            mock_session.closed = False
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session
            
            mock_response = Mock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value=json.dumps(token_response))
            
            # Mock the async context manager for post method
            mock_post_context = Mock()
            mock_post_context.__aenter__ = AsyncMock(return_value=mock_response)
            mock_post_context.__aexit__ = AsyncMock(return_value=None)
            mock_session.post = Mock(return_value=mock_post_context)
            
            success, error = await self.client.complete_oauth_flow(
                "authorization_code",
                "https://callback.example.com/callback",
                "https://auth.example.com/token"
            )
            
            assert success is True
            assert error is None
            assert self.client.access_token == "test_access_token"
            
            # 驗證請求參數
            call_args = mock_session.post.call_args
            assert call_args[0][0] == "https://auth.example.com/token"
            
            form_data = call_args[1]['data']
            assert form_data['grant_type'] == 'authorization_code'
            assert form_data['client_id'] == 'test_client_id'
            assert form_data['code'] == 'authorization_code'
            assert form_data['redirect_uri'] == 'https://callback.example.com/callback'
            assert form_data['code_verifier'] == 'test_code_verifier'