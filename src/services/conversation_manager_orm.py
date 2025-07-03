"""
ORM-based Conversation Manager
使用 SQLAlchemy ORM 管理對話歷史
"""
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from ..models.database import get_db_session, SimpleConversationHistory
import logging

logger = logging.getLogger(__name__)

class ORMConversationManager:
    """基於 SQLAlchemy ORM 的對話管理器"""
    
    def __init__(self):
        self.session_factory = get_db_session
    
    def add_message(self, user_id: str, model_provider: str, role: str, content: str, platform: str = 'line') -> bool:
        """新增對話訊息到資料庫"""
        try:
            with self.session_factory() as session:
                conversation = SimpleConversationHistory(
                    user_id=user_id,
                    platform=platform,
                    model_provider=model_provider,
                    role=role,
                    content=content
                )
                session.add(conversation)
                session.commit()
                
                logger.debug(f"Added conversation message for user {user_id} on platform {platform} ({model_provider})")
                return True
                
        except Exception as e:
            logger.error(f"Failed to add conversation message: {e}")
            return False
    
    def get_recent_conversations(self, user_id: str, model_provider: str, limit: int = 10, platform: str = 'line') -> List[Dict]:
        """取得用戶最近的對話歷史"""
        try:
            with self.session_factory() as session:
                conversations = session.query(SimpleConversationHistory).filter(
                    SimpleConversationHistory.user_id == user_id,
                    SimpleConversationHistory.platform == platform,
                    SimpleConversationHistory.model_provider == model_provider
                ).order_by(
                    desc(SimpleConversationHistory.created_at)
                ).limit(limit * 2).all()  # 取雙倍確保有足夠對話
                
                # 轉換為字典格式，並按時間正序排列
                result = []
                for conv in reversed(conversations):  # 反轉以獲得正序
                    result.append({
                        'role': conv.role,
                        'content': conv.content,
                        'created_at': conv.created_at.isoformat() if conv.created_at else None,
                        'model_provider': conv.model_provider
                    })
                
                logger.debug(f"Retrieved {len(result)} conversations for user {user_id} on platform {platform} ({model_provider})")
                return result
                
        except Exception as e:
            logger.error(f"Failed to get conversations for user {user_id}: {e}")
            return []
    
    def clear_user_history(self, user_id: str, model_provider: str, platform: str = 'line') -> bool:
        """清除指定用戶和模型的對話歷史"""
        try:
            with self.session_factory() as session:
                deleted_count = session.query(SimpleConversationHistory).filter(
                    SimpleConversationHistory.user_id == user_id,
                    SimpleConversationHistory.platform == platform,
                    SimpleConversationHistory.model_provider == model_provider
                ).delete()
                
                session.commit()
                
                logger.info(f"Cleared {deleted_count} conversation records for user {user_id} on platform {platform} ({model_provider})")
                return True
                
        except Exception as e:
            logger.error(f"Failed to clear conversation history for user {user_id}: {e}")
            return False
    
    def get_conversation_count(self, user_id: str, model_provider: str = None, platform: str = 'line') -> int:
        """取得用戶的對話數量"""
        try:
            with self.session_factory() as session:
                query = session.query(SimpleConversationHistory).filter(
                    SimpleConversationHistory.user_id == user_id,
                    SimpleConversationHistory.platform == platform
                )
                
                if model_provider:
                    query = query.filter(
                        SimpleConversationHistory.model_provider == model_provider
                    )
                
                count = query.count()
                return count
                
        except Exception as e:
            logger.error(f"Failed to get conversation count for user {user_id}: {e}")
            return 0
    
    def cleanup_old_conversations(self, days_to_keep: int = 30) -> int:
        """清理舊的對話記錄（資料庫維護）"""
        try:
            from datetime import datetime, timedelta
            
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            with self.session_factory() as session:
                deleted_count = session.query(SimpleConversationHistory).filter(
                    SimpleConversationHistory.created_at < cutoff_date
                ).delete()
                
                session.commit()
                
                logger.info(f"Cleaned up {deleted_count} old conversation records (older than {days_to_keep} days)")
                return deleted_count
                
        except Exception as e:
            logger.error(f"Failed to cleanup old conversations: {e}")
            return 0

# 向後兼容性：保持原有接口
def get_conversation_manager():
    """取得對話管理器實例（ORM 版本）"""
    return ORMConversationManager()