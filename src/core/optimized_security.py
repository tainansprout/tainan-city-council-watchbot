"""
優化的安全模組 - 高效能的輸入驗證和安全檢查
包含預編譯正則表達式和優化的速率限制器
"""

import re
import html
import time
import threading
from collections import defaultdict
from typing import Dict, Any, Optional, List, Pattern, Tuple
from .logger import get_logger

logger = get_logger(__name__)


class OptimizedInputValidator:
    """優化的輸入驗證器 - 使用預編譯正則表達式"""
    
    # 🔥 關鍵優化：預編譯所有正則表達式
    _COMPILED_PATTERNS: List[Pattern] = [
        re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL),
        re.compile(r'javascript:', re.IGNORECASE),
        re.compile(r'on\w+\s*=', re.IGNORECASE),
        re.compile(r'<iframe[^>]*>.*?</iframe>', re.IGNORECASE | re.DOTALL),
        re.compile(r'<object[^>]*>.*?</object>', re.IGNORECASE | re.DOTALL),
        re.compile(r'<embed[^>]*>', re.IGNORECASE),
        re.compile(r'<link[^>]*>', re.IGNORECASE),
        re.compile(r'<meta[^>]*>', re.IGNORECASE),
        re.compile(r'<style[^>]*>.*?</style>', re.IGNORECASE | re.DOTALL),
        re.compile(r'expression\s*\(', re.IGNORECASE),
        re.compile(r'@import', re.IGNORECASE),
        re.compile(r'vbscript:', re.IGNORECASE),
        re.compile(r'<!\[CDATA\[.*?\]\]>', re.DOTALL),
        re.compile(r'eval\s*\(', re.IGNORECASE),
        re.compile(r'exec\s*\(', re.IGNORECASE),
        re.compile(r'import\s+', re.IGNORECASE),
        re.compile(r'__\w+__'),  # Python 魔法方法
        re.compile(r'\.\./', re.IGNORECASE),  # 路徑遍歷
    ]
    
    # 🔥 效能優化：用戶 ID 格式驗證預編譯
    _USER_ID_PATTERN = re.compile(r'^U[0-9a-f]{32}$')
    
    # 🔥 快取機制：常見輸入的清理結果
    _sanitize_cache: Dict[str, str] = {}
    _cache_lock = threading.Lock()
    _max_cache_size = 1000
    
    @classmethod
    def sanitize_text_optimized(cls, text: str, max_length: int = 4000) -> str:
        """
        優化的文本清理 - 使用預編譯正則表達式
        
        Args:
            text: 要清理的文本
            max_length: 最大長度限制
            
        Returns:
            清理後的文本
        """
        if not text or not isinstance(text, str):
            return ""
        
        # 🔥 快取檢查（對於常見的短文本）
        cache_key = None
        if len(text) < 200:  # 只快取短文本
            cache_key = f"{text}:{max_length}"
            with cls._cache_lock:
                if cache_key in cls._sanitize_cache:
                    return cls._sanitize_cache[cache_key]
        
        # 長度限制
        if len(text) > max_length:
            text = text[:max_length]
        
        # HTML 編碼
        text = html.escape(text)
        
        # 🔥 效能提升：使用預編譯的正則，避免重複編譯
        for compiled_pattern in cls._COMPILED_PATTERNS:
            text = compiled_pattern.sub('', text)
        
        # 移除控制字符（但保留換行和製表符）
        text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t')
        
        sanitized = text.strip()
        
        # 🔥 結果快取（控制快取大小）
        if cache_key is not None:  # 只有當我們有有效的快取鍵時才快取
            with cls._cache_lock:
                if len(cls._sanitize_cache) >= cls._max_cache_size:
                    # 簡單的 LRU：清除一半最舊的項目
                    items = list(cls._sanitize_cache.items())
                    cls._sanitize_cache = dict(items[len(items)//2:])
                cls._sanitize_cache[cache_key] = sanitized
        
        return sanitized
    
    @classmethod
    def sanitize_text_batch(cls, texts: List[str], max_length: int = 4000) -> List[str]:
        """
        批次處理多個文本 - 更高效
        
        Args:
            texts: 文本列表
            max_length: 最大長度限制
            
        Returns:
            清理後的文本列表
        """
        return [cls.sanitize_text_optimized(text, max_length) for text in texts]
    
    @classmethod
    def validate_user_id_fast(cls, user_id: str) -> bool:
        """
        快速驗證用戶 ID 格式
        
        Args:
            user_id: 用戶 ID
            
        Returns:
            是否有效
        """
        if not isinstance(user_id, str):
            return False
        
        # 使用預編譯的正則表達式
        return bool(cls._USER_ID_PATTERN.match(user_id))
    
    @classmethod
    def validate_message_content_optimized(cls, content: str) -> Dict[str, Any]:
        """
        優化的訊息內容驗證
        
        Args:
            content: 訊息內容
            
        Returns:
            驗證結果字典
        """
        result = {
            'is_valid': True,
            'errors': [],
            'cleaned_content': content
        }
        
        if not isinstance(content, str):
            result['is_valid'] = False
            result['errors'].append('訊息必須是字符串格式')
            return result
        
        # 長度檢查
        if len(content) == 0:
            result['is_valid'] = False
            result['errors'].append('訊息不能為空')
        elif len(content) > 5000:
            result['is_valid'] = False
            result['errors'].append('訊息長度不能超過 5000 字符')
        
        # 清理內容
        result['cleaned_content'] = cls.sanitize_text_optimized(content)
        
        # 🔥 優化：使用預編譯正則檢查危險內容
        original_content = content.lower()
        for pattern in cls._COMPILED_PATTERNS:
            if pattern.search(original_content):
                result['is_valid'] = False
                result['errors'].append('訊息包含不安全的內容')
                break  # 找到一個就停止
        
        return result
    
    @classmethod
    def is_safe_content(cls, content: str) -> bool:
        """
        快速檢查內容是否安全
        
        Args:
            content: 要檢查的內容
            
        Returns:
            是否安全
        """
        if not content or not isinstance(content, str):
            return True
        
        # 使用預編譯正則快速檢查
        content_lower = content.lower()
        for pattern in cls._COMPILED_PATTERNS:
            if pattern.search(content_lower):
                return False
        
        return True
    
    @classmethod
    def get_cache_stats(cls) -> Dict[str, int]:
        """取得快取統計資訊"""
        with cls._cache_lock:
            return {
                'cache_size': len(cls._sanitize_cache),
                'max_cache_size': cls._max_cache_size,
                'cache_usage_percent': int((len(cls._sanitize_cache) / cls._max_cache_size) * 100)
            }
    
    @classmethod
    def clear_cache(cls):
        """清空快取"""
        with cls._cache_lock:
            cls._sanitize_cache.clear()


class OptimizedRateLimiter:
    """O(1) 複雜度的 Rate Limiter"""
    
    def __init__(self, cleanup_interval: int = 300):  # 5分鐘清理一次
        # 🔥 使用滑動窗口計數器取代時間戳列表
        self.windows: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
        self.last_cleanup = time.time()
        self.cleanup_interval = cleanup_interval
        self.lock = threading.RLock()
        
        # 統計資訊
        self.total_requests = 0
        self.blocked_requests = 0
    
    def is_allowed(self, client_id: str, requests_per_minute: int = 60, window_minutes: int = 1) -> bool:
        """
        O(1) 複雜度的速率檢查
        
        Args:
            client_id: 客戶端 ID
            requests_per_minute: 每分鐘請求限制
            window_minutes: 時間窗口（分鐘）
            
        Returns:
            是否允許請求
        """
        current_time = int(time.time())
        current_window = current_time // 60  # 以分鐘為單位的窗口
        
        with self.lock:
            self.total_requests += 1
            
            # 🔥 定期清理過期窗口（非阻塞）
            if current_time - self.last_cleanup > self.cleanup_interval:
                self._schedule_cleanup(current_window)
                self.last_cleanup = current_time
            
            # 🔥 O(1) 操作：計算當前窗口的請求數
            client_windows = self.windows[client_id]
            
            # 計算滑動窗口內的總請求數
            total_requests = 0
            for window_time in range(current_window - window_minutes + 1, current_window + 1):
                total_requests += client_windows.get(window_time, 0)
            
            # 檢查是否超過限制
            if total_requests >= requests_per_minute:
                self.blocked_requests += 1
                logger.debug(f"Rate limit exceeded for client {client_id}: {total_requests}/{requests_per_minute}")
                return False
            
            # 🔥 O(1) 操作：增加當前窗口計數
            client_windows[current_window] += 1
            return True
    
    def _schedule_cleanup(self, current_window: int):
        """非阻塞的清理排程"""
        def cleanup_worker():
            """背景清理工作"""
            cutoff_window = current_window - 5  # 保留最近5分鐘的資料
            
            with self.lock:
                clients_to_remove = []
                
                for client_id, client_windows in self.windows.items():
                    # 移除過期窗口
                    expired_windows = [w for w in client_windows.keys() if w < cutoff_window]
                    for window in expired_windows:
                        del client_windows[window]
                    
                    # 如果客戶端沒有活動窗口，標記為移除
                    if not client_windows:
                        clients_to_remove.append(client_id)
                
                # 移除無活動的客戶端
                for client_id in clients_to_remove:
                    del self.windows[client_id]
                
                logger.debug(f"RateLimiter cleanup: removed {len(clients_to_remove)} inactive clients")
        
        # 使用背景執行緒清理，避免阻塞主請求
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
    
    def get_stats(self) -> Dict[str, Any]:
        """取得統計資訊"""
        with self.lock:
            active_clients = len(self.windows)
            success_rate = (self.total_requests - self.blocked_requests) / max(self.total_requests, 1)
            
            return {
                'total_requests': self.total_requests,
                'blocked_requests': self.blocked_requests,
                'active_clients': active_clients,
                'success_rate_percent': round(success_rate * 100, 2),
                'current_windows': sum(len(windows) for windows in self.windows.values())
            }
    
    def get_client_status(self, client_id: str) -> Dict[str, int]:
        """取得特定客戶端狀態"""
        current_window = int(time.time()) // 60
        
        with self.lock:
            client_windows = self.windows.get(client_id, {})
            recent_requests = sum(
                count for window, count in client_windows.items()
                if current_window - window < 5  # 最近5分鐘
            )
            
            return {
                'recent_requests_5min': recent_requests,
                'active_windows': len(client_windows),
                'last_request_window': max(client_windows.keys()) if client_windows else 0
            }


class SecurityMiddleware:
    """安全中間件 - 整合優化的組件"""
    
    def __init__(self):
        self.rate_limiter = OptimizedRateLimiter()
        self.input_validator = OptimizedInputValidator()
        
        # 不同類型用戶的不同限制
        self.rate_limits = {
            'normal': 60,      # 一般用戶：60次/分鐘
            'premium': 120,    # 高級用戶：120次/分鐘
            'internal': 300,   # 內部系統：300次/分鐘
        }
    
    def check_request(self, client_id: str, user_type: str = 'normal', content: str = None) -> Tuple[bool, str]:
        """
        統一的請求檢查
        
        Args:
            client_id: 客戶端 ID
            user_type: 用戶類型
            content: 請求內容
            
        Returns:
            (是否允許, 錯誤訊息)
        """
        # 1. 速率限制檢查
        rate_limit = self.rate_limits.get(user_type, 60)
        if not self.rate_limiter.is_allowed(client_id, rate_limit):
            return False, f"速率限制：每分鐘最多 {rate_limit} 次請求"
        
        # 2. 內容安全檢查
        if content:
            if not self.input_validator.is_safe_content(content):
                return False, "請求內容包含不安全元素"
        
        return True, "OK"
    
    def get_security_stats(self) -> Dict[str, Any]:
        """取得安全統計資訊"""
        return {
            'rate_limiter': self.rate_limiter.get_stats(),
            'input_validator': self.input_validator.get_cache_stats()
        }


# 向後兼容包裝器
class InputValidator:
    """向後兼容的 InputValidator 包裝器"""
    
    @staticmethod
    def sanitize_text(text: str, max_length: int = 4000) -> str:
        return OptimizedInputValidator.sanitize_text_optimized(text, max_length)
    
    @staticmethod
    def validate_user_id(user_id: str) -> bool:
        return OptimizedInputValidator.validate_user_id_fast(user_id)
    
    @staticmethod
    def validate_message_content(content: str) -> Dict[str, Any]:
        return OptimizedInputValidator.validate_message_content_optimized(content)


# 全域安全中間件實例
_security_middleware = None
_security_lock = threading.Lock()

def get_security_middleware() -> SecurityMiddleware:
    """取得全域安全中間件實例"""
    global _security_middleware
    if _security_middleware is None:
        with _security_lock:
            if _security_middleware is None:
                _security_middleware = SecurityMiddleware()
    return _security_middleware