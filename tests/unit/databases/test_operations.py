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
            assert len(result["conversation_stats"]) == 2
            assert result["conversation_stats"]["openai"]["count"] == 5
            assert result["conversation_stats"]["anthropic"]["count"] == 3
    
    def test_get_user_summary_no_thread(self, db_ops):
        """測試沒有線程的用戶摘要獲取"""
        with patch.object(db_ops, 'session_factory') as mock_session_factory:
            
            # 設定 mock session
            mock_session = Mock()
            mock_session_factory.return_value.__enter__.return_value = mock_session
            
            # 設定線程查詢結果（無線程）
            mock_session.query.return_value.filter.return_value.first.return_value = None
            
            # 設定對話統計查詢結果（空）
            mock_session.query.return_value.filter.return_value.group_by.return_value.all.return_value = []
            
            # 執行摘要獲取
            result = db_ops.get_user_summary("new_user", "discord")
            
            # 驗證結果
            assert result["user_id"] == "new_user"
            assert result["platform"] == "discord"
            assert result["has_thread"] is False
            assert result["thread_id"] is None
            assert result["conversation_stats"] == {}
    
    def test_get_user_summary_error(self, db_ops):
        """測試用戶摘要獲取錯誤"""
        with patch.object(db_ops, 'session_factory') as mock_session_factory:
            
            # 模擬異常
            mock_session_factory.side_effect = Exception("Database connection failed")
            
            # 執行摘要獲取
            result = db_ops.get_user_summary("test_user", "line")
            
            # 驗證結果
            assert "error" in result
            assert "Database connection failed" in result["error"]
    
    def test_cleanup_old_data_error(self, db_ops):
        """測試舊資料清理錯誤"""
        with patch.object(db_ops, 'session_factory') as mock_session_factory:
            
            # 模擬異常
            mock_session_factory.side_effect = Exception("Cleanup failed")
            
            # 執行清理
            result = db_ops.cleanup_old_data(days_to_keep=7)
            
            # 驗證結果
            assert "error" in result
            assert "Cleanup failed" in result["error"]
    
    def test_get_database_stats_detailed(self, db_ops):
        """測試詳細的資料庫統計"""
        with patch.object(db_ops, 'session_factory') as mock_session_factory:
            
            # 設定 mock session
            mock_session = Mock()
            mock_session_factory.return_value.__enter__.return_value = mock_session
            
            # 設定查詢 mock
            mock_query = Mock()
            mock_session.query.return_value = mock_query
            
            # 設定統計查詢結果
            mock_query.scalar.side_effect = [5, 15]  # threads, conversations
            mock_query.group_by.return_value.all.side_effect = [
                [('line', 10), ('discord', 5)],  # platform stats
                [('openai', 8), ('anthropic', 7)]  # provider stats
            ]
            
            # 執行統計獲取
            result = db_ops._get_database_stats(mock_session)
            
            # 驗證結果
            assert result["total_threads"] == 5
            assert result["total_conversations"] == 15
            assert result["conversations_by_platform"]["line"] == 10
            assert result["conversations_by_platform"]["discord"] == 5
            assert result["conversations_by_provider"]["openai"] == 8
            assert result["conversations_by_provider"]["anthropic"] == 7
    
    def test_get_database_stats_error(self, db_ops):
        """測試資料庫統計獲取錯誤"""
        with patch('src.database.operations.logger') as mock_logger:
            
            # 設定 mock session（會拋出異常）
            mock_session = Mock()
            mock_session.query.side_effect = Exception("Query failed")
            
            # 執行統計獲取
            result = db_ops._get_database_stats(mock_session)
            
            # 驗證結果
            assert result == {}
            mock_logger.error.assert_called_once()
    
    def test_check_tables_exist_error(self, db_ops):
        """測試表存在檢查錯誤"""
        with patch('src.database.operations.logger') as mock_logger:
            
            # 設定 mock session（會拋出異常）
            mock_session = Mock()
            mock_session.execute.side_effect = Exception("Query failed")
            
            # 執行檢查
            result = db_ops._check_tables_exist(mock_session)
            
            # 驗證結果（所有表都標記為不存在）
            assert result["user_thread_table"] is False
            assert result["simple_conversation_history"] is False
            mock_logger.error.assert_called_once()
    
    def test_check_tables_exist_partial(self, db_ops, mock_session):
        """測試部分表存在檢查"""
        # 設定查詢結果 - 只有第一個表存在
        mock_session.execute.side_effect = [
            Mock(fetchone=lambda: [True]),   # user_thread_table exists
            Mock(fetchone=lambda: [False])   # simple_conversation_history doesn't exist
        ]
        
        # 執行檢查
        result = db_ops._check_tables_exist(mock_session)
        
        # 驗證結果
        assert result["user_thread_table"] is True
        assert result["simple_conversation_history"] is False
    
    def test_cleanup_old_data_with_custom_days(self, db_ops):
        """測試自定義天數的舊資料清理"""
        with patch.object(db_ops, 'session_factory') as mock_session_factory, \
             patch('src.database.operations.logger') as mock_logger:
            
            # 設定 mock session
            mock_session = Mock()
            mock_session_factory.return_value.__enter__.return_value = mock_session
            
            # 設定查詢 mock
            mock_query = Mock()
            mock_session.query.return_value = mock_query
            
            # 設定過濾和刪除結果
            mock_query.filter.return_value.delete.side_effect = [10, 5]  # 刪除的記錄數
            
            # 執行清理（7天）
            result = db_ops.cleanup_old_data(days_to_keep=7)
            
            # 驗證結果
            assert result["deleted_conversations"] == 10
            assert result["deleted_threads"] == 5
            
            # 驗證日誌記錄
            mock_logger.info.assert_called_once()
            assert "Cleanup completed" in mock_logger.info.call_args[0][0]


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