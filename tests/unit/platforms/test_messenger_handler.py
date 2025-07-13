"""
Facebook Messenger Platform 處理器測試
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from src.platforms.messenger_handler import MessengerHandler
from src.platforms.base import PlatformType, PlatformUser, PlatformMessage, PlatformResponse


class TestMessengerHandler:
    """Messenger 處理器測試類別"""
    
    @pytest.fixture
    def config(self):
        """測試配置"""
        return {
            'platforms': {
                'messenger': {
                    'enabled': True,
                    'app_id': 'test_app_id_123',
                    'app_secret': 'test_app_secret',
                    'page_access_token': 'test_page_access_token',
                    'verify_token': 'test_verify_token',
                    'api_version': 'v19.0'
                }
            }
        }
    
    @pytest.fixture
    def disabled_config(self):
        """停用的配置"""
        return {
            'platforms': {
                'messenger': {
                    'enabled': False,
                    'app_id': 'test_app_id_123',
                    'page_access_token': 'test_page_access_token',
                    'verify_token': 'test_verify_token'
                }
            }
        }
    
    @pytest.fixture
    def invalid_config(self):
        """無效配置"""
        return {
            'platforms': {
                'messenger': {
                    'enabled': True
                    # 缺少必要的配置
                }
            }
        }
    
    @pytest.fixture
    def messenger_handler(self, config):
        """Messenger 處理器實例"""
        return MessengerHandler(config)
    
    def test_platform_type(self, messenger_handler):
        """測試平台類型"""
        assert messenger_handler.get_platform_type() == PlatformType.MESSENGER
    
    def test_required_config_fields(self, messenger_handler):
        """測試必要配置欄位"""
        required_fields = messenger_handler.get_required_config_fields()
        assert 'app_id' in required_fields
        assert 'app_secret' in required_fields
        assert 'page_access_token' in required_fields
        assert 'verify_token' in required_fields
    
    def test_config_validation_success(self, config):
        """測試配置驗證成功"""
        handler = MessengerHandler(config)
        assert handler.validate_config() == True
        assert handler.is_enabled() == True
    
    def test_config_validation_failure(self, invalid_config):
        """測試配置驗證失敗"""
        handler = MessengerHandler(invalid_config)
        assert handler.validate_config() == False
    
    def test_disabled_platform(self, disabled_config):
        """測試停用平台"""
        handler = MessengerHandler(disabled_config)
        assert handler.is_enabled() == False
    
    def test_parse_text_message(self, messenger_handler):
        """測試解析文字訊息"""
        webhook_event = {
            "object": "page",
            "entry": [{
                "id": "page_id_123",
                "time": 1458692752478,
                "messaging": [{
                    "sender": {
                        "id": "user_id_123"
                    },
                    "recipient": {
                        "id": "page_id_123"
                    },
                    "timestamp": 1458692752478,
                    "message": {
                        "mid": "mid.1457764197618:41d102a3e1ae206a38",
                        "text": "Hello World",
                        "seq": 73
                    }
                }]
            }]
        }
        
        with patch('requests.get') as mock_get:
            # 模擬用戶資訊請求
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "first_name": "Test",
                "last_name": "User"
            }
            mock_get.return_value = mock_response
            
            message = messenger_handler.parse_message(webhook_event)
        
        assert message is not None
        assert message.message_id == 'mid.1457764197618:41d102a3e1ae206a38'
        assert message.content == 'Hello World'
        assert message.message_type == 'text'
        assert message.user.user_id == 'user_id_123'
        assert message.user.platform == PlatformType.MESSENGER
        assert message.user.display_name == 'Test User'
        assert message.metadata['sender_id'] == 'user_id_123'
        assert message.metadata['recipient_id'] == 'page_id_123'
    
    def test_parse_audio_message(self, messenger_handler):
        """測試解析音訊訊息"""
        webhook_event = {
            "object": "page",
            "entry": [{
                "messaging": [{
                    "sender": {
                        "id": "user_id_123"
                    },
                    "recipient": {
                        "id": "page_id_123"
                    },
                    "timestamp": 1458692752478,
                    "message": {
                        "mid": "mid.AUDIO123",
                        "attachments": [{
                            "type": "audio",
                            "payload": {
                                "url": "https://example.com/audio.mp3"
                            }
                        }]
                    }
                }]
            }]
        }
        
        with patch.object(messenger_handler, '_download_media', return_value=b'fake_audio_data'):
            message = messenger_handler.parse_message(webhook_event)
        
        assert message is not None
        assert message.message_id == 'mid.AUDIO123'
        assert '[Audio Message' in message.content
        assert message.message_type == 'audio'
        assert message.raw_data == b'fake_audio_data'
    
    def test_parse_image_message(self, messenger_handler):
        """測試解析圖片訊息"""
        webhook_event = {
            "object": "page",
            "entry": [{
                "messaging": [{
                    "sender": {
                        "id": "user_id_123"
                    },
                    "recipient": {
                        "id": "page_id_123"
                    },
                    "timestamp": 1458692752478,
                    "message": {
                        "mid": "mid.IMAGE123",
                        "attachments": [{
                            "type": "image",
                            "payload": {
                                "url": "https://example.com/image.jpg"
                            }
                        }]
                    }
                }]
            }]
        }
        
        with patch.object(messenger_handler, '_download_media', return_value=b'fake_image_data'):
            message = messenger_handler.parse_message(webhook_event)
        
        assert message is not None
        assert message.message_type == 'image'
        assert message.content == '[Image Message]'
        assert message.raw_data == b'fake_image_data'
    
    def test_parse_location_message(self, messenger_handler):
        """測試解析位置訊息"""
        webhook_event = {
            "object": "page",
            "entry": [{
                "messaging": [{
                    "sender": {
                        "id": "user_id_123"
                    },
                    "recipient": {
                        "id": "page_id_123"
                    },
                    "timestamp": 1458692752478,
                    "message": {
                        "mid": "mid.LOCATION123",
                        "attachments": [{
                            "type": "location",
                            "payload": {
                                "coordinates": {
                                    "lat": 37.4220656,
                                    "long": -122.0840897
                                }
                            }
                        }]
                    }
                }]
            }]
        }
        
        message = messenger_handler.parse_message(webhook_event)
        
        assert message is not None
        assert message.message_type == 'location'
        assert '[Location: 37.4220656, -122.0840897]' in message.content
    
    def test_parse_non_page_event(self, messenger_handler):
        """測試解析非頁面事件"""
        webhook_event = {
            "object": "other_object",
            "entry": []
        }
        
        message = messenger_handler.parse_message(webhook_event)
        assert message is None
    
    def test_parse_empty_event(self, messenger_handler):
        """測試解析空事件"""
        webhook_event = {
            "object": "page",
            "entry": []
        }
        
        message = messenger_handler.parse_message(webhook_event)
        assert message is None
    
    @patch('src.platforms.messenger_handler.requests.post')
    def test_send_text_message_success(self, mock_post, messenger_handler):
        """測試發送文字訊息成功"""
        # 模擬 API 回應
        mock_response = Mock(spec=['status_code', 'text'])
        mock_response.status_code = 200
        mock_response.text = 'Success'
        mock_post.return_value = mock_response
        
        # 建立測試訊息
        user = PlatformUser(user_id='user_id_123', platform=PlatformType.MESSENGER)
        message = PlatformMessage(
            message_id='test_msg',
            user=user,
            content='Test message'
        )
        
        response = PlatformResponse(
            content='Hello back!',
            response_type='text'
        )
        
        # 測試發送
        result = messenger_handler.send_response(response, message)
        
        assert result == True
        mock_post.assert_called_once()
        
        # 驗證 API 呼叫參數
        call_args = mock_post.call_args
        assert 'https://graph.facebook.com/v19.0/me/messages' in call_args[0][0]
        assert call_args[1]['json']['recipient']['id'] == 'user_id_123'
        assert call_args[1]['json']['message']['text'] == 'Hello back!'
    
    @patch('src.platforms.messenger_handler.requests.post')
    def test_send_text_message_failure(self, mock_post, messenger_handler):
        """測試發送文字訊息失敗"""
        # 模擬 API 錯誤回應
        mock_response = Mock(spec=['status_code', 'text'])
        mock_response.status_code = 400
        mock_response.text = 'Bad Request'
        mock_post.return_value = mock_response
        
        # 建立測試訊息
        user = PlatformUser(user_id='user_id_123', platform=PlatformType.MESSENGER)
        message = PlatformMessage(
            message_id='test_msg',
            user=user,
            content='Test message'
        )
        
        response = PlatformResponse(
            content='Hello back!',
            response_type='text'
        )
        
        # 測試發送
        result = messenger_handler.send_response(response, message)
        
        assert result == False
    
    def test_handle_webhook_single_message(self, messenger_handler):
        """測試處理單一 webhook 訊息"""
        webhook_data = {
            "object": "page",
            "entry": [{
                "messaging": [{
                    "sender": {
                        "id": "user_id_123"
                    },
                    "recipient": {
                        "id": "page_id_123"
                    },
                    "timestamp": 1458692752478,
                    "message": {
                        "mid": "mid.TEST123",
                        "text": "Hello"
                    }
                }]
            }]
        }
        
        webhook_body = json.dumps(webhook_data)
        signature = 'sha1=test_signature'
        
        # Calculate correct signature for the test
        import hmac
        import hashlib
        expected_signature = hmac.new(
            'test_app_secret'.encode('utf-8'),
            webhook_body.encode('utf-8'),
            hashlib.sha1
        ).hexdigest()
        signature = f'sha1={expected_signature}'
        
        headers = {"X-Hub-Signature": signature}
        messages = messenger_handler.handle_webhook(webhook_body, headers)
        
        assert len(messages) == 1
        assert messages[0].content == 'Hello'
        assert messages[0].user.user_id == 'user_id_123'
    
    def test_handle_webhook_echo_message(self, messenger_handler):
        """測試處理 echo 訊息（忽略）"""
        webhook_data = {
            "object": "page",
            "entry": [{
                "messaging": [{
                    "sender": {
                        "id": "page_id_123"
                    },
                    "recipient": {
                        "id": "user_id_123"
                    },
                    "timestamp": 1458692752478,
                    "message": {
                        "mid": "mid.ECHO123",
                        "text": "Echo message",
                        "is_echo": True
                    }
                }]
            }]
        }
        
        webhook_body = json.dumps(webhook_data)
        signature = ''
        
        headers = {"X-Hub-Signature": signature}
        messages = messenger_handler.handle_webhook(webhook_body, headers)
        
        assert len(messages) == 0  # Echo 訊息應該被忽略
    
    def test_handle_webhook_verification_request(self, messenger_handler):
        """測試處理 webhook 驗證請求"""
        webhook_data = {
            "hub.mode": "subscribe",
            "hub.verify_token": "test_verify_token",
            "hub.challenge": "challenge_value"
        }
        
        webhook_body = json.dumps(webhook_data)
        signature = ''
        
        headers = {"X-Hub-Signature": signature}
        messages = messenger_handler.handle_webhook(webhook_body, headers)
        
        assert len(messages) == 0  # 驗證請求不應該返回訊息
    
    def test_handle_webhook_invalid_json(self, messenger_handler):
        """測試處理無效 JSON webhook"""
        webhook_body = '{"invalid": json}'
        signature = 'sha1=test_signature'
        
        headers = {"X-Hub-Signature": signature}
        messages = messenger_handler.handle_webhook(webhook_body, headers)
        
        assert len(messages) == 0
    
    def test_verify_signature_success(self, messenger_handler):
        """測試簽名驗證成功"""
        request_body = '{"test": "data"}'
        # 使用正確的 HMAC 計算
        import hmac
        import hashlib
        expected_signature = hmac.new(
            'test_app_secret'.encode('utf-8'),
            request_body.encode('utf-8'),
            hashlib.sha1
        ).hexdigest()
        signature = f'sha1={expected_signature}'
        
        result = messenger_handler._verify_signature(request_body, signature)
        assert result == True
    
    def test_verify_signature_failure(self, messenger_handler):
        """測試簽名驗證失敗"""
        request_body = '{"test": "data"}'
        signature = 'sha1=invalid_signature'
        
        result = messenger_handler._verify_signature(request_body, signature)
        assert result == False
    
    def test_verify_signature_invalid_format(self, messenger_handler):
        """測試無效簽名格式"""
        request_body = '{"test": "data"}'
        signature = 'invalid_format'
        
        result = messenger_handler._verify_signature(request_body, signature)
        assert result == False
    
    def test_verify_webhook_success(self, messenger_handler):
        """測試 webhook 驗證成功"""
        verify_token = 'test_verify_token'
        challenge = 'challenge_value'
        
        result = messenger_handler.verify_webhook(verify_token, challenge)
        assert result == 'challenge_value'
    
    def test_verify_webhook_failure(self, messenger_handler):
        """測試 webhook 驗證失敗"""
        verify_token = 'wrong_token'
        challenge = 'challenge_value'
        
        result = messenger_handler.verify_webhook(verify_token, challenge)
        assert result is None
    
    def test_get_webhook_info(self, messenger_handler):
        """測試取得 webhook 資訊"""
        info = messenger_handler.get_webhook_info()
        
        assert info['platform'] == 'messenger'
        assert info['webhook_url'] == '/webhooks/messenger'
        assert info['verify_token'] == 'test_verify_token'
        assert info['app_id'] == 'test_app_id_123'
        assert info['api_version'] == 'v19.0'
    
    @patch('src.platforms.messenger_handler.requests.get')
    def test_download_media_success(self, mock_get, messenger_handler):
        """測試下載媒體成功"""
        # 模擬媒體下載
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'fake_media_data'
        mock_get.return_value = mock_response
        
        result = messenger_handler._download_media('https://example.com/media.jpg')
        
        assert result == b'fake_media_data'
    
    @patch('src.platforms.messenger_handler.requests.get')
    def test_download_media_failure(self, mock_get, messenger_handler):
        """測試下載媒體失敗"""
        # 模擬 API 錯誤回應
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        result = messenger_handler._download_media('https://example.com/invalid_media.jpg')
        
        assert result is None
    
    @patch('src.platforms.messenger_handler.requests.post')
    def test_send_quick_replies(self, mock_post, messenger_handler):
        """測試發送快速回覆"""
        # 模擬 API 回應
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        quick_replies = [
            {"title": "Yes", "payload": "YES"},
            {"title": "No", "payload": "NO"}
        ]
        
        result = messenger_handler.send_quick_replies(
            'user_id_123', 
            'Do you like this?', 
            quick_replies
        )
        
        assert result == True
        mock_post.assert_called_once()
        
        # 驗證快速回覆格式
        call_args = mock_post.call_args
        message_data = call_args[1]['json']['message']
        assert message_data['text'] == 'Do you like this?'
        assert len(message_data['quick_replies']) == 2
        assert message_data['quick_replies'][0]['title'] == 'Yes'
        assert message_data['quick_replies'][0]['payload'] == 'YES'
    
    def test_parse_message_string_input(self, messenger_handler):
        """測試解析字串格式的訊息"""
        webhook_event_str = """{
            "object": "page",
            "entry": [{
                "messaging": [{
                    "sender": {"id": "user_id_123"},
                    "recipient": {"id": "page_id_123"},
                    "timestamp": 1458692752478,
                    "message": {
                        "mid": "mid.STRING123",
                        "text": "String message",
                        "seq": 73
                    }
                }]
            }]
        }"""
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"first_name": "Test", "last_name": "User"}
            mock_get.return_value = mock_response
            
            message = messenger_handler.parse_message(webhook_event_str)
        
        assert message is not None
        assert message.content == 'String message'
        assert message.message_id == 'mid.STRING123'
    
    def test_parse_video_message(self, messenger_handler):
        """測試解析影片訊息"""
        webhook_event = {
            "object": "page",
            "entry": [{
                "messaging": [{
                    "sender": {"id": "user_id_123"},
                    "recipient": {"id": "page_id_123"},
                    "timestamp": 1458692752478,
                    "message": {
                        "mid": "mid.VIDEO123",
                        "attachments": [{
                            "type": "video",
                            "payload": {"url": "https://example.com/video.mp4"}
                        }]
                    }
                }]
            }]
        }
        
        message = messenger_handler.parse_message(webhook_event)
        
        assert message is not None
        assert message.message_type == 'video'
        assert message.content == '[Video Message]'
    
    def test_parse_file_message(self, messenger_handler):
        """測試解析檔案訊息"""
        webhook_event = {
            "object": "page",
            "entry": [{
                "messaging": [{
                    "sender": {"id": "user_id_123"},
                    "recipient": {"id": "page_id_123"},
                    "timestamp": 1458692752478,
                    "message": {
                        "mid": "mid.FILE123",
                        "attachments": [{
                            "type": "file",
                            "payload": {"url": "https://example.com/document.pdf"}
                        }]
                    }
                }]
            }]
        }
        
        message = messenger_handler.parse_message(webhook_event)
        
        assert message is not None
        assert message.message_type == 'file'
        assert message.content == '[File Message]'
    
    def test_parse_unknown_attachment_type(self, messenger_handler):
        """測試解析未知附件類型"""
        webhook_event = {
            "object": "page",
            "entry": [{
                "messaging": [{
                    "sender": {"id": "user_id_123"},
                    "recipient": {"id": "page_id_123"},
                    "timestamp": 1458692752478,
                    "message": {
                        "mid": "mid.UNKNOWN123",
                        "attachments": [{
                            "type": "unknown_type",
                            "payload": {"url": "https://example.com/unknown"}
                        }]
                    }
                }]
            }]
        }
        
        message = messenger_handler.parse_message(webhook_event)
        
        assert message is not None
        assert message.content == '[UNKNOWN_TYPE Message]'
    
    def test_parse_quick_reply_message(self, messenger_handler):
        """測試解析包含快速回覆的訊息"""
        webhook_event = {
            "object": "page",
            "entry": [{
                "messaging": [{
                    "sender": {"id": "user_id_123"},
                    "recipient": {"id": "page_id_123"},
                    "timestamp": 1458692752478,
                    "message": {
                        "mid": "mid.QUICKREPLY123",
                        "text": "Regular text",
                        "quick_reply": {"payload": "USER_CHOICE_YES"}
                    }
                }]
            }]
        }
        
        message = messenger_handler.parse_message(webhook_event)
        
        assert message is not None
        assert "Regular text [Quick Reply: USER_CHOICE_YES]" in message.content
    
    def test_user_info_fetch_failure(self, messenger_handler):
        """測試用戶資訊獲取失敗的情況"""
        webhook_event = {
            "object": "page",
            "entry": [{
                "messaging": [{
                    "sender": {"id": "user_id_123"},
                    "recipient": {"id": "page_id_123"},
                    "timestamp": 1458692752478,
                    "message": {
                        "mid": "mid.USERINFO123",
                        "text": "Test message"
                    }
                }]
            }]
        }
        
        with patch('requests.get') as mock_get:
            mock_get.side_effect = Exception("Network error")
            
            message = messenger_handler.parse_message(webhook_event)
        
        assert message is not None
        assert message.content == 'Test message'
        assert message.user.display_name is None
    
    @patch('src.platforms.messenger_handler.requests.post')
    def test_send_audio_message(self, mock_post, messenger_handler):
        """測試發送音訊訊息（暫未實現）"""
        user = PlatformUser(user_id='user_id_123', platform=PlatformType.MESSENGER)
        message = PlatformMessage(
            message_id='test_msg',
            user=user,
            content='Test message'
        )
        
        response = PlatformResponse(
            content='Audio response',
            response_type='audio',
            raw_response=b'fake_audio_data'
        )
        
        result = messenger_handler.send_response(response, message)
        
        # 目前音訊發送未實現，應該返回 False
        assert result == False
    
    def test_signature_verification_missing_secret(self):
        """測試缺少 app_secret 時的簽名驗證"""
        config_no_secret = {
            'platforms': {
                'messenger': {
                    'enabled': True,
                    'app_id': 'test_app_id_123',
                    'page_access_token': 'test_page_access_token',
                    'verify_token': 'test_verify_token',
                    'api_version': 'v19.0'
                    # 缺少 app_secret
                }
            }
        }
        
        handler = MessengerHandler(config_no_secret)
        
        # 沒有 app_secret 時應該跳過驗證  
        result = handler._verify_signature('{"test": "data"}', 'sha1=signature')
        assert result == True  # webhook.py 中如果沒有 app_secret 會返回 True
    
    def test_handle_webhook_no_signature_verification(self, messenger_handler):
        """測試沒有簽名驗證的 webhook 處理"""
        webhook_data = {
            "object": "page",
            "entry": [{
                "messaging": [{
                    "sender": {"id": "user_id_123"},
                    "recipient": {"id": "page_id_123"},
                    "timestamp": 1458692752478,
                    "message": {
                        "mid": "mid.NOSIG123",
                        "text": "No signature"
                    }
                }]
            }]
        }
        
        webhook_body = json.dumps(webhook_data)
        
        # 不提供簽名
        headers = {}
        messages = messenger_handler.handle_webhook(webhook_body, headers)
        
        assert len(messages) == 1
        assert messages[0].content == 'No signature'