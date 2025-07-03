"""
多平台支援模組
"""
from .base import (
    PlatformType,
    PlatformUser,
    PlatformMessage,
    PlatformResponse,
    PlatformHandlerInterface,
    BasePlatformHandler,
    PlatformManager,
    get_platform_manager
)

__all__ = [
    'PlatformType',
    'PlatformUser', 
    'PlatformMessage',
    'PlatformResponse',
    'PlatformHandlerInterface',
    'BasePlatformHandler',
    'PlatformManager',
    'get_platform_manager'
]