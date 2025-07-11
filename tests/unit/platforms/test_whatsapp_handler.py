"""
WhatsApp Business Cloud API 平台處理器測試
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from src.platforms.whatsapp_handler import WhatsAppHandler
from src.platforms.base import PlatformType, PlatformUser, PlatformMessage, PlatformResponse


class TestWhatsAppHandler:
    """WhatsApp 處理器測試類別"""
    
    @pytest.fixture
    def config(self):
        """測試配置"""
        return {
            'platforms': {
                'whatsapp': {
                    'enabled': True,
                    'access_token': 'test_access_token_123',
                    'phone_number_id': 'test_phone_number_id',
                    'app_secret': 'test_app_secret',
                    'verify_token': 'test_verify_token',
                    'api_version': 'v13.0'
                }
            }
        }
    
    @pytest.fixture
    def disabled_config(self):
        """停用的配置"""
        return {
            'platforms': {
                'whatsapp': {
                    'enabled': False,
                    'access_token': 'test_access_token_123',
                    'phone_number_id': 'test_phone_number_id',
                    'verify_token': 'test_verify_token'
                }
            }
        }
    
    @pytest.fixture
    def invalid_config(self):
        """無效配置"""
        return {
            'platforms': {
                'whatsapp': {
                    'enabled': True
                    # 缺少必要的配置
                }
            }
        }
    
    @pytest.fixture
    def whatsapp_handler(self, config):
        """WhatsApp 處理器實例"""
        return WhatsAppHandler(config)
    
    def test_platform_type(self, whatsapp_handler):
        """測試平台類型"""
        assert whatsapp_handler.get_platform_type() == PlatformType.WHATSAPP
    
    def test_required_config_fields(self, whatsapp_handler):
        """測試必要配置欄位"""
        required_fields = whatsapp_handler.get_required_config_fields()
        assert 'access_token' in required_fields
        assert 'phone_number_id' in required_fields
        assert 'verify_token' in required_fields
    
    def test_config_validation_success(self, config):
        """測試配置驗證成功"""
        handler = WhatsAppHandler(config)
        assert handler.validate_config() == True
        assert handler.is_enabled() == True
    
    def test_config_validation_failure(self, invalid_config):
        """測試配置驗證失敗"""
        handler = WhatsAppHandler(invalid_config)
        assert handler.validate_config() == False
    
    def test_disabled_platform(self, disabled_config):
        """測試停用平台"""
        handler = WhatsAppHandler(disabled_config)
        assert handler.is_enabled() == False
    
    def test_parse_text_message(self, whatsapp_handler):
        """測試解析文字訊息"""
        webhook_event = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "115730194473734",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "16469076883",
                            "phone_number_id": "111491931567355"
                        },
                        "contacts": [{
                            "profile": {
                                "name": "Test User"
                            },
                            "wa_id": "16315555555"
                        }],
                        "messages": [{
                            "from": "16315555555",
                            "id": "wamid.HBgN...",
                            "timestamp": "1657899618",
                            "text": {
                                "body": "Hello World"
                            },
                            "type": "text"
                        }]
                    },
                    "field": "messages"
                }]
            }]
        }
        
        message = whatsapp_handler.parse_message(webhook_event)
        
        assert message is not None
        assert message.message_id == 'wamid.HBgN...'
        assert message.content == 'Hello World'
        assert message.message_type == 'text'
        assert message.user.user_id == '16315555555'
        assert message.user.platform == PlatformType.WHATSAPP
        assert message.user.display_name == 'Test User'
        assert message.metadata['from'] == '16315555555'
        assert message.metadata['phone_number_id'] == '111491931567355'
    
    def test_parse_audio_message(self, whatsapp_handler):
        """測試解析音訊訊息"""
        webhook_event = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "phone_number_id": "111491931567355"
                        },
                        "contacts": [{
                            "profile": {
                                "name": "Test User"
                            },
                            "wa_id": "16315555555"
                        }],
                        "messages": [{
                            "from": "16315555555",
                            "id": "wamid.AUDIO123",
                            "timestamp": "1657899618",
                            "type": "audio",
                            "audio": {
                                "id": "media_id_123",
                                "mime_type": "audio/ogg"
                            }
                        }]
                    }
                }]
            }]
        }
        
        with patch.object(whatsapp_handler, '_download_media', return_value=b'fake_audio_data'):
            message = whatsapp_handler.parse_message(webhook_event)
        
        assert message is not None
        assert message.message_id == 'wamid.AUDIO123'
        assert message.content == '[Audio Message]'
        assert message.message_type == 'audio'
        assert message.raw_data == b'fake_audio_data'
    
    def test_parse_location_message(self, whatsapp_handler):
        """測試解析位置訊息"""
        webhook_event = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "phone_number_id": "111491931567355"
                        },
                        "contacts": [{
                            "wa_id": "16315555555"
                        }],
                        "messages": [{
                            "from": "16315555555",
                            "id": "wamid.LOCATION123",
                            "timestamp": "1657899618",
                            "type": "location",
                            "location": {
                                "latitude": 37.4220656,
                                "longitude": -122.0840897
                            }
                        }]
                    }
                }]
            }]
        }
        
        message = whatsapp_handler.parse_message(webhook_event)
        
        assert message is not None
        assert message.message_type == 'location'
        assert '[Location: 37.4220656, -122.0840897]' in message.content
    
    def test_parse_non_whatsapp_event(self, whatsapp_handler):
        """測試解析非 WhatsApp 事件"""
        webhook_event = {
            "object": "other_platform",
            "entry": []
        }
        
        message = whatsapp_handler.parse_message(webhook_event)
        assert message is None
    
    def test_parse_empty_event(self, whatsapp_handler):
        """測試解析空事件"""
        webhook_event = {
            "object": "whatsapp_business_account",
            "entry": []
        }
        
        message = whatsapp_handler.parse_message(webhook_event)
        assert message is None
    
    @patch('src.platforms.whatsapp_handler.requests.post')
    def test_send_text_message_success(self, mock_post, whatsapp_handler):
        """測試發送文字訊息成功"""
        # 模擬 API 回應 - 確保使用同步 Mock
        mock_response = Mock(spec=['status_code', 'text'])
        mock_response.status_code = 200
        mock_response.text = 'Success'
        mock_post.return_value = mock_response
        
        # 建立測試訊息
        user = PlatformUser(user_id='16315555555', platform=PlatformType.WHATSAPP)
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
        result = whatsapp_handler.send_response(response, message)
        
        assert result == True
        mock_post.assert_called_once()
        
        # 驗證 API 呼叫參數
        call_args = mock_post.call_args
        assert 'https://graph.facebook.com/v13.0/test_phone_number_id/messages' in call_args[0][0]
        assert call_args[1]['json']['to'] == '16315555555'
        assert call_args[1]['json']['text']['body'] == 'Hello back!'
        assert call_args[1]['json']['messaging_product'] == 'whatsapp'
    
    @patch('src.platforms.whatsapp_handler.requests.post')
    def test_send_text_message_failure(self, mock_post, whatsapp_handler):
        """測試發送文字訊息失敗"""
        # 模擬 API 錯誤回應 - 確保使用同步 Mock
        mock_response = Mock(spec=['status_code', 'text'])
        mock_response.status_code = 400
        mock_response.text = 'Bad Request'
        mock_post.return_value = mock_response
        
        # 建立測試訊息
        user = PlatformUser(user_id='16315555555', platform=PlatformType.WHATSAPP)
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
        result = whatsapp_handler.send_response(response, message)
        
        assert result == False
    
    def test_handle_webhook_single_message(self, whatsapp_handler):
        """測試處理單一 webhook 訊息"""
        webhook_data = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "phone_number_id": "111491931567355"
                        },
                        "contacts": [{
                            "wa_id": "16315555555"
                        }],
                        "messages": [{
                            "from": "16315555555",
                            "id": "wamid.TEST123",
                            "type": "text",
                            "text": {
                                "body": "Hello"
                            }
                        }]
                    }
                }]
            }]
        }
        
        webhook_body = json.dumps(webhook_data)
        signature = 'sha256=test_signature'
        
        with patch.object(whatsapp_handler, '_verify_signature', return_value=True):
            messages = whatsapp_handler.handle_webhook(webhook_body, signature)
        
        assert len(messages) == 1
        assert messages[0].content == 'Hello'
        assert messages[0].user.user_id == '16315555555'
    
    def test_handle_webhook_verification_request(self, whatsapp_handler):
        """測試處理 webhook 驗證請求"""
        webhook_data = {
            "hub.mode": "subscribe",
            "hub.verify_token": "test_verify_token",
            "hub.challenge": "challenge_value"
        }
        
        webhook_body = json.dumps(webhook_data)
        signature = ''
        
        messages = whatsapp_handler.handle_webhook(webhook_body, signature)
        
        assert len(messages) == 0  # 驗證請求不應該返回訊息
    
    def test_handle_webhook_invalid_json(self, whatsapp_handler):
        """測試處理無效 JSON webhook"""
        webhook_body = '{"invalid": json}'
        signature = 'sha256=test_signature'
        
        messages = whatsapp_handler.handle_webhook(webhook_body, signature)
        
        assert len(messages) == 0
    
    def test_verify_signature_success(self, whatsapp_handler):
        """測試簽名驗證成功"""
        request_body = '{"test": "data"}'
        # 使用正確的 HMAC 計算
        import hmac
        import hashlib
        expected_signature = hmac.new(
            'test_app_secret'.encode('utf-8'),
            request_body.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        signature = f'sha256={expected_signature}'
        
        result = whatsapp_handler._verify_signature(request_body, signature)
        assert result == True
    
    def test_verify_signature_failure(self, whatsapp_handler):
        """測試簽名驗證失敗"""
        request_body = '{"test": "data"}'
        signature = 'sha256=invalid_signature'
        
        result = whatsapp_handler._verify_signature(request_body, signature)
        assert result == False
    
    def test_verify_signature_invalid_format(self, whatsapp_handler):
        """測試無效簽名格式"""
        request_body = '{"test": "data"}'
        signature = 'invalid_format'
        
        result = whatsapp_handler._verify_signature(request_body, signature)
        assert result == False
    
    def test_verify_webhook_success(self, whatsapp_handler):
        """測試 webhook 驗證成功"""
        verify_token = 'test_verify_token'
        challenge = 'challenge_value'
        
        result = whatsapp_handler.verify_webhook(verify_token, challenge)
        assert result == 'challenge_value'
    
    def test_verify_webhook_failure(self, whatsapp_handler):
        """測試 webhook 驗證失敗"""
        verify_token = 'wrong_token'
        challenge = 'challenge_value'
        
        result = whatsapp_handler.verify_webhook(verify_token, challenge)
        assert result is None
    
    def test_get_webhook_info(self, whatsapp_handler):
        """測試取得 webhook 資訊"""
        info = whatsapp_handler.get_webhook_info()
        
        assert info['platform'] == 'whatsapp'
        assert info['webhook_url'] == '/webhooks/whatsapp'
        assert info['verify_token'] == 'test_verify_token'
        assert info['phone_number_id'] == 'test_phone_number_id'
        assert info['api_version'] == 'v13.0'
    
    @patch('src.platforms.whatsapp_handler.requests.get')
    def test_download_media_success(self, mock_get, whatsapp_handler):
        """測試下載媒體成功"""
        # 模擬第一次請求獲取媒體資訊
        mock_info_response = Mock()
        mock_info_response.status_code = 200
        mock_info_response.json.return_value = {
            'url': 'https://example.com/media.jpg'
        }
        
        # 模擬第二次請求下載媒體
        mock_media_response = Mock()
        mock_media_response.status_code = 200
        mock_media_response.content = b'fake_media_data'
        
        mock_get.side_effect = [mock_info_response, mock_media_response]
        
        result = whatsapp_handler._download_media('media_id_123')
        
        assert result == b'fake_media_data'
        assert mock_get.call_count == 2
    
    @patch('src.platforms.whatsapp_handler.requests.get')
    def test_download_media_failure(self, mock_get, whatsapp_handler):
        """測試下載媒體失敗"""
        # 模擬 API 錯誤回應
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        result = whatsapp_handler._download_media('invalid_media_id')
        
        assert result is None