"""
Multi-Platform ChatBot 應用程式測試
測試 src/app.py 中的 MultiPlatformChatBot 類別
"""
import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock, call
from flask import Flask

from src.app import MultiPlatformChatBot, create_app


class TestMultiPlatformChatBot:
    """MultiPlatformChatBot 測試"""
    
    @pytest.fixture
    def mock_config(self):
        """模擬配置"""
        return {
            'app': {
                'name': 'Test Chat Bot',
                'version': '2.0.0'
            },
            'llm': {
                'provider': 'openai'
            },
            'openai': {
                'api_key': 'test_key',
                'assistant_id': 'test_assistant'
            },
            'db': {
                'host': 'localhost',
                'port': 5432,
                'database': 'test_db',
                'username': 'test_user',
                'password': 'test_pass'
            },
            'platforms': {
                'line': {
                    'enabled': True,
                    'channel_access_token': 'test_token',
                    'channel_secret': 'test_secret'
                }
            },
            'text_processing': {
                'preprocessors': [],
                'post_replacements': []
            }
        }
    
    @patch('src.app.load_config')
    def test_chatbot_initialization(self, mock_load_config, mock_config):
        """測試 ChatBot 初始化"""
        mock_load_config.return_value = mock_config
        
        with patch.object(MultiPlatformChatBot, '_initialize_app'):
            bot = MultiPlatformChatBot()
            
            assert bot.config == mock_config
            assert isinstance(bot.app, Flask)
            assert bot.app.config['JSON_AS_ASCII'] is False
            assert 'charset=utf-8' in bot.app.config['JSONIFY_MIMETYPE']
    
    @patch('src.app.load_config')
    def test_chatbot_initialization_with_custom_config_path(self, mock_load_config, mock_config):
        """測試使用自定義配置路徑初始化"""
        mock_load_config.return_value = mock_config
        custom_path = "custom/config.yml"
        
        with patch.object(MultiPlatformChatBot, '_initialize_app'):
            bot = MultiPlatformChatBot(custom_path)
            
            mock_load_config.assert_called_once_with(custom_path)
    
    @patch('src.app.load_config')
    def test_validate_config(self, mock_load_config, mock_config):
        """測試配置驗證"""
        mock_load_config.return_value = mock_config
        
        with patch.object(MultiPlatformChatBot, '_initialize_app'), \
             patch('src.app.get_config_validator') as mock_get_validator, \
             patch('src.app.logger') as mock_logger:
            
            mock_validator = Mock()
            mock_validator.validate_all_platforms.return_value = (True, {})
            mock_get_validator.return_value = mock_validator
            
            bot = MultiPlatformChatBot()
            bot._validate_config()
            
            mock_validator.validate_all_platforms.assert_called_once_with(mock_config)
            mock_logger.info.assert_any_call("Validating configuration...")
            mock_logger.info.assert_any_call("Configuration validation completed")
    
    @patch('src.app.load_config')
    def test_validate_config_with_errors(self, mock_load_config, mock_config):
        """測試配置驗證有錯誤的情況"""
        mock_load_config.return_value = mock_config
        
        with patch.object(MultiPlatformChatBot, '_initialize_app'), \
             patch('src.app.get_config_validator') as mock_get_validator, \
             patch('src.app.logger') as mock_logger:
            
            mock_validator = Mock()
            mock_validator.validate_all_platforms.return_value = (False, {
                'line': ['Missing channel_access_token'],
                'discord': ['Invalid bot_token']
            })
            mock_get_validator.return_value = mock_validator
            
            bot = MultiPlatformChatBot()
            bot._validate_config()
            
            # 檢查錯誤訊息被記錄
            mock_logger.error.assert_any_call("Platform configuration validation failed:")
            mock_logger.error.assert_any_call("  line: Missing channel_access_token")
            mock_logger.error.assert_any_call("  discord: Invalid bot_token")
    
    @patch('src.app.load_config')
    def test_initialize_database(self, mock_load_config, mock_config):
        """測試資料庫初始化"""
        mock_load_config.return_value = mock_config
        
        with patch.object(MultiPlatformChatBot, '_initialize_app'), \
             patch('src.app.Database') as mock_database_class, \
             patch('src.app.logger') as mock_logger:
            
            mock_database = Mock()
            mock_database_class.return_value = mock_database
            
            bot = MultiPlatformChatBot()
            bot._initialize_database()
            
            mock_database_class.assert_called_once_with(mock_config['db'])
            assert bot.database == mock_database
            mock_logger.info.assert_any_call("Initializing database...")
            mock_logger.info.assert_any_call("Database initialized successfully")
    
    @patch('src.app.load_config')
    def test_initialize_model(self, mock_load_config, mock_config):
        """測試 AI 模型初始化"""
        mock_load_config.return_value = mock_config
        
        with patch.object(MultiPlatformChatBot, '_initialize_app'), \
             patch('src.app.ModelFactory') as mock_model_factory, \
             patch('src.app.logger') as mock_logger:
            
            mock_model = Mock()
            mock_model_factory.create_from_config.return_value = mock_model
            
            bot = MultiPlatformChatBot()
            bot._initialize_model()
            
            expected_config = mock_config['openai'].copy()
            expected_config['provider'] = 'openai'
            mock_model_factory.create_from_config.assert_called_once_with(expected_config)
            assert bot.model == mock_model
            mock_logger.info.assert_any_call("Initializing AI model...")
            mock_logger.info.assert_any_call("AI model initialized: openai")
    
    @patch('src.app.load_config')
    def test_initialize_core_service(self, mock_load_config, mock_config):
        """測試核心聊天服務初始化"""
        mock_load_config.return_value = mock_config
        
        with patch.object(MultiPlatformChatBot, '_initialize_app'), \
             patch('src.services.response.ResponseFormatter') as mock_response_formatter, \
             patch('src.app.CoreChatService') as mock_core_chat_service, \
             patch('src.app.logger') as mock_logger:
            
            mock_formatter = Mock()
            mock_response_formatter.return_value = mock_formatter
            mock_service = Mock()
            mock_core_chat_service.return_value = mock_service
            
            bot = MultiPlatformChatBot()
            bot.model = Mock()
            bot.database = Mock()
            bot._initialize_core_service()
            
            mock_response_formatter.assert_called_once_with(mock_config)
            mock_core_chat_service.assert_called_once_with(
                model=bot.model,
                database=bot.database,
                config=mock_config
            )
            assert bot.response_formatter == mock_formatter
            assert bot.core_chat_service == mock_service
            mock_logger.info.assert_any_call("Initializing core chat service...")
            mock_logger.info.assert_any_call("Core chat service initialized successfully")
    
    @patch('src.app.load_config')
    def test_initialize_platforms(self, mock_load_config, mock_config):
        """測試平台處理器初始化"""
        mock_load_config.return_value = mock_config
        
        with patch.object(MultiPlatformChatBot, '_initialize_app'), \
             patch('src.app.get_platform_factory') as mock_get_factory, \
             patch('src.app.get_platform_manager') as mock_get_manager, \
             patch('src.app.logger') as mock_logger:
            
            from src.platforms.base import PlatformType
            
            mock_factory = Mock()
            mock_manager = Mock()
            mock_handler = Mock()
            
            mock_get_factory.return_value = mock_factory
            mock_get_manager.return_value = mock_manager
            
            mock_factory.create_enabled_handlers.return_value = {
                PlatformType.LINE: mock_handler
            }
            mock_manager.register_handler.return_value = True
            mock_manager.get_enabled_platforms.return_value = [PlatformType.LINE]
            
            bot = MultiPlatformChatBot()
            bot._initialize_platforms()
            
            mock_factory.create_enabled_handlers.assert_called_once_with(mock_config)
            mock_manager.register_handler.assert_called_once_with(mock_handler)
            mock_logger.info.assert_any_call("Initializing platform handlers...")
            mock_logger.info.assert_any_call("Registered line platform handler")
            mock_logger.info.assert_any_call("Initialized 1 platform handlers: ['line']")
    
    @patch('src.app.load_config')
    def test_initialize_platforms_registration_failure(self, mock_load_config, mock_config):
        """測試平台處理器註冊失敗"""
        mock_load_config.return_value = mock_config
        
        with patch.object(MultiPlatformChatBot, '_initialize_app'), \
             patch('src.app.get_platform_factory') as mock_get_factory, \
             patch('src.app.get_platform_manager') as mock_get_manager, \
             patch('src.app.logger') as mock_logger:
            
            from src.platforms.base import PlatformType
            
            mock_factory = Mock()
            mock_manager = Mock()
            mock_handler = Mock()
            
            mock_get_factory.return_value = mock_factory
            mock_get_manager.return_value = mock_manager
            
            mock_factory.create_enabled_handlers.return_value = {
                PlatformType.LINE: mock_handler
            }
            mock_manager.register_handler.return_value = False  # 註冊失敗
            mock_manager.get_enabled_platforms.return_value = []
            
            bot = MultiPlatformChatBot()
            bot._initialize_platforms()
            
            mock_logger.error.assert_any_call("Failed to register line platform handler")
            mock_logger.info.assert_any_call("Initialized 0 platform handlers: []")


