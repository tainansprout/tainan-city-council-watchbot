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
    
    async def handle_function_call(self, function_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        處理 function call 並回傳結果
        
        Args:
            function_name: 函數名稱
            arguments: 函數參數
            
        Returns:
            Dict[str, Any]: 處理結果
        """
        if not self.is_enabled:
            return self._format_error_response("MCP service is not enabled")
        
        try:
            # 驗證函數和參數
            is_valid, error_msg = self.config_manager.validate_function_arguments(
                function_name, arguments, self.config_name
            )
            
            if not is_valid:
                logger.warning(f"Function validation failed: {error_msg}")
                return self._format_error_response(f"Parameter validation failed: {error_msg}")
            
            # 取得函數設定
            func_config = self.config_manager.get_function_by_name(function_name, self.config_name)
            if not func_config:
                return self._format_error_response(f"Unknown function: {function_name}")
            
            mcp_tool_name = func_config['mcp_tool']
            
            # 執行 MCP 工具呼叫
            logger.info(f"Executing MCP function: {function_name} -> {mcp_tool_name}")
            
            async with self.mcp_client as client:
                result = await client.call_tool(mcp_tool_name, arguments)
            
            if result.get('success', True):
                logger.info(f"MCP function {function_name} completed successfully")
                return {
                    "success": True,
                    "data": result.get('data'),
                    "content_type": result.get('content_type', 'text'),
                    "metadata": {
                        "function_name": function_name,
                        "mcp_tool": mcp_tool_name,
                        "execution_metadata": result.get('metadata', {})
                    }
                }
            else:
                error_msg = result.get('error', 'Unknown MCP error')
                logger.error(f"MCP function {function_name} failed: {error_msg}")
                return self._format_error_response(error_msg)
                
        except (MCPClientError, MCPServerError) as e:
            logger.error(f"MCP communication error for {function_name}: {e}")
            return self._format_error_response(str(e))
        except Exception as e:
            logger.error(f"Unexpected error in MCP function {function_name}: {e}")
            return self._format_error_response(f"Function execution error: {str(e)}")
    
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
            
            if "connection" in error_lower or "network" in error_lower:
                return error_messages.get("connection_error", "連線錯誤，請稍後再試")
            elif "timeout" in error_lower:
                return error_messages.get("timeout_error", "請求超時，請稍後再試")
            elif "no results" in error_lower or "empty" in error_lower:
                return error_messages.get("no_results", "查無相關結果")
            else:
                return "處理請求時發生錯誤，請稍後再試"
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
    
    async def list_available_tools(self) -> Tuple[bool, Optional[List[Dict[str, Any]]], Optional[str]]:
        """取得 MCP 伺服器可用工具列表"""
        if not self.is_enabled:
            return False, None, "MCP service is not enabled"
        
        try:
            async with self.mcp_client as client:
                return await client.list_tools()
        except Exception as e:
            return False, None, str(e)
    
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
        return {
            "enabled": self.is_enabled,
            "config_dir": self.config_dir,
            "config_name": self.config_name,
            "available_configs": self.config_manager.list_available_configs(),
            "configured_functions": len(self.get_configured_functions()) if self.is_enabled else 0
        }


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