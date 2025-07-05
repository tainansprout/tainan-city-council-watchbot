"""
測試資料庫操作工具的單元測試
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import text, func
from src.database.operations import DatabaseOperations, get_database_operations


class TestDatabaseOperations:
    """測試資料庫操作工具類"""
    
    @pytest.fixture
    def db_ops(self):
        """建立資料庫操作實例"""
        return DatabaseOperations()
    
    @pytest.fixture
    def mock_session(self):
        """建立模擬資料庫 session"""
        session = Mock()
        return session
    
    def test_database_operations_initialization(self, db_ops):
        """測試資料庫操作工具初始化"""
        assert db_ops.session_factory is not None
        assert callable(db_ops.session_factory)
    
    def test_health_check_success(self, db_ops):
        """測試成功的健康檢查"""
        with patch.object(db_ops, 'session_factory') as mock_session_factory, \
             patch.object(db_ops, '_check_tables_exist') as mock_check_tables, \
             patch.object(db_ops, '_get_database_stats') as mock_get_stats:
            
            # 設定 mock session
            mock_session = Mock()
            mock_session_factory.return_value.__enter__.return_value = mock_session
            
            # 設定查詢結果
            mock_result = Mock()
            mock_result.fetchone.return_value = [1]
            mock_session.execute.return_value = mock_result
            
            # 設定其他方法的返回值
            mock_check_tables.return_value = {
                "user_thread_table": True,
                "simple_conversation_history": True
            }
            mock_get_stats.return_value = {
                "total_threads": 5,
                "total_conversations": 10
            }
            
            # 執行健康檢查
            result = db_ops.health_check()
            
            # 驗證結果
            assert result["status"] == "healthy"
            assert result["connection"] is True
            assert result["tables"]["user_thread_table"] is True
            assert result["tables"]["simple_conversation_history"] is True
            assert result["stats"]["total_threads"] == 5
            assert result["stats"]["total_conversations"] == 10
    
    def test_health_check_connection_failure(self, db_ops):
        """測試連接失敗的健康檢查"""
        with patch.object(db_ops, 'session_factory') as mock_session_factory:
            
            # 模擬連接失敗
            mock_session_factory.side_effect = Exception("Database connection failed")
            
            # 執行健康檢查
            result = db_ops.health_check()
            
            # 驗證結果
            assert result["status"] == "unhealthy"
            assert result["connection"] is False
            assert "Database connection failed" in result["error"]
    
    def test_check_tables_exist_success(self, db_ops, mock_session):
        """測試成功的表存在檢查"""
        # 設定查詢結果 - 兩個表都存在
        mock_session.execute.side_effect = [
            Mock(fetchone=lambda: [True]),  # user_thread_table exists
            Mock(fetchone=lambda: [True])   # simple_conversation_history exists
        ]
        
        # 執行檢查
        result = db_ops._check_tables_exist(mock_session)
        
        # 驗證結果
        assert result["user_thread_table"] is True
        assert result["simple_conversation_history"] is True
        
        # 驗證 SQL 查詢調用
        assert mock_session.execute.call_count == 2
    
    def test_cleanup_old_data_success(self, db_ops):
        """測試成功的舊資料清理"""
        with patch.object(db_ops, 'session_factory') as mock_session_factory:
            
            # 設定 mock session
            mock_session = Mock()
            mock_session_factory.return_value.__enter__.return_value = mock_session
            
            # 設定查詢 mock
            mock_query = Mock()
            mock_session.query.return_value = mock_query
            
            # 設定過濾和刪除結果
            mock_query.filter.return_value.delete.side_effect = [3, 2]  # 刪除的記錄數
            
            # 執行清理
            result = db_ops.cleanup_old_data(days_to_keep=30)
            
            # 驗證結果
            assert result["deleted_conversations"] == 3
            assert result["deleted_threads"] == 2
            
            # 驗證 commit 被調用
            mock_session.commit.assert_called_once()
    
    def test_get_user_summary_success(self, db_ops):
        """測試成功的用戶摘要獲取"""
        with patch.object(db_ops, 'session_factory') as mock_session_factory:
            
            # 設定 mock session
            mock_session = Mock()
            mock_session_factory.return_value.__enter__.return_value = mock_session
            
            # 設定線程查詢結果
            mock_thread = Mock()
            mock_thread.thread_id = "test_thread_123"
            mock_session.query.return_value.filter.return_value.first.return_value = mock_thread
            
            # 設定對話統計查詢結果
            mock_stats = [
                ('openai', 5, datetime(2023, 1, 15, 10, 0, 0)),
                ('anthropic', 3, datetime(2023, 1, 14, 15, 30, 0))
            ]
            mock_session.query.return_value.filter.return_value.group_by.return_value.all.return_value = mock_stats
            
            # 執行摘要獲取
            result = db_ops.get_user_summary("test_user", "line")
            
            # 驗證結果
            assert result["user_id"] == "test_user"
            assert result["platform"] == "line"
            assert result["has_thread"] is True
            assert result["thread_id"] == "test_thread_123"


class TestDatabaseOperationsSingleton:
    """測試資料庫操作工具的單例模式"""
    
    def test_get_database_operations_singleton(self):
        """測試單例模式"""
        # 清理全域變數
        import src.database.operations
        src.database.operations._db_operations = None
        
        # 獲取兩個實例
        ops1 = get_database_operations()
        ops2 = get_database_operations()
        
        # 驗證是同一個實例
        assert ops1 is ops2
        assert isinstance(ops1, DatabaseOperations)