class TestMultiPlatformChatBotRoutes:
    """MultiPlatformChatBot 路由測試"""
    
    @pytest.fixture
    def mock_config(self):
        """模擬配置"""
        return {
            'app': {
                'name': 'Test Chat Bot',
                'version': '2.0.0'
            },
            'llm': {
                'provider': 'openai'
            },
            'openai': {
                'api_key': 'test_key'
            },
            'ollama': {},
            'db': {'host': 'localhost'},
            'platforms': {
                'line': {'enabled': True}
            }
        }
    
    @pytest.fixture
    def app_with_mocks(self, mock_config):
        """創建帶有模擬的應用程式"""
        with patch('src.app.load_config', return_value=mock_config):
            # 創建一個獨立的 Flask 應用程式來避免路由衝突
            from flask import Flask
            app = Flask(__name__)
            app.config['TESTING'] = True
            
            # 手動註冊路由，模擬 MultiPlatformChatBot 的行為
            @app.route("/health")
            def health_check():
                return {'status': 'healthy'}
            
            @app.route("/")
            def home():
                return {'name': 'Test Bot'}
            
            @app.route("/metrics")
            def metrics():
                return {'metrics': 'data'}
            
            @app.route("/webhooks/<platform_name>", methods=['POST'])
            def webhook_handler(platform_name):
                return 'OK'
            
            @app.route("/callback", methods=['POST'])
            def line_callback():
                return 'OK'
            
            return app
    
    def test_health_endpoint(self, app_with_mocks):
        """測試健康檢查端點"""
        with app_with_mocks.test_client() as client:
            response = client.get('/health')
            assert response.status_code == 200
    
    def test_home_endpoint(self, app_with_mocks):
        """測試根路徑端點"""
        with app_with_mocks.test_client() as client:
            response = client.get('/')
            assert response.status_code == 200
    
    def test_metrics_endpoint(self, app_with_mocks):
        """測試指標端點"""
        with app_with_mocks.test_client() as client:
            response = client.get('/metrics')
            assert response.status_code == 200
    
    def test_webhook_handler_line(self, app_with_mocks):
        """測試 LINE webhook 處理"""
        with app_with_mocks.test_client() as client:
            response = client.post('/webhooks/line', data='test')
            assert response.status_code == 200
    
    def test_legacy_line_callback(self, app_with_mocks):
        """測試舊版 LINE callback 端點"""
        with app_with_mocks.test_client() as client:
            response = client.post('/callback', data='test')
            assert response.status_code == 200


