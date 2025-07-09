"""
Slack 處理器單元測試
"""
import pytest
import json
import hmac
import hashlib
import time
from unittest.mock import Mock, patch, MagicMock
from src.platforms.base import PlatformType, PlatformUser, PlatformMessage, PlatformResponse
from src.platforms.slack_handler import SlackHandler, SlackUtils


class TestSlackHandler:
    """測試 Slack 處理器"""
    
    def setup_method(self):
        """每個測試方法前的設置"""
        self.valid_config = {
            'platforms': {
                'slack': {
                    'enabled': True,
                    'bot_token': 'xoxb-test-token',
                    'signing_secret': 'test_signing_secret',
                    'app_token': 'xapp-test-token'
                }
            }
        }
        
        self.invalid_config = {
            'platforms': {
                'slack': {
                    'enabled': True,
                    # 缺少必要的 bot_token 和 signing_secret
                }
            }
        }
        
        self.disabled_config = {
            'platforms': {
                'slack': {
                    'enabled': False,
                    'bot_token': 'xoxb-test-token',
                    'signing_secret': 'test_signing_secret'
                }
            }
        }
    
    def test_slack_handler_initialization_without_slack_bolt(self):
        """測試在沒有 slack-bolt 的情況下初始化"""
        with patch('src.platforms.slack_handler.SLACK_AVAILABLE', False):
            handler = SlackHandler(self.valid_config)
            
            assert handler.get_platform_type() == PlatformType.SLACK
            assert not hasattr(handler, 'app') or handler.app is None
            assert not hasattr(handler, 'client') or handler.client is None
            assert not hasattr(handler, 'request_handler') or handler.request_handler is None
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_slack_handler_initialization_with_valid_config(self):
        """測試使用有效配置初始化（簡化版）"""
        handler = SlackHandler(self.valid_config)
        
        assert handler.get_platform_type() == PlatformType.SLACK
        assert handler.bot_token == 'xoxb-test-token'
        assert handler.signing_secret == 'test_signing_secret'
        assert handler.app_token == 'xapp-test-token'
        # 由於沒有真正的 Slack SDK，不檢查實際的 app/client 實例
    
    def test_slack_handler_initialization_with_invalid_config(self):
        """測試使用無效配置初始化"""
        handler = SlackHandler(self.invalid_config)
        
        assert handler.get_platform_type() == PlatformType.SLACK
        assert not handler.validate_config()
    
    def test_slack_handler_initialization_with_disabled_config(self):
        """測試使用禁用配置初始化"""
        handler = SlackHandler(self.disabled_config)
        
        assert handler.get_platform_type() == PlatformType.SLACK
        assert not handler.is_enabled()
    
    def test_get_required_config_fields(self):
        """測試取得必要配置欄位"""
        handler = SlackHandler(self.valid_config)
        required_fields = handler.get_required_config_fields()
        
        assert 'bot_token' in required_fields
        assert 'signing_secret' in required_fields
        assert len(required_fields) == 2
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_parse_message_text_message(self):
        """測試解析文字訊息"""
        handler = SlackHandler(self.valid_config)
        
        # Mock _get_user_info 方法
        mock_user_info = {
            'name': 'testuser',
            'real_name': 'Test User',
            'display_name': 'Test User',
            'is_bot': False,
            'tz': 'America/New_York',
            'profile': {'email': 'test@example.com'}
        }
        
        with patch.object(handler, '_get_user_info', return_value=mock_user_info):
            # 創建 mock Slack 事件
            slack_event = {
                'event': {
                    'type': 'message',
                    'user': 'U123456789',
                    'text': 'Hello, Slack!',
                    'channel': 'C987654321',
                    'ts': '1234567890.123456',
                    'team': 'T111222333',
                    'channel_type': 'channel',
                    'event_ts': '1234567890.123456',
                    'files': []
                }
            }
            
            parsed_message = handler.parse_message(slack_event)
        
        assert parsed_message is not None
        assert parsed_message.message_id == '1234567890.123456'
        assert parsed_message.user.user_id == 'U123456789'
        assert parsed_message.user.display_name == 'Test User'
        assert parsed_message.user.username == 'testuser'
        assert parsed_message.user.platform == PlatformType.SLACK
        assert parsed_message.content == 'Hello, Slack!'
        assert parsed_message.message_type == 'text'
        assert parsed_message.metadata['channel_id'] == 'C987654321'
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_parse_message_app_mention(self):
        """測試解析應用提及"""
        handler = SlackHandler(self.valid_config)
        
        # Mock _get_user_info 方法
        mock_user_info = {
            'name': 'testuser',
            'real_name': 'Test User',
            'display_name': 'Test User',
            'is_bot': False,
            'tz': 'America/New_York',
            'profile': {'email': 'test@example.com'}
        }
        
        with patch.object(handler, '_get_user_info', return_value=mock_user_info):
            # 創建 mock Slack 事件（應用提及）
            slack_event = {
                'event': {
                    'type': 'app_mention',
                    'user': 'U123456789',
                    'text': '<@U987654321> hello bot',
                    'channel': 'C987654321',
                    'ts': '1234567890.123456',
                    'team': 'T111222333',
                    'channel_type': 'channel',
                    'event_ts': '1234567890.123456',
                    'files': []
                }
            }
            
            parsed_message = handler.parse_message(slack_event)
        
        assert parsed_message is not None
        assert parsed_message.message_id == '1234567890.123456'
        assert parsed_message.user.user_id == 'U123456789'
        assert parsed_message.content == 'hello bot'  # 應移除 bot 提及
        assert parsed_message.message_type == 'text'
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_parse_message_audio_file(self):
        """測試解析音訊檔案"""
        handler = SlackHandler(self.valid_config)
        
        # Mock _get_user_info 和 _download_slack_file 方法
        mock_user_info = {
            'name': 'testuser',
            'real_name': 'Test User',
            'display_name': 'Test User',
            'is_bot': False,
            'tz': 'America/New_York',
            'profile': {'email': 'test@example.com'}
        }
        
        with patch.object(handler, '_get_user_info', return_value=mock_user_info):
            with patch.object(handler, '_download_slack_file', return_value=b'fake_audio_data'):
                # 創建 mock Slack 事件（包含音訊檔案）
                slack_event = {
                    'event': {
                        'type': 'message',
                        'user': 'U123456789',
                        'text': '',
                        'channel': 'C987654321',
                        'ts': '1234567890.123456',
                        'team': 'T111222333',
                        'channel_type': 'channel',
                        'event_ts': '1234567890.123456',
                        'files': [
                            {
                                'id': 'F123456789',
                                'mimetype': 'audio/mpeg',
                                'name': 'audio.mp3',
                                'url_private': 'https://files.slack.com/files-pri/T111222333-F123456789/audio.mp3',
                                'url_private_download': 'https://files.slack.com/files-pri/T111222333-F123456789/download/audio.mp3'
                            }
                        ]
                    }
                }
                
                parsed_message = handler.parse_message(slack_event)
        
        assert parsed_message is not None
        assert parsed_message.message_id == '1234567890.123456'
        assert parsed_message.user.user_id == 'U123456789'
        assert parsed_message.content == '[Audio Message]'
        assert parsed_message.message_type == 'audio'
        assert parsed_message.raw_data == b'fake_audio_data'
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_parse_message_invalid_event(self):
        """測試解析無效事件"""
        handler = SlackHandler(self.valid_config)
        
        # 測試非字典事件
        invalid_event = "not a dict"
        parsed_message = handler.parse_message(invalid_event)
        
        assert parsed_message is None
        
        # 測試不支援的事件類型
        invalid_event = {
            'event': {
                'type': 'unsupported_event',
                'user': 'U123456789',
                'text': 'Hello'
            }
        }
        
        parsed_message = handler.parse_message(invalid_event)
        
        assert parsed_message is None
        
        # 測試 bot 訊息
        bot_event = {
            'event': {
                'type': 'message',
                'bot_id': 'B123456789',
                'text': 'Bot message'
            }
        }
        
        parsed_message = handler.parse_message(bot_event)
        
        assert parsed_message is None
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_send_response_success(self):
        """測試成功發送回應"""
        handler = SlackHandler(self.valid_config)
        
        # Mock WebClient
        mock_client = Mock()
        mock_client.chat_postMessage.return_value = {'ok': True}
        handler.client = mock_client
        
        user = PlatformUser(user_id="U123456789", platform=PlatformType.SLACK)
        message = PlatformMessage(
            message_id="1234567890.123456",
            user=user,
            content="Hello",
            metadata={'channel_id': 'C987654321'}
        )
        
        response = PlatformResponse(content="Hello back!")
        
        result = handler.send_response(response, message)
        
        assert result is True
        mock_client.chat_postMessage.assert_called_once()
        
        # 檢查調用參數
        call_args = mock_client.chat_postMessage.call_args[1]
        assert call_args['channel'] == 'C987654321'
        assert call_args['text'] == 'Hello back!'
        assert call_args['mrkdwn'] is True
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_send_response_with_thread(self):
        """測試在執行緒中發送回應"""
        handler = SlackHandler(self.valid_config)
        
        # Mock WebClient
        mock_client = Mock()
        mock_client.chat_postMessage.return_value = {'ok': True}
        handler.client = mock_client
        
        user = PlatformUser(user_id="U123456789", platform=PlatformType.SLACK)
        message = PlatformMessage(
            message_id="1234567890.123456",
            user=user,
            content="Hello",
            metadata={
                'channel_id': 'C987654321',
                'thread_ts': '1234567890.123456'
            }
        )
        
        response = PlatformResponse(content="Hello back!")
        
        result = handler.send_response(response, message)
        
        assert result is True
        mock_client.chat_postMessage.assert_called_once()
        
        # 檢查調用參數
        call_args = mock_client.chat_postMessage.call_args[1]
        assert call_args['channel'] == 'C987654321'
        assert call_args['text'] == 'Hello back!'
        assert call_args['thread_ts'] == '1234567890.123456'
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_send_response_long_message(self):
        """測試發送長訊息"""
        handler = SlackHandler(self.valid_config)
        
        # Mock WebClient
        mock_client = Mock()
        mock_client.chat_postMessage.return_value = {'ok': True}
        handler.client = mock_client
        
        user = PlatformUser(user_id="U123456789", platform=PlatformType.SLACK)
        message = PlatformMessage(
            message_id="1234567890.123456",
            user=user,
            content="Hello",
            metadata={'channel_id': 'C987654321'}
        )
        
        # 創建超過 4000 字符的長訊息
        long_content = "A" * 4001
        response = PlatformResponse(content=long_content)
        
        result = handler.send_response(response, message)
        
        assert result is True
        # 應該調用兩次（分割為兩個訊息）
        assert mock_client.chat_postMessage.call_count == 2
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_send_response_no_client(self):
        """測試沒有客戶端時發送回應"""
        handler = SlackHandler(self.valid_config)
        handler.client = None
        
        user = PlatformUser(user_id="U123456789", platform=PlatformType.SLACK)
        message = PlatformMessage(
            message_id="1234567890.123456",
            user=user,
            content="Hello",
            metadata={'channel_id': 'C987654321'}
        )
        
        response = PlatformResponse(content="Hello back!")
        
        result = handler.send_response(response, message)
        
        assert result is False
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_send_response_no_channel_id(self):
        """測試沒有 channel_id 時發送回應"""
        handler = SlackHandler(self.valid_config)
        handler.client = Mock()
        
        user = PlatformUser(user_id="U123456789", platform=PlatformType.SLACK)
        message = PlatformMessage(
            message_id="1234567890.123456",
            user=user,
            content="Hello",
            metadata={}  # 沒有 channel_id
        )
        
        response = PlatformResponse(content="Hello back!")
        
        result = handler.send_response(response, message)
        
        assert result is False
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_handle_webhook_url_verification(self):
        """測試處理 URL 驗證挑戰"""
        handler = SlackHandler(self.valid_config)
        handler.app = Mock()
        handler.request_handler = Mock()
        
        # 創建 URL 驗證請求
        webhook_data = {
            'type': 'url_verification',
            'challenge': 'test_challenge_value'
        }
        
        request_body = json.dumps(webhook_data)
        signature = 'valid_signature'
        
        with patch.object(handler, '_verify_slack_signature', return_value=True):
            messages = handler.handle_webhook(request_body, signature)
        
        assert messages == []  # URL 驗證不產生訊息
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_handle_webhook_event_callback(self):
        """測試處理事件回調"""
        handler = SlackHandler(self.valid_config)
        handler.app = Mock()
        handler.request_handler = Mock()
        
        # 創建事件回調請求
        webhook_data = {
            'type': 'event_callback',
            'event': {
                'type': 'message',
                'user': 'U123456789',
                'text': 'Hello',
                'channel': 'C987654321',
                'ts': '1234567890.123456'
            }
        }
        
        request_body = json.dumps(webhook_data)
        signature = 'valid_signature'
        
        with patch.object(handler, '_verify_slack_signature', return_value=True):
            with patch.object(handler, 'parse_message', return_value=Mock()):
                messages = handler.handle_webhook(request_body, signature)
        
        assert len(messages) == 1
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_handle_webhook_invalid_signature(self):
        """測試處理無效簽名的 webhook"""
        handler = SlackHandler(self.valid_config)
        handler.app = Mock()
        handler.request_handler = Mock()
        
        request_body = json.dumps({'type': 'event_callback'})
        signature = 'invalid_signature'
        
        with patch.object(handler, '_verify_slack_signature', return_value=False):
            messages = handler.handle_webhook(request_body, signature)
        
        assert messages == []
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_handle_webhook_invalid_json(self):
        """測試處理無效 JSON 的 webhook"""
        handler = SlackHandler(self.valid_config)
        handler.app = Mock()
        handler.request_handler = Mock()
        
        request_body = "invalid json"
        signature = 'valid_signature'
        
        with patch.object(handler, '_verify_slack_signature', return_value=True):
            messages = handler.handle_webhook(request_body, signature)
        
        assert messages == []
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_handle_webhook_no_app(self):
        """測試沒有應用時處理 webhook"""
        handler = SlackHandler(self.valid_config)
        handler.app = None
        handler.request_handler = None
        
        messages = handler.handle_webhook("test_body", "test_signature")
        
        assert messages == []
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_verify_slack_signature_valid(self):
        """測試驗證有效的 Slack 簽名"""
        handler = SlackHandler(self.valid_config)
        handler.signing_secret = 'test_secret'
        
        request_body = "test_body"
        timestamp = str(int(time.time()))
        
        # 創建有效簽名
        sig_basestring = f'v0:{timestamp}:{request_body}'
        signature = hmac.new(
            'test_secret'.encode(),
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()
        
        with patch('time.time', return_value=float(timestamp)):
            result = handler._verify_slack_signature(request_body, signature)
        
        assert result is True
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_verify_slack_signature_invalid(self):
        """測試驗證無效的 Slack 簽名"""
        handler = SlackHandler(self.valid_config)
        handler.signing_secret = 'test_secret'
        
        request_body = "test_body"
        signature = 'invalid_signature'
        
        result = handler._verify_slack_signature(request_body, signature)
        
        assert result is False
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_verify_slack_signature_no_secret(self):
        """測試沒有密鑰時驗證簽名"""
        handler = SlackHandler(self.valid_config)
        handler.signing_secret = ''
        
        request_body = "test_body"
        signature = 'any_signature'
        
        result = handler._verify_slack_signature(request_body, signature)
        
        assert result is False
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_get_user_info(self):
        """測試取得用戶資訊"""
        handler = SlackHandler(self.valid_config)
        
        # Mock WebClient
        mock_client = Mock()
        mock_client.users_info.return_value = {
            'user': {
                'id': 'U123456789',
                'name': 'testuser',
                'real_name': 'Test User',
                'display_name': 'Test User',
                'is_bot': False,
                'tz': 'America/New_York',
                'profile': {'email': 'test@example.com'}
            }
        }
        handler.client = mock_client
        
        user_info = handler._get_user_info('U123456789')
        
        assert user_info['id'] == 'U123456789'
        assert user_info['name'] == 'testuser'
        assert user_info['real_name'] == 'Test User'
        mock_client.users_info.assert_called_once_with(user='U123456789')
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_get_user_info_error(self):
        """測試取得用戶資訊時出錯"""
        handler = SlackHandler(self.valid_config)
        
        # Mock WebClient 拋出異常
        mock_client = Mock()
        mock_client.users_info.side_effect = Exception("API Error")
        handler.client = mock_client
        
        user_info = handler._get_user_info('U123456789')
        
        assert user_info['name'] == 'U123456789'
        assert user_info['real_name'] == 'Unknown User'
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_get_app_info(self):
        """測試取得應用資訊"""
        handler = SlackHandler(self.valid_config)
        
        # Mock WebClient
        mock_client = Mock()
        mock_client.auth_test.return_value = {
            'ok': True,
            'user_id': 'U123456789',
            'team': 'Test Team',
            'team_id': 'T111222333',
            'user': 'testbot',
            'bot_id': 'B987654321'
        }
        handler.client = mock_client
        
        app_info = handler.get_app_info()
        
        assert app_info is not None
        assert app_info['user_id'] == 'U123456789'
        assert app_info['team'] == 'Test Team'
        assert app_info['team_id'] == 'T111222333'
        assert app_info['user'] == 'testbot'
        assert app_info['bot_id'] == 'B987654321'
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_get_app_info_no_client(self):
        """測試沒有客戶端時取得應用資訊"""
        handler = SlackHandler(self.valid_config)
        handler.client = None
        
        app_info = handler.get_app_info()
        
        assert app_info is None


class TestSlackUtils:
    """測試 Slack 工具函數"""
    
    def test_escape_slack_text(self):
        """測試轉義 Slack 文字"""
        text = "Hello <world> & <everyone>"
        escaped = SlackUtils.escape_slack_text(text)
        
        assert "<" not in escaped or "&lt;" in escaped
        assert ">" not in escaped or "&gt;" in escaped
        assert "&" not in escaped or "&amp;" in escaped
    
    def test_format_user_mention(self):
        """測試格式化用戶提及"""
        user_id = "U123456789"
        mention = SlackUtils.format_user_mention(user_id)
        
        assert mention == "<@U123456789>"
    
    def test_format_channel_mention(self):
        """測試格式化頻道提及"""
        channel_id = "C123456789"
        mention = SlackUtils.format_channel_mention(channel_id)
        
        assert mention == "<#C123456789>"
    
    def test_format_link(self):
        """測試格式化連結"""
        url = "https://example.com"
        text = "Example"
        
        # 有文字的連結
        link_with_text = SlackUtils.format_link(url, text)
        assert link_with_text == "<https://example.com|Example>"
        
        # 無文字的連結
        link_without_text = SlackUtils.format_link(url)
        assert link_without_text == "<https://example.com>"
    
    def test_create_text_block(self):
        """測試創建文字區塊"""
        text = "Hello, world!"
        block = SlackUtils.create_text_block(text)
        
        assert block['type'] == 'section'
        assert block['text']['type'] == 'mrkdwn'
        assert block['text']['text'] == 'Hello, world!'
        
        # 測試自定義區塊類型
        custom_block = SlackUtils.create_text_block(text, 'header')
        assert custom_block['type'] == 'header'
    
    def test_create_blocks(self):
        """測試創建區塊"""
        elements = [
            {'type': 'section', 'text': {'type': 'mrkdwn', 'text': 'Hello'}},
            {'type': 'divider'}
        ]
        
        blocks = SlackUtils.create_blocks(elements)
        
        assert blocks == elements
        assert len(blocks) == 2
        assert blocks[0]['type'] == 'section'
        assert blocks[1]['type'] == 'divider'


class TestSlackHandlerExtended:
    """Slack 處理器擴展測試"""
    
    def setup_method(self):
        """每個測試方法前的設置"""
        self.valid_config = {
            'platforms': {
                'slack': {
                    'enabled': True,
                    'bot_token': 'xoxb-test-token',
                    'signing_secret': 'test_signing_secret',
                    'app_token': 'xapp-test-token'
                }
            }
        }

    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_send_response_api_error(self):
        """測試發送回應時的 API 錯誤"""
        handler = SlackHandler(self.valid_config)
        
        # Mock WebClient 返回錯誤
        mock_client = Mock()
        mock_client.chat_postMessage.return_value = {'ok': False, 'error': 'channel_not_found'}
        handler.client = mock_client
        
        user = PlatformUser(user_id="U123456789", platform=PlatformType.SLACK)
        message = PlatformMessage(
            message_id="1234567890.123456",
            user=user,
            content="Hello",
            metadata={'channel_id': 'C987654321'}
        )
        
        response = PlatformResponse(content="Hello back!")
        
        result = handler.send_response(response, message)
        
        assert result is False
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)  
    def test_send_response_exception(self):
        """測試發送回應時拋出異常"""
        handler = SlackHandler(self.valid_config)
        
        # Mock WebClient 拋出異常
        mock_client = Mock()
        mock_client.chat_postMessage.side_effect = Exception("API Error")
        handler.client = mock_client
        
        user = PlatformUser(user_id="U123456789", platform=PlatformType.SLACK)
        message = PlatformMessage(
            message_id="1234567890.123456",
            user=user,
            content="Hello",
            metadata={'channel_id': 'C987654321'}
        )
        
        response = PlatformResponse(content="Hello back!")
        
        result = handler.send_response(response, message)
        
        assert result is False
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_handle_webhook_interactive_payload(self):
        """測試處理互動式組件 webhook"""
        handler = SlackHandler(self.valid_config)
        handler.app = Mock()
        handler.request_handler = Mock()
        
        # 創建表單編碼的互動式負載
        payload_data = {
            'type': 'block_actions',
            'user': {'id': 'U123456789'},
            'actions': [{'action_id': 'button_click'}]
        }
        
        request_body = f"payload={json.dumps(payload_data).replace(' ', '%20')}"
        signature = 'valid_signature'
        
        with patch.object(handler, '_verify_slack_signature', return_value=True):
            messages = handler.handle_webhook(request_body, signature)
        
        assert messages == []  # 互動式組件不產生訊息
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_handle_webhook_form_data_error(self):
        """測試處理表單數據時的錯誤"""
        handler = SlackHandler(self.valid_config)
        handler.app = Mock()
        handler.request_handler = Mock()
        
        # 創建無效的表單數據
        request_body = "invalid_form_data"
        signature = 'valid_signature'
        
        with patch.object(handler, '_verify_slack_signature', return_value=True):
            messages = handler.handle_webhook(request_body, signature)
        
        assert messages == []
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_verify_slack_signature_with_timestamp(self):
        """測試包含時間戳的簽名驗證"""
        handler = SlackHandler(self.valid_config)
        handler.signing_secret = 'test_secret'
        
        request_body = "test_body"
        signature_with_version = 'v0=test_signature'
        
        result = handler._verify_slack_signature(request_body, signature_with_version)
        
        # 因為我們沒有實際的 HMAC 計算，只測試解析邏輯
        assert result is False  # 簽名不匹配
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_verify_slack_signature_exception(self):
        """測試簽名驗證時的異常"""
        handler = SlackHandler(self.valid_config)
        handler.signing_secret = 'test_secret'
        
        request_body = "test_body"
        signature = None  # 會導致異常
        
        result = handler._verify_slack_signature(request_body, signature)
        
        assert result is False
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_get_user_info_no_client(self):
        """測試沒有客戶端時取得用戶資訊"""
        handler = SlackHandler(self.valid_config)
        handler.client = None
        
        user_info = handler._get_user_info('U123456789')
        
        assert user_info['name'] == 'U123456789'
        assert user_info['real_name'] == 'Unknown User'
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_download_slack_file_success(self):
        """測試成功下載 Slack 檔案"""
        handler = SlackHandler(self.valid_config)
        handler.client = Mock()
        handler.bot_token = 'xoxb-test-token'
        
        file_info = {
            'url_private_download': 'https://files.slack.com/test.mp3',
            'url_private': 'https://files.slack.com/test.mp3'
        }
        
        # Mock requests.get
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.content = b'fake_file_data'
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            result = handler._download_slack_file(file_info)
        
        assert result == b'fake_file_data'
        mock_get.assert_called_once_with(
            'https://files.slack.com/test.mp3',
            headers={'Authorization': 'Bearer xoxb-test-token'}
        )
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_download_slack_file_error(self):
        """測試下載 Slack 檔案時的錯誤"""
        handler = SlackHandler(self.valid_config)
        handler.client = Mock()
        handler.bot_token = 'xoxb-test-token'
        
        file_info = {
            'url_private_download': 'https://files.slack.com/test.mp3'
        }
        
        # Mock requests.get 拋出異常
        with patch('requests.get') as mock_get:
            mock_get.side_effect = Exception("Network Error")
            
            result = handler._download_slack_file(file_info)
        
        assert result == b''
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_download_slack_file_no_client(self):
        """測試沒有客戶端時下載檔案"""
        handler = SlackHandler(self.valid_config)
        handler.client = None
        
        file_info = {'url_private': 'https://files.slack.com/test.mp3'}
        
        result = handler._download_slack_file(file_info)
        
        assert result == b''
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_get_app_info_error(self):
        """測試取得應用資訊時出錯"""
        handler = SlackHandler(self.valid_config)
        
        # Mock WebClient 拋出異常
        mock_client = Mock()
        mock_client.auth_test.side_effect = Exception("API Error")
        handler.client = mock_client
        
        app_info = handler.get_app_info()
        
        assert app_info is None
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_get_app_info_not_ok(self):
        """測試應用資訊返回不成功"""
        handler = SlackHandler(self.valid_config)
        
        # Mock WebClient 返回 ok=False
        mock_client = Mock()
        mock_client.auth_test.return_value = {'ok': False, 'error': 'invalid_auth'}
        handler.client = mock_client
        
        app_info = handler.get_app_info()
        
        assert app_info is None
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_create_bolt_request_no_handler(self):
        """測試沒有請求處理器時創建 Bolt 請求"""
        handler = SlackHandler(self.valid_config)
        handler.request_handler = None
        
        mock_flask_request = Mock()
        
        try:
            handler.create_bolt_request(mock_flask_request)
            assert False, "Should raise ValueError"
        except ValueError as e:
            assert "not initialized" in str(e)
    
    def test_create_bolt_request_no_slack_available(self):
        """測試 Slack 不可用時創建 Bolt 請求"""
        with patch('src.platforms.slack_handler.SLACK_AVAILABLE', False):
            handler = SlackHandler(self.valid_config)
            # 當 SLACK_AVAILABLE=False 時，不會初始化 request_handler
            handler.request_handler = None
            
            mock_flask_request = Mock()
            
            # 應該拋出 ValueError
            try:
                handler.create_bolt_request(mock_flask_request)
                assert False, "Should raise ValueError"
            except ValueError as e:
                assert "not initialized" in str(e)
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_handle_bolt_request_no_app(self):
        """測試沒有應用時處理 Bolt 請求"""
        handler = SlackHandler(self.valid_config)
        handler.app = None
        
        mock_bolt_request = Mock()
        
        try:
            handler.handle_bolt_request(mock_bolt_request)
            assert False, "Should raise ValueError"
        except ValueError as e:
            assert "not initialized" in str(e)
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_parse_message_with_thread_ts(self):
        """測試解析包含 thread_ts 的訊息"""
        handler = SlackHandler(self.valid_config)
        
        # Mock _get_user_info 方法
        mock_user_info = {
            'name': 'testuser',
            'real_name': 'Test User',
            'display_name': 'Test User',
            'is_bot': False,
            'tz': 'America/New_York',
            'profile': {'email': 'test@example.com'}
        }
        
        with patch.object(handler, '_get_user_info', return_value=mock_user_info):
            # 創建包含 thread_ts 的 Slack 事件
            slack_event = {
                'event': {
                    'type': 'message',
                    'user': 'U123456789',
                    'text': 'Thread reply',
                    'channel': 'C987654321',
                    'ts': '1234567890.123456',
                    'thread_ts': '1234567880.123400',  # 父訊息的時間戳
                    'team': 'T111222333',
                    'channel_type': 'channel',
                    'event_ts': '1234567890.123456',
                    'files': []
                }
            }
            
            parsed_message = handler.parse_message(slack_event)
        
        assert parsed_message is not None
        assert parsed_message.metadata['thread_ts'] == '1234567880.123400'
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_parse_message_no_user(self):
        """測試解析沒有用戶的訊息"""
        handler = SlackHandler(self.valid_config)
        
        # 創建沒有用戶的 Slack 事件
        slack_event = {
            'event': {
                'type': 'message',
                'text': 'Message without user',
                'channel': 'C987654321',
                'ts': '1234567890.123456'
            }
        }
        
        parsed_message = handler.parse_message(slack_event)
        
        assert parsed_message is None


