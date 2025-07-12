"""
測試 LINE 平台處理器的單元測試
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from src.platforms.line_handler import LineHandler
from src.platforms.base import PlatformType, PlatformMessage, PlatformResponse, PlatformUser


class TestLineHandlerInitialization:
    """測試 LineHandler 初始化"""
    
    def test_initialization_success(self):
        """測試成功初始化"""
        config = {
            'platforms': {
                'line': {
                    'enabled': True,
                    'channel_access_token': 'test_token',
                    'channel_secret': 'test_secret'
                }
            }
        }
        
        with patch('src.platforms.line_handler.WebhookParser') as mock_parser, \
             patch('src.platforms.line_handler.Configuration') as mock_config:
            
            handler = LineHandler(config)
            
            # 檢查基本屬性
            assert handler.get_config('channel_access_token') == 'test_token'
            assert handler.get_config('channel_secret') == 'test_secret'
            assert handler.get_platform_type() == PlatformType.LINE
            
            # 檢查 LINE SDK 對象是否被創建（因為配置有效且啟用）
            mock_parser.assert_called_once_with('test_secret')
            mock_config.assert_called_once_with(access_token='test_token')
            
            # 檢查實例屬性
            assert hasattr(handler, 'parser')
            assert hasattr(handler, 'configuration')
    
    def test_initialization_missing_config(self):
        """測試缺少配置時的初始化"""
        config = {
            'platforms': {
                'line': {
                    'enabled': True,
                    # 缺少必要的配置
                }
            }
        }
        
        # 初始化應該成功但配置驗證失敗
        handler = LineHandler(config)
        assert not handler.validate_config()
    
    def test_get_required_config_fields(self):
        """測試獲取必需配置字段"""
        config = {
            'platforms': {
                'line': {
                    'enabled': False,  # 禁用以避免初始化
                }
            }
        }
        
        handler = LineHandler(config)
        fields = handler.get_required_config_fields()
        
        assert 'channel_access_token' in fields
        assert 'channel_secret' in fields


class TestLineHandlerMessageParsing:
    """測試訊息解析功能"""
    
    @pytest.fixture
    def handler(self):
        config = {
            'platforms': {
                'line': {
                    'enabled': True,
                    'channel_access_token': 'test_token',
                    'channel_secret': 'test_secret'
                }
            }
        }
        
        with patch('src.platforms.line_handler.WebhookParser') as mock_parser, \
             patch('src.platforms.line_handler.Configuration') as mock_config:
            
            handler = LineHandler(config)
            
            # 確保 handler 有必要的屬性（模擬完整初始化）
            if not hasattr(handler, 'parser'):
                handler.parser = mock_parser.return_value
            if not hasattr(handler, 'configuration'):
                handler.configuration = mock_config.return_value
            
            return handler
    
    def test_parse_text_message(self, handler):
        """測試解析文字訊息"""
        from linebot.v3.webhooks import MessageEvent, TextMessageContent
        
        # 模擬真實的 LINE 事件對象
        mock_event = Mock(spec=MessageEvent)
        mock_event.source = Mock()
        mock_event.source.user_id = 'test_user_123'
        mock_event.source.type = 'user'
        mock_event.reply_token = 'reply_token_456'
        
        mock_content = Mock(spec=TextMessageContent)
        mock_content.id = 'msg_id_123'
        mock_content.text = 'Hello World'
        mock_event.message = mock_content
        
        result = handler.parse_message(mock_event)
        
        assert result is not None
        assert isinstance(result, PlatformMessage)
        assert result.content == 'Hello World'
        assert result.user.user_id == 'test_user_123'
        assert result.message_type == 'text'
    
    def test_parse_audio_message(self, handler):
        """測試解析音訊訊息"""
        from linebot.v3.webhooks import MessageEvent, AudioMessageContent
        
        # 確保 handler 有必要的屬性（模擬完整初始化）
        if not hasattr(handler, 'configuration'):
            with patch('src.platforms.line_handler.Configuration') as mock_config:
                handler.configuration = mock_config.return_value
        
        # 模擬真實的 LINE 音訊事件
        mock_event = Mock(spec=MessageEvent)
        mock_event.source = Mock()
        mock_event.source.user_id = 'test_user_123'
        mock_event.source.type = 'user'
        mock_event.reply_token = 'reply_token_456'
        
        mock_content = Mock(spec=AudioMessageContent)
        mock_content.id = 'audio_id_123'
        mock_content.duration = 5000
        mock_event.message = mock_content
        
        # Mock API client and blob download
        with patch('src.platforms.line_handler.ApiClient') as mock_api_client, \
             patch('src.platforms.line_handler.MessagingApiBlob') as mock_blob_api:
            
            # 設置模擬的 API 客戶端上下文管理器
            mock_api_client.return_value.__enter__ = Mock(return_value=mock_api_client.return_value)
            mock_api_client.return_value.__exit__ = Mock(return_value=None)
            
            mock_blob_api.return_value.get_message_content.return_value = b'audio_data'
            
            result = handler.parse_message(mock_event)
            
            assert result is not None
            assert result.message_type == 'audio'
            assert result.raw_data == b'audio_data'
            assert result.content == '[Audio Message]'
    
    def test_parse_unsupported_message(self, handler):
        """測試解析不支援的訊息類型"""
        mock_event = Mock()
        mock_event.message = Mock()
        
        # 模擬不支援的訊息類型
        result = handler.parse_message(mock_event)
        
        assert result is None


class TestLineHandlerWebhook:
    """測試 Webhook 處理"""

    @pytest.fixture
    def handler(self):
        config = {
            'platforms': {
                'line': {
                    'enabled': True,
                    'channel_access_token': 'test_token',
                    'channel_secret': 'test_secret'
                }
            }
        }
        with patch('src.platforms.line_handler.WebhookParser') as mock_parser, \
             patch('src.platforms.line_handler.Configuration') as mock_config:
            handler = LineHandler(config)
            handler.parser = mock_parser.return_value
            handler.configuration = mock_config.return_value
            return handler

    def test_handle_webhook_success_with_events(self, handler):
        """測試成功處理帶有事件的 webhook"""
        request_body = '{"events": ["event1", "event2"]}'
        headers = {'X-Line-Signature': 'valid_signature'}
        
        # 模擬 parser 回傳兩個事件
        mock_event1 = Mock()
        mock_event2 = Mock()
        handler.parser.parse.return_value = [mock_event1, mock_event2]
        
        # 模擬 parse_message 的回傳值
        mock_user = PlatformUser(user_id="test_user", platform=PlatformType.LINE)
        mock_msg = PlatformMessage(message_id="1", user=mock_user, content="msg1")
        with patch.object(handler, 'parse_message', side_effect=[mock_msg, None]) as mock_parse_message:
            messages = handler.handle_webhook(request_body, headers)
            
            # 驗證 messages 不是 None
            assert messages is not None
            assert isinstance(messages, list)
            
            # 驗證 parser 被正確呼叫
            handler.parser.parse.assert_called_once_with(request_body, headers['X-Line-Signature'])
            
            # 驗證 parse_message 被呼叫兩次
            assert mock_parse_message.call_count == 2
            mock_parse_message.assert_any_call(mock_event1)
            mock_parse_message.assert_any_call(mock_event2)
            
            # 驗證回傳的訊息列表
            assert len(messages) == 1
            assert messages[0].content == "msg1"

    def test_handle_webhook_invalid_signature(self, handler):
        """測試無效簽名的 webhook"""
        request_body = '{"events": []}'
        headers = {'X-Line-Signature': 'invalid_signature'}
        
        from linebot.v3.exceptions import InvalidSignatureError
        handler.parser.parse.side_effect = InvalidSignatureError('Invalid signature')
        
        messages = handler.handle_webhook(request_body, headers)
        
        assert messages == []
        handler.parser.parse.assert_called_once_with(request_body, headers['X-Line-Signature'])

    def test_handle_webhook_no_signature(self, handler):
        """測試沒有簽名的 webhook"""
        request_body = '{"events": []}'
        
        messages = handler.handle_webhook(request_body, {}) # 空 headers
        
        assert messages == []
        handler.parser.parse.assert_not_called()

    def test_handle_webhook_parser_exception(self, handler):
        """測試解析器拋出一般例外"""
        request_body = '{"events": []}'
        headers = {'X-Line-Signature': 'valid_signature'}
        
        handler.parser.parse.side_effect = Exception('Something went wrong')
        
        messages = handler.handle_webhook(request_body, headers)
        
        assert messages == []
        handler.parser.parse.assert_called_once_with(request_body, headers['X-Line-Signature'])


class TestLineHandlerResponse:
    """測試回應發送"""
    
    @pytest.fixture
    def handler(self):
        config = {
            'platforms': {
                'line': {
                    'enabled': True,
                    'channel_access_token': 'test_token',
                    'channel_secret': 'test_secret'
                }
            }
        }
        
        with patch('src.platforms.line_handler.WebhookParser') as mock_parser, \
             patch('src.platforms.line_handler.Configuration') as mock_config:
            
            handler = LineHandler(config)
            
            # 確保 handler 有必要的屬性（模擬完整初始化）
            if not hasattr(handler, 'parser'):
                handler.parser = mock_parser.return_value
            if not hasattr(handler, 'configuration'):
                handler.configuration = mock_config.return_value
            
            return handler
    
    def test_send_response_success(self, handler):
        """測試成功發送回應"""
        response = PlatformResponse(content='Hello back!')
        message = Mock()
        message.reply_token = 'reply_token_123'
        message.user = Mock()
        message.user.user_id = 'test_user_123'
        
        # 確保 handler 有必要的屬性（模擬完整初始化）
        if not hasattr(handler, 'configuration'):
            with patch('src.platforms.line_handler.Configuration') as mock_config:
                handler.configuration = mock_config.return_value
        
        # Mock ApiClient 和 MessagingApi
        with patch('src.platforms.line_handler.ApiClient') as mock_api_client, \
             patch('src.platforms.line_handler.MessagingApi') as mock_messaging_api:
            
            # 設置模擬的 API 客戶端上下文管理器
            mock_api_client.return_value.__enter__ = Mock(return_value=mock_api_client.return_value)
            mock_api_client.return_value.__exit__ = Mock(return_value=None)
            
            result = handler.send_response(response, message)
            
            assert result is True
            mock_messaging_api.assert_called_once_with(mock_api_client.return_value)
            mock_messaging_api.return_value.reply_message_with_http_info.assert_called_once()
    
    def test_send_response_missing_reply_token(self, handler):
        """測試缺少 reply token 時的回應"""
        response = PlatformResponse(content='Hello back!')
        message = Mock()
        message.reply_token = None
        
        result = handler.send_response(response, message)
        
        assert result is False