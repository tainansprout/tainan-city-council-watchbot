"""
平台工廠 - 使用 Factory Pattern 和 Registry Pattern
"""
from ..core.logger import get_logger
from typing import Dict, Any, Optional, Type, List, Tuple
from .base import PlatformType, PlatformHandlerInterface, BasePlatformHandler
from .line_handler import LineHandler

logger = get_logger(__name__)


class PlatformRegistry:
    """
    平台註冊表 - 使用 Registry Pattern
    
    管理所有可用的平台處理器類別
    """
    
    def __init__(self):
        self._handlers: Dict[PlatformType, Type[BasePlatformHandler]] = {}
        self._register_built_in_handlers()
    
    def _register_built_in_handlers(self):
        """註冊內建的平台處理器"""
        self.register(PlatformType.LINE, LineHandler)
        logger.info("Built-in platform handlers registered")
    
    def register(self, platform_type: PlatformType, handler_class: Type[BasePlatformHandler]):
        """註冊平台處理器類別"""
        if not issubclass(handler_class, BasePlatformHandler):
            raise ValueError(f"Handler class must inherit from BasePlatformHandler")
        
        self._handlers[platform_type] = handler_class
        logger.info(f"Registered handler for platform: {platform_type.value}")
    
    def get_handler_class(self, platform_type: PlatformType) -> Optional[Type[BasePlatformHandler]]:
        """取得平台處理器類別"""
        return self._handlers.get(platform_type)
    
    def get_available_platforms(self) -> List[PlatformType]:
        """取得所有已註冊的平台類型"""
        return list(self._handlers.keys())
    
    def is_platform_supported(self, platform_type: PlatformType) -> bool:
        """檢查平台是否支援"""
        return platform_type in self._handlers


class PlatformFactory:
    """
    平台工廠 - 使用 Factory Pattern
    
    負責創建和配置平台處理器實例
    """
    
    def __init__(self, registry: PlatformRegistry = None):
        self.registry = registry or PlatformRegistry()
    
    def create_handler(self, platform_type: PlatformType, config: Dict[str, Any]) -> Optional[PlatformHandlerInterface]:
        """
        創建平台處理器實例
        
        Args:
            platform_type: 平台類型
            config: 完整的配置字典
            
        Returns:
            PlatformHandlerInterface: 平台處理器實例，如果創建失敗則返回 None
        """
        try:
            logger.debug(f"[FACTORY] Creating handler for platform: {platform_type.value}")
            
            # 檢查平台是否支援
            if not self.registry.is_platform_supported(platform_type):
                logger.error(f"[FACTORY] Unsupported platform: {platform_type.value}")
                return None
            
            # 取得處理器類別
            handler_class = self.registry.get_handler_class(platform_type)
            if not handler_class:
                logger.error(f"[FACTORY] No handler class found for platform: {platform_type.value}")
                return None
            
            logger.debug(f"[FACTORY] Found handler class: {handler_class.__name__}")
            
            # 檢查配置中是否有平台配置
            platform_config = config.get('platforms', {}).get(platform_type.value, {})
            logger.debug(f"[FACTORY] Platform config for {platform_type.value}: {platform_config}")
            
            # 創建處理器實例
            logger.debug(f"[FACTORY] Creating handler instance")
            handler = handler_class(config)
            
            logger.debug(f"[FACTORY] Handler instance created, validating config")
            
            # 驗證設定和啟用狀態
            is_valid = handler.validate_config()
            logger.debug(f"[FACTORY] Config validation result: {is_valid}")
            
            if not is_valid:
                logger.error(f"[FACTORY] Invalid config for platform: {platform_type.value}")
                return None
            
            is_enabled = handler.is_enabled()
            logger.debug(f"[FACTORY] Platform enabled status: {is_enabled}")
            
            if not is_enabled:
                logger.debug(f"[FACTORY] Platform {platform_type.value} is disabled")
                return None
            
            logger.info(f"[FACTORY] Successfully created handler for platform: {platform_type.value}")
            return handler
            
        except Exception as e:
            logger.error(f"[FACTORY] Error creating handler for platform {platform_type.value}: {type(e).__name__}: {e}")
            logger.error(f"[FACTORY] Exception traceback:", exc_info=True)
            return None
    
    def create_all_handlers(self, config: Dict[str, Any]) -> Dict[PlatformType, PlatformHandlerInterface]:
        """
        創建所有啟用的平台處理器
        
        Args:
            config: 完整的配置字典
            
        Returns:
            Dict[PlatformType, PlatformHandlerInterface]: 平台類型到處理器的映射
        """
        handlers = {}
        available_platforms = self.registry.get_available_platforms()
        
        for platform_type in available_platforms:
            handler = self.create_handler(platform_type, config)
            if handler:
                handlers[platform_type] = handler
        
        logger.debug(f"Created {len(handlers)} platform handlers: {[p.value for p in handlers.keys()]}")
        return handlers
    
    def create_enabled_handlers(self, config: Dict[str, Any]) -> Dict[PlatformType, PlatformHandlerInterface]:
        """
        只創建啟用的平台處理器
        
        Args:
            config: 完整的配置字典
            
        Returns:
            Dict[PlatformType, PlatformHandlerInterface]: 啟用的平台處理器
        """
        handlers = {}
        platforms_config = config.get('platforms', {})
        
        for platform_name, platform_config in platforms_config.items():
            if not platform_config.get('enabled', False):
                continue
            
            try:
                platform_type = PlatformType(platform_name)
                handler = self.create_handler(platform_type, config)
                if handler:
                    handlers[platform_type] = handler
            except ValueError:
                logger.warning(f"Unknown platform in config: {platform_name}")
                continue
        
        logger.debug(f"Created {len(handlers)} enabled platform handlers")
        return handlers
    
    def get_platform_requirements(self, platform_type: PlatformType) -> Dict[str, str]:
        """
        取得平台的必要設定需求
        
        Args:
            platform_type: 平台類型
            
        Returns:
            Dict[str, str]: 設定欄位名稱到說明的映射
        """
        handler_class = self.registry.get_handler_class(platform_type)
        if not handler_class:
            return {}
        
        # 創建臨時實例取得需求 (使用最小化配置避免驗證失敗)
        try:
            # 創建一個最小化的配置，避免觸發驗證錯誤
            temp_config = {
                'platforms': {
                    platform_type.value: {
                        'enabled': False  # 設為 False 避免觸發驗證
                    }
                }
            }
            temp_handler = handler_class(temp_config)
            return {
                field: f"Required configuration for {platform_type.value}"
                for field in temp_handler.get_required_config_fields()
            }
        except Exception as e:
            logger.error(f"Error getting requirements for {platform_type.value}: {e}")
            return {}


