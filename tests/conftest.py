import pytest
import os
import tempfile
from unittest.mock import Mock, MagicMock
from flask import Flask

# 設定測試環境
os.environ['ENVIRONMENT'] = 'test'

@pytest.fixture
def app():
    """建立測試用的 Flask 應用程式"""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.app_context():
        yield app


@pytest.fixture
def client(app):
    """Flask 測試客戶端"""
    return app.test_client()


@pytest.fixture
def mock_config():
    """模擬配置檔案"""
    return {
        'line': {
            'channel_access_token': 'test_channel_access_token',
            'channel_secret': 'test_channel_secret'
        },
        'openai': {
            'api_key': 'test_openai_api_key',
            'assistant_id': 'test_assistant_id'
        },
        'db': {
            'host': 'localhost',
            'port': 5432,
            'db_name': 'test_db',
            'user': 'test_user',
            'password': 'test_password',
            'sslmode': 'disable'
        },
        'logfile': './logs/test.log',
        'commands': {
            'help': 'Test help message'
        },
        'text_processing': {
            'preprocessors': [
                {'type': 'replace_date_string'}
            ],
            'post-replacements': []
        }
    }


@pytest.fixture
def mock_database():
    """模擬資料庫"""
    db = Mock()
    db.query_thread.return_value = None
    db.save_thread.return_value = None
    db.delete_thread.return_value = None
    db.get_connection_info.return_value = {
        'pool_size': 10,
        'checked_in': 2,
        'checked_out': 1,
        'overflow': 0,
        'invalid': 0
    }
    
    # 模擬 context manager
    db.get_session.return_value.__enter__ = Mock()
    db.get_session.return_value.__exit__ = Mock()
    
    return db


@pytest.fixture
def mock_openai_model():
    """模擬 OpenAI 模型"""
    model = Mock()
    model.get_provider.return_value.value = 'openai'
    model.check_connection.return_value = (True, None)
    model.create_thread.return_value = (True, Mock(thread_id='test_thread_123'), None)
    model.delete_thread.return_value = (True, None)
    model.query_with_rag.return_value = (
        True, 
        Mock(
            answer='Test response',
            sources=[{
                'file_id': 'file_123',
                'filename': 'test.txt',
                'text': 'Test content'
            }]
        ), 
        None
    )
    model.get_file_references.return_value = {'file_123': 'test'}
    
    return model


@pytest.fixture
def mock_chat_service(mock_openai_model, mock_database, mock_config):
    """模擬聊天服務"""
    from src.services.chat_service import ChatService
    
    service = ChatService(mock_openai_model, mock_database, mock_config)
    return service


@pytest.fixture
def mock_audio_service(mock_openai_model, mock_chat_service):
    """模擬音訊服務"""
    from src.services.audio_service import AudioService
    
    service = AudioService(mock_openai_model, mock_chat_service)
    return service


@pytest.fixture
def temp_file():
    """建立臨時檔案"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("This is test content for knowledge base.")
        temp_path = f.name
    
    yield temp_path
    
    # 清理
    try:
        os.unlink(temp_path)
    except FileNotFoundError:
        pass


@pytest.fixture
def sample_line_event():
    """模擬 Line 事件"""
    event = Mock()
    event.source.user_id = 'test_user_123'
    event.message.text = 'Hello, test message'
    event.reply_token = 'test_reply_token'
    event.message.id = 'test_message_id'
    return event


@pytest.fixture
def mock_line_api_response():
    """模擬 Line API 回應"""
    response = Mock()
    response.status_code = 200
    response.json.return_value = {'status': 'success'}
    return response


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """自動設定測試環境"""
    # 設定測試環境變數
    monkeypatch.setenv('TESTING', 'true')
    monkeypatch.setenv('LOG_LEVEL', 'DEBUG')
    
    # 模擬檔案路徑
    test_log_dir = tempfile.mkdtemp()
    monkeypatch.setenv('LOG_DIR', test_log_dir)


class TestDataFactory:
    """測試資料工廠"""
    
    @staticmethod
    def create_chat_message(role='user', content='test message'):
        """建立聊天訊息"""
        from src.models.base import ChatMessage
        return ChatMessage(role=role, content=content)
    
    @staticmethod
    def create_file_info(file_id='test_file', filename='test.txt'):
        """建立檔案資訊"""
        from src.models.base import FileInfo
        return FileInfo(
            file_id=file_id,
            filename=filename,
            size=1024,
            status='processed',
            purpose='knowledge_base'
        )
    
    @staticmethod
    def create_rag_response(answer='test answer', sources=None):
        """建立 RAG 回應"""
        from src.models.base import RAGResponse
        if sources is None:
            sources = []
        return RAGResponse(
            answer=answer,
            sources=sources,
            metadata={'model': 'test'}
        )


@pytest.fixture
def test_factory():
    """測試資料工廠實例"""
    return TestDataFactory()