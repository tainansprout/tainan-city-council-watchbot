"""
資料庫操作工具
提供常用的資料庫操作功能
"""
import logging
from typing import Dict, List, Optional
from sqlalchemy import text, func
from .connection import Database
from .models import get_db_session, UserThreadTable, SimpleConversationHistory

logger = logging.getLogger(__name__)


class DatabaseOperations:
    """資料庫操作工具類"""
    
    def __init__(self):
        # 使用 models 中的 DatabaseManager 而不是 connection 中的 Database
        self.session_factory = get_db_session
    
    def health_check(self) -> Dict[str, any]:
        """資料庫健康檢查"""
        try:
            with self.session_factory() as session:
                # 測試基本查詢
                result = session.execute(text("SELECT 1 as test")).fetchone()
                
                # 檢查表是否存在
                tables_exist = self._check_tables_exist(session)
                
                # 獲取統計資訊
                stats = self._get_database_stats(session)
                
                return {
                    "status": "healthy",
                    "connection": True,
                    "tables": tables_exist,
                    "stats": stats
                }
                
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "connection": False,
                "error": str(e)
            }
    
    def _check_tables_exist(self, session) -> Dict[str, bool]:
        """檢查必要的表是否存在"""
        tables = {
            "user_thread_table": False,
            "simple_conversation_history": False
        }
        
        try:
            for table_name in tables.keys():
                result = session.execute(text(
                    f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table_name}')"
                )).fetchone()
                tables[table_name] = result[0] if result else False
                
        except Exception as e:
            logger.error(f"Error checking table existence: {e}")
            
        return tables
    
    def _get_database_stats(self, session) -> Dict[str, any]:
        """獲取資料庫統計資訊"""
        try:
            stats = {}
            
            # 用戶線程統計
            thread_count = session.query(func.count(UserThreadTable.user_id)).scalar()
            stats["total_threads"] = thread_count or 0
            
            # 對話歷史統計
            conversation_count = session.query(func.count(SimpleConversationHistory.id)).scalar()
            stats["total_conversations"] = conversation_count or 0
            
            # 平台統計
            platform_stats = session.query(
                SimpleConversationHistory.platform,
                func.count(SimpleConversationHistory.id)
            ).group_by(SimpleConversationHistory.platform).all()
            
            stats["conversations_by_platform"] = {
                platform: count for platform, count in platform_stats
            }
            
            # 模型提供商統計
            provider_stats = session.query(
                SimpleConversationHistory.model_provider,
                func.count(SimpleConversationHistory.id)
            ).group_by(SimpleConversationHistory.model_provider).all()
            
            stats["conversations_by_provider"] = {
                provider: count for provider, count in provider_stats
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {}
    
    def cleanup_old_data(self, days_to_keep: int = 30) -> Dict[str, int]:
        """清理舊資料"""
        try:
            from datetime import datetime, timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            with self.session_factory() as session:
                # 清理舊的對話記錄
                deleted_conversations = session.query(SimpleConversationHistory).filter(
                    SimpleConversationHistory.created_at < cutoff_date
                ).delete()
                
                # 清理舊的線程記錄
                deleted_threads = session.query(UserThreadTable).filter(
                    UserThreadTable.created_at < cutoff_date
                ).delete()
                
                session.commit()
                
                result = {
                    "deleted_conversations": deleted_conversations,
                    "deleted_threads": deleted_threads
                }
                
                logger.info(f"Cleanup completed: {result}")
                return result
                
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            return {"error": str(e)}
    
    def get_user_summary(self, user_id: str, platform: str = 'line') -> Dict[str, any]:
        """獲取用戶摘要資訊"""
        try:
            with self.session_factory() as session:
                # 線程資訊
                thread = session.query(UserThreadTable).filter(
                    UserThreadTable.user_id == user_id,
                    UserThreadTable.platform == platform
                ).first()
                
                # 對話統計
                conversation_stats = session.query(
                    SimpleConversationHistory.model_provider,
                    func.count(SimpleConversationHistory.id),
                    func.max(SimpleConversationHistory.created_at)
                ).filter(
                    SimpleConversationHistory.user_id == user_id,
                    SimpleConversationHistory.platform == platform
                ).group_by(SimpleConversationHistory.model_provider).all()
                
                return {
                    "user_id": user_id,
                    "platform": platform,
                    "has_thread": thread is not None,
                    "thread_id": thread.thread_id if thread else None,
                    "conversation_stats": {
                        provider: {
                            "count": count,
                            "last_activity": last_activity.isoformat() if last_activity else None
                        }
                        for provider, count, last_activity in conversation_stats
                    }
                }
                
        except Exception as e:
            logger.error(f"Error getting user summary: {e}")
            return {"error": str(e)}


# 全域實例
_db_operations = None

def get_database_operations() -> DatabaseOperations:
    """獲取資料庫操作實例（單例模式）"""
    global _db_operations
    if _db_operations is None:
        _db_operations = DatabaseOperations()
    return _db_operations