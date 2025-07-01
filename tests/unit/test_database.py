import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.exc import SQLAlchemyError

from src.database import Database, UserThread, UserThread
from src.core.exceptions import DatabaseError


class TestDatabase:
    """資料庫單元測試"""
    
    @pytest.fixture
    def db_config(self):
        return {
            'host': 'localhost',
            'port': 5432,
            'db_name': 'test_db',
            'user': 'test_user',
            'password': 'test_password',
            'sslmode': 'disable'
        }
    
    @pytest.fixture
    def mock_engine(self):
        engine = Mock()
        engine.pool.size.return_value = 10
        engine.pool.checkedin.return_value = 2
        engine.pool.checkedout.return_value = 1
        engine.pool.overflow.return_value = 0
        engine.pool.invalid.return_value = 0
        return engine
    
    @pytest.fixture
    def mock_session(self):
        session = Mock()
        session.commit = Mock()
        session.rollback = Mock()
        session.close = Mock()
        return session
    
    @patch('sqlalchemy.create_engine')
    @patch('sqlalchemy.orm.sessionmaker')
    def test_database_init(self, mock_sessionmaker, mock_create_engine, db_config):
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine
        
        db = Database(db_config)
        
        assert db.config == db_config
        assert db.engine == mock_engine
        mock_create_engine.assert_called_once()
        mock_sessionmaker.assert_called_once_with(bind=mock_engine)
    
    def test_build_connection_string(self, db_config):
        with patch('sqlalchemy.create_engine') as mock_create_engine, \
             patch('sqlalchemy.orm.sessionmaker'):
            
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
        
        with patch('sqlalchemy.create_engine'), \
             patch('sqlalchemy.orm.sessionmaker'):
            
            db = Database(db_config)
            ssl_args = db._get_ssl_args()
            
            assert ssl_args['sslmode'] == 'require'
            assert ssl_args['sslrootcert'] == '/path/to/ca.crt'
            assert ssl_args['sslcert'] == '/path/to/client.crt'
            assert ssl_args['sslkey'] == '/path/to/client.key'
    
    @patch('sqlalchemy.create_engine')
    @patch('sqlalchemy.orm.sessionmaker')
    def test_query_thread_exists(self, mock_sessionmaker, mock_create_engine, db_config):
        # 設定模擬
        mock_session = Mock()
        mock_sessionmaker.return_value.return_value = mock_session
        
        mock_user_thread = Mock()
        mock_user_thread.thread_id = 'thread_123'
        mock_session.query.return_value.filter.return_value.first.return_value = mock_user_thread
        
        db = Database(db_config)
        
        # 模擬 context manager
        with patch.object(db, 'get_session') as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session
            mock_get_session.return_value.__exit__.return_value = None
            
            result = db.query_thread('user_123')
            
            assert result == 'thread_123'
            mock_session.query.assert_called_once_with(UserThread)
    
    @patch('sqlalchemy.create_engine')
    @patch('sqlalchemy.orm.sessionmaker')
    def test_query_thread_not_exists(self, mock_sessionmaker, mock_create_engine, db_config):
        # 設定模擬
        mock_session = Mock()
        mock_sessionmaker.return_value.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        db = Database(db_config)
        
        with patch.object(db, 'get_session') as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session
            mock_get_session.return_value.__exit__.return_value = None
            
            result = db.query_thread('user_123')
            
            assert result is None
    
    @patch('sqlalchemy.create_engine')
    @patch('sqlalchemy.orm.sessionmaker')
    def test_save_thread_new_user(self, mock_sessionmaker, mock_create_engine, db_config):
        mock_session = Mock()
        mock_sessionmaker.return_value.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        db = Database(db_config)
        
        with patch.object(db, 'get_session') as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session
            mock_get_session.return_value.__exit__.return_value = None
            
            db.save_thread('user_123', 'thread_456')
            
            mock_session.add.assert_called_once()
    
    @patch('sqlalchemy.create_engine')
    @patch('sqlalchemy.orm.sessionmaker')
    def test_save_thread_existing_user(self, mock_sessionmaker, mock_create_engine, db_config):
        mock_session = Mock()
        mock_sessionmaker.return_value.return_value = mock_session
        
        mock_user_thread = Mock()
        mock_session.query.return_value.filter.return_value.first.return_value = mock_user_thread
        
        db = Database(db_config)
        
        with patch.object(db, 'get_session') as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session
            mock_get_session.return_value.__exit__.return_value = None
            
            db.save_thread('user_123', 'thread_456')
            
            assert mock_user_thread.thread_id == 'thread_456'
            # 不應該調用 add，因為是更新現有記錄
            mock_session.add.assert_not_called()
    
    @patch('sqlalchemy.create_engine')
    @patch('sqlalchemy.orm.sessionmaker')
    def test_delete_thread(self, mock_sessionmaker, mock_create_engine, db_config):
        mock_session = Mock()
        mock_sessionmaker.return_value.return_value = mock_session
        
        db = Database(db_config)
        
        with patch.object(db, 'get_session') as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session
            mock_get_session.return_value.__exit__.return_value = None
            
            db.delete_thread('user_123')
            
            mock_session.query.assert_called_once_with(UserThread)
            mock_session.query.return_value.filter.return_value.delete.assert_called_once()
    
    @patch('sqlalchemy.create_engine')
    @patch('sqlalchemy.orm.sessionmaker')
    def test_get_connection_info(self, mock_sessionmaker, mock_create_engine, mock_engine, db_config):
        mock_create_engine.return_value = mock_engine
        
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
    
    @patch('sqlalchemy.create_engine')
    @patch('sqlalchemy.orm.sessionmaker')
    def test_get_session_context_manager(self, mock_sessionmaker, mock_create_engine, db_config):
        mock_session = Mock()
        mock_sessionmaker.return_value.return_value = mock_session
        
        db = Database(db_config)
        
        # 測試正常情況
        with db.get_session() as session:
            assert session == mock_session
            session.execute('SELECT 1')
        
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()
    
    @patch('sqlalchemy.create_engine')
    @patch('sqlalchemy.orm.sessionmaker')
    def test_get_session_context_manager_with_exception(self, mock_sessionmaker, mock_create_engine, db_config):
        mock_session = Mock()
        mock_sessionmaker.return_value.return_value = mock_session
        
        db = Database(db_config)
        
        # 測試異常情況
        try:
            with db.get_session() as session:
                raise SQLAlchemyError("Database error")
        except DatabaseError:
            pass  # 預期的異常
        
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()
        # 異常情況下不應該 commit
        mock_session.commit.assert_not_called()
    
    @patch('sqlalchemy.create_engine')
    @patch('sqlalchemy.orm.sessionmaker')
    def test_close_engine(self, mock_sessionmaker, mock_create_engine, mock_engine, db_config):
        mock_create_engine.return_value = mock_engine
        
        db = Database(db_config)
        db.close_engine()
        
        mock_engine.dispose.assert_called_once()


class TestUserThread:
    """UserThread 模型測試"""
    
    def test_user_thread_creation(self):
        import datetime
        
        user_thread = UserThread(
            user_id='user_123',
            thread_id='thread_456',
            created_at=datetime.datetime.utcnow()
        )
        
        assert user_thread.user_id == 'user_123'
        assert user_thread.thread_id == 'thread_456'
        assert isinstance(user_thread.created_at, datetime.datetime)
    
    def test_user_thread_tablename(self):
        assert UserThread.__tablename__ == 'user_thread_table'