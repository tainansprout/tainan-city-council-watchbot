import datetime
from ..core.logger import get_logger
from contextlib import contextmanager
from typing import Optional
from sqlalchemy import create_engine, Column, String, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from ..core.exceptions import DatabaseError

logger = get_logger(__name__)

# CREATE TABLE user_thread_table (
#     user_id VARCHAR(255) PRIMARY KEY,
#     thread_id VARCHAR(255),
#     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
# );

Base = declarative_base()

class UserThreadTable(Base):
    __tablename__ = 'user_thread_table'

    user_id = Column(String(255), primary_key=True)
    platform = Column(String(50), primary_key=True, default='line')
    thread_id = Column(String(255))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Database:
    def __init__(self, config):
        self.config = config
        self.engine = self._create_engine()
        self.SessionLocal = sessionmaker(bind=self.engine)
        try:

            logger.debug('create SQLAlchemy ORM engine')

        except ValueError:

            pass

    def _create_engine(self):
        """建立資料庫引擎with最佳化設定"""
        connection_string = self._build_connection_string()
        ssl_args = self._get_ssl_args()
        
        return create_engine(
            connection_string,
            connect_args=ssl_args,
            pool_size=5,            # 優化：降低基本連線數（適配 2 worker gunicorn）
            max_overflow=10,        # 優化：降低最大溢出數
            pool_pre_ping=True,     # 連線健康檢查
            pool_recycle=1800,      # 優化：30分鐘回收連線，減少記憶體使用
            echo=False              # 生產環境關閉SQL日誌
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
            try:

                logger.error(f"Database error: {e}")

            except ValueError:

                pass
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
            # Logger may be closed already during cleanup
            pass
    
    def get_connection_info(self) -> dict:
        """取得連線池資訊（用於監控）"""
        pool = self.engine.pool
        return {
            'pool_size': pool.size(),
            'checked_in': pool.checkedin(),
            'checked_out': pool.checkedout(),
            'overflow': pool.overflow(),
            'invalid': getattr(pool, 'invalidated', 0)  # 使用 invalidated 或默認值
        }


# 全局資料庫實例管理 - 修復記憶體洩漏
_global_database = None
_database_lock = None

def _get_database_lock():
    """獲取資料庫鎖（延遲初始化）"""
    global _database_lock
    if _database_lock is None:
        import threading
        _database_lock = threading.Lock()
    return _database_lock

def get_global_database():
    """取得全局資料庫實例（線程安全單例模式）"""
    global _global_database
    if _global_database is None:
        with _get_database_lock():
            # 雙重檢查鎖定模式
            if _global_database is None:
                from ..core.config import ConfigManager
                config = ConfigManager().get_config()
                _global_database = Database(config['db'])
                logger.info("Created global database instance")
    return _global_database

# 向後兼容性函數 - 供 OpenAI 模型使用（已優化）
def get_thread_id_by_user_id(user_id: str, platform: str = 'line') -> Optional[str]:
    """取得用戶的對話串 ID（優化：使用全局實例）"""
    database = get_global_database()  # ✅ 使用全局實例
    return database.query_thread(user_id, platform)

def save_thread_id(user_id: str, thread_id: str, platform: str = 'line'):
    """儲存用戶的對話串 ID（優化：使用全局實例）"""
    database = get_global_database()  # ✅ 使用全局實例
    return database.save_thread(user_id, thread_id, platform)

def delete_thread_id(user_id: str, platform: str = 'line'):
    """刪除用戶的對話串 ID（優化：使用全局實例）"""
    database = get_global_database()  # ✅ 使用全局實例
    return database.delete_thread(user_id, platform)