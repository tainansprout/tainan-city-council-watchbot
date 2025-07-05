"""
ORM-based Conversation Manager
使用 SQLAlchemy ORM 管理對話歷史
整合版本，包含快取、統計和清理功能
"""
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime, timedelta
from ..database.models import get_db_session, SimpleConversationHistory
from ..core.logger import get_logger

logger = get_logger(__name__)

class ORMConversationManager:
    """基於 SQLAlchemy ORM 的對話管理器（完整版）"""
    
    def __init__(self):
        self.session_factory = get_db_session
        # 記憶體快取最近對話
        self.memory_cache = {}
        self.cache_ttl = 300  # 5分鐘快取
        
        logger.info("ORMConversationManager initialized with caching support")
    
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
                
                # 清除快取，強制下次重新載入
                cache_key = f"{user_id}:{platform}:{model_provider}"
                if cache_key in self.memory_cache:
                    del self.memory_cache[cache_key]
                
                logger.debug(f"Added conversation message for user {user_id} on platform {platform} ({model_provider})")
                return True
                
        except Exception as e:
            logger.error(f"Failed to add conversation message: {e}")
            return False
    
    def get_recent_conversations(self, user_id: str, model_provider: str, limit: int = 5, platform: str = 'line') -> List[Dict]:
        """取得用戶最近的對話歷史（支援快取）"""
        try:
            cache_key = f"{user_id}:{platform}:{model_provider}"
            
            # 檢查快取
            if cache_key in self.memory_cache:
                cache_data = self.memory_cache[cache_key]
                if datetime.now() - cache_data['timestamp'] < timedelta(seconds=self.cache_ttl):
                    logger.debug(f"Cache hit for user {user_id} on platform {platform} ({model_provider})")
                    return cache_data['conversations'][:limit * 2]  # 取雙倍以防萬一
            
            # 從資料庫查詢
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
                
                # 更新快取
                self.memory_cache[cache_key] = {
                    'conversations': result,
                    'timestamp': datetime.now()
                }
                
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
                
                # 清除快取
                cache_key = f"{user_id}:{platform}:{model_provider}"
                if cache_key in self.memory_cache:
                    del self.memory_cache[cache_key]
                
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
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            with self.session_factory() as session:
                deleted_count = session.query(SimpleConversationHistory).filter(
                    SimpleConversationHistory.created_at < cutoff_date
                ).delete()
                
                session.commit()
                
                logger.info(f"Cleaned up {deleted_count} old conversation records (older than {days_to_keep} days)")
                
                # 清除所有快取
                self.memory_cache.clear()
                
                return deleted_count
                
        except Exception as e:
            logger.error(f"Failed to cleanup old conversations: {e}")
            return 0
    
    def get_user_statistics(self, user_id: str, platform: str = 'line') -> Dict:
        """
        獲取用戶統計資訊
        
        Args:
            user_id: 用戶 ID
            platform: 平台名稱
            
        Returns:
            Dict: 統計資訊
        """
        try:
            with self.session_factory() as session:
                # 使用 ORM 查詢統計資訊
                from sqlalchemy import func
                
                stats_query = session.query(
                    SimpleConversationHistory.model_provider,
                    func.count(SimpleConversationHistory.id).label('message_count'),
                    func.max(SimpleConversationHistory.created_at).label('last_activity')
                ).filter(
                    SimpleConversationHistory.user_id == user_id,
                    SimpleConversationHistory.platform == platform
                ).group_by(
                    SimpleConversationHistory.model_provider
                ).all()
                
                stats = {}
                for provider, count, last_activity in stats_query:
                    stats[provider] = {
                        'message_count': count,
                        'last_activity': last_activity.isoformat() if last_activity else None
                    }
                
                logger.debug(f"Retrieved statistics for user {user_id} on platform {platform}: {len(stats)} providers")
                return stats
                
        except Exception as e:
            logger.error(f"Failed to get user statistics for user {user_id}: {e}")
            return {}


# 全域實例（單例模式）
_conversation_manager = None

def get_conversation_manager() -> ORMConversationManager:
    """取得對話管理器實例（單例模式）"""
    global _conversation_manager
    if _conversation_manager is None:
        _conversation_manager = ORMConversationManager()
    return _conversation_manager