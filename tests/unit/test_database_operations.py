"""
資料庫操作測試
測試 src/database/operations.py 中的資料庫操作功能
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from src.database.operations import DatabaseOperations, get_database_operations


class TestDatabaseOperations:
    """DatabaseOperations 測試"""
    
    @pytest.fixture
    def mock_session(self):
        """模擬資料庫 session"""
        session = Mock()
        return session
    
    @pytest.fixture
    def db_operations(self, mock_session):
        """創建 DatabaseOperations 實例"""
        with patch('src.database.operations.get_db_session') as mock_session_factory:
            mock_session_factory.return_value.__enter__.return_value = mock_session
            mock_session_factory.return_value.__exit__.return_value = None
            
            ops = DatabaseOperations()
            ops.session_factory = mock_session_factory
            return ops
    
    def test_health_check_success(self, db_operations, mock_session):
        """測試健康檢查成功情況"""
        # 模擬成功的查詢
        mock_session.execute.return_value.fetchone.return_value = [1]
        mock_session.query.return_value.scalar.return_value = 10
        mock_session.query.return_value.group_by.return_value.all.return_value = [
            ("line", 5), ("discord", 3)
        ]
        
        with patch.object(db_operations, '_check_tables_exist') as mock_check_tables:
            mock_check_tables.return_value = {"user_thread_table": True, "simple_conversation_history": True}
            
            result = db_operations.health_check()
            
            assert result["status"] == "healthy"
            assert result["connection"] is True
            assert result["tables"]["user_thread_table"] is True
            assert "stats" in result
    
    def test_health_check_failure(self, db_operations, mock_session):
        """測試健康檢查失敗情況"""
        # 模擬資料庫連接失敗
        mock_session.execute.side_effect = Exception("Connection failed")
        
        result = db_operations.health_check()
        
        assert result["status"] == "unhealthy"
        assert result["connection"] is False
        assert "error" in result
    
    def test_check_tables_exist(self, db_operations, mock_session):
        """測試表存在檢查"""
        # 模擬表存在檢查
        mock_session.execute.return_value.fetchone.side_effect = [
            [True],   # user_thread_table 存在
            [False]   # simple_conversation_history 不存在
        ]
        
        result = db_operations._check_tables_exist(mock_session)
        
        assert result["user_thread_table"] is True
        assert result["simple_conversation_history"] is False
    
    def test_get_database_stats(self, db_operations, mock_session):
        """測試資料庫統計"""
        # 模擬統計查詢
        mock_session.query.return_value.scalar.side_effect = [10, 50]  # threads, conversations
        
        # 模擬平台統計
        mock_session.query.return_value.group_by.return_value.all.side_effect = [
            [("line", 30), ("discord", 20)],  # conversations_by_platform
            [("anthropic", 25), ("gemini", 25)]  # conversations_by_provider
        ]
        
        result = db_operations._get_database_stats(mock_session)
        
        assert result["total_threads"] == 10
        assert result["total_conversations"] == 50
        assert result["conversations_by_platform"]["line"] == 30
        assert result["conversations_by_provider"]["anthropic"] == 25
    
    def test_cleanup_old_data(self, db_operations, mock_session):
        """測試舊資料清理"""
        # 模擬刪除操作
        mock_session.query.return_value.filter.return_value.delete.side_effect = [5, 2]
        
        result = db_operations.cleanup_old_data(days_to_keep=30)
        
        assert result["deleted_conversations"] == 5
        assert result["deleted_threads"] == 2
        mock_session.commit.assert_called_once()
    
    def test_cleanup_old_data_failure(self, db_operations, mock_session):
        """測試清理失敗情況"""
        # 模擬清理失敗
        mock_session.query.side_effect = Exception("Cleanup failed")
        
        result = db_operations.cleanup_old_data()
        
        assert "error" in result
        assert "Cleanup failed" in result["error"]
    
    def test_get_user_summary(self, db_operations, mock_session):
        """測試用戶摘要資訊"""
        # 模擬用戶線程查詢
        mock_thread = Mock()
        mock_thread.thread_id = "thread_123"
        mock_session.query.return_value.filter.return_value.first.return_value = mock_thread
        
        # 模擬對話統計查詢
        mock_session.query.return_value.filter.return_value.group_by.return_value.all.return_value = [
            ("anthropic", 10, datetime.now()),
            ("gemini", 5, datetime.now() - timedelta(days=1))
        ]
        
        result = db_operations.get_user_summary("test_user", "line")
        
        assert result["user_id"] == "test_user"
        assert result["platform"] == "line"
        assert result["has_thread"] is True
        assert result["thread_id"] == "thread_123"
        assert "conversation_stats" in result
        assert "anthropic" in result["conversation_stats"]
    
    def test_get_user_summary_no_thread(self, db_operations, mock_session):
        """測試沒有線程的用戶摘要"""
        # 模擬沒有找到線程
        mock_session.query.return_value.filter.return_value.first.return_value = None
        mock_session.query.return_value.filter.return_value.group_by.return_value.all.return_value = []
        
        result = db_operations.get_user_summary("new_user", "line")
        
        assert result["user_id"] == "new_user"
        assert result["has_thread"] is False
        assert result["thread_id"] is None
        assert result["conversation_stats"] == {}


class TestDatabaseOperationsSingleton:
    """資料庫操作單例模式測試"""
    
    def test_get_database_operations_singleton(self):
        """測試單例模式"""
        # 清除可能存在的實例
        import src.database.operations
        src.database.operations._db_operations = None
        
        # 測試單例
        ops1 = get_database_operations()
        ops2 = get_database_operations()
        
        assert ops1 is ops2
        assert isinstance(ops1, DatabaseOperations)
    
    @patch('src.database.operations.DatabaseOperations')
    def test_get_database_operations_creation(self, mock_db_operations_class):
        """測試實例創建"""
        # 清除可能存在的實例
        import src.database.operations
        src.database.operations._db_operations = None
        
        mock_instance = Mock()
        mock_db_operations_class.return_value = mock_instance
        
        result = get_database_operations()
        
        mock_db_operations_class.assert_called_once()
        assert result == mock_instance


class TestDatabaseOperationsIntegration:
    """資料庫操作整合測試"""
    
    @patch('src.database.operations.Database')
    @patch('src.database.operations.get_db_session')
    def test_database_operations_initialization(self, mock_get_db_session, mock_database):
        """測試 DatabaseOperations 初始化"""
        mock_db_instance = Mock()
        mock_database.return_value = mock_db_instance
        
        ops = DatabaseOperations()
        
        assert ops.db == mock_db_instance
        assert ops.session_factory == mock_get_db_session
        mock_database.assert_called_once()
    
    def test_error_handling_consistency(self, db_operations, mock_session):
        """測試錯誤處理一致性"""
        # 所有方法都應該有適當的錯誤處理
        mock_session.execute.side_effect = Exception("Test error")
        
        # 測試各種方法的錯誤處理
        health_result = db_operations.health_check()
        cleanup_result = db_operations.cleanup_old_data()
        summary_result = db_operations.get_user_summary("test_user")
        
        # 所有方法都應該gracefully處理錯誤
        assert health_result["status"] == "unhealthy"
        assert "error" in cleanup_result
        assert "error" in summary_result