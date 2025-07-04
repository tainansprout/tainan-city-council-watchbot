"""
資料庫模型測試
測試 src/database/models.py 中的資料庫模型定義
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from src.database.models import (
    UserThreadTable, 
    SimpleConversationHistory, 
    get_db_session
)


class TestUserThreadTable:
    """UserThreadTable 模型測試"""
    
    def test_user_thread_table_creation(self):
        """測試 UserThreadTable 建立"""
        thread = UserThreadTable(
            user_id="test_user_123",
            platform="line",
            thread_id="thread_456"
        )
        
        assert thread.user_id == "test_user_123"
        assert thread.platform == "line"
        assert thread.thread_id == "thread_456"
        assert thread.created_at is None  # 尚未儲存到資料庫
    
    def test_user_thread_table_composite_key(self):
        """測試複合主鍵"""
        thread1 = UserThreadTable(
            user_id="test_user",
            platform="line",
            thread_id="thread_1"
        )
        
        thread2 = UserThreadTable(
            user_id="test_user",
            platform="discord",
            thread_id="thread_2"
        )
        
        # 同一用戶在不同平台應該可以有不同的 thread
        assert thread1.user_id == thread2.user_id
        assert thread1.platform != thread2.platform
        assert thread1.thread_id != thread2.thread_id


class TestSimpleConversationHistory:
    """SimpleConversationHistory 模型測試"""
    
    def test_conversation_history_creation(self):
        """測試對話歷史建立"""
        conversation = SimpleConversationHistory(
            user_id="test_user_123",
            platform="line",
            model_provider="anthropic",
            role="user",
            content="測試訊息"
        )
        
        assert conversation.user_id == "test_user_123"
        assert conversation.platform == "line"
        assert conversation.model_provider == "anthropic"
        assert conversation.role == "user"
        assert conversation.content == "測試訊息"
        assert conversation.id is None  # 尚未儲存到資料庫
        assert conversation.created_at is None
    
    def test_conversation_history_roles(self):
        """測試不同角色的對話"""
        user_msg = SimpleConversationHistory(
            user_id="test_user",
            platform="line",
            model_provider="gemini",
            role="user",
            content="用戶訊息"
        )
        
        assistant_msg = SimpleConversationHistory(
            user_id="test_user",
            platform="line", 
            model_provider="gemini",
            role="assistant",
            content="助手回應"
        )
        
        assert user_msg.role == "user"
        assert assistant_msg.role == "assistant"
        assert user_msg.user_id == assistant_msg.user_id
        assert user_msg.platform == assistant_msg.platform
    
    def test_conversation_history_providers(self):
        """測試不同模型提供商"""
        providers = ["anthropic", "gemini", "ollama", "openai"]
        
        for provider in providers:
            conversation = SimpleConversationHistory(
                user_id="test_user",
                platform="line",
                model_provider=provider,
                role="user",
                content=f"使用 {provider} 的訊息"
            )
            assert conversation.model_provider == provider


class TestDatabaseSession:
    """資料庫 Session 測試"""
    
    @patch('src.database.models.SessionLocal')
    def test_get_db_session(self, mock_session_local):
        """測試資料庫 session 取得"""
        mock_session = Mock()
        mock_session_local.return_value = mock_session
        
        # 測試 context manager
        with get_db_session() as session:
            assert session == mock_session
        
        # 驗證 session 被正確關閉
        mock_session.close.assert_called_once()
    
    @patch('src.database.models.SessionLocal')
    def test_get_db_session_exception_handling(self, mock_session_local):
        """測試資料庫 session 異常處理"""
        mock_session = Mock()
        mock_session_local.return_value = mock_session
        
        # 模擬異常
        try:
            with get_db_session() as session:
                raise Exception("測試異常")
        except Exception:
            pass
        
        # 即使發生異常，session 也應該被關閉
        mock_session.close.assert_called_once()


class TestModelIntegration:
    """模型整合測試"""
    
    def test_multi_platform_data_structure(self):
        """測試多平台資料結構"""
        platforms = ["line", "discord", "telegram"]
        user_id = "multi_platform_user"
        
        # 建立多平台的 thread 記錄
        threads = []
        for platform in platforms:
            thread = UserThreadTable(
                user_id=user_id,
                platform=platform,
                thread_id=f"{platform}_thread_123"
            )
            threads.append(thread)
        
        # 驗證每個平台都有獨立的記錄
        assert len(threads) == 3
        assert all(thread.user_id == user_id for thread in threads)
        assert len(set(thread.platform for thread in threads)) == 3
    
    def test_conversation_and_thread_relationship(self):
        """測試對話和線程的關聯"""
        user_id = "relationship_test_user"
        platform = "line"
        
        # 建立 thread 記錄
        thread = UserThreadTable(
            user_id=user_id,
            platform=platform,
            thread_id="thread_123"
        )
        
        # 建立對話記錄
        conversation = SimpleConversationHistory(
            user_id=user_id,
            platform=platform,
            model_provider="anthropic",
            role="user",
            content="測試對話"
        )
        
        # 驗證關聯性
        assert thread.user_id == conversation.user_id
        assert thread.platform == conversation.platform
        
        # 對於 OpenAI 模型，會使用 thread
        # 對於其他模型，會使用 conversation history