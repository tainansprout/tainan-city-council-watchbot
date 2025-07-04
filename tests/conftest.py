import pytest
import os
import tempfile
from unittest.mock import Mock, patch

# 設置 pytest-asyncio 配置
pytest_plugins = ('pytest_asyncio',)

# 配置 asyncio
def pytest_configure(config):
    """Configure pytest settings"""
    # 正確設定 asyncio 的 fixture loop scope
    import pytest_asyncio
    pytest_asyncio.plugin.DEFAULT_FIXTURE_LOOP_SCOPE = "function"
    
    # 配置測試標記
    config.addinivalue_line(
        "markers", "integration: 標記為整合測試"
    )
    config.addinivalue_line(
        "markers", "slow: 標記為慢速測試"
    )
    config.addinivalue_line(
        "markers", "database: 標記為資料庫相關測試"
    )
    config.addinivalue_line(
        "markers", "external: 標記為需要外部服務的測試"
    )

# 設定測試環境變數
os.environ.update({
    'FLASK_ENV': 'testing',
    'FLASK_DEBUG': 'false',
    'TEST_AUTH_METHOD': 'simple_password',
    'TEST_PASSWORD': 'test123',
    'TEST_SECRET_KEY': 'test_secret_key_for_testing_only',
    'ENABLE_SECURITY_HEADERS': 'false',
    'LOG_SECURITY_EVENTS': 'false',
    'ENABLE_TEST_ENDPOINTS': 'true',
    'GENERAL_RATE_LIMIT': '1000',  # 測試時放寬限制
    'TEST_ENDPOINT_RATE_LIMIT': '1000',
    'WEBHOOK_RATE_LIMIT': '1000',
    'MAX_MESSAGE_LENGTH': '5000',
    'MAX_TEST_MESSAGE_LENGTH': '1000'
})

@pytest.fixture(scope='session', autouse=True)
def setup_test_environment():
    """設定測試環境"""
    # 禁用安全中間件的速率限制
    with patch('src.core.security.RateLimiter.is_allowed', return_value=True):
        yield

@pytest.fixture
def mock_config():
    """模擬配置 - 新的多平台格式"""
    return {
        'platforms': {
            'line': {
                'enabled': True,
                'channel_access_token': 'test_token',
                'channel_secret': 'test_secret'
            }
        },
        'llm': {
            'provider': 'openai'
        },
        'openai': {
            'api_key': 'test_openai_key',
            'assistant_id': 'test_assistant_id'
        },
        'db': {
            'host': 'localhost',
            'port': 5432,
            'db_name': 'test_db',
            'user': 'test_user',
            'password': 'test_password'
        },
        'commands': {
            'help': 'Test help message'
        }
    }

@pytest.fixture
def client():
    """Flask 測試客戶端 - 使用新架構"""
    # 避免導入時的初始化問題
    with patch('src.core.config.load_config') as mock_load_config:
        mock_load_config.return_value = {
            'platforms': {
                'line': {
                    'enabled': True,
                    'channel_access_token': 'test_token',
                    'channel_secret': 'test_secret'
                }
            },
            'llm': {
                'provider': 'openai'
            },
            'openai': {
                'api_key': 'test_openai_key',
                'assistant_id': 'test_assistant_id'
            },
            'db': {
                'host': 'localhost',
                'port': 5432,
                'db_name': 'test_db',
                'user': 'test_user',
                'password': 'test_password'
            }
        }
        
        from main import create_app
        app = create_app()
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        
        with app.test_client() as client:
            with app.app_context():
                yield client

@pytest.fixture
def mock_database():
    """模擬資料庫"""
    mock_db = Mock()
    mock_db.get_connection_info.return_value = {
        'pool_size': 10,
        'checked_in': 2,
        'checked_out': 1,
        'overflow': 0,
        'invalid': 0
    }
    return mock_db

@pytest.fixture
def mock_model():
    """模擬 AI 模型"""
    mock_model = Mock()
    mock_model.check_connection.return_value = (True, None)
    mock_model.get_provider.return_value = Mock(value='openai')
    return mock_model

@pytest.fixture
def mock_chat_service():
    """模擬聊天服務"""
    mock_service = Mock()
    mock_service.handle_message.return_value = Mock(text="Test response")
    return mock_service

@pytest.fixture
def mock_audio_service():
    """模擬音訊服務"""
    mock_service = Mock()
    mock_service.handle_audio_message.return_value = Mock(text="Audio response")
    return mock_service

