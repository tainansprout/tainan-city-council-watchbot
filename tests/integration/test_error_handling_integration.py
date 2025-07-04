"""
錯誤處理整合測試
測試完整的錯誤處理流程，包括從資料庫錯誤到最終用戶訊息的整個鏈路
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import json
from flask import Flask
from sqlalchemy.exc import ProgrammingError
import psycopg2.errors

from src.app import MultiPlatformChatBot
from src.platforms.base import PlatformType


class TestErrorHandlingIntegration:
    """錯誤處理整合測試"""
    
    @pytest.fixture
    def mock_config(self):
        """模擬配置"""
        return {
            'app': {'name': '測試聊天機器人', 'version': '2.0.0'},
            'llm': {'provider': 'openai'},
            'openai': {'api_key': 'test_key', 'assistant_id': 'test_assistant'},
            'platforms': {
                'line': {
                    'enabled': True,
                    'channel_access_token': 'test_token',
                    'channel_secret': 'test_secret'
                }
            },
            'db': {
                'host': 'localhost',
                'port': 5432,
                'database': 'test_db',
                'username': 'test_user',
                'password': 'test_pass'
            },
            'auth': {
                'method': 'simple_password',
                'password': 'test_password'
            },
            'text_processing': {
                'preprocessors': [],
                'post_replacements': []
            }
        }
    
    @pytest.fixture
    def app_instance(self, mock_config):
        """創建應用實例"""
        with patch('src.app.load_config', return_value=mock_config):
            with patch('src.models.factory.ModelFactory') as mock_factory:
                with patch('src.platforms.factory.PlatformFactory') as mock_platform_factory:
                    # 模擬模型
                    mock_model = Mock()
                    mock_model.get_provider.return_value.value = "openai"
                    mock_factory.return_value.create_model.return_value = mock_model
                    
                    # 模擬平台處理器
                    mock_platform_factory.return_value.create_enabled_handlers.return_value = {}
                    
                    app = MultiPlatformChatBot()
                    return app
    
    @pytest.fixture
    def client(self, app_instance):
        """創建測試客戶端"""
        flask_app = app_instance.get_flask_app()
        flask_app.config['TESTING'] = True
        flask_app.config['SECRET_KEY'] = 'test_secret_key'
        return flask_app.test_client()
    
    def test_database_error_in_chat_interface_shows_detailed_message(self, client, app_instance):
        """測試 /chat 介面的資料庫錯誤顯示詳細訊息"""
        # 模擬登入
        with client.session_transaction() as sess:
            sess['test_authenticated'] = True
        
        # 模擬資料庫錯誤
        with patch.object(app_instance.chat.model, 'chat_with_user') as mock_chat:
            mock_chat.return_value = (
                False, 
                None, 
                "Database operation failed: column 'platform' does not exist"
            )
            
            # 發送請求到 /ask 端點
            response = client.post('/ask', 
                json={'message': '測試訊息'},
                content_type='application/json'
            )
            
            # 應該返回 500 錯誤和詳細錯誤訊息
            assert response.status_code == 500
            data = json.loads(response.data)
            assert 'error' in data
            # 應該顯示詳細的資料庫錯誤訊息
            assert '資料庫查詢失敗' in data['error']
            assert 'SQL 查詢' in data['error']
    
    def test_openai_error_in_chat_interface_shows_detailed_message(self, client, app_instance):
        """測試 /chat 介面的 OpenAI 錯誤顯示詳細訊息"""
        # 模擬登入
        with client.session_transaction() as sess:
            sess['test_authenticated'] = True
        
        # 模擬 OpenAI 錯誤
        with patch.object(app_instance.chat.model, 'chat_with_user') as mock_chat:
            mock_chat.return_value = (
                False, 
                None, 
                "Invalid API key provided"
            )
            
            # 發送請求到 /ask 端點
            response = client.post('/ask', 
                json={'message': '測試訊息'},
                content_type='application/json'
            )
            
            # 應該返回 500 錯誤和詳細錯誤訊息
            assert response.status_code == 500
            data = json.loads(response.data)
            assert 'error' in data
            # 應該顯示詳細的 OpenAI 錯誤訊息
            assert 'API' in data['error'] or '金鑰' in data['error']
    
    def test_sql_exception_classification(self, client, app_instance):
        """測試 SQL 異常的正確分類"""
        # 模擬登入
        with client.session_transaction() as sess:
            sess['test_authenticated'] = True
        
        # 模擬 SQLAlchemy 異常
        with patch.object(app_instance.chat.model, 'chat_with_user') as mock_chat:
            mock_chat.side_effect = ProgrammingError(
                "", "", "column 'platform' does not exist"
            )
            
            # 發送請求到 /ask 端點
            response = client.post('/ask', 
                json={'message': '測試訊息'},
                content_type='application/json'
            )
            
            # 應該返回 500 錯誤和資料庫錯誤訊息
            assert response.status_code == 500
            data = json.loads(response.data)
            assert 'error' in data
            # SQL 異常應該被分類為資料庫錯誤
            assert '資料庫' in data['error']
    
    def test_unknown_error_classification(self, client, app_instance):
        """測試未知錯誤的分類"""
        # 模擬登入
        with client.session_transaction() as sess:
            sess['test_authenticated'] = True
        
        # 模擬未知錯誤
        with patch.object(app_instance.chat.model, 'chat_with_user') as mock_chat:
            mock_chat.side_effect = Exception("Some random error")
            
            # 發送請求到 /ask 端點
            response = client.post('/ask', 
                json={'message': '測試訊息'},
                content_type='application/json'
            )
            
            # 應該返回 500 錯誤和未知錯誤訊息
            assert response.status_code == 500
            data = json.loads(response.data)
            assert 'error' in data
            # 未知錯誤應該有適當的訊息
            assert '未知錯誤' in data['error'] or '系統錯誤' in data['error']
    
    @patch('src.services.chat.logger')
    def test_error_logging_in_integration(self, mock_logger, client, app_instance):
        """測試整合環境中的錯誤日誌記錄"""
        # 模擬登入
        with client.session_transaction() as sess:
            sess['test_authenticated'] = True
        
        # 模擬資料庫錯誤
        with patch.object(app_instance.chat.model, 'chat_with_user') as mock_chat:
            mock_chat.return_value = (
                False, 
                None, 
                "Database operation failed: column does not exist"
            )
            
            # 發送請求
            response = client.post('/ask', 
                json={'message': '測試錯誤日誌'},
                content_type='application/json'
            )
            
            # 驗證錯誤被正確日誌記錄
            assert mock_logger.error.called
            
            # 檢查日誌內容
            log_calls = [call[0][0] for call in mock_logger.error.call_args_list]
            assert any("Error handling text message" in log for log in log_calls)
            assert any("Error processing chat message" in log for log in log_calls)
    
    def test_authentication_required_for_ask_endpoint(self, client):
        """測試 /ask 端點需要認證"""
        # 未登入狀態下訪問
        response = client.post('/ask', 
            json={'message': '測試訊息'},
            content_type='application/json'
        )
        
        # 應該返回 401 未授權
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'error' in data
        assert '需要先登入' in data['error']
    
    def test_error_message_format_consistency(self, client, app_instance):
        """測試錯誤訊息格式的一致性"""
        # 模擬登入
        with client.session_transaction() as sess:
            sess['test_authenticated'] = True
        
        # 測試多種類型的錯誤
        error_scenarios = [
            ("Database operation failed: column does not exist", "資料庫"),
            ("Invalid API key", "API"),
            ("Some unknown error", "未知")
        ]
        
        for error_msg, expected_keyword in error_scenarios:
            with patch.object(app_instance.chat.model, 'chat_with_user') as mock_chat:
                mock_chat.return_value = (False, None, error_msg)
                
                response = client.post('/ask', 
                    json={'message': '測試訊息'},
                    content_type='application/json'
                )
                
                assert response.status_code == 500
                data = json.loads(response.data)
                assert 'error' in data
                # 每種錯誤都應該有適當的中文錯誤訊息
                assert expected_keyword in data['error']


class TestRealDatabaseErrorScenarios:
    """真實資料庫錯誤場景測試"""
    
    def test_psycopg2_undefined_column_error(self):
        """測試 psycopg2 UndefinedColumn 錯誤"""
        from src.core.error_handler import ErrorHandler
        
        # 模擬真實的 psycopg2 錯誤
        error = psycopg2.errors.UndefinedColumn(
            "column user_thread_table.platform does not exist\n"
            "LINE 1: ...hread_table.user_id AS user_thread_table_user_id, user_threa...\n"
            "                                                             ^"
        )
        
        error_handler = ErrorHandler()
        detailed_msg = error_handler.get_error_message(error, use_detailed=True)
        simple_msg = error_handler.get_error_message(error, use_detailed=False)
        
        # 詳細訊息應該指出是資料庫查詢問題
        assert "資料庫查詢失敗" in detailed_msg
        assert "SQL 查詢" in detailed_msg
        
        # 簡化訊息應該是用戶友好的
        assert "機器人發生錯誤" in simple_msg
        assert "請換個問法" in simple_msg
    
    def test_sqlalchemy_programming_error(self):
        """測試 SQLAlchemy ProgrammingError"""
        from src.core.error_handler import ErrorHandler
        
        # 模擬 SQLAlchemy 錯誤
        error = ProgrammingError(
            "SELECT statement",
            "SELECT user_thread_table.platform FROM user_thread_table",
            "relation 'user_thread_table' does not exist"
        )
        
        error_handler = ErrorHandler()
        detailed_msg = error_handler.get_error_message(error, use_detailed=True)
        simple_msg = error_handler.get_error_message(error, use_detailed=False)
        
        # 應該被正確分類為資料庫錯誤
        assert "資料庫查詢失敗" in detailed_msg
        assert "機器人發生錯誤" in simple_msg
    
    def test_database_connection_error(self):
        """測試資料庫連線錯誤"""
        from src.core.error_handler import ErrorHandler
        from src.core.exceptions import DatabaseError
        
        # 模擬連線錯誤
        error = DatabaseError("Database connection failed: could not connect to server")
        
        error_handler = ErrorHandler()
        detailed_msg = error_handler.get_error_message(error, use_detailed=True)
        simple_msg = error_handler.get_error_message(error, use_detailed=False)
        
        # 應該有適當的錯誤訊息
        assert "Database connection failed" in detailed_msg
        assert "機器人發生錯誤" in simple_msg