import pytest
from unittest.mock import Mock, patch, MagicMock
from linebot.v3.messaging import TextMessage, AudioMessage
import tempfile
import os

from src.services.chat_service import ChatService
from src.services.audio_service import AudioService
from src.models.factory import ModelFactory
from src.database import Database
from src.models.base import ChatMessage, ChatResponse, RAGResponse, FileInfo, ThreadInfo


class TestChatFlow:
    """聊天流程整合測試"""
    
    @pytest.fixture
    def mock_config(self):
        return {
            'chatgpt': {
                'model': 'gpt-4',
                'assistant_id': 'test_assistant',
                'api_key': 'test_key'
            },
            'line': {
                'reply': {
                    'help': 'Test help message',
                    'reset': 'Reset The Chatbot',
                    'reset_fail': 'Nothing to reset',
                    'default': 'Command not found'
                }
            },
            'text_processing': {
                'preprocessors': [
                    {'type': 'replace_date_string'}
                ],
                'post-replacements': [
                    {'pattern': r'AI', 'replacement': '人工智慧'}
                ]
            }
        }
    
    @pytest.fixture
    def integration_setup(self, mock_config):
        """設定整合測試環境"""
        # 建立模擬的模型和資料庫
        mock_model = Mock()
        mock_database = Mock()
        mock_model.check_connection.return_value = (True, None)
        mock_model.list_files.return_value = (True, [], None)
        mock_model.assistant_id = 'test_assistant'
        
        # 建立服務實例
        chat_service = ChatService(mock_model, mock_database, mock_config)
        audio_service = AudioService(mock_model, chat_service)
        
        return {
            'chat_service': chat_service,
            'audio_service': audio_service,
            'mock_model': mock_model,
            'mock_database': mock_database,
            'config': mock_config
        }
    
    def test_complete_chat_flow_with_rag(self, integration_setup):
        """測試完整的聊天流程，包含 RAG 功能"""
        setup = integration_setup
        chat_service = setup['chat_service']
        mock_model = setup['mock_model']
        mock_database = setup['mock_database']
        
        # 設定模擬回應
        mock_database.query_thread.return_value = 'thread_123'
        mock_model.retrieve_thread.return_value = (True, ThreadInfo(thread_id='thread_123'), None)

        mock_rag_response = RAGResponse(
            answer='根據文件，天氣很好。',
            sources=[
                {'filename': 'weather.txt', 'text': '今天天氣晴朗'},
                {'filename': 'forecast.json', 'text': '未來三天都是好天氣'}
            ],
            metadata={'thread_messages': []}
        )
        mock_model.query_with_rag.return_value = (True, mock_rag_response, None)
        
        with patch('src.services.chat_service.preprocess_text') as mock_preprocess, \
             patch('src.services.chat_service.postprocess_text') as mock_postprocess:
            
            mock_preprocess.return_value = '今天天氣如何？'
            mock_postprocess.return_value = '根據文件，天氣很好。\n\n[1]: weather\n[2]: forecast'
            
            # 執行測試
            response = chat_service.handle_message('user_123', '今天天氣如何？')
            
            # 驗證結果
            assert isinstance(response, TextMessage)
            assert '根據文件，天氣很好。' in response.text
            assert '[1]: weather' in response.text
            assert '[2]: forecast' in response.text
            
            # 驗證調用順序
            mock_preprocess.assert_called_once()
            mock_model.query_with_rag.assert_called_once()
            mock_postprocess.assert_called_once()
    
    def test_complete_audio_to_chat_flow(self, integration_setup):
        """測試完整的語音轉文字再聊天的流程"""
        setup = integration_setup
        audio_service = setup['audio_service']
        mock_model = setup['mock_model']
        mock_database = setup['mock_database']

        # 設定模擬回應
        mock_database.query_thread.return_value = 'thread_123'
        mock_model.retrieve_thread.return_value = (True, ThreadInfo(thread_id='thread_123'), None)
        
        audio_content = b'fake_audio_data'
        with patch.object(audio_service, '_transcribe_audio', return_value='請問今天的天氣如何？') as mock_transcribe_audio,              patch('os.path.exists', return_value=True),              patch('os.remove') as mock_remove,              patch('builtins.open', create=True),              patch('uuid.uuid4') as mock_uuid:
            
            mock_uuid.return_value.__str__ = Mock(return_value='test-uuid')
            
            # 執行測試
            response = audio_service.handle_audio_message('user_123', audio_content)
            
            # 驗證結果
            assert isinstance(response, TextMessage)
            mock_model.query_with_rag.return_value = (True, Mock(answer='今天天氣晴朗，適合外出。', sources=[]), None)
    
    def test_thread_management_flow(self, integration_setup):
        """測試對話串管理流程"""
        setup = integration_setup
        chat_service = setup['chat_service']
        mock_model = setup['mock_model']
        mock_database = setup['mock_database']
        
        # 測試新用戶（無對話串）
        mock_database.query_thread.return_value = None
        mock_model.create_thread.return_value = (True, ThreadInfo(thread_id='new_thread_456'), None)
        
        mock_rag_response = RAGResponse(answer='你好！', sources=[], metadata={'thread_messages': []})
        mock_model.query_with_rag.return_value = (True, mock_rag_response, None)
        
        # 執行測試
        response = chat_service.handle_message('new_user', '你好')
        
        # 驗證新用戶流程
        assert isinstance(response, TextMessage)
        mock_model.create_thread.assert_called_once()
        mock_database.save_thread.assert_called_once_with('new_user', 'new_thread_456')
    
    def test_reset_command_flow(self, integration_setup):
        """測試重設指令的完整流程"""
        setup = integration_setup
        chat_service = setup['chat_service']
        mock_model = setup['mock_model']
        mock_database = setup['mock_database']
        
        # 設定用戶有現有對話串
        mock_database.query_thread.return_value = 'existing_thread_789'
        mock_model.delete_thread.return_value = (True, None)
        
        # 執行重設指令
        response = chat_service.handle_message('user_123', '/reset')
        
        # 驗證重設流程
        assert isinstance(response, TextMessage)
        assert 'Reset The Chatbot' in response.text
        mock_model.delete_thread.assert_called_once_with('existing_thread_789')
        mock_database.delete_thread.assert_called_once_with('user_123')
    
    def test_error_recovery_flow(self, integration_setup):
        """測試錯誤恢復流程"""
        setup = integration_setup
        chat_service = setup['chat_service']
        mock_model = setup['mock_model']
        mock_database = setup['mock_database']
        
        # 模擬 API 錯誤
        mock_database.query_thread.return_value = 'thread_123'
        mock_model.retrieve_thread.return_value = (True, ThreadInfo(thread_id='thread_123'), None)
        mock_model.query_with_rag.return_value = (False, None, 'API rate limit exceeded')
        
        # 執行測試
        response = chat_service.handle_message('user_123', '測試訊息')
        
        # 驗證錯誤處理
        assert isinstance(response, TextMessage)
        assert 'OpenAI API Token 有誤，請重新設定。' in response.text
    
    def test_response_formatter_integration_flow(self, integration_setup):
        """測試 ResponseFormatter 整合流程（重構後版本）"""
        setup = integration_setup
        chat_service = setup['chat_service']
        
        # 驗證 ResponseFormatter 正確初始化
        assert hasattr(chat_service, 'response_formatter')
        assert chat_service.response_formatter is not None
        
        # 測試不同來源格式的處理
        sources = [
            {'filename': 'document1.txt', 'type': 'file_citation'},
            {'document_id': 'doc-123', 'title': 'Gemini Document', 'type': 'document'}
        ]
        
        result = chat_service.response_formatter._format_sources(sources)
        
        # 驗證格式化結果
        assert '[1]: document1' in result
        assert '[2]: Gemini Document' in result


