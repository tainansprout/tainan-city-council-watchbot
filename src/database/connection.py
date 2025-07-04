import datetime
import logging
from contextlib import contextmanager
from typing import Optional
from sqlalchemy import create_engine, Column, String, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from ..core.exceptions import DatabaseError

logger = logging.getLogger(__name__)

# CREATE TABLE user_thread_table (
#     user_id VARCHAR(255) PRIMARY KEY,
#     thread_id VARCHAR(255),
#     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
# );

Base = declarative_base()

class UserThread(Base):
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
        logger.debug('create SQLAlchemy ORM engine')

    def _create_engine(self):
        """建立資料庫引擎with最佳化設定"""
        connection_string = self._build_connection_string()
        ssl_args = self._get_ssl_args()
        
        return create_engine(
            connection_string,
            connect_args=ssl_args,
            pool_size=10,           # 增加連線池大小
            max_overflow=20,        # 允許超過連線池的連線數
            pool_pre_ping=True,     # 連線健康檢查
            pool_recycle=3600,      # 1小時回收連線
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
            logger.error(f"Database error: {e}")
            raise DatabaseError(f"Database operation failed: {e}")
        finally:
            session.close()

    def query_thread(self, user_id: str, platform: str = 'line') -> Optional[str]:
        """查詢用戶對話串"""
        with self.get_session() as session:
            user_thread = session.query(UserThread).filter(
                UserThread.user_id == user_id,
                UserThread.platform == platform
            ).first()
            return user_thread.thread_id if user_thread else None

    def save_thread(self, user_id: str, thread_id: str, platform: str = 'line'):
        """儲存用戶對話串"""
        with self.get_session() as session:
            user_thread = session.query(UserThread).filter(
                UserThread.user_id == user_id,
                UserThread.platform == platform
            ).first()
            
            if user_thread:
                user_thread.thread_id = thread_id
                user_thread.created_at = datetime.datetime.utcnow()
            else:
                user_thread = UserThread(
                    user_id=user_id,
                    platform=platform,
                    thread_id=thread_id,
                    created_at=datetime.datetime.utcnow()
                )
                session.add(user_thread)

    def delete_thread(self, user_id: str, platform: str = 'line'):
        """刪除用戶對話串"""
        with self.get_session() as session:
            session.query(UserThread).filter(
                UserThread.user_id == user_id,
                UserThread.platform == platform
            ).delete()

    def close_engine(self):
        """關閉資料庫引擎"""
        self.engine.dispose()
        logger.debug('close SQLAlchemy engine.')
    
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


# 向後兼容性函數 - 供 OpenAI 模型使用
def get_thread_id_by_user_id(user_id: str, platform: str = 'line') -> Optional[str]:
    """取得用戶的對話串 ID（兼容性函數）"""
    from ..core.config import load_config
    config = load_config()
    db = Database(config['db'])
    return db.query_thread(user_id, platform)


def save_thread_id(user_id: str, thread_id: str, platform: str = 'line'):
    """儲存用戶的對話串 ID（兼容性函數）"""
    from ..core.config import load_config
    config = load_config()
    db = Database(config['db'])
    return db.save_thread(user_id, thread_id, platform)


def delete_thread_id(user_id: str, platform: str = 'line'):
    """刪除用戶的對話串 ID（兼容性函數）"""
    from ..core.config import load_config
    config = load_config()
    db = Database(config['db'])
    return db.delete_thread(user_id, platform)