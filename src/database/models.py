"""
SQLAlchemy ORM Models and Database Configuration
"""
import os
from datetime import datetime
from typing import Optional
from sqlalchemy import create_engine, Column, String, Text, DateTime, Integer, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
import logging

logger = logging.getLogger(__name__)

Base = declarative_base()

class UserThreadTable(Base):
    """原有的 OpenAI thread 管理表"""
    __tablename__ = 'user_thread_table'
    
    user_id = Column(String(255), primary_key=True)
    platform = Column(String(50), primary_key=True, default='line')
    thread_id = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<UserThread(user_id='{self.user_id}', platform='{self.platform}', thread_id='{self.thread_id}')>"

class SimpleConversationHistory(Base):
    """簡化的對話歷史表（適用於非 OpenAI 模型）"""
    __tablename__ = 'simple_conversation_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False)
    platform = Column(String(50), nullable=False, default='line')
    model_provider = Column(String(50), nullable=False, index=True)  # 'anthropic', 'gemini', 'ollama'
    role = Column(String(20), nullable=False)  # 'user', 'assistant'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # 複合 index 提升查詢效率
    __table_args__ = (
        Index('idx_conversation_user_platform', 'user_id', 'platform'),
        Index('idx_conversation_user_platform_provider', 'user_id', 'platform', 'model_provider'),
    )
    
    def __repr__(self):
        return f"<Conversation(user_id='{self.user_id}', platform='{self.platform}', provider='{self.model_provider}', role='{self.role}')>"

class DatabaseManager:
    """資料庫連線管理器 - 高可用性配置"""
    
    def __init__(self, database_url: str = None):
        if not database_url:
            database_url = self._build_database_url()
        
        # 根據資料庫類型設定連線參數
        connect_args = {}
        if database_url.startswith('postgresql'):
            # PostgreSQL 特定設定
            connect_args = {
                "sslmode": "require",
                "connect_timeout": 10,
                "keepalives_idle": 600,    # TCP keepalive
                "keepalives_interval": 30,
                "keepalives_count": 3,
            }
        elif database_url.startswith('sqlite'):
            # SQLite 特定設定
            connect_args = {
                "check_same_thread": False,
                "timeout": 20
            }
        
        # 高可用性連線池配置
        self.engine = create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=20,          # 連線池大小
            max_overflow=30,       # 最大溢出連線
            pool_timeout=30,       # 連線等待超時
            pool_recycle=3600,     # 連線回收時間（1小時）
            pool_pre_ping=True,    # 連線前測試
            echo=False,            # 生產環境關閉 SQL 日誌
            connect_args=connect_args
        )
        
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
    
    def _build_database_url(self) -> str:
        """從配置或環境變數建構資料庫 URL"""
        try:
            from ..core.config import load_config
            config = load_config()
            db_config = config.get('db', {})
            
            host = db_config.get('host', os.getenv('DB_HOST', 'localhost'))
            port = db_config.get('port', os.getenv('DB_PORT', '5432'))
            database = db_config.get('database', os.getenv('DB_NAME', 'chatbot'))
            username = db_config.get('username', os.getenv('DB_USER', 'postgres'))
            password = db_config.get('password', os.getenv('DB_PASSWORD', ''))
            
            return f"postgresql://{username}:{password}@{host}:{port}/{database}"
            
        except Exception as e:
            logger.warning(f"Failed to load config, using environment variables: {e}")
            # 回退到環境變數
            return os.getenv('DATABASE_URL', 'postgresql://postgres:password@localhost:5432/chatbot')
    
    def get_session(self) -> Session:
        """取得資料庫 session"""
        return self.SessionLocal()
    
    def create_all_tables(self):
        """建立所有表格"""
        Base.metadata.create_all(bind=self.engine)
        logger.info("All database tables created successfully")
    
    def check_connection(self) -> bool:
        """檢查資料庫連線"""
        try:
            from sqlalchemy import text
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False
    
    def close(self):
        """關閉資料庫連線"""
        self.engine.dispose()
        try:
            logger.info("Database connection closed")
        except (ValueError, OSError):
            # Logger may be closed already during cleanup
            pass

# 全域資料庫管理器實例
_db_manager: Optional[DatabaseManager] = None

def get_database_manager() -> DatabaseManager:
    """取得全域資料庫管理器"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager

def get_db_session() -> Session:
    """取得資料庫 session（便利函數）"""
    return get_database_manager().get_session()