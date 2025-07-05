"""
對話服務測試
測試 src/services/conversation.py 中的 ORMConversationManager
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from src.services.conversation import ORMConversationManager, get_conversation_manager


class TestORMConversationManager:
    """ORMConversationManager 測試"""
    
    @pytest.fixture
    def mock_session(self):
        """模擬資料庫 session"""
        session = Mock()
        return session
    
    @pytest.fixture
    def conversation_manager(self, mock_session):
        """創建對話管理器實例"""
        with patch('src.services.conversation.get_db_session') as mock_session_factory:
            mock_session_factory.return_value.__enter__.return_value = mock_session
            mock_session_factory.return_value.__exit__.return_value = None
            
            manager = ORMConversationManager()
            manager.session_factory = mock_session_factory
            return manager
    
    def test_conversation_manager_initialization(self, conversation_manager):
        """測試對話管理器初始化"""
        assert hasattr(conversation_manager, 'memory_cache')
        assert hasattr(conversation_manager, 'cache_ttl')
        assert conversation_manager.cache_ttl == 300  # 5分鐘
        assert isinstance(conversation_manager.memory_cache, dict)
    
    def test_add_message_success(self, conversation_manager, mock_session):
        """測試成功添加訊息"""
        result = conversation_manager.add_message(
            user_id="test_user",
            model_provider="anthropic",
            role="user",
            content="測試訊息",
            platform="line"
        )
        
        assert result is True
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
    
    def test_add_message_clears_cache(self, conversation_manager, mock_session):
        """測試添加訊息會清除快取"""
        # 預設快取
        cache_key = "test_user:line:anthropic"
        conversation_manager.memory_cache[cache_key] = {
            'conversations': [],
            'timestamp': datetime.now()
        }
        
        conversation_manager.add_message(
            user_id="test_user",
            model_provider="anthropic", 
            role="user",
            content="測試訊息",
            platform="line"
        )
        
        # 快取應該被清除
        assert cache_key not in conversation_manager.memory_cache
    
    def test_add_message_failure(self, conversation_manager, mock_session):
        """測試添加訊息失敗"""
        mock_session.add.side_effect = Exception("Database error")
        
        result = conversation_manager.add_message(
            user_id="test_user",
            model_provider="anthropic",
            role="user", 
            content="測試訊息"
        )
        
        assert result is False
    
    def test_get_recent_conversations_from_cache(self, conversation_manager, mock_session):
        """測試從快取取得對話"""
        # 設置快取
        cache_key = "test_user:line:anthropic"
        cached_conversations = [
            {'role': 'user', 'content': '快取訊息', 'created_at': '2023-01-01T00:00:00'}
        ]
        conversation_manager.memory_cache[cache_key] = {
            'conversations': cached_conversations,
            'timestamp': datetime.now()
        }
        
        result = conversation_manager.get_recent_conversations(
            user_id="test_user",
            model_provider="anthropic",
            platform="line"
        )
        
        assert result == cached_conversations
        # 不應該查詢資料庫
        mock_session.query.assert_not_called()
    
    def test_get_recent_conversations_from_database(self, conversation_manager, mock_session):
        """測試從資料庫取得對話"""
        # 模擬資料庫查詢
        mock_conversation = Mock()
        mock_conversation.role = "user"
        mock_conversation.content = "資料庫訊息"
        mock_conversation.created_at = datetime.now()
        mock_conversation.model_provider = "anthropic"
        
        mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_conversation]
        
        result = conversation_manager.get_recent_conversations(
            user_id="test_user",
            model_provider="anthropic",
            platform="line"
        )
        
        assert len(result) == 1
        assert result[0]['role'] == "user"
        assert result[0]['content'] == "資料庫訊息"
        
        # 快取應該被設置
        cache_key = "test_user:line:anthropic"
        assert cache_key in conversation_manager.memory_cache
    
    def test_get_recent_conversations_cache_expired(self, conversation_manager, mock_session):
        """測試快取過期情況"""
        # 設置過期的快取
        cache_key = "test_user:line:anthropic"
        conversation_manager.memory_cache[cache_key] = {
            'conversations': [],
            'timestamp': datetime.now() - timedelta(seconds=400)  # 超過 300 秒
        }
        
        # 模擬資料庫查詢
        mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        
        conversation_manager.get_recent_conversations(
            user_id="test_user",
            model_provider="anthropic",
            platform="line"
        )
        
        # 應該查詢資料庫
        mock_session.query.assert_called()
    
    def test_clear_user_history(self, conversation_manager, mock_session):
        """測試清除用戶歷史"""
        mock_session.query.return_value.filter.return_value.delete.return_value = 5
        
        # 設置快取
        cache_key = "test_user:line:anthropic"
        conversation_manager.memory_cache[cache_key] = {'test': 'data'}
        
        result = conversation_manager.clear_user_history(
            user_id="test_user",
            model_provider="anthropic",
            platform="line"
        )
        
        assert result is True
        mock_session.commit.assert_called_once()
        # 快取應該被清除
        assert cache_key not in conversation_manager.memory_cache
    
    def test_get_conversation_count(self, conversation_manager, mock_session):
        """測試取得對話數量"""
        mock_session.query.return_value.filter.return_value.filter.return_value.count.return_value = 10
        
        result = conversation_manager.get_conversation_count(
            user_id="test_user",
            model_provider="anthropic",
            platform="line"
        )
        
        assert result == 10
    
    def test_get_conversation_count_all_providers(self, conversation_manager, mock_session):
        """測試取得所有提供商的對話數量"""
        mock_session.query.return_value.filter.return_value.count.return_value = 25
        
        result = conversation_manager.get_conversation_count(
            user_id="test_user",
            platform="line"
        )
        
        assert result == 25
    
    def test_cleanup_old_conversations(self, conversation_manager, mock_session):
        """測試清理舊對話"""
        mock_session.query.return_value.filter.return_value.delete.return_value = 3
        
        # 設置一些快取
        conversation_manager.memory_cache["key1"] = {"data": "test1"}
        conversation_manager.memory_cache["key2"] = {"data": "test2"}
        
        result = conversation_manager.cleanup_old_conversations(days_to_keep=30)
        
        assert result == 3
        mock_session.commit.assert_called_once()
        # 所有快取應該被清除
        assert len(conversation_manager.memory_cache) == 0
    
    def test_get_user_statistics(self, conversation_manager, mock_session):
        """測試取得用戶統計"""
        # 模擬統計查詢結果
        mock_session.query.return_value.filter.return_value.group_by.return_value.all.return_value = [
            ("anthropic", 10, datetime.now()),
            ("gemini", 5, datetime.now() - timedelta(days=1))
        ]
        
        result = conversation_manager.get_user_statistics(
            user_id="test_user",
            platform="line"
        )
        
        assert "anthropic" in result
        assert "gemini" in result
        assert result["anthropic"]["message_count"] == 10
        assert result["gemini"]["message_count"] == 5
        assert "last_activity" in result["anthropic"]


class TestConversationManagerSingleton:
    """對話管理器單例測試"""
    
    def test_get_conversation_manager_singleton(self):
        """測試單例模式"""
        # 清除可能存在的實例
        import src.services.conversation
        src.services.conversation._conversation_manager = None
        
        manager1 = get_conversation_manager()
        manager2 = get_conversation_manager()
        
        assert manager1 is manager2
        assert isinstance(manager1, ORMConversationManager)
    
    @patch('src.services.conversation.ORMConversationManager')
    def test_get_conversation_manager_creation(self, mock_manager_class):
        """測試管理器創建"""
        # 清除可能存在的實例
        import src.services.conversation
        src.services.conversation._conversation_manager = None
        
        mock_instance = Mock()
        mock_manager_class.return_value = mock_instance
        
        result = get_conversation_manager()
        
        mock_manager_class.assert_called_once()
        assert result == mock_instance


class TestConversationManagerCache:
    """對話管理器快取測試"""
    
    @pytest.fixture
    def manager_with_cache(self):
        """帶快取的管理器"""
        with patch('src.services.conversation.get_db_session'):
            manager = ORMConversationManager()
            return manager
    
    def test_cache_key_format(self, manager_with_cache):
        """測試快取鍵格式"""
        # 這個測試確保快取鍵的格式一致性
        user_id = "test_user"
        platform = "line"
        model_provider = "anthropic"
        
        expected_key = f"{user_id}:{platform}:{model_provider}"
        
        # 透過添加訊息來測試快取鍵
        with patch.object(manager_with_cache, 'session_factory') as mock_factory:
            mock_session = Mock()
            mock_factory.return_value.__enter__.return_value = mock_session
            mock_factory.return_value.__exit__.return_value = None
            
            # 設置快取
            manager_with_cache.memory_cache[expected_key] = {"test": "data"}
            
            # 添加訊息應該清除快取
            manager_with_cache.add_message(
                user_id=user_id,
                model_provider=model_provider,
                role="user",
                content="test",
                platform=platform
            )
            
            # 快取應該被清除
            assert expected_key not in manager_with_cache.memory_cache
    
    def test_cache_ttl_behavior(self, manager_with_cache):
        """測試快取 TTL 行為"""
        cache_key = "test:line:anthropic"
        
        # 設置新的快取
        manager_with_cache.memory_cache[cache_key] = {
            'conversations': [{'test': 'data'}],
            'timestamp': datetime.now()
        }
        
        # 立即檢查應該命中快取
        assert cache_key in manager_with_cache.memory_cache
        
        # 模擬時間過去
        manager_with_cache.memory_cache[cache_key]['timestamp'] = datetime.now() - timedelta(seconds=400)
        
        # 現在快取應該被視為過期（在實際的 get_recent_conversations 中）
        cache_data = manager_with_cache.memory_cache[cache_key]
        is_expired = datetime.now() - cache_data['timestamp'] >= timedelta(seconds=manager_with_cache.cache_ttl)
        assert is_expired is True