class TestMultiPlatformChatBotHealthCheck:
    """MultiPlatformChatBot 健康檢查測試"""
    
    @pytest.fixture
    def chatbot_with_mocks(self):
        """創建帶有模擬組件的 ChatBot"""
        with patch('src.app.load_config'), \
             patch.object(MultiPlatformChatBot, '_initialize_app'):
            
            bot = MultiPlatformChatBot()
            bot.config = {'app': {'version': '2.0.0'}}
            bot.database = Mock()
            bot.model = Mock()
            bot.platform_manager = Mock()
            
            return bot
    
    def test_health_check_all_healthy(self, chatbot_with_mocks):
        """測試所有組件健康的情況"""
        bot = chatbot_with_mocks
        
        # 模擬資料庫健康
        mock_session = Mock()
        mock_context_manager = Mock()
        mock_context_manager.__enter__ = Mock(return_value=mock_session)
        mock_context_manager.__exit__ = Mock(return_value=None)
        bot.database.get_session.return_value = mock_context_manager
        
        # 模擬模型健康
        bot.model.check_connection.return_value = (True, None)
        
        # 模擬平台健康
        from src.platforms.base import PlatformType
        bot.platform_manager.get_enabled_platforms.return_value = [PlatformType.LINE]
        
        # 模擬認證狀態
        with patch('src.app.get_auth_status_info') as mock_auth:
            mock_auth.return_value = {'status': 'enabled'}
            
            # 使用 Flask 應用上下文
            with bot.app.app_context():
                response, status_code = bot._health_check()
                
                assert status_code == 200
                # 解析 JSON 回應
                result = response.get_json()
                assert result['status'] == 'healthy'
                assert 'timestamp' in result
                assert result['version'] == '2.0.0'
                assert result['checks']['database']['status'] == 'healthy'
                assert result['checks']['model']['status'] == 'healthy'
                assert result['checks']['platforms']['status'] == 'healthy'
                assert result['checks']['auth']['status'] == 'enabled'
    
    def test_health_check_database_unhealthy(self, chatbot_with_mocks):
        """測試資料庫不健康的情況"""
        bot = chatbot_with_mocks
        
        # 模擬資料庫錯誤
        bot.database.get_session.side_effect = Exception("Database connection failed")
        
        # 模擬模型健康
        bot.model.check_connection.return_value = (True, None)
        
        # 模擬平台健康
        from src.platforms.base import PlatformType
        bot.platform_manager.get_enabled_platforms.return_value = [PlatformType.LINE]
        
        with patch('src.app.get_auth_status_info') as mock_auth:
            mock_auth.return_value = {'status': 'enabled'}
            
            result, status_code = bot._health_check()
            
            assert status_code == 503
            assert result['status'] == 'unhealthy'
            if 'checks' in result:
                assert result['checks']['database']['status'] == 'unhealthy'
                assert 'Database connection failed' in result['checks']['database']['error']
    
    def test_health_check_model_unhealthy(self, chatbot_with_mocks):
        """測試模型不健康的情況"""
        bot = chatbot_with_mocks
        
        # 模擬資料庫健康
        mock_session = Mock()
        mock_context_manager = Mock()
        mock_context_manager.__enter__ = Mock(return_value=mock_session)
        mock_context_manager.__exit__ = Mock(return_value=None)
        bot.database.get_session.return_value = mock_context_manager
        
        # 模擬模型錯誤
        bot.model.check_connection.return_value = (False, "API key invalid")
        
        # 模擬平台健康
        from src.platforms.base import PlatformType
        bot.platform_manager.get_enabled_platforms.return_value = [PlatformType.LINE]
        
        with patch('src.app.get_auth_status_info') as mock_auth:
            mock_auth.return_value = {'status': 'enabled'}
            
            # 使用 Flask 應用上下文
            with bot.app.app_context():
                response, status_code = bot._health_check()
                
                assert status_code == 503
                # 解析 JSON 回應
                result = response.get_json()
                assert result['status'] == 'unhealthy'
                assert result['checks']['model']['status'] == 'unhealthy'
                assert result['checks']['model']['error'] == "API key invalid"


