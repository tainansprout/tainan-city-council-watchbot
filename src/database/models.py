"""
SQLAlchemy ORM Models
純 ORM 模型定義，不包含 engine 或 session 管理
"""
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Integer, Index
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class UserThreadTable(Base):
    """OpenAI thread 管理表"""
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
    model_provider = Column(String(50), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index('idx_conversation_user_platform', 'user_id', 'platform'),
        Index('idx_conversation_user_platform_provider', 'user_id', 'platform', 'model_provider'),
    )

    def __repr__(self):
        return f"<Conversation(user_id='{self.user_id}', platform='{self.platform}', provider='{self.model_provider}', role='{self.role}')>"
