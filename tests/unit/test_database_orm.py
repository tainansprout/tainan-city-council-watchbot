"""
ORM Database Models and Manager Tests
"""
import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta

from src.models.database import (
    DatabaseManager, 
    UserThreadTable, 
    SimpleConversationHistory,
    Base,
    get_database_manager,
    get_db_session
)
from sqlalchemy import text


class TestDatabaseManager:
    """SQLAlchemy DatabaseManager 測試"""
    
    @pytest.fixture
    def temp_db_url(self):
        """創建臨時 SQLite 資料庫用於測試"""
        return "sqlite:///:memory:"
    
    @pytest.fixture
    def db_manager(self, temp_db_url):
        """創建測試用的 DatabaseManager"""
        return DatabaseManager(database_url=temp_db_url)
    
    def test_database_manager_init(self, db_manager):
        """測試 DatabaseManager 初始化"""
        assert db_manager.engine is not None
        assert db_manager.SessionLocal is not None
        assert hasattr(db_manager, '_build_database_url')
    
    def test_create_all_tables(self, db_manager):
        """測試建立所有表格"""
        db_manager.create_all_tables()
        
        # 檢查表格是否存在
        with db_manager.engine.connect() as conn:
            # SQLite 中檢查表格存在
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = [row[0] for row in result]
            
        assert 'user_thread_table' in tables
        assert 'simple_conversation_history' in tables
    
    def test_check_connection_success(self, db_manager):
        """測試資料庫連線檢查成功"""
        db_manager.create_all_tables()
        assert db_manager.check_connection() == True
    
    def test_get_session(self, db_manager):
        """測試取得資料庫 session"""
        db_manager.create_all_tables()
        
        session = db_manager.get_session()
        assert session is not None
        
        # 測試 session 可以使用
        result = session.execute(text("SELECT 1")).scalar()
        assert result == 1
        
        session.close()
    
    def test_session_context_manager(self, db_manager):
        """測試 session 上下文管理器"""
        db_manager.create_all_tables()
        
        with db_manager.get_session() as session:
            result = session.execute(text("SELECT 1")).scalar()
            assert result == 1
    
    @patch.dict(os.environ, {
        'DB_HOST': 'test_host',
        'DB_PORT': '5433',
        'DB_NAME': 'test_db',
        'DB_USER': 'test_user',
        'DB_PASSWORD': 'test_pass'
    })
    def test_build_database_url_from_env(self):
        """測試從環境變數建構資料庫 URL"""
        manager = DatabaseManager()
        # 這會嘗試從配置檔案載入，失敗後使用環境變數
        # 由於是測試環境，預期會使用預設值或環境變數
        assert manager.engine is not None
    
    def test_close(self, db_manager):
        """測試關閉資料庫連線"""
        db_manager.close()
        # 確保不會拋出異常


class TestUserThreadTable:
    """UserThreadTable ORM 模型測試"""
    
    @pytest.fixture
    def db_session(self):
        """創建測試用的資料庫 session"""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        yield session
        session.close()
    
    def test_user_thread_creation(self, db_session):
        """測試 UserThread 記錄創建"""
        user_thread = UserThreadTable(
            user_id="test_user_123",
            thread_id="thread_456"
        )
        
        db_session.add(user_thread)
        db_session.commit()
        
        # 查詢驗證
        saved_thread = db_session.query(UserThreadTable).filter_by(
            user_id="test_user_123"
        ).first()
        
        assert saved_thread is not None
        assert saved_thread.user_id == "test_user_123"
        assert saved_thread.thread_id == "thread_456"
        assert saved_thread.created_at is not None
    
    def test_user_thread_update(self, db_session):
        """測試更新 UserThread 記錄"""
        # 創建記錄
        user_thread = UserThreadTable(
            user_id="test_user_update",
            thread_id="old_thread"
        )
        db_session.add(user_thread)
        db_session.commit()
        
        # 更新記錄
        user_thread.thread_id = "new_thread"
        db_session.commit()
        
        # 驗證更新
        updated_thread = db_session.query(UserThreadTable).filter_by(
            user_id="test_user_update"
        ).first()
        
        assert updated_thread.thread_id == "new_thread"
    
    def test_user_thread_delete(self, db_session):
        """測試刪除 UserThread 記錄"""
        user_thread = UserThreadTable(
            user_id="test_user_delete",
            thread_id="thread_to_delete"
        )
        db_session.add(user_thread)
        db_session.commit()
        
        # 刪除記錄
        db_session.delete(user_thread)
        db_session.commit()
        
        # 驗證刪除
        deleted_thread = db_session.query(UserThreadTable).filter_by(
            user_id="test_user_delete"
        ).first()
        
        assert deleted_thread is None