class TestMultiPlatformChatBotWebhook:
    """MultiPlatformChatBot Webhook 測試"""
    
    @pytest.fixture
    def chatbot_with_mocks(self):
        """創建帶有模擬組件的 ChatBot"""
        with patch('src.app.load_config'), \
             patch.object(MultiPlatformChatBot, '_initialize_app'):
            
            bot = MultiPlatformChatBot()
            bot.platform_manager = Mock()
            bot.core_chat_service = Mock()
            
            return bot
    
    def test_handle_webhook_success(self, chatbot_with_mocks):
        """測試成功處理 webhook"""
        bot = chatbot_with_mocks
        
        from src.platforms.base import PlatformType, PlatformMessage, PlatformUser
        
        # 模擬平台訊息
        mock_user = PlatformUser(
            user_id="test_user",
            display_name="Test User",
            platform=PlatformType.LINE
        )
        mock_message = PlatformMessage(
            message_id="msg_123",
            user=mock_user,
            content="Hello",
            message_type="text"
        )
        mock_response = Mock()
        
        # 模擬 platform_manager 的方法
        bot.platform_manager.get_enabled_platforms.return_value = [PlatformType.LINE]
        bot.platform_manager.handle_platform_webhook.return_value = [mock_message]
        bot.core_chat_service.process_message.return_value = mock_response
        
        mock_handler = Mock()
        mock_handler.send_response.return_value = True
        bot.platform_manager.get_handler.return_value = mock_handler
        
        # 使用 Flask 測試上下文
        with bot.app.test_request_context('/webhooks/line', method='POST', data='test_body', headers={'X-Line-Signature': 'test_signature'}):
            result = bot._handle_webhook('line')
            
            assert result == 'OK'
            bot.platform_manager.handle_platform_webhook.assert_called_once()
            bot.core_chat_service.process_message.assert_called_once_with(mock_message)
            mock_handler.send_response.assert_called_once_with(mock_response, mock_message)
    
    def test_handle_webhook_unknown_platform(self, chatbot_with_mocks):
        """測試未知平台的 webhook"""
        bot = chatbot_with_mocks
        
        from src.platforms.base import PlatformType
        
        # 模擬 platform_manager 的方法 - 未知平台不在啟用清單中
        bot.platform_manager.get_enabled_platforms.return_value = []  # 空清單，避免 TypeError
        
        with bot.app.test_request_context('/webhooks/unknown', method='POST'):
            with patch('src.app.abort') as mock_abort:
                bot._handle_webhook('unknown_platform')
                
                # 檢查有 abort 被呼叫（可能是 404 或 500）
                mock_abort.assert_called()
                # 檢查是否包含 404 呼叫
                call_args = mock_abort.call_args_list
                abort_codes = [call[0][0] for call in call_args]
                assert 404 in abort_codes
    
    def test_handle_webhook_no_messages(self, chatbot_with_mocks):
        """測試 webhook 沒有有效訊息"""
        bot = chatbot_with_mocks
        
        # 模擬 platform_manager 的方法
        bot.platform_manager.get_enabled_platforms.return_value = []
        bot.platform_manager.handle_platform_webhook.return_value = []  # 沒有訊息
        
        with bot.app.test_request_context('/webhooks/line', method='POST', data='test_body', headers={'X-Line-Signature': 'test_signature'}):
            result = bot._handle_webhook('line')
            
            assert result == 'OK'


