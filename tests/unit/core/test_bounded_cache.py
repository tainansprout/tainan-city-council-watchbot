"""
測試有界快取模組的單元測試
"""
import pytest
import time
import threading
from unittest.mock import patch

from src.core.bounded_cache import BoundedCache, ConversationCache, FileCache


class TestBoundedCache:
    """測試 BoundedCache 的核心功能"""

    def test_set_and_get(self):
        cache = BoundedCache(max_size=3)
        cache.set('a', 1)
        cache.set('b', 2)
        assert cache.get('a') == 1
        assert cache.get('b') == 2
        assert cache.get('c') is None

    def test_lru_eviction(self):
        cache = BoundedCache(max_size=2)
        cache.set('a', 1)
        cache.set('b', 2)
        cache.set('c', 3)  # 'a' 應該被淘汰
        assert cache.get('a') is None
        assert cache.get('b') == 2
        assert cache.get('c') == 3

    def test_lru_update_on_get(self):
        cache = BoundedCache(max_size=2)
        cache.set('a', 1)
        cache.set('b', 2)
        cache.get('a')  # 'a' 變成最近使用的
        cache.set('c', 3)  # 'b' 應該被淘汰
        assert cache.get('b') is None
        assert cache.get('a') == 1

    def test_ttl_expiration(self):
        cache = BoundedCache(max_size=3, ttl=0.1)
        cache.set('a', 1)
        time.sleep(0.2)
        assert cache.get('a') is None

    def test_cleanup_expired(self):
        cache = BoundedCache(max_size=3, ttl=0.1)
        cache.set('a', 1)
        cache.set('b', 2)
        time.sleep(0.2)
        cache.set('c', 3)
        assert cache.cleanup_expired() == 2
        assert cache.size() == 1
        assert cache.get('c') == 3

    def test_clear(self):
        cache = BoundedCache(max_size=3)
        cache.set('a', 1)
        cache.clear()
        assert cache.size() == 0

    def test_stats(self):
        cache = BoundedCache(max_size=2)
        cache.set('a', 1)
        cache.get('a')  # hit
        cache.get('b')  # miss
        cache.set('b', 2)
        cache.set('c', 3)  # evict
        stats = cache.stats()
        assert stats['size'] == 2
        assert stats['hit_count'] == 1
        assert stats['miss_count'] == 1
        assert stats['eviction_count'] == 1
        assert stats['hit_rate'] == "50.0%"

    def test_thread_safety(self):
        cache = BoundedCache(max_size=100)
        num_threads = 10
        items_per_thread = 100

        def worker(thread_id):
            for i in range(items_per_thread):
                key = f"key-{thread_id}-{i}"
                cache.set(key, i)
                cache.get(key)

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert cache.size() == 100


class TestSpecializedCaches:
    """測試特化的快取類別"""

    def test_conversation_cache_initialization(self):
        cache = ConversationCache(max_conversations=500, conversation_ttl=1800)
        assert cache.max_size == 500
        assert cache.ttl == 1800

    def test_file_cache_initialization(self):
        cache = FileCache(max_files=100, file_ttl=600)
        assert cache.max_size == 100
        assert cache.ttl == 600