class TestSimpleConversationHistory:
    """SimpleConversationHistory ORM 模型測試"""
    
    @pytest.fixture
    def db_session(self):
        """創建測試用的資料庫 session"""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        yield session
        session.close()
    
    def test_conversation_creation(self, db_session):
        """測試對話記錄創建"""
        conversation = SimpleConversationHistory(
            user_id="test_user_123",
            model_provider="anthropic",
            role="user",
            content="Hello, how are you?"
        )
        
        db_session.add(conversation)
        db_session.commit()
        
        # 查詢驗證
        saved_conv = db_session.query(SimpleConversationHistory).filter_by(
            user_id="test_user_123"
        ).first()
        
        assert saved_conv is not None
        assert saved_conv.user_id == "test_user_123"
        assert saved_conv.model_provider == "anthropic"
        assert saved_conv.role == "user"
        assert saved_conv.content == "Hello, how are you?"
        assert saved_conv.created_at is not None
    
    def test_multiple_conversations(self, db_session):
        """測試多個對話記錄"""
        conversations = [
            SimpleConversationHistory(
                user_id="test_user_multi",
                model_provider="anthropic",
                role="user",
                content="First message"
            ),
            SimpleConversationHistory(
                user_id="test_user_multi",
                model_provider="anthropic", 
                role="assistant",
                content="First response"
            ),
            SimpleConversationHistory(
                user_id="test_user_multi",
                model_provider="anthropic",
                role="user", 
                content="Second message"
            )
        ]
        
        for conv in conversations:
            db_session.add(conv)
        db_session.commit()
        
        # 查詢驗證
        saved_convs = db_session.query(SimpleConversationHistory).filter_by(
            user_id="test_user_multi"
        ).order_by(SimpleConversationHistory.created_at).all()
        
        assert len(saved_convs) == 3
        assert saved_convs[0].content == "First message"
        assert saved_convs[1].content == "First response"
        assert saved_convs[2].content == "Second message"
    
    def test_conversation_by_provider(self, db_session):
        """測試按模型提供商查詢對話"""
        # 創建不同提供商的對話
        conversations = [
            SimpleConversationHistory(
                user_id="test_user_provider",
                model_provider="anthropic",
                role="user",
                content="Anthropic message"
            ),
            SimpleConversationHistory(
                user_id="test_user_provider",
                model_provider="gemini",
                role="user",
                content="Gemini message"
            ),
            SimpleConversationHistory(
                user_id="test_user_provider",
                model_provider="ollama",
                role="user",
                content="Ollama message"
            )
        ]
        
        for conv in conversations:
            db_session.add(conv)
        db_session.commit()
        
        # 查詢 Anthropic 對話
        anthropic_convs = db_session.query(SimpleConversationHistory).filter_by(
            user_id="test_user_provider",
            model_provider="anthropic"
        ).all()
        
        assert len(anthropic_convs) == 1
        assert anthropic_convs[0].content == "Anthropic message"
        
        # 查詢所有對話
        all_convs = db_session.query(SimpleConversationHistory).filter_by(
            user_id="test_user_provider"
        ).all()
        
        assert len(all_convs) == 3


