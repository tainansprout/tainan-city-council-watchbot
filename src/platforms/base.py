"""
多平台支援的抽象介面和基礎類別
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Union, List
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class PlatformType(Enum):
    """支援的平台類型"""
    LINE = "line"
    DISCORD = "discord"
    TELEGRAM = "telegram"
    WEB = "web"
    API = "api"


@dataclass
class PlatformUser:
    """平台用戶資訊的統一格式"""
    user_id: str
    platform: PlatformType
    display_name: Optional[str] = None
    username: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class PlatformMessage:
    """平台訊息的統一格式"""
    message_id: str
    user: PlatformUser
    content: str
    message_type: str = "text"  # text, audio, image, file, etc.
    raw_data: Optional[bytes] = None  # 原始二進位資料（如音訊、圖片）
    reply_token: Optional[str] = None  # 回覆 token（LINE 需要）
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class PlatformResponse:
    """平台回應的統一格式"""
    content: str
    response_type: str = "text"  # text, image, audio, file
    metadata: Optional[Dict[str, Any]] = None
    raw_response: Optional[Any] = None  # 平台特定的回應物件


class PlatformHandlerInterface(ABC):
    """平台處理器的抽象介面"""
    
    @abstractmethod
    def get_platform_type(self) -> PlatformType:
        """取得平台類型"""
        pass
    
    @abstractmethod
    def parse_message(self, raw_event: Any) -> Optional[PlatformMessage]:
        """
        解析平台原始事件為統一的 PlatformMessage 格式
        
        Args:
            raw_event: 平台原始事件物件
            
        Returns:
            PlatformMessage: 統一格式的訊息，解析失敗時返回 None
        """
        pass
    
    @abstractmethod
    def send_response(self, response: PlatformResponse, message: PlatformMessage) -> bool:
        """
        發送回應到平台
        
        Args:
            response: 統一格式的回應
            message: 原始訊息（用於取得回覆資訊）
            
        Returns:
            bool: 是否成功發送
        """
        pass
    
    @abstractmethod
    def validate_signature(self, request_data: bytes, signature: str) -> bool:
        """
        驗證請求簽名
        
        Args:
            request_data: 請求資料
            signature: 請求簽名
            
        Returns:
            bool: 簽名是否有效
        """
        pass
    
    @abstractmethod
    def handle_webhook(self, request_body: str, signature: str) -> List[PlatformMessage]:
        """
        處理 webhook 請求
        
        Args:
            request_body: 請求內容
            signature: 請求簽名
            
        Returns:
            List[PlatformMessage]: 解析出的訊息列表
        """
        pass


class BasePlatformHandler(PlatformHandlerInterface):
    """平台處理器的基礎實作"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.platform_config = config.get('platforms', {}).get(self.get_platform_type().value, {})
        logger.info(f"Initialized {self.get_platform_type().value} platform handler")
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """取得平台特定設定"""
        return self.platform_config.get(key, default)
    
    def is_enabled(self) -> bool:
        """檢查平台是否啟用"""
        return self.platform_config.get('enabled', False)
    
    def validate_config(self) -> bool:
        """驗證平台設定是否完整"""
        required_fields = self.get_required_config_fields()
        for field in required_fields:
            if not self.get_config(field):
                logger.error(f"{self.get_platform_type().value} platform missing required config: {field}")
                return False
        return True
    
    @abstractmethod
    def get_required_config_fields(self) -> List[str]:
        """取得必要的設定欄位"""
        pass


class PlatformManager:
    """平台管理器 - 管理所有已註冊的平台處理器"""
    
    def __init__(self):
        self._handlers: Dict[PlatformType, PlatformHandlerInterface] = {}
        logger.info("Platform manager initialized")
    
    def register_handler(self, handler: PlatformHandlerInterface):
        """註冊平台處理器"""
        platform_type = handler.get_platform_type()
        if not isinstance(handler, BasePlatformHandler) or not handler.validate_config():
            logger.error(f"Failed to register {platform_type.value} handler: invalid config")
            return False
        
        if not handler.is_enabled():
            logger.info(f"{platform_type.value} platform is disabled, skipping registration")
            return False
        
        self._handlers[platform_type] = handler
        logger.info(f"Registered {platform_type.value} platform handler")
        return True
    
    def get_handler(self, platform_type: PlatformType) -> Optional[PlatformHandlerInterface]:
        """取得指定平台的處理器"""
        return self._handlers.get(platform_type)
    
    def get_enabled_platforms(self) -> List[PlatformType]:
        """取得所有啟用的平台列表"""
        return list(self._handlers.keys())
    
    def handle_platform_webhook(self, platform_type: PlatformType, request_body: str, signature: str) -> List[PlatformMessage]:
        """處理指定平台的 webhook"""
        handler = self.get_handler(platform_type)
        if not handler:
            logger.error(f"No handler found for platform: {platform_type.value}")
            return []
        
        try:
            return handler.handle_webhook(request_body, signature)
        except Exception as e:
            logger.error(f"Error handling {platform_type.value} webhook: {e}")
            return []


# 全域平台管理器實例
platform_manager = PlatformManager()


def get_platform_manager() -> PlatformManager:
    """取得全域平台管理器"""
    return platform_manager