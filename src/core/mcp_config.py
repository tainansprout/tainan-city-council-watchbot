"""
MCP 設定載入和管理器

核心基礎設施：負責載入和管理 MCP 設定檔案
- 不依賴高層級組件，僅使用標準庫和 core 模組
- 提供統一的設定檔案載入接口
- 支援設定檔案驗證和熱重載
"""

import json
import os
from typing import Dict, List, Any, Optional, Tuple
from ..core.logger import get_logger

logger = get_logger(__name__)


class MCPConfigManager:
    """MCP 設定載入和管理器"""
    
    def __init__(self, config_dir: str = "config/mcp"):
        self.config_dir = config_dir
        self._config_cache = {}
        self._last_modified = {}
    
    def load_mcp_config(self, config_name: str = None) -> Dict[str, Any]:
        """
        載入 MCP 設定檔案
        
        Args:
            config_name: 設定檔案名稱，如果為 None 則嘗試載入可用的設定檔案
            
        Returns:
            Dict[str, Any]: 完整的 MCP 設定
            
        Raises:
            FileNotFoundError: 找不到設定檔案
            json.JSONDecodeError: JSON 格式錯誤
        """
        try:
            if config_name is None:
                config_name = self._find_available_config()
            
            config_path = os.path.join(self.config_dir, config_name)
            
            # 檢查檔案是否存在
            if not os.path.exists(config_path):
                raise FileNotFoundError(f"MCP config file not found: {config_path}")
            
            # 檢查是否需要重新載入
            if self._should_reload(config_path):
                logger.info(f"Loading MCP config from: {config_path}")
                
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # 驗證設定檔案
                self._validate_config(config)
                
                # 更新快取
                self._config_cache[config_name] = config
                self._last_modified[config_path] = os.path.getmtime(config_path)
                
                logger.info(f"Successfully loaded MCP config: {config_name}")
            
            return self._config_cache[config_name]
            
        except Exception as e:
            logger.error(f"Failed to load MCP config {config_name}: {e}")
            raise
    
    def _find_available_config(self) -> str:
        """尋找可用的設定檔案"""
        if not os.path.exists(self.config_dir):
            raise FileNotFoundError(f"MCP config directory not found: {self.config_dir}")
        
        # 優先順序：具體名稱的設定檔 > 預設設定檔
        potential_configs = []
        
        for filename in os.listdir(self.config_dir):
            if filename.endswith('.json') and not filename.endswith('.example'):
                potential_configs.append(filename)
        
        if not potential_configs:
            raise FileNotFoundError(f"No MCP config files found in {self.config_dir}")
        
        # 回傳第一個找到的設定檔案
        selected_config = potential_configs[0]
        logger.info(f"Auto-selected MCP config: {selected_config}")
        return selected_config
    
    def _should_reload(self, config_path: str) -> bool:
        """檢查是否需要重新載入設定檔案"""
        if config_path not in self._last_modified:
            return True
        
        current_mtime = os.path.getmtime(config_path)
        return current_mtime > self._last_modified[config_path]
    
    def _validate_config(self, config: Dict[str, Any]) -> None:
        """驗證 MCP 設定檔案格式"""
        required_sections = ['mcp_server', 'functions', 'tools']
        
        for section in required_sections:
            if section not in config:
                raise ValueError(f"Missing required section in MCP config: {section}")
        
        # 驗證 MCP server 設定
        mcp_server = config['mcp_server']
        if 'base_url' not in mcp_server:
            raise ValueError("Missing 'base_url' in mcp_server config")
        
        # 驗證 functions 設定
        functions = config['functions']
        if not isinstance(functions, list):
            raise ValueError("'functions' must be a list")
        
        for func in functions:
            if 'name' not in func or 'mcp_tool' not in func:
                raise ValueError("Each function must have 'name' and 'mcp_tool'")
        
        logger.debug("MCP config validation passed")
    
    def get_server_config(self, config_name: str = None) -> Dict[str, Any]:
        """取得 MCP 伺服器設定"""
        config = self.load_mcp_config(config_name)
        return config['mcp_server']
    
    def get_function_schemas_for_openai(self, config_name: str = None) -> List[Dict[str, Any]]:
        """取得 OpenAI function calling 格式的 schemas"""
        config = self.load_mcp_config(config_name)
        schemas = []
        
        for func in config['functions']:
            if func.get('enabled', True):
                schema = {
                    "type": "function",
                    "function": {
                        "name": func['name'],
                        "description": func['description'],
                        "parameters": func['parameters']
                    }
                }
                schemas.append(schema)
        
        logger.debug(f"Generated {len(schemas)} OpenAI function schemas")
        return schemas
    
    def get_function_schemas_for_anthropic(self, config_name: str = None) -> str:
        """取得 Anthropic system prompt 格式的 function schemas"""
        config = self.load_mcp_config(config_name)
        
        functions_desc = []
        for func in config['functions']:
            if func.get('enabled', True):
                func_desc = f"Function: {func['name']}\n"
                func_desc += f"Description: {func['description']}\n"
                func_desc += f"Parameters: {json.dumps(func['parameters'], ensure_ascii=False, indent=2)}\n"
                
                # 新增使用範例
                if 'usage_examples' in func:
                    func_desc += "Examples:\n"
                    for example in func['usage_examples']:
                        func_desc += f"- {example['description']}: {json.dumps(example['arguments'], ensure_ascii=False)}\n"
                
                functions_desc.append(func_desc)
        
        prompt = "Available tools:\n\n" + "\n".join(functions_desc)
        prompt += "\nTo use a tool, respond with a JSON object containing 'function_name' and 'arguments'."
        
        return prompt
    
    def get_tool_config(self, function_name: str, config_name: str = None) -> Optional[Dict[str, Any]]:
        """取得特定工具的設定"""
        config = self.load_mcp_config(config_name)
        return config['tools'].get(function_name)
    
    def get_function_by_name(self, function_name: str, config_name: str = None) -> Optional[Dict[str, Any]]:
        """根據函數名稱取得函數設定"""
        config = self.load_mcp_config(config_name)
        
        for func in config['functions']:
            if func['name'] == function_name:
                return func
        
        return None
    
    def validate_function_arguments(self, function_name: str, arguments: Dict[str, Any], config_name: str = None) -> Tuple[bool, Optional[str]]:
        """驗證函數參數"""
        try:
            func_config = self.get_function_by_name(function_name, config_name)
            if not func_config:
                return False, f"Unknown function: {function_name}"
            
            tool_config = self.get_tool_config(function_name, config_name)
            if not tool_config or 'validation' not in tool_config:
                return True, None  # 沒有驗證規則就通過
            
            validation = tool_config['validation']
            
            # 檢查必填欄位
            for required_field in validation.get('required_fields', []):
                if required_field not in arguments:
                    return False, f"Missing required field: {required_field}"
            
            # 檢查欄位限制
            field_limits = validation.get('field_limits', {})
            for field_name, limits in field_limits.items():
                if field_name in arguments:
                    value = arguments[field_name]
                    
                    # 檢查陣列長度
                    if isinstance(value, list):
                        if 'max_items' in limits and len(value) > limits['max_items']:
                            return False, f"Field {field_name} exceeds max items: {limits['max_items']}"
                    
                    # 檢查字串長度
                    if isinstance(value, str):
                        if 'max_length' in limits and len(value) > limits['max_length']:
                            return False, f"Field {field_name} exceeds max length: {limits['max_length']}"
                    
                    # 檢查數值範圍
                    if isinstance(value, int):
                        if 'min' in limits and value < limits['min']:
                            return False, f"Field {field_name} below minimum: {limits['min']}"
                        if 'max' in limits and value > limits['max']:
                            return False, f"Field {field_name} above maximum: {limits['max']}"
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error validating function arguments: {e}")
            return False, str(e)
    
    def get_error_messages(self, config_name: str = None) -> Dict[str, str]:
        """取得錯誤訊息模板"""
        config = self.load_mcp_config(config_name)
        error_handling = config.get('error_handling', {})
        return error_handling.get('fallback_messages', {})
    
    def get_default_params(self, config_name: str = None) -> Dict[str, Any]:
        """取得預設參數"""
        config = self.load_mcp_config(config_name)
        return config.get('default_search_params', {})
    
    def reload_config(self, config_name: str = None) -> None:
        """重新載入設定檔案"""
        if config_name is None:
            # 清除所有快取
            self._config_cache.clear()
            self._last_modified.clear()
            logger.info("Cleared all MCP config cache")
        else:
            # 清除特定設定檔案的快取
            if config_name in self._config_cache:
                del self._config_cache[config_name]
            
            config_path = os.path.join(self.config_dir, config_name)
            if config_path in self._last_modified:
                del self._last_modified[config_path]
            
            logger.info(f"Cleared MCP config cache for: {config_name}")
    
    def list_available_configs(self) -> List[str]:
        """列出可用的設定檔案"""
        if not os.path.exists(self.config_dir):
            return []
        
        configs = []
        for filename in os.listdir(self.config_dir):
            if filename.endswith('.json') and not filename.endswith('.example'):
                configs.append(filename)
        
        return sorted(configs)
    
    def is_mcp_enabled(self) -> bool:
        """檢查 MCP 是否可用"""
        try:
            # 檢查 config.yml 中的設定
            try:
                from .config import get_value
                config_enabled = get_value('features.enable_mcp', False) and get_value('mcp.enabled', False)
            except Exception as e:
                logger.warning(f"Unable to check config.yml MCP settings: {e}")
                config_enabled = True  # 如果無法讀取設定，預設允許
            
            if not config_enabled:
                return False
            
            # 檢查是否有合格的 JSON 設定檔案
            available_configs = self.list_available_configs()
            if len(available_configs) == 0:
                return False
                
            # 嘗試載入至少一個設定檔案以驗證格式
            for config_name in available_configs:
                try:
                    self.load_mcp_config(config_name)
                    return True  # 至少有一個有效的設定檔案
                except Exception as e:
                    logger.warning(f"Invalid MCP config file {config_name}: {e}")
                    continue
            
            return False
        except Exception as e:
            logger.warning(f"Error checking MCP availability: {e}")
            return False