class TestORMConversationManager:
    """ORM ConversationManager 測試"""
    
    @pytest.fixture
    def conversation_manager(self):
        """創建測試用的 ConversationManager"""
        from src.services.conversation_manager_orm import ORMConversationManager
        
        # Mock 資料庫 session
        with patch('src.services.conversation_manager_orm.get_db_session') as mock_get_session:
            engine = create_engine("sqlite:///:memory:")
            Base.metadata.create_all(engine)
            SessionLocal = sessionmaker(bind=engine)
            
            def mock_session():
                return SessionLocal()
            
            mock_get_session.side_effect = mock_session
            
            yield ORMConversationManager()
    
    def test_add_message(self, conversation_manager):
        """測試添加訊息"""
        result = conversation_manager.add_message(
            user_id="test_user",
            model_provider="anthropic",
            role="user",
            content="Test message"
        )
        
        assert result == True
    
    def test_get_recent_conversations(self, conversation_manager):
        """測試取得最近對話"""
        # 添加一些測試對話
        conversation_manager.add_message("test_user", "anthropic", "user", "Message 1")
        conversation_manager.add_message("test_user", "anthropic", "assistant", "Response 1")
        conversation_manager.add_message("test_user", "anthropic", "user", "Message 2")
        
        # 取得對話
        conversations = conversation_manager.get_recent_conversations(
            user_id="test_user",
            model_provider="anthropic",
            limit=5
        )
        
        assert len(conversations) == 3
        assert conversations[0]['role'] == 'user'
        assert conversations[0]['content'] == 'Message 1'
        assert conversations[1]['role'] == 'assistant'
        assert conversations[2]['role'] == 'user'
    
    def test_clear_user_history(self, conversation_manager):
        """測試清除用戶歷史"""
        # 添加測試對話
        conversation_manager.add_message("test_user_clear", "anthropic", "user", "Test message")
        
        # 清除歷史
        result = conversation_manager.clear_user_history("test_user_clear", "anthropic")
        assert result == True
        
        # 驗證已清除
        conversations = conversation_manager.get_recent_conversations(
            user_id="test_user_clear",
            model_provider="anthropic"
        )
        assert len(conversations) == 0
    
    def test_get_conversation_count(self, conversation_manager):
        """測試取得對話數量"""
        # 添加測試對話
        user_id = "test_user_count"
        conversation_manager.add_message(user_id, "anthropic", "user", "Message 1")
        conversation_manager.add_message(user_id, "anthropic", "assistant", "Response 1")
        conversation_manager.add_message(user_id, "gemini", "user", "Message 2")
        
        # 測試總數量
        total_count = conversation_manager.get_conversation_count(user_id)
        assert total_count == 3
        
        # 測試特定提供商數量
        anthropic_count = conversation_manager.get_conversation_count(user_id, "anthropic")
        assert anthropic_count == 2
        
        gemini_count = conversation_manager.get_conversation_count(user_id, "gemini")
        assert gemini_count == 1


class TestGlobalDatabaseFunctions:
    """測試全域資料庫函數"""
    
    @patch('src.models.database._db_manager', None)
    def test_get_database_manager_singleton(self):
        """測試 get_database_manager 單例模式"""
        # 重置全域變數
        from src.models import database
        database._db_manager = None
        
        manager1 = get_database_manager()
        manager2 = get_database_manager()
        
        assert manager1 is manager2  # 應該是同一個實例
    
    def test_get_db_session(self):
        """測試 get_db_session 便利函數"""
        session = get_db_session()
        assert session is not None
        session.close()


class TestDatabaseMigration:
    """測試資料庫遷移相關功能"""
    
    def test_base_metadata(self):
        """測試 Base metadata 包含所有表格"""
        table_names = Base.metadata.tables.keys()
        
        assert 'user_thread_table' in table_names
        assert 'simple_conversation_history' in table_names
    
    def test_table_relationships(self):
        """測試表格關係和索引"""
        # 檢查 SimpleConversationHistory 的索引
        table = SimpleConversationHistory.__table__
        
        # 檢查是否有適當的欄位
        column_names = [col.name for col in table.columns]
        assert 'user_id' in column_names
        assert 'model_provider' in column_names
        assert 'role' in column_names
        assert 'content' in column_names
        assert 'created_at' in column_names
    
    @patch('src.core.config.load_config')
    def test_database_url_config_loading(self, mock_load_config):
        """測試從配置檔案載入資料庫 URL"""
        mock_load_config.return_value = {
            'db': {
                'host': 'test-host',
                'port': 5432,
                'database': 'test-db',
                'username': 'test-user',
                'password': 'test-pass'
            }
        }
        
        manager = DatabaseManager()
        # 應該能夠成功創建，不會拋出異常
        assert manager.engine is not None