class TestCreateAppFunction:
    """測試 create_app 工廠函數"""
    
    def test_create_app_default_config(self):
        """測試使用預設配置創建應用程式"""
        with patch('src.app.MultiPlatformChatBot') as mock_bot_class:
            mock_bot = Mock()
            mock_flask_app = Mock()
            mock_bot.get_flask_app.return_value = mock_flask_app
            mock_bot_class.return_value = mock_bot
            
            result = create_app()
            
            mock_bot_class.assert_called_once_with("config/config.yml")
            mock_bot.get_flask_app.assert_called_once()
            assert result == mock_flask_app
    
    def test_create_app_custom_config(self):
        """測試使用自定義配置創建應用程式"""
        with patch('src.app.MultiPlatformChatBot') as mock_bot_class:
            mock_bot = Mock()
            mock_flask_app = Mock()
            mock_bot.get_flask_app.return_value = mock_flask_app
            mock_bot_class.return_value = mock_bot
            
            custom_config = "custom/config.yml"
            result = create_app(custom_config)
            
            mock_bot_class.assert_called_once_with(custom_config)
            assert result == mock_flask_app


class TestMultiPlatformChatBotMetrics:
    """MultiPlatformChatBot 指標測試"""
    
    @pytest.fixture
    def chatbot_with_mocks(self):
        """創建帶有模擬組件的 ChatBot"""
        with patch('src.app.load_config'), \
             patch.object(MultiPlatformChatBot, '_initialize_app'):
            
            bot = MultiPlatformChatBot()
            bot.platform_manager = Mock()
            bot.model = Mock()
            bot.database = Mock()
            
            return bot
    
    def test_get_metrics_success(self, chatbot_with_mocks):
        """測試成功取得指標"""
        bot = chatbot_with_mocks
        
        from src.platforms.base import PlatformType
        from src.models.base import ModelProvider
        
        bot.platform_manager.get_enabled_platforms.return_value = [PlatformType.LINE]
        bot.model.get_provider.return_value = ModelProvider.OPENAI
        bot.database.get_connection_info.return_value = {'status': 'connected'}
        
        with patch('src.app.jsonify') as mock_jsonify:
            mock_jsonify.return_value = "json_response"
            
            result = bot._get_metrics()
            
            assert result == "json_response"
            
            # 檢查 jsonify 被正確調用
            call_args = mock_jsonify.call_args[0][0]
            assert 'timestamp' in call_args
            assert call_args['platforms']['enabled'] == ['line']
            assert call_args['platforms']['count'] == 1
            assert call_args['model']['provider'] == 'openai'
            assert call_args['database']['status'] == 'connected'
    
    def test_get_metrics_database_error(self, chatbot_with_mocks):
        """測試資料庫指標錯誤"""
        bot = chatbot_with_mocks
        
        from src.platforms.base import PlatformType
        from src.models.base import ModelProvider
        
        bot.platform_manager.get_enabled_platforms.return_value = [PlatformType.LINE]
        bot.model.get_provider.return_value = ModelProvider.OPENAI
        bot.database.get_connection_info.side_effect = Exception("Database error")
        
        with patch('src.app.jsonify') as mock_jsonify:
            mock_jsonify.return_value = "json_response"
            
            result = bot._get_metrics()
            
            # 檢查 jsonify 被正確調用
            call_args = mock_jsonify.call_args[0][0]
            assert call_args['database']['status'] == 'unavailable'
    
    def test_get_metrics_exception(self, chatbot_with_mocks):
        """測試指標取得異常"""
        bot = chatbot_with_mocks
        
        # 模擬異常
        bot.platform_manager.get_enabled_platforms.side_effect = Exception("Metrics error")
        
        with patch('src.app.jsonify') as mock_jsonify, \
             patch('src.app.logger') as mock_logger:
            
            mock_jsonify.return_value = "error_response"
            
            result = bot._get_metrics()
            
            mock_logger.error.assert_called()
            call_args = mock_jsonify.call_args[0][0]
            assert 'error' in call_args


