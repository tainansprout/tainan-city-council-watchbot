import datetime
import threading
from ..core.logger import get_logger
from contextlib import contextmanager
from typing import Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ..core.exceptions import DatabaseError
from .models import Base, UserThreadTable

logger = get_logger(__name__)


class Database:
    def __init__(self, config):
        self.config = config
        self.engine = self._create_engine()
        self.SessionLocal = sessionmaker(bind=self.engine)
        logger.debug('create SQLAlchemy ORM engine')

    def _create_engine(self):
        """建立資料庫引擎"""
        connection_string = self._build_connection_string()
        ssl_args = self._get_ssl_args()

        return create_engine(
            connection_string,
            connect_args=ssl_args,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_pre_ping=True,
            pool_recycle=1800,
            echo=False
        )

    def _build_connection_string(self) -> str:
        """建立資料庫連線字串"""
        host = self.config['host']
        port = self.config['port']
        db_name = self.config['db_name']
        user = self.config['user']
        password = self.config['password']

        return f"postgresql://{user}:{password}@{host}:{port}/{db_name}"

    def _get_ssl_args(self) -> dict:
        """取得 SSL 參數"""
        ssl_args = {}

        if 'sslmode' in self.config:
            ssl_args['sslmode'] = self.config['sslmode']
        if 'sslrootcert' in self.config:
            ssl_args['sslrootcert'] = self.config['sslrootcert']
        if 'sslcert' in self.config:
            ssl_args['sslcert'] = self.config['sslcert']
        if 'sslkey' in self.config:
            ssl_args['sslkey'] = self.config['sslkey']

        return ssl_args

    @contextmanager
    def get_session(self):
        """使用 context manager 管理 session"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database error: {e}")
            raise DatabaseError(f"Database operation failed: {e}")
        finally:
            session.close()

    def query_thread(self, user_id: str, platform: str = 'line') -> Optional[str]:
        """查詢用戶對話串"""
        with self.get_session() as session:
            user_thread = session.query(UserThreadTable).filter(
                UserThreadTable.user_id == user_id,
                UserThreadTable.platform == platform
            ).first()
            return user_thread.thread_id if user_thread else None

    def save_thread(self, user_id: str, thread_id: str, platform: str = 'line'):
        """儲存用戶對話串"""
        with self.get_session() as session:
            user_thread = session.query(UserThreadTable).filter(
                UserThreadTable.user_id == user_id,
                UserThreadTable.platform == platform
            ).first()

            if user_thread:
                user_thread.thread_id = thread_id
                user_thread.created_at = datetime.datetime.utcnow()
            else:
                user_thread = UserThreadTable(
                    user_id=user_id,
                    platform=platform,
                    thread_id=thread_id,
                    created_at=datetime.datetime.utcnow()
                )
                session.add(user_thread)

    def delete_thread(self, user_id: str, platform: str = 'line'):
        """刪除用戶對話串"""
        with self.get_session() as session:
            session.query(UserThreadTable).filter(
                UserThreadTable.user_id == user_id,
                UserThreadTable.platform == platform
            ).delete()

    def close_engine(self):
        """關閉資料庫引擎"""
        self.engine.dispose()
        try:
            logger.debug('close SQLAlchemy engine.')
        except (ValueError, OSError):
            pass

    def check_connection(self) -> bool:
        """檢查資料庫連線是否正常"""
        try:
            from sqlalchemy import text
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database connection check failed: {e}")
            return False

    def get_connection_info(self) -> dict:
        """取得連線池資訊（用於監控）"""
        pool = self.engine.pool
        return {
            'pool_size': pool.size(),
            'checked_in': pool.checkedin(),
            'checked_out': pool.checkedout(),
            'overflow': pool.overflow(),
            'invalid': getattr(pool, 'invalidated', 0)
        }


# 全局資料庫實例管理
_global_database = None
_database_lock = threading.Lock()


def get_global_database():
    """取得全局資料庫實例（線程安全單例模式）"""
    global _global_database
    if _global_database is None:
        with _database_lock:
            if _global_database is None:
                from ..core.config import ConfigManager
                config = ConfigManager().get_config()
                _global_database = Database(config['db'])
                logger.info("Created global database instance")
    return _global_database


def reset_global_database():
    """重置全局資料庫實例（用於 Gunicorn fork 後重建連線池）"""
    global _global_database
    with _database_lock:
        if _global_database is not None:
            _global_database.engine.dispose()
            _global_database = None


# 統一的 session context manager 便利函數
def get_db_session():
    """取得資料庫 session context manager（統一入口）"""
    return get_global_database().get_session()


# 向後兼容性函數
def get_thread_id_by_user_id(user_id: str, platform: str = 'line') -> Optional[str]:
    """取得用戶的對話串 ID"""
    database = get_global_database()
    return database.query_thread(user_id, platform)


def save_thread_id(user_id: str, thread_id: str, platform: str = 'line'):
    """儲存用戶的對話串 ID"""
    database = get_global_database()
    return database.save_thread(user_id, thread_id, platform)


def delete_thread_id(user_id: str, platform: str = 'line'):
    """刪除用戶的對話串 ID"""
    database = get_global_database()
    return database.delete_thread(user_id, platform)