class PlatformConfigValidator:
    """平台設定驗證器"""
    
    def __init__(self, factory: PlatformFactory):
        self.factory = factory
    
    def validate_platform_config(self, platform_type: PlatformType, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        驗證單一平台設定
        
        Args:
            platform_type: 平台類型
            config: 平台設定
            
        Returns:
            Tuple[bool, List[str]]: (是否有效, 錯誤訊息列表)
        """
        errors = []
        
        # 檢查平台是否支援
        if not self.factory.registry.is_platform_supported(platform_type):
            errors.append(f"Platform {platform_type.value} is not supported")
            return False, errors
        
        # 取得必要欄位
        requirements = self.factory.get_platform_requirements(platform_type)
        platform_config = config.get('platforms', {}).get(platform_type.value, {})
        
        # 檢查必要欄位
        for field in requirements.keys():
            if not platform_config.get(field):
                errors.append(f"Missing required field '{field}' for platform {platform_type.value}")
        
        return len(errors) == 0, errors
    
    def validate_all_platforms(self, config: Dict[str, Any]) -> Tuple[bool, Dict[str, List[str]]]:
        """
        驗證所有平台設定
        
        Args:
            config: 完整配置字典
            
        Returns:
            Tuple[bool, Dict[str, List[str]]]: (是否全部有效, 平台錯誤映射)
        """
        all_valid = True
        platform_errors = {}
        
        platforms_config = config.get('platforms', {})
        
        for platform_name in platforms_config.keys():
            try:
                platform_type = PlatformType(platform_name)
                is_valid, errors = self.validate_platform_config(platform_type, config)
                
                if not is_valid:
                    all_valid = False
                    platform_errors[platform_name] = errors
                    
            except ValueError:
                all_valid = False
                platform_errors[platform_name] = [f"Unknown platform: {platform_name}"]
        
        return all_valid, platform_errors


# 全域實例
_platform_registry = PlatformRegistry()
_platform_factory = PlatformFactory(_platform_registry)
_config_validator = PlatformConfigValidator(_platform_factory)


def get_platform_factory() -> PlatformFactory:
    """取得全域平台工廠實例"""
    return _platform_factory


def get_platform_registry() -> PlatformRegistry:
    """取得全域平台註冊表實例"""
    return _platform_registry


def get_config_validator() -> PlatformConfigValidator:
    """取得全域設定驗證器實例"""
    return _config_validator


def register_platform_handler(platform_type: PlatformType, handler_class: Type[BasePlatformHandler]):
    """註冊自定義平台處理器"""
    _platform_registry.register(platform_type, handler_class)