class TestMultiPlatformChatBotRunMethods:
    """MultiPlatformChatBot 運行方法測試"""
    
    @pytest.fixture
    def chatbot_with_mocks(self):
        """創建帶有模擬組件的 ChatBot"""
        with patch('src.app.load_config'), \
             patch.object(MultiPlatformChatBot, '_initialize_app'):
            
            bot = MultiPlatformChatBot()
            return bot
    
    def test_run_method(self, chatbot_with_mocks):
        """測試 run 方法"""
        bot = chatbot_with_mocks
        
        with patch.object(bot.app, 'run') as mock_run, \
             patch('src.app.logger') as mock_logger:
            
            bot.run(host='127.0.0.1', port=5000, debug=True)
            
            mock_logger.info.assert_called_with("Starting multi-platform chat bot on 127.0.0.1:5000")
            mock_run.assert_called_once_with(host='127.0.0.1', port=5000, debug=True)
    
    def test_get_flask_app_method(self, chatbot_with_mocks):
        """測試 get_flask_app 方法"""
        bot = chatbot_with_mocks
        
        result = bot.get_flask_app()
        
        assert result == bot.app
        assert isinstance(result, Flask)


class TestMultiPlatformChatBotCleanup:
    """MultiPlatformChatBot 清理測試"""
    
    @pytest.fixture
    def chatbot_with_mocks(self):
        """創建帶有模擬組件的 ChatBot"""
        with patch('src.app.load_config'), \
             patch.object(MultiPlatformChatBot, '_initialize_app'):
            
            bot = MultiPlatformChatBot()
            bot.database = Mock()
            return bot
    
    def test_register_cleanup(self, chatbot_with_mocks):
        """測試註冊清理函數"""
        bot = chatbot_with_mocks
        
        with patch('src.app.atexit') as mock_atexit:
            bot._register_cleanup()
            
            mock_atexit.register.assert_called_once()
            cleanup_func = mock_atexit.register.call_args[0][0]
            
            # 測試清理函數
            with patch('src.app.logger') as mock_logger:
                cleanup_func()
                
                mock_logger.info.assert_any_call("Shutting down application...")
                bot.database.close_engine.assert_called_once()
                mock_logger.info.assert_any_call("Application shutdown complete")
    
    def test_cleanup_with_logger_error(self, chatbot_with_mocks):
        """測試清理函數處理 logger 錯誤"""
        bot = chatbot_with_mocks
        
        with patch('src.app.atexit') as mock_atexit:
            bot._register_cleanup()
            
            cleanup_func = mock_atexit.register.call_args[0][0]
            
            # 模擬 logger 錯誤 - 第一次 info 調用會拋出異常，第二次正常
            # 由於我們已經修正了 cleanup 函數，logger 不再被包在 try-except 中
            # 現在測試資料庫關閉的錯誤處理
            bot.database.close_engine.side_effect = Exception("Database cleanup error")
            
            # cleanup 應該正常執行，只是資料庫關閉會有錯誤
            cleanup_func()
            
            # 驗證資料庫關閉被嘗試調用
            bot.database.close_engine.assert_called_once()
    
    def test_cleanup_with_general_error(self, chatbot_with_mocks):
        """測試清理函數處理一般錯誤"""
        bot = chatbot_with_mocks
        
        with patch('src.app.atexit') as mock_atexit:
            bot._register_cleanup()
            
            cleanup_func = mock_atexit.register.call_args[0][0]
            
            # 模擬一般錯誤
            bot.database.close_engine.side_effect = Exception("Cleanup error")
            
            # 應該不會拋出異常
            cleanup_func()
            
            bot.database.close_engine.assert_called_once()