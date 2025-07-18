"""
MCP 服務協調層

業務邏輯層：協調 MCP 設定管理和客戶端通訊
- 整合 MCPConfigManager 和 MCPClient
- 提供統一的 function calling 處理接口
- 支援不同模型提供商的 function calling 格式
"""

import asyncio
import json
from typing import Dict, List, Any, Optional, Tuple
from ..core.logger import get_logger
from ..core.mcp_config import MCPConfigManager
from ..core.mcp_client import MCPClient, MCPClientError, MCPServerError

logger = get_logger(__name__)


class MCPService:
    """MCP Function Calling 處理器和服務協調層"""
    
    def __init__(self, config_dir: str = "config/mcp", config_name: str = None):
        self.config_dir = config_dir
        self.config_name = config_name
        self.config_manager = MCPConfigManager(config_dir)
        self.mcp_client = None
        self.is_enabled = False
        
        
        # 初始化 MCP 服務
        self._init_mcp_service()
    
    def _init_mcp_service(self) -> None:
        """初始化 MCP 服務"""
        try:
            # 檢查是否有可用的設定檔案
            if not self.config_manager.is_mcp_enabled():
                logger.info("No MCP config found, MCP service disabled")
                return
            
            # 載入伺服器設定
            server_config = self.config_manager.get_server_config(self.config_name)
            self.mcp_client = MCPClient(server_config)
            self.is_enabled = True
            
            logger.info("MCP service initialized successfully")
            
        except Exception as e:
            logger.warning(f"Failed to initialize MCP service: {e}")
            self.is_enabled = False
    
    
    def handle_function_call_sync(self, function_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        同步版本的 function call 處理器（為了與 sync 模型兼容）
        內部使用 asyncio.run() 執行異步操作
        """
        import asyncio
        
        try:
            # 檢查是否已經在事件循環中
            try:
                loop = asyncio.get_running_loop()
                # 如果已經在事件循環中，使用 create_task
                logger.warning("Already in event loop, using asyncio.create_task")
                task = asyncio.create_task(self.handle_function_call_async(function_name, arguments))
                return asyncio.run_coroutine_threadsafe(task, loop).result()
            except RuntimeError:
                # 沒有運行中的事件循環，安全使用 asyncio.run
                return asyncio.run(self.handle_function_call_async(function_name, arguments))
        except Exception as e:
            logger.error(f"Error in sync MCP call: {e}")
            return {
                "success": False,
                "error": str(e),
                "content": f"MCP 調用失敗: {e}"
            }

    async def handle_function_call(self, function_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """異步版本的 function call 處理器（向後兼容）"""
        return await self.handle_function_call_async(function_name, arguments)

    async def handle_function_call_async(self, function_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        處理 function call 並回傳結果
        
        Args:
            function_name: 函數名稱
            arguments: 函數參數
            
        Returns:
            Dict[str, Any]: 處理結果
        """
        import time
        
        start_time = time.time()
        call_id = f"mcp-svc-{int(start_time * 1000) % 100000}"
        
        # 詳細的服務層日志記錄
        logger.info(f"[{call_id}] 🚀 MCP Service Call Started")
        logger.info(f"[{call_id}] 📞 Function: {function_name}")
        logger.info(f"[{call_id}] 📊 Arguments: {json.dumps(arguments, ensure_ascii=False, indent=2)}")
        logger.info(f"[{call_id}] 🏗️ Service Status: enabled={self.is_enabled}, config={self.config_name}")
        
        if not self.is_enabled:
            error_msg = "MCP service is not enabled"
            logger.error(f"[{call_id}] ❌ MCP Service Disabled")
            return self._format_error_response(error_msg)
        
        try:
            # 步驟 1: 驗證函數和參數
            logger.info(f"[{call_id}] 🔍 Step 1: Validating function arguments")
            is_valid, error_msg = self.config_manager.validate_function_arguments(
                function_name, arguments, self.config_name
            )
            
            if not is_valid:
                error_msg_full = f"Parameter validation failed: {error_msg}"
                logger.warning(f"[{call_id}] ⚠️ Validation Failed: {error_msg}")
                return self._format_error_response(error_msg_full)
            
            logger.info(f"[{call_id}] ✅ Arguments validation passed")
            
            # 步驟 2: 取得函數設定
            logger.info(f"[{call_id}] 🔍 Step 2: Loading function configuration")
            func_config = self.config_manager.get_function_by_name(function_name, self.config_name)
            if not func_config:
                error_msg = f"Unknown function: {function_name}"
                logger.error(f"[{call_id}] ❌ Unknown function: {function_name}")
                return self._format_error_response(error_msg)
            
            mcp_tool_name = func_config['mcp_tool']
            logger.info(f"[{call_id}] 🔧 Function Mapping: {function_name} -> {mcp_tool_name}")
            logger.debug(f"[{call_id}] 📋 Function Config: {json.dumps(func_config, ensure_ascii=False, indent=2)}")
            
            # 步驟 3: 執行 MCP 工具呼叫
            logger.info(f"[{call_id}] 🔍 Step 3: Executing MCP tool call")
            logger.info(f"[{call_id}] 🌐 Server: {self.mcp_client.base_url if self.mcp_client else 'N/A'}")
            
            async with self.mcp_client as client:
                result = await client.call_tool(mcp_tool_name, arguments)
            
            execution_time = time.time() - start_time
            
            # 步驟 4: 處理結果
            if result.get('success', True):
                data_size = len(str(result.get('data', '')))
                logger.info(f"[{call_id}] ✅ MCP Success - Function: {function_name}, Time: {execution_time:.2f}s")
                logger.info(f"[{call_id}] 📊 Result: size={data_size} chars, type={result.get('content_type', 'unknown')}")
                logger.debug(f"[{call_id}] 📋 Full Result: {json.dumps(result, ensure_ascii=False, indent=2)}")
                
                # 檢查是否有來源信息
                metadata = result.get('metadata', {})
                sources = metadata.get('sources', [])
                if sources:
                    logger.info(f"[{call_id}] 📚 Sources Found: {len(sources)} items")
                    for i, source in enumerate(sources[:3]):  # 只記錄前3個來源
                        logger.debug(f"[{call_id}] 📚 Source {i+1}: {source}")
                
                return {
                    "success": True,
                    "data": result.get('data'),
                    "content_type": result.get('content_type', 'text'),
                    "metadata": {
                        "function_name": function_name,
                        "mcp_tool": mcp_tool_name,
                        "execution_time": execution_time,
                        "call_id": call_id,
                        "sources": sources,
                        "execution_metadata": metadata
                    },
                    # 🔥 MCP 互動資訊：記錄發送與回應的 JSON 內容
                    "mcp_interaction": {
                        "request": {
                            "function_name": function_name,
                            "arguments": arguments
                        },
                        "response": {
                            "success": True,
                            "data": result.get('data'),
                            "execution_time": execution_time
                        },
                        "status": "success"
                    }
                }
            else:
                error_msg = result.get('error', 'Unknown MCP error')
                logger.error(f"[{call_id}] ❌ MCP Tool Failed: {error_msg}")
                logger.debug(f"[{call_id}] 📄 Error Details: {json.dumps(result, ensure_ascii=False, indent=2)}")
                
                # 🔥 失敗情況的 MCP 互動記錄
                error_response = self._format_error_response(error_msg)
                error_response["mcp_interaction"] = {
                    "request": {
                        "function_name": function_name,
                        "arguments": arguments
                    },
                    "response": {
                        "success": False,
                        "error": error_msg,
                        "execution_time": execution_time
                    },
                    "status": "failed"
                }
                return error_response
                
        except (MCPClientError, MCPServerError) as e:
            execution_time = time.time() - start_time
            logger.error(f"[{call_id}] 🌐 MCP Communication Error: {e} (Time: {execution_time:.2f}s)")
            
            # 🔥 通訊錯誤的 MCP 互動記錄
            error_response = self._format_error_response(str(e))
            error_response["mcp_interaction"] = {
                "request": {
                    "function_name": function_name,
                    "arguments": arguments
                },
                "response": {
                    "success": False,
                    "error": str(e),
                    "execution_time": execution_time
                },
                "status": "error"
            }
            return error_response
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"[{call_id}] 💥 Unexpected Service Error: {e} (Time: {execution_time:.2f}s)")
            logger.exception(f"[{call_id}] 📄 Full Exception Details:")
            
            # 🔥 未預期錯誤的 MCP 互動記錄
            error_response = self._format_error_response(f"Function execution error: {str(e)}")
            error_response["mcp_interaction"] = {
                "request": {
                    "function_name": function_name,
                    "arguments": arguments
                },
                "response": {
                    "success": False,
                    "error": f"Function execution error: {str(e)}",
                    "execution_time": execution_time
                },
                "status": "error"
            }
            return error_response
    
    def get_function_schemas_for_openai(self) -> List[Dict[str, Any]]:
        """取得 OpenAI function calling 格式的 schemas"""
        if not self.is_enabled:
            return []
        
        try:
            schemas = self.config_manager.get_function_schemas_for_openai(self.config_name)
            logger.debug(f"Generated {len(schemas)} OpenAI function schemas")
            return schemas
        except Exception as e:
            logger.error(f"Error generating OpenAI function schemas: {e}")
            return []
    
    def get_function_schemas_for_anthropic(self) -> str:
        """取得 Anthropic system prompt 格式的 function schemas"""
        if not self.is_enabled:
            return ""
        
        try:
            prompt = self.config_manager.get_function_schemas_for_anthropic(self.config_name)
            logger.debug("Generated Anthropic function schemas prompt")
            return prompt
        except Exception as e:
            logger.error(f"Error generating Anthropic function schemas: {e}")
            return ""
    
    def get_function_schemas_for_gemini(self) -> List[Dict[str, Any]]:
        """取得 Gemini function calling 格式的 schemas"""
        if not self.is_enabled:
            return []
        
        try:
            config = self.config_manager.load_mcp_config(self.config_name)
            schemas = []
            
            for func in config['functions']:
                if func.get('enabled', True):
                    # Gemini function declaration 格式
                    schema = {
                        "name": func['name'],
                        "description": func['description'],
                        "parameters": func['parameters']
                    }
                    schemas.append(schema)
            
            logger.debug(f"Generated {len(schemas)} Gemini function schemas")
            return schemas
        except Exception as e:
            logger.error(f"Error generating Gemini function schemas: {e}")
            return []
    
    def _format_error_response(self, error_msg: str) -> Dict[str, Any]:
        """格式化錯誤回應"""
        # 根據錯誤類型取得友善的錯誤訊息
        fallback_msg = self._get_fallback_message(error_msg)
        
        return {
            "success": False,
            "error": error_msg,
            "fallback_message": fallback_msg,
            "metadata": {
                "error_type": "mcp_service_error"
            }
        }
    
    def _get_fallback_message(self, error: str) -> str:
        """根據錯誤類型取得適當的 fallback 訊息"""
        try:
            error_messages = self.config_manager.get_error_messages(self.config_name)
            error_lower = error.lower()

            if "timeout" in error_lower:
                return error_messages.get("timeout_error", "請求超時，請稍後再試")
            elif "connection" in error_lower or "network" in error_lower:
                return error_messages.get("connection_error", "連線錯誤，請稍後再試")
            elif "no results" in error_lower or "empty" in error_lower:
                return error_messages.get("no_results", "查無相關結果")
            else:
                return error_messages.get("unknown_error", "處理請求時發生錯誤，請稍後再試")
        except Exception:
            return "處理請求時發生錯誤，請稍後再試"
    
    async def health_check(self) -> Tuple[bool, Optional[str]]:
        """檢查 MCP 服務健康狀態"""
        if not self.is_enabled:
            return False, "MCP service is not enabled"
        
        try:
            async with self.mcp_client as client:
                return await client.health_check()
        except Exception as e:
            return False, str(e)
    
    async def initialize_connection(self) -> Tuple[bool, Optional[str]]:
        """
        初始化 MCP 連線並宣告客戶端功能
        
        Returns:
            Tuple[bool, Optional[str]]: (成功, 錯誤訊息)
        """
        if not self.is_enabled:
            return False, "MCP service is not enabled"
        
        try:
            async with self.mcp_client as client:
                return await client.initialize_capabilities()
        except Exception as e:
            logger.error(f"Failed to initialize MCP connection: {e}")
            return False, str(e)
    
    async def setup_oauth_authentication(self, authorization_url: str, redirect_uri: str) -> Tuple[bool, Optional[str]]:
        """
        設定 OAuth 認證
        
        Args:
            authorization_url: 授權服務器 URL
            redirect_uri: 重定向 URI
            
        Returns:
            Tuple[bool, Optional[str]]: (成功, 授權 URL 或錯誤訊息)
        """
        if not self.is_enabled:
            return False, "MCP service is not enabled"
        
        try:
            async with self.mcp_client as client:
                return await client.authenticate_oauth(authorization_url, redirect_uri)
        except Exception as e:
            logger.error(f"Failed to setup OAuth authentication: {e}")
            return False, str(e)
    
    async def complete_oauth_authentication(self, authorization_code: str, redirect_uri: str, token_url: str) -> Tuple[bool, Optional[str]]:
        """
        完成 OAuth 認證流程
        
        Args:
            authorization_code: 授權碼
            redirect_uri: 重定向 URI
            token_url: Token 端點 URL
            
        Returns:
            Tuple[bool, Optional[str]]: (成功, 錯誤訊息)
        """
        if not self.is_enabled:
            return False, "MCP service is not enabled"
        
        try:
            async with self.mcp_client as client:
                return await client.complete_oauth_flow(authorization_code, redirect_uri, token_url)
        except Exception as e:
            logger.error(f"Failed to complete OAuth authentication: {e}")
            return False, str(e)
    
    async def list_available_tools(self, cursor: Optional[str] = None) -> Tuple[bool, Optional[List[Dict[str, Any]]], Optional[str], Optional[str]]:
        """
        取得 MCP 伺服器可用工具列表 (支援分頁)
        
        Args:
            cursor: 分頁游標
        
        Returns:
            Tuple[bool, Optional[List], Optional[str], Optional[str]]: (成功, 工具列表, 下一頁游標, 錯誤訊息)
        """
        if not self.is_enabled:
            return False, None, None, "MCP service is not enabled"
        
        try:
            async with self.mcp_client as client:
                return await client.list_tools(cursor)
        except Exception as e:
            return False, None, None, str(e)
    
    def get_configured_functions(self) -> List[Dict[str, Any]]:
        """取得已設定的函數列表"""
        if not self.is_enabled:
            return []
        
        try:
            config = self.config_manager.load_mcp_config(self.config_name)
            return [func for func in config['functions'] if func.get('enabled', True)]
        except Exception as e:
            logger.error(f"Error getting configured functions: {e}")
            return []
    
    def reload_config(self) -> bool:
        """重新載入 MCP 設定"""
        try:
            self.config_manager.reload_config(self.config_name)
            self._init_mcp_service()
            logger.info("MCP service config reloaded")
            return True
        except Exception as e:
            logger.error(f"Failed to reload MCP config: {e}")
            return False
    
    def get_service_info(self) -> Dict[str, Any]:
        """取得 MCP 服務資訊"""
        info = {
            "enabled": self.is_enabled,
            "config_dir": self.config_dir,
            "config_name": self.config_name,
            "available_configs": self.config_manager.list_available_configs(),
            "configured_functions": len(self.get_configured_functions()) if self.is_enabled else 0
        }
        
        if self.is_enabled and self.mcp_client:
            info.update({
                "server_url": self.mcp_client.base_url,
                "timeout": self.mcp_client.timeout,
                "auth_configured": bool(self.mcp_client.auth_config),
                "capabilities": list(self.mcp_client.capabilities.keys()),
                "has_access_token": bool(self.mcp_client.access_token)
            })
        
        return info


# 全域 MCP 服務實例
_mcp_service_instance = None


def get_mcp_service(config_dir: str = "config/mcp", config_name: str = None) -> MCPService:
    """
    取得 MCP 服務實例（單例模式）
    
    Args:
        config_dir: 設定檔目錄
        config_name: 設定檔名稱
        
    Returns:
        MCPService: MCP 服務實例
    """
    global _mcp_service_instance
    
    if _mcp_service_instance is None:
        _mcp_service_instance = MCPService(config_dir, config_name)
    
    return _mcp_service_instance


def reload_mcp_service() -> bool:
    """重新載入全域 MCP 服務"""
    global _mcp_service_instance
    
    if _mcp_service_instance:
        return _mcp_service_instance.reload_config()
    
    return False