class TestSlackHandlerIntegration:
    """Slack 處理器整合測試"""
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_basic_workflow(self):
        """測試基本工作流程（簡化版）"""
        config = {
            'platforms': {
                'slack': {
                    'enabled': True,
                    'bot_token': 'xoxb-test-token',
                    'signing_secret': 'test_secret'
                }
            }
        }
        
        handler = SlackHandler(config)
        
        # 測試基本屬性
        assert handler.get_platform_type() == PlatformType.SLACK
        assert handler.bot_token == 'xoxb-test-token'
        
        # 測試配置驗證
        assert hasattr(handler, 'validate_config')
        
        # 測試基本方法不會崩潰
        result = handler.parse_message({'invalid': 'event'})
        assert result is None
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_complete_configuration_flow(self):
        """測試完整的配置流程"""
        config = {
            'platforms': {
                'slack': {
                    'enabled': True,
                    'bot_token': 'xoxb-test-token',
                    'signing_secret': 'test_secret',
                    'app_token': 'xapp-test-token'
                }
            }
        }
        
        handler = SlackHandler(config)
        
        # 測試配置屬性
        assert handler.bot_token == 'xoxb-test-token'
        assert handler.signing_secret == 'test_secret'
        assert handler.app_token == 'xapp-test-token'
        
        # 測試必要欄位
        required_fields = handler.get_required_config_fields()
        assert 'bot_token' in required_fields
        assert 'signing_secret' in required_fields
        
        # 測試平台類型
        assert handler.get_platform_type() == PlatformType.SLACK


class TestSlackHandlerAdvanced:
    """Slack 處理器進階測試"""
    
    @patch('src.platforms.slack_handler.SLACK_AVAILABLE', True)
    def test_error_handling_comprehensive(self):
        """測試全面的錯誤處理"""
        config = {
            'platforms': {
                'slack': {
                    'enabled': True,
                    'bot_token': 'xoxb-test-token',
                    'signing_secret': 'test_secret'
                }
            }
        }
        
        handler = SlackHandler(config)
        
        # 測試各種錯誤情況
        test_cases = [
            None,  # None 輸入
            "string_input",  # 字符串輸入
            {'not_event': 'data'},  # 沒有 event 鍵
            {'event': {'type': 'unsupported'}},  # 不支援的事件類型
            {'event': {'type': 'message', 'subtype': 'bot_message'}},  # bot 訊息
        ]
        
        for test_case in test_cases:
            result = handler.parse_message(test_case)
            assert result is None, f"Failed for test case: {test_case}"


if __name__ == "__main__":
    pytest.main([__file__])