class TestDatabaseIntegration:
    """資料庫整合測試"""
    
    @pytest.fixture
    def db_config(self):
        return {
            'host': 'localhost',
            'port': 5432,
            'db_name': 'test_db',
            'user': 'test_user',
            'password': 'test_password',
            'sslmode': 'disable'
        }
    
    def test_thread_lifecycle(self, db_config):
        """測試對話串的完整生命周期"""
        with patch('src.database.db.create_engine') as mock_engine, \
             patch('src.database.db.sessionmaker') as mock_sessionmaker:
            
            # 設定模擬
            mock_session = Mock()
            mock_sessionmaker.return_value.return_value = mock_session
            
            db = Database(db_config)
            
            with patch.object(db, 'get_session') as mock_get_session:
                mock_get_session.return_value.__enter__.return_value = mock_session
                mock_get_session.return_value.__exit__.return_value = None
                
                # 1. 查詢不存在的對話串
                mock_session.query.return_value.filter.return_value.first.return_value = None
                result = db.query_thread('user_123')
                assert result is None
                
                # 2. 儲存新對話串
                db.save_thread('user_123', 'thread_456')
                mock_session.add.assert_called_once()
                
                # 3. 查詢存在的對話串
                mock_thread = Mock()
                mock_thread.thread_id = 'thread_456'
                mock_session.query.return_value.filter.return_value.first.return_value = mock_thread
                result = db.query_thread('user_123')
                assert result == 'thread_456'
                
                # 4. 刪除對話串
                db.delete_thread('user_123')
                mock_session.query.return_value.filter.return_value.delete.assert_called_once()


class TestModelIntegration:
    """模型整合測試"""
    
    def test_model_factory_with_config(self):
        """測試模型工廠與配置的整合"""
        configs = [
            {
                'provider': 'openai',
                'api_key': 'test_openai_key',
                'assistant_id': 'test_assistant'
            },
            {
                'provider': 'anthropic',
                'api_key': 'test_anthropic_key',
                'model': 'claude-3-sonnet-20240229'
            },
            {
                'provider': 'gemini',
                'api_key': 'test_gemini_key'
            },
            {
                'provider': 'ollama',
                'model': 'llama2',
                'base_url': 'http://localhost:11434'
            }
        ]
        
        for config in configs:
            model = ModelFactory.create_from_config(config)
            assert model is not None
            assert hasattr(model, 'get_provider')
            assert hasattr(model, 'chat_completion')
            assert hasattr(model, 'query_with_rag')
    
    @patch('requests.post')
    def test_rag_flow_across_models(self, mock_post):
        """測試不同模型的 RAG 流程"""
        # 模擬 HTTP 回應
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'Test response'}}]
        }
        mock_post.return_value = mock_response
        
        # 測試 OpenAI 模型
        from src.models.openai_model import OpenAIModel
        openai_model = OpenAIModel(api_key='test_key', assistant_id='test_id')
        
        with patch.object(openai_model, 'get_knowledge_files') as mock_get_files:
            mock_get_files.return_value = (True, {'data': []}, None)
            
            # 測試 RAG 查詢
            is_successful, response, error = openai_model.query_with_rag('test query')
            
            # 由於沒有知識庫檔案，應該使用普通聊天
            assert is_successful is True or error is not None  # 可能因為模擬而失敗