@pytest.fixture
def mock_openai_model():
    """模擬 OpenAI 模型"""
    mock_model = Mock()
    mock_model.check_connection.return_value = (True, None)
    mock_model.get_provider.return_value = Mock(value='openai')
    mock_model.delete_thread.return_value = (True, None)

    # 修正 create_thread 的返回值
    mock_thread_response = Mock()
    mock_thread_response.thread_id = 'new_thread_123'
    mock_model.create_thread.return_value = (True, mock_thread_response, None)

    # 修正 query_with_rag 的返回值
    mock_rag_response = Mock()
    mock_rag_response.answer = 'Test response'
    mock_rag_response.sources = []
    mock_rag_response.metadata = {'thread_messages': []}
    mock_model.query_with_rag.return_value = (True, mock_rag_response, None)

    mock_model.list_files.return_value = (True, [], None)
    mock_model.retrieve_thread.return_value = (True, Mock(), None)
    return mock_model

@pytest.fixture(autouse=True)
def disable_security_middleware():
    """在測試中禁用安全中間件的限制"""
    with patch('src.core.security.SecurityMiddleware._before_request'):
        yield

@pytest.fixture
def temp_file():
    """創建一個暫存檔案用於測試"""
    fd, path = tempfile.mkstemp()
    with os.fdopen(fd, 'w') as tmp:
        tmp.write("test content")
    yield path
    os.remove(path)

@pytest.fixture
def mock_database_session():
    """Mock 資料庫 session"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from src.database.models import Base
    
    # 使用記憶體 SQLite 資料庫
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    
    session = SessionLocal()
    yield session
    session.close()

# 測試收集配置
def pytest_collection_modifyitems(config, items):
    """修改測試收集行為"""
    # 為整合測試添加 slow 標記
    for item in items:
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.slow)
        
        # 為資料庫測試添加標記
        if "database" in item.nodeid.lower() or "db" in item.nodeid.lower():
            item.add_marker(pytest.mark.database)


# === 新增的 fixtures ===
"""
測試用的 fixtures 和 mocks
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from flask import Flask


@pytest.fixture
def mock_config():
    """標準測試配置"""
    return {
        'app': {
            'name': 'Test Bot',
            'version': '2.0.0'
        },
        'platforms': {
            'line': {
                'enabled': True,
                'channel_access_token': 'test_token',
                'channel_secret': 'test_secret'
            }
        },
        'llm': {'provider': 'openai'},
        'openai': {
            'api_key': 'test_key',
            'assistant_id': 'test_assistant'
        },
        'db': {
            'host': 'localhost',
            'port': 5432,
            'user': 'test',
            'password': 'test',
            'db_name': 'test'
        },
        'auth': {
            'method': 'simple_password',
            'password': 'test123'
        }
    }


@pytest.fixture
def mock_app(mock_config):
    """創建 mock 應用"""
    with patch('src.core.config.load_config', return_value=mock_config):
        # 創建基本的 Flask 應用
        app = Flask(__name__)
        app.config['TESTING'] = True
        
        # 添加基本路由
        @app.route('/health')
        def health():
            return {'status': 'healthy'}
        
        @app.route('/')
        def root():
            return {'name': 'Test Bot', 'version': '2.0.0'}
        
        return app


@pytest.fixture
def mock_database():
    """Mock 資料庫"""
    db = Mock()
    db.get_session = Mock()
    db.get_connection_info = Mock(return_value={
        'pool_size': 10,
        'checked_out': 1
    })
    return db


@pytest.fixture
def mock_model():
    """Mock AI 模型"""
    model = Mock()
    model.check_connection.return_value = (True, None)
    model.get_provider.return_value = Mock(value='openai')
    model.chat_with_user.return_value = (True, Mock(answer='Test response'), None)
    return model


@pytest.fixture
def patched_app(mock_config):
    """完全 patched 的應用"""
    with patch('src.core.config.load_config', return_value=mock_config), \
         patch('src.database.connection.Database') as MockDB, \
         patch('src.models.factory.ModelFactory.create_from_config') as mock_factory:
        
        # 設定 mock
        MockDB.return_value = Mock()
        mock_factory.return_value = Mock()
        
        # 只 patch 初始化方法
        with patch('src.app.MultiPlatformChatBot._initialize_database'), \
             patch('src.app.MultiPlatformChatBot._initialize_model'), \
             patch('src.app.MultiPlatformChatBot._initialize_core_service'), \
             patch('src.app.MultiPlatformChatBot._initialize_platforms'), \
             patch('src.app.MultiPlatformChatBot._register_cleanup'):
            
            from main import create_app
            app = create_app()
            app.config['TESTING'] = True
            
            yield app
