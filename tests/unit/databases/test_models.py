"""
測試資料庫模型的單元測試
"""
import pytest
from datetime import datetime
from src.database.models import (
    Base, UserThreadTable, SimpleConversationHistory
)


class TestUserThreadTable:
    """測試 UserThreadTable 模型"""

    def test_user_thread_table_creation(self):
        """測試創建 UserThreadTable 實例"""
        user_thread = UserThreadTable(
            user_id="test_user_123",
            platform="line",
            thread_id="thread_456"
        )

        assert user_thread.user_id == "test_user_123"
        assert user_thread.platform == "line"
        assert user_thread.thread_id == "thread_456"
        assert user_thread.created_at is None  # 在未 commit 前為 None

    def test_user_thread_table_default_platform(self):
        """測試默認平台設定"""
        user_thread = UserThreadTable(
            user_id="test_user_123",
            thread_id="thread_456"
        )

        # SQLAlchemy 預設值只有在資料庫操作時才會生效
        # 這裡測試欄位的預設值定義
        assert hasattr(UserThreadTable.platform.property.columns[0], 'default')
        assert UserThreadTable.platform.property.columns[0].default.arg == 'line'

    def test_user_thread_table_repr(self):
        """測試 __repr__ 方法"""
        user_thread = UserThreadTable(
            user_id="test_user_123",
            platform="discord",
            thread_id="thread_456"
        )

        expected_repr = "<UserThread(user_id='test_user_123', platform='discord', thread_id='thread_456')>"
        assert repr(user_thread) == expected_repr

    def test_user_thread_table_tablename(self):
        """測試表名稱"""
        assert UserThreadTable.__tablename__ == 'user_thread_table'

    def test_user_thread_table_primary_keys(self):
        """測試複合主鍵"""
        # 檢查主鍵列
        primary_key_columns = [col.name for col in UserThreadTable.__table__.primary_key.columns]
        assert 'user_id' in primary_key_columns
        assert 'platform' in primary_key_columns
        assert len(primary_key_columns) == 2


class TestSimpleConversationHistory:
    """測試 SimpleConversationHistory 模型"""

    def test_conversation_history_creation(self):
        """測試創建 SimpleConversationHistory 實例"""
        conversation = SimpleConversationHistory(
            user_id="test_user_123",
            platform="line",
            model_provider="anthropic",
            role="user",
            content="Hello, how are you?"
        )

        assert conversation.user_id == "test_user_123"
        assert conversation.platform == "line"
        assert conversation.model_provider == "anthropic"
        assert conversation.role == "user"
        assert conversation.content == "Hello, how are you?"
        assert conversation.created_at is None  # 在未 commit 前為 None

    def test_conversation_history_default_platform(self):
        """測試默認平台設定"""
        conversation = SimpleConversationHistory(
            user_id="test_user_123",
            model_provider="gemini",
            role="assistant",
            content="I'm doing well, thank you!"
        )

        # SQLAlchemy 預設值只有在資料庫操作時才會生效
        # 這裡測試欄位的預設值定義
        assert hasattr(SimpleConversationHistory.platform.property.columns[0], 'default')
        assert SimpleConversationHistory.platform.property.columns[0].default.arg == 'line'

    def test_conversation_history_repr(self):
        """測試 __repr__ 方法"""
        conversation = SimpleConversationHistory(
            user_id="test_user_123",
            platform="telegram",
            model_provider="ollama",
            role="user",
            content="Test message"
        )

        expected_repr = "<Conversation(user_id='test_user_123', platform='telegram', provider='ollama', role='user')>"
        assert repr(conversation) == expected_repr

    def test_conversation_history_tablename(self):
        """測試表名稱"""
        assert SimpleConversationHistory.__tablename__ == 'simple_conversation_history'

    def test_conversation_history_indexes(self):
        """測試索引設定"""
        table = SimpleConversationHistory.__table__
        index_names = [index.name for index in table.indexes]

        assert 'idx_conversation_user_platform' in index_names
        assert 'idx_conversation_user_platform_provider' in index_names

    def test_conversation_history_autoincrement_id(self):
        """測試自動遞增 ID"""
        conversation = SimpleConversationHistory(
            user_id="test_user_123",
            model_provider="anthropic",
            role="user",
            content="Test"
        )

        # ID 在實際插入資料庫前為 None
        assert conversation.id is None


