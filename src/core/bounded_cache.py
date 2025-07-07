"""
有界快取實現 - 支援 LRU 淘汰策略
針對 RAG 應用優化，支援大容量快取
"""
from collections import OrderedDict
import threading
import time
from typing import Any, Optional, Dict
import logging

logger = logging.getLogger(__name__)


class BoundedCache:
    """
    線程安全的有界快取，使用 LRU 淘汰策略
    針對 RAG 應用優化，支援較大的快取容量
    """
    
    def __init__(self, max_size: int = 1000, ttl: Optional[int] = None):
        """
        初始化有界快取
        
        Args:
            max_size: 最大快取項目數量，預設 1000（針對 RAG 優化）
            ttl: 快取項目存活時間（秒），None 表示不過期
        """
        self.cache: OrderedDict = OrderedDict()
        self.max_size = max_size
        self.ttl = ttl
        self.access_times: Dict[Any, float] = {} if ttl is not None else None
        self.lock = threading.RLock()
        
        # 統計資訊
        self.hit_count = 0
        self.miss_count = 0
        self.eviction_count = 0
        
        logger.info(f"BoundedCache initialized: max_size={max_size}, ttl={ttl}")
    
    def get(self, key: Any, default: Any = None) -> Any:
        """取得快取值，支援 LRU 更新"""
        with self.lock:
            # 檢查 TTL 過期
            if self.ttl is not None and key in self.cache:
                if time.time() - self.access_times.get(key, 0) > self.ttl:
                    self._remove_expired(key)
                    self.miss_count += 1
                    return default
            
            if key in self.cache:
                # LRU: 移動到末尾（最近使用）
                self.cache.move_to_end(key)
                if self.access_times:
                    self.access_times[key] = time.time()
                self.hit_count += 1
                return self.cache[key]
            
            self.miss_count += 1
            return default
    
    def set(self, key: Any, value: Any) -> None:
        """設置快取值，支援自動淘汰"""
        with self.lock:
            current_time = time.time()
            
            if key in self.cache:
                # 更新現有項目
                self.cache.move_to_end(key)
                self.cache[key] = value
                if self.ttl is not None:
                    if self.access_times is None:
                        self.access_times = {}
                    self.access_times[key] = current_time
            else:
                # 新增項目，檢查是否需要淘汰
                if len(self.cache) >= self.max_size:
                    self._evict_oldest()
                
                self.cache[key] = value
                if self.ttl is not None:
                    if self.access_times is None:
                        self.access_times = {}
                    self.access_times[key] = current_time
    
    def __setitem__(self, key: Any, value: Any) -> None:
        """支援 cache[key] = value 語法"""
        self.set(key, value)
    
    def __getitem__(self, key: Any) -> Any:
        """支援 cache[key] 語法"""
        result = self.get(key)
        if result is None and key not in self.cache:
            raise KeyError(key)
        return result
    
    def __contains__(self, key: Any) -> bool:
        """支援 key in cache 語法"""
        with self.lock:
            return key in self.cache
    
    def _evict_oldest(self) -> None:
        """淘汰最舊的項目"""
        if self.cache:
            oldest_key = next(iter(self.cache))
            self.cache.pop(oldest_key)
            if self.access_times and oldest_key in self.access_times:
                self.access_times.pop(oldest_key)
            self.eviction_count += 1
            logger.debug(f"Evicted oldest cache entry: {oldest_key}")
    
    def _remove_expired(self, key: Any) -> None:
        """移除過期項目"""
        if key in self.cache:
            self.cache.pop(key)
        if self.access_times and key in self.access_times:
            self.access_times.pop(key)
        logger.debug(f"Removed expired cache entry: {key}")
    
    def cleanup_expired(self) -> int:
        """清理所有過期項目，返回清理數量"""
        if not self.ttl or not self.access_times:
            return 0
        
        with self.lock:
            current_time = time.time()
            expired_keys = []
            
            for key, access_time in self.access_times.items():
                if current_time - access_time > self.ttl:
                    expired_keys.append(key)
            
            for key in expired_keys:
                self._remove_expired(key)
            
            if expired_keys:
                logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
            
            return len(expired_keys)
    
    def clear(self) -> None:
        """清空所有快取"""
        with self.lock:
            self.cache.clear()
            if self.access_times:
                self.access_times.clear()
            logger.info("Cache cleared")
    
    def size(self) -> int:
        """取得當前快取大小"""
        return len(self.cache)
    
    def stats(self) -> Dict[str, Any]:
        """取得快取統計資訊"""
        with self.lock:
            total_requests = self.hit_count + self.miss_count
            hit_rate = (self.hit_count / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'size': len(self.cache),
                'max_size': self.max_size,
                'hit_count': self.hit_count,
                'miss_count': self.miss_count,
                'hit_rate': f"{hit_rate:.1f}%",
                'eviction_count': self.eviction_count,
                'ttl': self.ttl
            }
    
    def __len__(self) -> int:
        return len(self.cache)
    
    def __contains__(self, key: Any) -> bool:
        with self.lock:
            return key in self.cache
    
    def __delitem__(self, key: Any) -> None:
        """支援 del cache[key] 語法"""
        with self.lock:
            if key in self.cache:
                self.cache.pop(key)
                if self.access_times and key in self.access_times:
                    self.access_times.pop(key)
            else:
                raise KeyError(key)
    
    def values(self):
        """支援 cache.values() 語法"""
        with self.lock:
            return list(self.cache.values())
    
    def keys(self):
        """支援 cache.keys() 語法"""
        with self.lock:
            return list(self.cache.keys())
    
    def items(self):
        """支援 cache.items() 語法"""
        with self.lock:
            return list(self.cache.items())


class ConversationCache(BoundedCache):
    """
    專門針對對話快取優化的快取類別
    支援更大的容量以適應 RAG 應用的需求
    """
    
    def __init__(self, max_conversations: int = 2000, conversation_ttl: int = 7200):
        """
        初始化對話快取
        
        Args:
            max_conversations: 最大對話數量，預設 2000（適合 RAG 高頻使用）
            conversation_ttl: 對話存活時間，預設 2 小時
        """
        super().__init__(max_size=max_conversations, ttl=conversation_ttl)
        logger.info(f"ConversationCache initialized: max={max_conversations}, ttl={conversation_ttl}s")


class FileCache(BoundedCache):
    """
    專門針對檔案快取優化的快取類別
    """
    
    def __init__(self, max_files: int = 500, file_ttl: int = 3600):
        """
        初始化檔案快取
        
        Args:
            max_files: 最大檔案數量，預設 500
            file_ttl: 檔案存活時間，預設 1 小時
        """
        super().__init__(max_size=max_files, ttl=file_ttl)
        logger.info(f"FileCache initialized: max={max_files}, ttl={file_ttl}s")