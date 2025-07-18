"""
MCP 伺服器客戶端

核心基礎設施：負責與 MCP 伺服器進行 HTTP 通訊
- 純 HTTP 客戶端，不包含業務邏輯
- 支援重試機制和錯誤處理
- 統一的 MCP 協議實現
"""

import json
import asyncio
import aiohttp
import time
from typing import Dict, Any, Optional, Tuple, List
from ..core.logger import get_logger
from ..utils.retry import retry_with_backoff

logger = get_logger(__name__)


class MCPClient:
    """MCP 伺服器客戶端"""
    
    def __init__(self, server_config: Dict[str, Any]):
        self.base_url = server_config['base_url'].rstrip('/')
        self.timeout = server_config.get('timeout', 30)
        self.retry_attempts = server_config.get('retry_attempts', 3)
        self.retry_delay = server_config.get('retry_delay', 1.0)
        
        # Authorization configuration
        self.auth_config = server_config.get('authorization', {})
        self.access_token = None
        
        # Client capabilities
        self.capabilities = server_config.get('capabilities', {
            'roots': {'listChanged': False},
            'sampling': {},
            'elicitation': {}
        })
        
        # 建立 session 設定
        self.session_timeout = aiohttp.ClientTimeout(total=self.timeout)
        self._session = None
        
        logger.info(f"Initialized MCP client for: {self.base_url}")
        if self.auth_config:
            logger.info(f"Authorization configured: {list(self.auth_config.keys())}")
    
    async def __aenter__(self):
        """異步上下文管理器進入"""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """異步上下文管理器退出"""
        await self.close()
    
    async def _ensure_session(self):
        """確保 HTTP session 存在"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.session_timeout)
    
    async def close(self):
        """關閉 HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
    
    @retry_with_backoff(max_retries=3, base_delay=1.0)
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        呼叫 MCP 工具
        
        Args:
            tool_name: MCP 工具名稱
            arguments: 工具參數
            
        Returns:
            Dict[str, Any]: MCP 回應結果
            
        Raises:
            MCPClientError: MCP 通訊錯誤
            MCPServerError: MCP 伺服器錯誤
        """
        start_time = time.time()
        request_id = f"mcp-{int(start_time * 1000) % 100000}"
        
        try:
            await self._ensure_session()
            
            # 建構 MCP 請求
            mcp_request = self._build_mcp_request(tool_name, arguments)
            
            # 記錄詳細的請求日志
            logger.info(f"[{request_id}] 🔌 MCP Request - Tool: {tool_name}")
            logger.info(f"[{request_id}] 📤 Request URL: {self.base_url}")
            logger.info(f"[{request_id}] 📊 Request Arguments: {json.dumps(arguments, ensure_ascii=False, indent=2)}")
            logger.debug(f"[{request_id}] 📋 Full MCP Request: {json.dumps(mcp_request, ensure_ascii=False, indent=2)}")
            
            # 發送 HTTP 請求到 MCP 端點
            endpoint = self.base_url
            
            headers = await self._get_auth_headers()
            headers.update({
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            })
            
            async with self._session.post(
                endpoint,
                json=mcp_request,
                headers=headers
            ) as response:
                # 記錄回應狀態
                elapsed_time = time.time() - start_time
                logger.info(f"[{request_id}] 📡 MCP Response - Status: {response.status}, Time: {elapsed_time:.2f}s")
                
                # 讀取回應內容
                response_text = await response.text()
                logger.info(f"[{request_id}] 📥 Response Size: {len(response_text)} chars")
                logger.debug(f"[{request_id}] 📄 Raw Response: {response_text}")
                
                if response.status >= 500:
                    error_msg = f"MCP server error {response.status}: {response_text}"
                    logger.error(f"[{request_id}] ❌ {error_msg}")
                    raise MCPServerError(error_msg)
                elif response.status >= 400:
                    error_msg = f"MCP client error {response.status}: {response_text}"
                    logger.error(f"[{request_id}] ❌ {error_msg}")
                    raise MCPClientError(error_msg)
                
                # 解析 JSON 回應
                try:
                    response_data = json.loads(response_text)
                    logger.debug(f"[{request_id}] 🔍 Parsed JSON Response: {json.dumps(response_data, ensure_ascii=False, indent=2)}")
                except json.JSONDecodeError as e:
                    error_msg = f"Invalid JSON response from MCP server: {e}"
                    logger.error(f"[{request_id}] ❌ {error_msg}")
                    raise MCPClientError(error_msg)
                
                # 處理 MCP 回應格式
                result = self._parse_mcp_response(response_data, request_id)
                
                # 記錄最終結果
                total_time = time.time() - start_time
                if result.get('success', False):
                    data_preview = str(result.get('data', ''))[:200] + ('...' if len(str(result.get('data', ''))) > 200 else '')
                    logger.info(f"[{request_id}] ✅ MCP Success - Tool: {tool_name}, Time: {total_time:.2f}s")
                    logger.info(f"[{request_id}] 📋 Result Preview: {data_preview}")
                else:
                    logger.error(f"[{request_id}] ❌ MCP Failed - Tool: {tool_name}, Error: {result.get('error', 'Unknown')}")
                
                return result
                
        except (MCPClientError, MCPServerError):
            # 重新拋出 MCP 特定錯誤
            raise
        except asyncio.TimeoutError:
            error_msg = f"MCP request timeout after {self.timeout}s"
            logger.error(error_msg)
            raise MCPClientError(error_msg)
        except aiohttp.ClientError as e:
            error_msg = f"HTTP request failed: {e}"
            logger.error(error_msg)
            raise MCPClientError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error calling MCP tool {tool_name}: {e}"
            logger.error(error_msg)
            raise MCPClientError(error_msg)
    
    def _build_mcp_request(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """建構 MCP 請求格式 (JSON-RPC 2.0)"""
        import time
        request_id = int(time.time() * 1000) % 100000  # 生成請求 ID
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
    
    def _parse_mcp_response(self, response: Dict[str, Any], request_id: str = "") -> Dict[str, Any]:
        """
        解析 MCP 回應格式
        
        Args:
            response: 原始 MCP 回應
            request_id: 請求 ID（用於日志）
            
        Returns:
            Dict[str, Any]: 處理後的回應資料
        """
        try:
            # 檢查是否有錯誤
            if 'error' in response:
                error_info = response['error']
                error_msg = error_info.get('message', 'Unknown MCP error')
                error_code = error_info.get('code', 'UNKNOWN')
                logger.error(f"[{request_id}] 🚫 MCP Server Error: {error_msg} (Code: {error_code})")
                logger.debug(f"[{request_id}] 📄 Error Details: {json.dumps(error_info, ensure_ascii=False, indent=2)}")
                return {
                    "success": False,
                    "error": error_msg,
                    "error_code": error_code,
                    "raw_response": response
                }
            
            # 提取結果內容
            if 'result' in response:
                result_data = response['result']
                if result_data is None:
                    return {
                        "success": True,
                        "data": None,
                        "content_type": "raw",
                        "metadata": {}
                    }
                logger.debug(f"[{request_id}] 🔍 Processing result data: {json.dumps(result_data, ensure_ascii=False, indent=2)}")
                
                # 檢查結果格式
                if 'content' in result_data:
                    content = result_data['content']
                    logger.info(f"[{request_id}] 📄 Found content field, type: {type(content)}")
                    
                    # 處理不同的內容格式
                    if isinstance(content, list) and len(content) > 0:
                        # 取第一個內容項目
                        first_content = content[0]
                        logger.debug(f"[{request_id}] 📋 First content item: {json.dumps(first_content, ensure_ascii=False, indent=2)}")
                        
                        if isinstance(first_content, dict) and 'text' in first_content:
                            text_content = first_content['text']
                            logger.info(f"[{request_id}] 📝 Extracted text content: {len(text_content)} chars")
                            
                            return {
                                "success": True,
                                "data": text_content,
                                "content_type": first_content.get('type', 'text'),
                                "metadata": {
                                    "content_count": len(content),
                                    "raw_result": result_data,
                                    "sources": self._extract_sources_from_content(content)
                                }
                            }
                    
                    # 直接回傳內容
                    logger.info(f"[{request_id}] 📋 Using content directly")
                    return {
                        "success": True,
                        "data": content,
                        "content_type": "raw",
                        "metadata": {
                            "raw_result": result_data
                        }
                    }
                
                # 沒有 content 欄位，直接回傳 result
                logger.info(f"[{request_id}] 📋 No content field, using result directly")
                return {
                    "success": True,
                    "data": result_data,
                    "content_type": "raw",
                    "metadata": {}
                }
            
            # 沒有 result 欄位，可能是其他格式
            logger.warning(f"[{request_id}] ⚠️ Unexpected MCP response format: {json.dumps(response, ensure_ascii=False, indent=2)}")
            return {
                "success": True,
                "data": response,
                "content_type": "unknown",
                "metadata": {}
            }
            
        except Exception as e:
            error_msg = f"Error parsing MCP response: {e}"
            logger.error(f"[{request_id}] ❌ {error_msg}")
            logger.debug(f"[{request_id}] 📄 Raw response that failed parsing: {json.dumps(response, ensure_ascii=False, indent=2)}")
            return {
                "success": False,
                "error": error_msg,
                "raw_response": response
            }
    
    def _extract_sources_from_content(self, content: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """從內容中提取來源信息"""
        sources = []
        
        for item in content:
            if isinstance(item, dict):
                # 檢查是否有來源信息
                if 'source' in item:
                    sources.append(item['source'])
                elif 'metadata' in item and isinstance(item['metadata'], dict):
                    if 'source' in item['metadata']:
                        sources.append(item['metadata']['source'])
        
        return sources
    
    async def _get_auth_headers(self) -> Dict[str, str]:
        """
        建構認證標頭
        
        Returns:
            Dict[str, str]: HTTP 標頭
        """
        headers = {}
        
        if self.access_token:
            headers['Authorization'] = f'Bearer {self.access_token}'
        elif self.auth_config.get('api_key'):
            headers['Authorization'] = f'Bearer {self.auth_config["api_key"]}'
        
        return headers
    
    async def initialize_capabilities(self) -> Tuple[bool, Optional[str]]:
        """
        初始化客戶端功能宣告
        
        Returns:
            Tuple[bool, Optional[str]]: (成功, 錯誤訊息)
        """
        try:
            await self._ensure_session()
            
            import time
            request_id = int(time.time() * 1000) % 100000
            
            rpc_request = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": self.capabilities,
                    "clientInfo": {
                        "name": "ChatGPT-Line-Bot",
                        "version": "2.2.0"
                    }
                }
            }
            
            headers = await self._get_auth_headers()
            headers.update({
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            })
            
            async with self._session.post(
                self.base_url,
                json=rpc_request,
                headers=headers
            ) as response:
                response_text = await response.text()
                
                if response.status != 200:
                    error_msg = f"Failed to initialize: HTTP {response.status} - {response_text}"
                    logger.error(error_msg)
                    return False, error_msg
                
                try:
                    data = json.loads(response_text)
                    
                    if 'error' in data:
                        error_msg = data['error'].get('message', 'Unknown initialization error')
                        logger.error(f"Initialization error: {error_msg}")
                        return False, error_msg
                    
                    result = data.get('result', {})
                    server_capabilities = result.get('capabilities', {})
                    logger.info(f"MCP server capabilities: {list(server_capabilities.keys())}")
                    
                    return True, None
                    
                except json.JSONDecodeError as e:
                    error_msg = f"Invalid JSON response from initialize: {e}"
                    logger.error(error_msg)
                    return False, error_msg
                    
        except Exception as e:
            error_msg = f"Error initializing MCP client: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    async def authenticate_oauth(self, authorization_url: str, redirect_uri: str) -> Tuple[bool, Optional[str]]:
        """
        執行 OAuth 2.1 認證流程
        
        Args:
            authorization_url: 授權服務器 URL
            redirect_uri: 重定向 URI
            
        Returns:
            Tuple[bool, Optional[str]]: (成功, 錯誤訊息或授權 URL)
        """
        try:
            if not self.auth_config.get('client_id'):
                return False, "OAuth client_id not configured"
            
            # 生成 PKCE 參數
            import base64
            import hashlib
            import secrets
            
            code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
            code_challenge = base64.urlsafe_b64encode(
                hashlib.sha256(code_verifier.encode('utf-8')).digest()
            ).decode('utf-8').rstrip('=')
            
            # 建構授權 URL
            auth_params = {
                'response_type': 'code',
                'client_id': self.auth_config['client_id'],
                'redirect_uri': redirect_uri,
                'code_challenge': code_challenge,
                'code_challenge_method': 'S256',
                'scope': self.auth_config.get('scope', 'read')
            }
            
            import urllib.parse
            auth_url = f"{authorization_url}?{urllib.parse.urlencode(auth_params)}"
            
            # 儲存 code_verifier 供稍後使用
            self.auth_config['_code_verifier'] = code_verifier
            
            logger.info("OAuth authorization URL generated")
            return True, auth_url
            
        except Exception as e:
            error_msg = f"Error generating OAuth URL: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    async def complete_oauth_flow(self, authorization_code: str, redirect_uri: str, token_url: str) -> Tuple[bool, Optional[str]]:
        """
        完成 OAuth 認證流程並取得 access token
        
        Args:
            authorization_code: 授權碼
            redirect_uri: 重定向 URI
            token_url: Token 端點 URL
            
        Returns:
            Tuple[bool, Optional[str]]: (成功, 錯誤訊息)
        """
        try:
            await self._ensure_session()
            
            code_verifier = self.auth_config.get('_code_verifier')
            if not code_verifier:
                return False, "OAuth flow not properly initialized"
            
            token_data = {
                'grant_type': 'authorization_code',
                'client_id': self.auth_config['client_id'],
                'code': authorization_code,
                'redirect_uri': redirect_uri,
                'code_verifier': code_verifier
            }
            
            async with self._session.post(
                token_url,
                data=token_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            ) as response:
                response_text = await response.text()
                
                if response.status != 200:
                    error_msg = f"Token request failed: HTTP {response.status} - {response_text}"
                    logger.error(error_msg)
                    return False, error_msg
                
                try:
                    token_response = json.loads(response_text)
                    
                    if 'access_token' in token_response:
                        self.access_token = token_response['access_token']
                        logger.info("OAuth authentication successful")
                        return True, None
                    else:
                        error_msg = f"No access token in response: {token_response}"
                        logger.error(error_msg)
                        return False, error_msg
                        
                except json.JSONDecodeError as e:
                    error_msg = f"Invalid JSON token response: {e}"
                    logger.error(error_msg)
                    return False, error_msg
                    
        except Exception as e:
            error_msg = f"Error completing OAuth flow: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    async def health_check(self) -> Tuple[bool, Optional[str]]:
        """
        檢查 MCP 伺服器健康狀態
        
        Returns:
            Tuple[bool, Optional[str]]: (是否健康, 錯誤訊息)
        """
        try:
            await self._ensure_session()
            
            # 嘗試簡單的 HTTP 請求
            endpoint = f"{self.base_url}/health"
            
            async with self._session.get(endpoint) as response:
                if response.status == 200:
                    logger.debug("MCP server health check passed")
                    return True, None
                else:
                    error_msg = f"MCP server health check failed: HTTP {response.status}"
                    logger.warning(error_msg)
                    return False, error_msg
                    
        except Exception as e:
            error_msg = f"MCP server health check error: {e}"
            logger.warning(error_msg)
            return False, error_msg
    
    async def list_tools(self, cursor: Optional[str] = None) -> Tuple[bool, Optional[List[Dict[str, Any]]], Optional[str], Optional[str]]:
        """
        取得 MCP 伺服器可用工具列表 (支援分頁)
        
        Args:
            cursor: 分頁游標
            
        Returns:
            Tuple[bool, Optional[List], Optional[str], Optional[str]]: (成功, 工具列表, 下一頁游標, 錯誤訊息)
        """
        try:
            await self._ensure_session()
            
            # 建構 JSON-RPC 2.0 請求
            import time
            request_id = int(time.time() * 1000) % 100000
            
            params = {}
            if cursor:
                params['cursor'] = cursor
            
            rpc_request = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/list",
                "params": params
            }
            
            headers = await self._get_auth_headers()
            headers.update({
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            })
            
            async with self._session.post(
                self.base_url,
                json=rpc_request,
                headers=headers
            ) as response:
                response_text = await response.text()
                
                if response.status != 200:
                    error_msg = f"Failed to list tools: HTTP {response.status} - {response_text}"
                    logger.error(error_msg)
                    return False, None, None, error_msg
                
                try:
                    data = json.loads(response_text)
                    
                    # 檢查 JSON-RPC 錯誤
                    if 'error' in data:
                        error_msg = data['error'].get('message', 'Unknown RPC error')
                        logger.error(f"RPC error listing tools: {error_msg}")
                        return False, None, None, error_msg
                    
                    # 提取工具列表和分頁資訊
                    result = data.get('result', {})
                    tools = result.get('tools', [])
                    next_cursor = result.get('nextCursor')
                    
                    logger.debug(f"Retrieved {len(tools)} tools from MCP server")
                    if next_cursor:
                        logger.debug(f"Next page available with cursor: {next_cursor[:20]}...")
                    
                    return True, tools, next_cursor, None
                    
                except json.JSONDecodeError as e:
                    error_msg = f"Invalid JSON response from tools/list: {e}"
                    logger.error(error_msg)
                    return False, None, None, error_msg
                    
        except Exception as e:
            error_msg = f"Error listing MCP tools: {e}"
            logger.error(error_msg)
            return False, None, None, error_msg


class MCPClientError(Exception):
    """MCP 客戶端錯誤"""
    pass


class MCPServerError(Exception):
    """MCP 伺服器錯誤"""
    pass


# 便利函數：建立 MCP 客戶端
def create_mcp_client(server_config: Dict[str, Any]) -> MCPClient:
    """
    建立 MCP 客戶端實例
    
    Args:
        server_config: MCP 伺服器設定
        
    Returns:
        MCPClient: MCP 客戶端實例
    """
    return MCPClient(server_config)