class TestDatabaseModelIntegration:
    """測試資料庫模型整合"""

    def test_models_are_sqlalchemy_declarative_base(self):
        """測試模型是否正確繼承 SQLAlchemy declarative base"""
        assert hasattr(UserThreadTable, '__table__')
        assert hasattr(SimpleConversationHistory, '__table__')
        assert UserThreadTable.__table__.name == 'user_thread_table'
        assert SimpleConversationHistory.__table__.name == 'simple_conversation_history'

    def test_models_have_correct_column_types(self):
        """測試模型有正確的欄位類型"""
        # UserThreadTable 欄位檢查
        user_thread_table = UserThreadTable.__table__
        assert str(user_thread_table.c.user_id.type) == 'VARCHAR(255)'
        assert str(user_thread_table.c.platform.type) == 'VARCHAR(50)'
        assert str(user_thread_table.c.thread_id.type) == 'VARCHAR(255)'
        assert 'DATETIME' in str(user_thread_table.c.created_at.type)

        # SimpleConversationHistory 欄位檢查
        conversation_table = SimpleConversationHistory.__table__
        assert str(conversation_table.c.id.type) == 'INTEGER'
        assert str(conversation_table.c.user_id.type) == 'VARCHAR(255)'
        assert str(conversation_table.c.platform.type) == 'VARCHAR(50)'
        assert str(conversation_table.c.model_provider.type) == 'VARCHAR(50)'
        assert str(conversation_table.c.role.type) == 'VARCHAR(20)'
        assert str(conversation_table.c.content.type) == 'TEXT'

    def test_models_nullable_constraints(self):
        """測試模型的可空約束"""
        # UserThreadTable 約束
        user_thread_table = UserThreadTable.__table__
        assert user_thread_table.c.user_id.nullable is False
        assert user_thread_table.c.platform.nullable is False
        assert user_thread_table.c.thread_id.nullable is False
        assert user_thread_table.c.created_at.nullable is True  # 有默認值

        # SimpleConversationHistory 約束
        conversation_table = SimpleConversationHistory.__table__
        assert conversation_table.c.id.nullable is False
        assert conversation_table.c.user_id.nullable is False
        assert conversation_table.c.platform.nullable is False
        assert conversation_table.c.model_provider.nullable is False
        assert conversation_table.c.role.nullable is False
        assert conversation_table.c.content.nullable is False
        assert conversation_table.c.created_at.nullable is True  # 有默認值


class TestMultiPlatformSupport:
    """測試多平台支援"""

    def test_multi_platform_thread_support(self):
        """測試多平台 thread 支援"""
        platforms = ["line", "discord", "telegram"]
        user_id = "multi_platform_user"

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
        unique_thread_ids = set(thread.thread_id for thread in threads)
        assert len(unique_thread_ids) == 3

    def test_multi_platform_conversation_support(self):
        """測試多平台對話支援"""
        platforms = ["line", "discord", "telegram"]
        providers = ["anthropic", "gemini", "ollama"]
        user_id = "conversation_user"

        conversations = []
        for platform in platforms:
            for provider in providers:
                conversation = SimpleConversationHistory(
                    user_id=user_id,
                    platform=platform,
                    model_provider=provider,
                    role="user",
                    content=f"Message on {platform} using {provider}"
                )
                conversations.append(conversation)

        # 驗證組合的唯一性
        assert len(conversations) == 9  # 3 platforms × 3 providers
        assert all(conv.user_id == user_id for conv in conversations)

        # 驗證平台和提供商的組合
        combinations = set((conv.platform, conv.model_provider) for conv in conversations)
        assert len(combinations) == 9


class TestModelEdgeCases:
    """測試模型邊界情況"""

    def test_empty_content_handling(self):
        """測試空內容處理"""
        conversation = SimpleConversationHistory(
            user_id="test_user",
            platform="line",
            model_provider="anthropic",
            role="user",
            content=""  # 空內容
        )

        assert conversation.content == ""
        assert conversation.user_id == "test_user"

    def test_very_long_content(self):
        """測試非常長的內容"""
        long_content = "A" * 10000  # 10,000 字元
        conversation = SimpleConversationHistory(
            user_id="test_user",
            platform="line",
            model_provider="anthropic",
            role="user",
            content=long_content
        )

        assert len(conversation.content) == 10000
        assert conversation.content == long_content

    def test_special_characters_in_content(self):
        """測試特殊字元處理"""
        special_content = "Hello! 你好 🎵 @#$%^&*()_+ 測試"
        conversation = SimpleConversationHistory(
            user_id="test_user",
            platform="line",
            model_provider="anthropic",
            role="user",
            content=special_content
        )

        assert conversation.content == special_content

    def test_long_user_id_and_thread_id(self):
        """測試長 user_id 和 thread_id"""
        long_user_id = "U" + "x" * 254  # 255 字元總長度
        long_thread_id = "T" + "y" * 254  # 255 字元總長度

        thread = UserThreadTable(
            user_id=long_user_id,
            platform="line",
            thread_id=long_thread_id
        )

        assert len(thread.user_id) == 255
        assert len(thread.thread_id) == 255
        assert thread.user_id == long_user_id
        assert thread.thread_id == long_thread_id


if __name__ == "__main__":
    pytest.main([__file__])
