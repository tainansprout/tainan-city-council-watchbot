import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.exc import SQLAlchemyError

from src.database.connection import Database, UserThreadTable
from src.core.exceptions import DatabaseError

# 使用 pytest.fixture 來集中管理 mock
@pytest.fixture
def db_config():
    return {
        'host': 'localhost',
        'port': 5432,
        'db_name': 'test_db',
        'user': 'test_user',
        'password': 'test_password',
        'sslmode': 'disable'
    }

@pytest.fixture
def mock_engine():
    """一個模擬的 SQLAlchemy 引擎"""
    engine = MagicMock()
    engine.pool.size.return_value = 10
    engine.pool.checkedin.return_value = 2
    engine.pool.checkedout.return_value = 1
    engine.pool.overflow.return_value = 0
    # 確保 invalidated 屬性存在
    type(engine.pool).invalidated = 0
    return engine

@pytest.fixture
def mock_session():
    """一個模擬的 SQLAlchemy session"""
    return MagicMock()

@pytest.fixture(autouse=True)
def patch_db_dependencies(mock_engine, mock_session):
    """自動 patch 所有測試的資料庫依賴"""
    with patch('src.database.connection.create_engine', return_value=mock_engine) as mock_create_engine, \
         patch('src.database.connection.sessionmaker', return_value=lambda: mock_session) as mock_sessionmaker:
        yield mock_create_engine, mock_sessionmaker

class TestDatabase:
    """資料庫單元測試"""

    def test_database_init(self, db_config, mock_engine, patch_db_dependencies):
        mock_create_engine, mock_sessionmaker = patch_db_dependencies
        db = Database(db_config)
        
        assert db.config == db_config
        assert db.engine == mock_engine
        mock_create_engine.assert_called_once()
        mock_sessionmaker.assert_called_once_with(bind=mock_engine)

    def test_build_connection_string(self, db_config):
        db = Database(db_config)
        connection_string = db._build_connection_string()
        expected = "postgresql://test_user:test_password@localhost:5432/test_db"
        assert connection_string == expected

    def test_get_ssl_args(self, db_config):
        db_config.update({
            'sslmode': 'require',
            'sslrootcert': '/path/to/ca.crt',
            'sslcert': '/path/to/client.crt',
            'sslkey': '/path/to/client.key'
        })
        db = Database(db_config)
        ssl_args = db._get_ssl_args()
        assert ssl_args['sslmode'] == 'require'
        assert ssl_args['sslrootcert'] == '/path/to/ca.crt'

    def test_query_thread_exists(self, db_config, mock_session):
        mock_user_thread = Mock()
        mock_user_thread.thread_id = 'thread_123'
        mock_session.query.return_value.filter.return_value.first.return_value = mock_user_thread
        
        db = Database(db_config)
        result = db.query_thread('user_123')
        
        assert result == 'thread_123'
        mock_session.query.assert_called_once_with(UserThreadTable)

    def test_query_thread_not_exists(self, db_config, mock_session):
        mock_session.query.return_value.filter.return_value.first.return_value = None
        db = Database(db_config)
        result = db.query_thread('user_123')
        assert result is None

    def test_save_thread_new_user(self, db_config, mock_session):
        mock_session.query.return_value.filter.return_value.first.return_value = None
        db = Database(db_config)
        db.save_thread('user_123', 'thread_456')
        mock_session.add.assert_called_once()

    def test_save_thread_existing_user(self, db_config, mock_session):
        mock_user_thread = Mock()
        mock_session.query.return_value.filter.return_value.first.return_value = mock_user_thread
        db = Database(db_config)
        db.save_thread('user_123', 'thread_456')
        assert mock_user_thread.thread_id == 'thread_456'
        mock_session.add.assert_not_called()

    def test_delete_thread(self, db_config, mock_session):
        db = Database(db_config)
        db.delete_thread('user_123')
        mock_session.query.return_value.filter.return_value.delete.assert_called_once()

    def test_get_connection_info(self, db_config, mock_engine):
        db = Database(db_config)
        info = db.get_connection_info()
        expected = {
            'pool_size': 10,
            'checked_in': 2,
            'checked_out': 1,
            'overflow': 0,
            'invalid': 0
        }
        assert info == expected

    def test_get_session_context_manager(self, db_config, mock_session):
        db = Database(db_config)
        with db.get_session() as session:
            assert session == mock_session
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()
        mock_session.close.assert_called_once()

    def test_get_session_context_manager_with_exception(self, db_config, mock_session):
        db = Database(db_config)
        mock_session.commit.side_effect = SQLAlchemyError("Test error")
        with pytest.raises(DatabaseError):
            with db.get_session():
                pass  # The error is raised on commit
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()

    def test_close_engine(self, db_config, mock_engine):
        db = Database(db_config)
        db.close_engine()
        mock_engine.dispose.assert_called_once()


class TestUserThreadTable:
    """UserThreadTable 模型測試"""

    def test_user_thread_creation(self):
        import datetime
        user_thread = UserThreadTable(
            user_id='user_123',
            thread_id='thread_456',
            created_at=datetime.datetime.utcnow()
        )
        assert user_thread.user_id == 'user_123'
        assert user_thread.thread_id == 'thread_456'
        assert isinstance(user_thread.created_at, datetime.datetime)

    def test_user_thread_tablename(self):
        assert UserThreadTable.__tablename__ == 'user_thread_table'
