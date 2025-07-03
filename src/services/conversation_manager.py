"""
簡單對話歷史管理服務
用於非 OpenAI 模型的對話歷史管理
"""

import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from ..core.config import load_config

logger = logging.getLogger(__name__)


class SimpleConversationManager:
    """簡單的對話歷史管理服務"""
    
    def __init__(self, db_connection=None):
        """
        初始化對話管理器
        
        Args:
            db_connection: 資料庫連接，如果為 None 則從配置創建
        """
        if db_connection:
            self.db = db_connection
        else:
            config = load_config()
            self.db = self._create_db_connection(config)
        
        # 記憶體快取最近對話
        self.memory_cache = {}
        self.cache_ttl = 300  # 5分鐘快取
        
        logger.info("SimpleConversationManager initialized")
    
    def _create_db_connection(self, config):
        """從配置創建資料庫連接"""
        try:
            db_config = config.get('db', {})
            
            # 建立連接字串
            host = db_config.get('host', 'localhost')
            port = db_config.get('port', 5432)
            db_name = db_config.get('db_name', 'postgres')
            user = db_config.get('user', 'postgres')
            password = db_config.get('password', '')
            
            connection_string = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
            
            # SSL 參數
            ssl_args = {}
            if 'sslmode' in db_config:
                ssl_args['sslmode'] = db_config['sslmode']
            if 'sslrootcert' in db_config:
                ssl_args['sslrootcert'] = db_config['sslrootcert']
            if 'sslcert' in db_config:
                ssl_args['sslcert'] = db_config['sslcert']
            if 'sslkey' in db_config:
                ssl_args['sslkey'] = db_config['sslkey']
            
            engine = create_engine(connection_string, connect_args=ssl_args)
            Session = sessionmaker(bind=engine)
            return Session()
        except Exception as e:
            logger.error(f"Failed to create database connection: {e}")
            return None
    
    def add_message(self, user_id: str, model_provider: str, role: str, content: str, platform: str = 'line') -> bool:
        """
        添加訊息到對話歷史
        
        Args:
            user_id: 用戶 ID
            model_provider: 模型提供商 ('anthropic', 'gemini', 'ollama')
            role: 角色 ('user', 'assistant')
            content: 訊息內容
            platform: 平台 ('line', 'discord', 'telegram')
            
        Returns:
            bool: 是否成功添加
        """
        try:
            if not self.db:
                logger.error("Database connection not available")
                return False
            
            # 插入到資料庫
            query = text("""
                INSERT INTO simple_conversation_history 
                (user_id, platform, model_provider, role, content, created_at)
                VALUES (:user_id, :platform, :model_provider, :role, :content, :created_at)
            """)
            
            self.db.execute(query, {
                'user_id': user_id,
                'platform': platform,
                'model_provider': model_provider,
                'role': role,
                'content': content,
                'created_at': datetime.now()
            })
            self.db.commit()
            
            # 清除快取，強制下次重新載入
            cache_key = f"{user_id}:{platform}:{model_provider}"
            if cache_key in self.memory_cache:
                del self.memory_cache[cache_key]
            
            logger.debug(f"Added message for user {user_id}, platform {platform}, provider {model_provider}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add message: {e}")
            if self.db:
                self.db.rollback()
            return False
    
    def get_recent_conversations(self, user_id: str, model_provider: str, limit: int = 5, platform: str = 'line') -> List[Dict]:
        """
        獲取用戶最近的對話歷史
        
        Args:
            user_id: 用戶 ID
            model_provider: 模型提供商
            limit: 取得最近幾輪對話
            platform: 平台
            
        Returns:
            List[Dict]: 對話歷史列表，格式為 [{'role': 'user', 'content': '...', 'created_at': '...'}, ...]
        """
        try:
            cache_key = f"{user_id}:{platform}:{model_provider}"
            
            # 檢查快取
            if cache_key in self.memory_cache:
                cache_data = self.memory_cache[cache_key]
                if datetime.now() - cache_data['timestamp'] < timedelta(seconds=self.cache_ttl):
                    return cache_data['conversations'][:limit * 2]  # 取雙倍以防萬一
            
            if not self.db:
                logger.error("Database connection not available")
                return []
            
            # 從資料庫查詢
            query = text("""
                SELECT role, content, created_at
                FROM simple_conversation_history
                WHERE user_id = :user_id AND platform = :platform AND model_provider = :model_provider
                ORDER BY created_at DESC
                LIMIT :limit
            """)
            
            result = self.db.execute(query, {
                'user_id': user_id,
                'platform': platform,
                'model_provider': model_provider,
                'limit': limit * 2  # 取雙倍記錄確保有足夠的對話輪次
            })
            
            conversations = []
            for row in result:
                conversations.append({
                    'role': row.role,
                    'content': row.content,
                    'created_at': row.created_at.isoformat() if row.created_at else None
                })
            
            # 反轉順序（最舊的在前）
            conversations.reverse()
            
            # 更新快取
            self.memory_cache[cache_key] = {
                'conversations': conversations,
                'timestamp': datetime.now()
            }
            
            logger.debug(f"Retrieved {len(conversations)} conversations for user {user_id} on platform {platform}")
            return conversations
            
        except Exception as e:
            logger.error(f"Failed to get conversations: {e}")
            return []
    
    def clear_user_history(self, user_id: str, model_provider: str, platform: str = 'line') -> bool:
        """
        清除用戶的對話歷史
        
        Args:
            user_id: 用戶 ID
            model_provider: 模型提供商
            
        Returns:
            bool: 是否成功清除
        """
        try:
            if not self.db:
                logger.error("Database connection not available")
                return False
            
            query = text("""
                DELETE FROM simple_conversation_history
                WHERE user_id = :user_id AND platform = :platform AND model_provider = :model_provider
            """)
            
            result = self.db.execute(query, {
                'user_id': user_id,
                'platform': platform,
                'model_provider': model_provider
            })
            self.db.commit()
            
            # 清除快取
            cache_key = f"{user_id}:{platform}:{model_provider}"
            if cache_key in self.memory_cache:
                del self.memory_cache[cache_key]
            
            deleted_count = result.rowcount
            logger.info(f"Cleared {deleted_count} messages for user {user_id} on platform {platform}, provider {model_provider}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear user history: {e}")
            if self.db:
                self.db.rollback()
            return False
    
    def cleanup_old_conversations(self, days_to_keep: int = 30) -> int:
        """
        清理舊的對話記錄
        
        Args:
            days_to_keep: 保留最近幾天的對話
            
        Returns:
            int: 清理的記錄數量
        """
        try:
            if not self.db:
                logger.error("Database connection not available")
                return 0
            
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            query = text("""
                DELETE FROM simple_conversation_history
                WHERE created_at < :cutoff_date
            """)
            
            result = self.db.execute(query, {'cutoff_date': cutoff_date})
            self.db.commit()
            
            deleted_count = result.rowcount
            logger.info(f"Cleaned up {deleted_count} old conversation records (older than {days_to_keep} days)")
            
            # 清除所有快取
            self.memory_cache.clear()
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old conversations: {e}")
            if self.db:
                self.db.rollback()
            return 0
    
    def get_user_statistics(self, user_id: str) -> Dict:
        """
        獲取用戶統計資訊
        
        Args:
            user_id: 用戶 ID
            
        Returns:
            Dict: 統計資訊
        """
        try:
            if not self.db:
                return {}
            
            query = text("""
                SELECT 
                    model_provider,
                    COUNT(*) as message_count,
                    MAX(created_at) as last_activity
                FROM simple_conversation_history
                WHERE user_id = :user_id
                GROUP BY model_provider
            """)
            
            result = self.db.execute(query, {'user_id': user_id})
            
            stats = {}
            for row in result:
                stats[row.model_provider] = {
                    'message_count': row.message_count,
                    'last_activity': row.last_activity.isoformat() if row.last_activity else None
                }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get user statistics: {e}")
            return {}


# 全域實例（單例模式）
_conversation_manager = None

def get_conversation_manager() -> SimpleConversationManager:
    """獲取對話管理器實例（單例模式）"""
    global _conversation_manager
    if _conversation_manager is None:
        _conversation_manager = SimpleConversationManager()
    return _conversation_manager