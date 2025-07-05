"""
測試資料庫模型的單元測試
"""
import pytest
import os
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from src.database.models import (
    Base, UserThreadTable, SimpleConversationHistory, 
    DatabaseManager, get_database_manager, get_db_session
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
        
        assert user_thread.platform == "line"  # 默認值
    
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
        
        assert conversation.platform == "line"  # 默認值
    
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


class TestDatabaseManagerInitialization:
    """測試 DatabaseManager 初始化"""
    
    def test_init_with_custom_url(self):
        """測試使用自定義資料庫 URL 初始化"""
        custom_url = "postgresql://user:pass@localhost:5432/test_db"
        
        with patch('src.database.models.create_engine') as mock_create_engine, \
             patch('src.database.models.sessionmaker') as mock_sessionmaker:
            
            mock_engine = Mock()
            mock_create_engine.return_value = mock_engine
            mock_session_class = Mock()
            mock_sessionmaker.return_value = mock_session_class
            
            manager = DatabaseManager(database_url=custom_url)
            
            assert manager.engine == mock_engine
            assert manager.SessionLocal == mock_session_class
            mock_create_engine.assert_called_once()
            mock_sessionmaker.assert_called_once()
    
    def test_init_without_url_calls_build_database_url(self):
        """測試不提供 URL 時會調用 _build_database_url"""
        with patch('src.database.models.create_engine') as mock_create_engine, \
             patch('src.database.models.sessionmaker') as mock_sessionmaker, \
             patch.object(DatabaseManager, '_build_database_url', return_value="test_url") as mock_build_url:
            
            mock_engine = Mock()
            mock_create_engine.return_value = mock_engine
            
            manager = DatabaseManager()
            
            mock_build_url.assert_called_once()
            mock_create_engine.assert_called_once_with(
                "test_url",
                poolclass=patch.ANY,
                pool_size=20,
                max_overflow=30,
                pool_timeout=30,
                pool_recycle=3600,
                pool_pre_ping=True,
                echo=False,
                connect_args=patch.ANY
            )
    
    def test_postgresql_connect_args(self):
        """測試 PostgreSQL 連接參數"""
        postgresql_url = "postgresql://user:pass@localhost:5432/test_db"
        
        with patch('src.database.models.create_engine') as mock_create_engine, \
             patch('src.database.models.sessionmaker'):
            
            DatabaseManager(database_url=postgresql_url)
            
            call_args = mock_create_engine.call_args
            connect_args = call_args[1]['connect_args']
            
            assert connect_args['sslmode'] == 'require'
            assert connect_args['connect_timeout'] == 10
            assert connect_args['keepalives_idle'] == 600
            assert connect_args['keepalives_interval'] == 30
            assert connect_args['keepalives_count'] == 3
    
    def test_sqlite_connect_args(self):
        """測試 SQLite 連接參數"""
        sqlite_url = "sqlite:///test.db"
        
        with patch('src.database.models.create_engine') as mock_create_engine, \
             patch('src.database.models.sessionmaker'):
            
            DatabaseManager(database_url=sqlite_url)
            
            call_args = mock_create_engine.call_args
            connect_args = call_args[1]['connect_args']
            
            assert connect_args['check_same_thread'] is False
            assert connect_args['timeout'] == 20


class TestDatabaseManagerBuildDatabaseUrl:
    """測試 DatabaseManager._build_database_url 方法"""
    
    def test_build_url_from_config(self):
        """測試從配置檔案建構 URL"""
        mock_config = {
            'db': {
                'host': 'test_host',
                'port': '5433',
                'db_name': 'test_database',
                'user': 'test_user',
                'password': 'test_password'
            }
        }
        
        with patch('src.database.models.load_config', return_value=mock_config), \
             patch('src.database.models.create_engine'), \
             patch('src.database.models.sessionmaker'):
            
            manager = DatabaseManager()
            url = manager._build_database_url()
            
            expected_url = "postgresql://test_user:test_password@test_host:5433/test_database"
            assert url == expected_url
    
    def test_build_url_with_ssl_params(self):
        """測試包含 SSL 參數的 URL 建構"""
        mock_config = {
            'db': {
                'host': 'secure_host',
                'port': '5432',
                'db_name': 'secure_db',
                'user': 'secure_user',
                'password': 'secure_pass',
                'sslmode': 'verify-full',
                'sslrootcert': '/path/to/ca.crt',
                'sslcert': '/path/to/client.crt',
                'sslkey': '/path/to/client.key'
            }
        }
        
        with patch('src.database.models.load_config', return_value=mock_config), \
             patch('src.database.models.create_engine'), \
             patch('src.database.models.sessionmaker'):
            
            manager = DatabaseManager()
            url = manager._build_database_url()
            
            assert 'sslmode=verify-full' in url
            assert 'sslrootcert=/path/to/ca.crt' in url
            assert 'sslcert=/path/to/client.crt' in url
            assert 'sslkey=/path/to/client.key' in url
    
    def test_build_url_fallback_to_env_vars(self):
        """測試回退到環境變數"""
        with patch('src.database.models.load_config', side_effect=Exception("Config error")), \
             patch('src.database.models.create_engine'), \
             patch('src.database.models.sessionmaker'), \
             patch('os.getenv') as mock_getenv:
            
            mock_getenv.side_effect = lambda key, default: {
                'DB_HOST': 'env_host',
                'DB_PORT': '5434',
                'DB_NAME': 'env_database',
                'DB_USER': 'env_user',
                'DB_PASSWORD': 'env_password',
                'DATABASE_URL': 'postgresql://env_user:env_password@env_host:5434/env_database'
            }.get(key, default)
            
            manager = DatabaseManager()
            url = manager._build_database_url()
            
            expected_url = "postgresql://env_user:env_password@env_host:5434/env_database"
            assert url == expected_url
    
    def test_build_url_ultimate_fallback(self):
        """測試最終回退到預設值"""
        with patch('src.database.models.load_config', side_effect=Exception("Config error")), \
             patch('src.database.models.create_engine'), \
             patch('src.database.models.sessionmaker'), \
             patch('os.getenv', return_value='postgresql://postgres:password@localhost:5432/chatbot'):
            
            manager = DatabaseManager()
            url = manager._build_database_url()
            
            assert url == 'postgresql://postgres:password@localhost:5432/chatbot'


class TestDatabaseManagerMethods:
    """測試 DatabaseManager 的其他方法"""
    
    @pytest.fixture
    def manager(self):
        """創建 DatabaseManager 實例"""
        with patch('src.database.models.create_engine') as mock_create_engine, \
             patch('src.database.models.sessionmaker') as mock_sessionmaker:
            
            mock_engine = Mock()
            mock_create_engine.return_value = mock_engine
            mock_session_class = Mock()
            mock_sessionmaker.return_value = mock_session_class
            
            manager = DatabaseManager("postgresql://test:test@localhost:5432/test")
            return manager
    
    def test_get_session(self, manager):
        """測試取得 session"""
        mock_session = Mock()
        manager.SessionLocal.return_value = mock_session
        
        session = manager.get_session()
        
        assert session == mock_session
        manager.SessionLocal.assert_called_once()
    
    def test_create_all_tables(self, manager):
        """測試建立所有表格"""
        with patch('src.database.models.Base') as mock_base, \
             patch('src.database.models.logger') as mock_logger:
            
            mock_metadata = Mock()
            mock_base.metadata = mock_metadata
            
            manager.create_all_tables()
            
            mock_metadata.create_all.assert_called_once_with(bind=manager.engine)
            mock_logger.info.assert_called_once_with("All database tables created successfully")
    
    def test_check_connection_success(self, manager):
        """測試成功的連線檢查"""
        mock_connection = Mock()
        manager.engine.connect.return_value.__enter__.return_value = mock_connection
        
        result = manager.check_connection()
        
        assert result is True
        mock_connection.execute.assert_called_once()
    
    def test_check_connection_failure(self, manager):
        """測試失敗的連線檢查"""
        manager.engine.connect.side_effect = SQLAlchemyError("Connection failed")
        
        with patch('src.database.models.logger') as mock_logger:
            result = manager.check_connection()
            
            assert result is False
            mock_logger.error.assert_called_once()
    
    def test_close(self, manager):
        """測試關閉連線"""
        with patch('src.database.models.logger') as mock_logger:
            manager.close()
            
            manager.engine.dispose.assert_called_once()
            mock_logger.info.assert_called_once_with("Database connection closed")
    
    def test_close_with_logger_error(self, manager):
        """測試關閉連線時日誌錯誤"""
        with patch('src.database.models.logger') as mock_logger:
            mock_logger.info.side_effect = ValueError("Logger error")
            
            # 應該不會拋出異常
            manager.close()
            
            manager.engine.dispose.assert_called_once()


class TestGlobalDatabaseManager:
    """測試全域資料庫管理器函數"""
    
    def teardown_method(self):
        """每個測試後清理全域狀態"""
        import src.database.models
        src.database.models._db_manager = None
    
    def test_get_database_manager_singleton(self):
        """測試單例模式"""
        with patch('src.database.models.DatabaseManager') as mock_db_manager_class:
            mock_instance = Mock()
            mock_db_manager_class.return_value = mock_instance
            
            # 第一次調用
            manager1 = get_database_manager()
            # 第二次調用
            manager2 = get_database_manager()
            
            assert manager1 == manager2
            assert manager1 == mock_instance
            # DatabaseManager 構造函數只應該被調用一次
            mock_db_manager_class.assert_called_once()
    
    def test_get_database_manager_creates_new_instance(self):
        """測試創建新實例"""
        with patch('src.database.models.DatabaseManager') as mock_db_manager_class:
            mock_instance = Mock()
            mock_db_manager_class.return_value = mock_instance
            
            manager = get_database_manager()
            
            assert manager == mock_instance
            mock_db_manager_class.assert_called_once()
    
    def test_get_db_session(self):
        """測試取得資料庫 session 便利函數"""
        with patch('src.database.models.get_database_manager') as mock_get_manager:
            mock_manager = Mock()
            mock_session = Mock()
            mock_manager.get_session.return_value = mock_session
            mock_get_manager.return_value = mock_manager
            
            session = get_db_session()
            
            assert session == mock_session
            mock_get_manager.assert_called_once()
            mock_manager.get_session.assert_called_once()


class TestDatabaseConnectionScenarios:
    """測試各種資料庫連線場景"""
    
    def test_postgresql_connection_with_all_ssl_options(self):
        """測試包含所有 SSL 選項的 PostgreSQL 連線"""
        mock_config = {
            'db': {
                'host': 'ssl-host',
                'port': '5432',
                'db_name': 'ssl_db',
                'user': 'ssl_user',
                'password': 'ssl_pass',
                'sslmode': 'verify-full',
                'sslrootcert': '/certs/ca.crt',
                'sslcert': '/certs/client.crt',
                'sslkey': '/certs/client.key'
            }
        }
        
        with patch('src.database.models.load_config', return_value=mock_config), \
             patch('src.database.models.create_engine') as mock_create_engine, \
             patch('src.database.models.sessionmaker'):
            
            manager = DatabaseManager()
            
            # 檢查建構的 URL 包含所有 SSL 參數
            call_args = mock_create_engine.call_args[0]
            database_url = call_args[0]
            
            assert 'sslmode=verify-full' in database_url
            assert 'sslrootcert=/certs/ca.crt' in database_url
            assert 'sslcert=/certs/client.crt' in database_url
            assert 'sslkey=/certs/client.key' in database_url
    
    def test_partial_ssl_configuration(self):
        """測試部分 SSL 配置"""
        mock_config = {
            'db': {
                'host': 'partial-ssl-host',
                'port': '5432',
                'db_name': 'partial_ssl_db',
                'user': 'ssl_user',
                'password': 'ssl_pass',
                'sslmode': 'require'
                # 只有 sslmode，沒有其他 SSL 參數
            }
        }
        
        with patch('src.database.models.load_config', return_value=mock_config), \
             patch('src.database.models.create_engine') as mock_create_engine, \
             patch('src.database.models.sessionmaker'):
            
            manager = DatabaseManager()
            
            call_args = mock_create_engine.call_args[0]
            database_url = call_args[0]
            
            assert 'sslmode=require' in database_url
            assert 'sslrootcert=' not in database_url
            assert 'sslcert=' not in database_url
            assert 'sslkey=' not in database_url
    
    def test_no_ssl_configuration(self):
        """測試無 SSL 配置"""
        mock_config = {
            'db': {
                'host': 'no-ssl-host',
                'port': '5432',
                'db_name': 'no_ssl_db',
                'user': 'regular_user',
                'password': 'regular_pass'
                # 沒有任何 SSL 參數
            }
        }
        
        with patch('src.database.models.load_config', return_value=mock_config), \
             patch('src.database.models.create_engine') as mock_create_engine, \
             patch('src.database.models.sessionmaker'):
            
            manager = DatabaseManager()
            
            call_args = mock_create_engine.call_args[0]
            database_url = call_args[0]
            
            # 不應該包含任何 SSL 參數
            assert 'ssl' not in database_url.lower()
            assert database_url == "postgresql://regular_user:regular_pass@no-ssl-host:5432/no_ssl_db"


class TestDatabaseErrorHandling:
    """測試資料庫錯誤處理"""
    
    def test_connection_check_with_operational_error(self):
        """測試連線檢查遇到操作錯誤"""
        with patch('src.database.models.create_engine') as mock_create_engine, \
             patch('src.database.models.sessionmaker'):
            
            mock_engine = Mock()
            mock_create_engine.return_value = mock_engine
            mock_engine.connect.side_effect = OperationalError("Connection timeout", None, None)
            
            manager = DatabaseManager("postgresql://test:test@localhost:5432/test")
            
            with patch('src.database.models.logger') as mock_logger:
                result = manager.check_connection()
                
                assert result is False
                mock_logger.error.assert_called_once()
                error_call = mock_logger.error.call_args[0][0]
                assert "Database connection failed" in error_call
    
    def test_config_loading_exception_handling(self):
        """測試配置載入異常處理"""
        with patch('src.database.models.load_config', side_effect=ImportError("Module not found")), \
             patch('src.database.models.create_engine'), \
             patch('src.database.models.sessionmaker'), \
             patch('src.database.models.logger') as mock_logger, \
             patch('os.getenv', return_value='fallback_url'):
            
            manager = DatabaseManager()
            
            mock_logger.warning.assert_called_once()
            warning_call = mock_logger.warning.call_args[0][0]
            assert "Failed to load config, using environment variables" in warning_call


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