"""
Meta 平台基礎處理器測試
測試 MetaBaseHandler 的共同功能，包括 webhook 簽名驗證
"""
import pytest
import json
import hmac
import hashlib
from unittest.mock import Mock, patch, MagicMock
from src.platforms.meta_base_handler import MetaBaseHandler
from src.platforms.base import PlatformType, PlatformUser, PlatformMessage, PlatformResponse


class TestMetaBaseHandler:
    """Meta 基礎處理器測試類別"""
    
    class ConcreteMetaHandler(MetaBaseHandler):
        """具體實現的 Meta 處理器，用於測試抽象基類"""
        
        def get_platform_type(self):
            return PlatformType.WHATSAPP
        
        def get_required_config_fields(self):
            return ['access_token', 'verify_token']
        
        def get_default_api_version(self):
            return 'v16.0'
        
        def _setup_platform_config(self):
            self.access_token = self.get_config('access_token')
        
        def get_webhook_object_type(self):
            return 'test_object'
        
        def get_platform_name(self):
            return 'TestMeta'
        
        def parse_message(self, webhook_event):
            return None
        
        def _process_webhook_messages(self, webhook_data):
            return []
        
        def _get_recipient_id(self, message):
            return message.user.user_id
        
        def _send_text_message(self, recipient_id, text):
            return True
    
    @pytest.fixture
    def config(self):
        """測試配置"""
        return {
            'platforms': {
                'whatsapp': {
                    'enabled': True,
                    'access_token': 'test_access_token',
                    'app_secret': 'test_app_secret',
                    'verify_token': 'test_verify_token',
                    'api_version': 'v16.0'
                }
            }
        }
    
    @pytest.fixture
    def meta_handler(self, config):
        """Meta 處理器實例"""
        return self.ConcreteMetaHandler(config)
    
    def test_initialization(self, meta_handler):
        """測試初始化"""
        assert meta_handler.app_secret == 'test_app_secret'
        assert meta_handler.verify_token == 'test_verify_token'
        assert meta_handler.api_version == 'v16.0'
        assert meta_handler.base_url == 'https://graph.facebook.com/v16.0'
        assert meta_handler.access_token == 'test_access_token'
    
    def test_meta_signature_verification_sha256_success(self, meta_handler):
        """測試 SHA256 簽名驗證成功"""
        request_body = '{"test": "data"}'
        body_bytes = request_body.encode('utf-8')
        
        # 計算正確的 HMAC-SHA256 簽名
        expected_signature = hmac.new(
            'test_app_secret'.encode('utf-8'),
            body_bytes,
            hashlib.sha256
        ).hexdigest()
        signature = f'sha256={expected_signature}'
        
        result = meta_handler._verify_meta_signature('test_app_secret', body_bytes, signature)
        assert result == True
    
    def test_meta_signature_verification_sha1_success(self, meta_handler):
        """測試 SHA1 簽名驗證成功（Messenger 舊版本）"""
        request_body = '{"test": "data"}'
        body_bytes = request_body.encode('utf-8')
        
        # 計算正確的 HMAC-SHA1 簽名
        expected_signature = hmac.new(
            'test_app_secret'.encode('utf-8'),
            body_bytes,
            hashlib.sha1
        ).hexdigest()
        signature = f'sha1={expected_signature}'
        
        result = meta_handler._verify_meta_signature('test_app_secret', body_bytes, signature)
        assert result == True
    
    def test_meta_signature_verification_failure(self, meta_handler):
        """測試簽名驗證失敗"""
        request_body = '{"test": "data"}'
        body_bytes = request_body.encode('utf-8')
        signature = 'sha256=invalid_signature'
        
        result = meta_handler._verify_meta_signature('test_app_secret', body_bytes, signature)
        assert result == False
    
    def test_meta_signature_verification_invalid_format(self, meta_handler):
        """測試無效簽名格式"""
        request_body = '{"test": "data"}'
        body_bytes = request_body.encode('utf-8')
        signature = 'invalid_format'
        
        result = meta_handler._verify_meta_signature('test_app_secret', body_bytes, signature)
        assert result == False
    
    def test_meta_signature_verification_no_signature(self, meta_handler):
        """測試沒有簽名"""
        request_body = '{"test": "data"}'
        body_bytes = request_body.encode('utf-8')
        
        result = meta_handler._verify_meta_signature('test_app_secret', body_bytes, None)
        assert result == False
    
    def test_meta_signature_verification_no_app_secret(self, meta_handler):
        """測試沒有 app_secret 時跳過驗證"""
        request_body = '{"test": "data"}'
        body_bytes = request_body.encode('utf-8')
        signature = 'sha256=any_signature'
        
        result = meta_handler._verify_meta_signature('', body_bytes, signature)
        assert result == True
        
        result = meta_handler._verify_meta_signature(None, body_bytes, signature)
        assert result == True
    
    def test_webhook_signature_verification(self, meta_handler):
        """測試 webhook 簽名驗證流程"""
        request_body = '{"test": "data"}'
        
        # 測試有簽名的情況
        headers = {'X-Hub-Signature-256': 'sha256=test_signature'}
        
        with patch.object(meta_handler, '_verify_signature', return_value=True):
            result = meta_handler._verify_webhook_signature(request_body, headers)
            assert result == True
        
        # 測試沒有簽名和 app_secret 的情況
        meta_handler.app_secret = None
        headers = {}
        result = meta_handler._verify_webhook_signature(request_body, headers)
        assert result == True
    
    def test_parse_webhook_data_success(self, meta_handler):
        """測試 webhook 數據解析成功"""
        webhook_data = {"object": "test_object", "data": "test"}
        request_body = json.dumps(webhook_data)
        
        result = meta_handler._parse_webhook_data(request_body)
        assert result == webhook_data
    
    def test_parse_webhook_data_invalid_json(self, meta_handler):
        """測試無效 JSON"""
        request_body = '{"invalid": json}'
        
        result = meta_handler._parse_webhook_data(request_body)
        assert result is None
    
    def test_validate_webhook_object_success(self, meta_handler):
        """測試 webhook object 驗證成功"""
        webhook_data = {"object": "test_object"}
        
        result = meta_handler._validate_webhook_object(webhook_data)
        assert result == True
    
    def test_validate_webhook_object_failure(self, meta_handler):
        """測試 webhook object 驗證失敗"""
        webhook_data = {"object": "wrong_object"}
        
        result = meta_handler._validate_webhook_object(webhook_data)
        assert result == False
    
    def test_handle_webhook_full_flow(self, meta_handler):
        """測試完整的 webhook 處理流程"""
        webhook_data = {"object": "test_object", "entry": []}
        request_body = json.dumps(webhook_data)
        headers = {}
        
        # Mock 所有相關方法
        with patch.object(meta_handler, '_verify_webhook_signature', return_value=True), \
             patch.object(meta_handler, '_process_webhook_messages', return_value=[]):
            
            result = meta_handler.handle_webhook(request_body, headers)
            assert result == []
    
    def test_handle_webhook_signature_failure(self, meta_handler):
        """測試簽名驗證失敗時的 webhook 處理"""
        webhook_data = {"object": "test_object"}
        request_body = json.dumps(webhook_data)
        headers = {}
        
        with patch.object(meta_handler, '_verify_webhook_signature', return_value=False):
            result = meta_handler.handle_webhook(request_body, headers)
            assert result == []
    
    @patch('src.platforms.meta_base_handler.requests.get')
    def test_download_media_from_url_success(self, mock_get, meta_handler):
        """測試從 URL 下載媒體成功"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'fake_media_data'
        mock_get.return_value = mock_response
        
        result = meta_handler._download_media_from_url('https://example.com/media.jpg')
        assert result == b'fake_media_data'
    
    @patch('src.platforms.meta_base_handler.requests.get')
    def test_download_media_from_url_failure(self, mock_get, meta_handler):
        """測試從 URL 下載媒體失敗"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        result = meta_handler._download_media_from_url('https://example.com/media.jpg')
        assert result is None
    
    @patch('src.platforms.meta_base_handler.requests.get')
    def test_download_media_from_id_success(self, mock_get, meta_handler):
        """測試從 ID 下載媒體成功"""
        # Mock 第一次請求獲取媒體資訊
        mock_info_response = Mock()
        mock_info_response.status_code = 200
        mock_info_response.json.return_value = {'url': 'https://example.com/media.jpg'}
        
        # Mock 第二次請求下載媒體
        mock_media_response = Mock()
        mock_media_response.status_code = 200
        mock_media_response.content = b'fake_media_data'
        
        mock_get.side_effect = [mock_info_response, mock_media_response]
        
        result = meta_handler._download_media_from_id('media_id_123')
        assert result == b'fake_media_data'
    
    @patch('src.platforms.meta_base_handler.requests.get')
    def test_download_media_from_id_failure(self, mock_get, meta_handler):
        """測試從 ID 下載媒體失敗"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        result = meta_handler._download_media_from_id('invalid_media_id')
        assert result is None
    
    def test_send_response_text(self, meta_handler):
        """測試發送文字回應"""
        user = PlatformUser(user_id='test_user', platform=PlatformType.WHATSAPP)
        message = PlatformMessage(
            message_id='test_msg',
            user=user,
            content='Test message'
        )
        
        response = PlatformResponse(
            content='Hello back!',
            response_type='text'
        )
        
        result = meta_handler.send_response(response, message)
        assert result == True
    
    def test_send_response_audio_not_implemented(self, meta_handler):
        """測試發送音訊回應（未實現）"""
        user = PlatformUser(user_id='test_user', platform=PlatformType.WHATSAPP)
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
        
        result = meta_handler.send_response(response, message)
        assert result == False
    
    def test_verify_webhook_success(self, meta_handler):
        """測試 webhook 驗證成功"""
        result = meta_handler.verify_webhook('test_verify_token', 'challenge_value')
        assert result == 'challenge_value'
    
    def test_verify_webhook_failure(self, meta_handler):
        """測試 webhook 驗證失敗"""
        result = meta_handler.verify_webhook('wrong_token', 'challenge_value')
        assert result is None
    
    def test_get_webhook_info(self, meta_handler):
        """測試取得 webhook 資訊"""
        info = meta_handler.get_webhook_info()
        
        assert info['platform'] == 'testmeta'
        assert info['webhook_url'] == '/webhooks/testmeta'
        assert info['verify_token'] == 'test_verify_token'
        assert info['api_version'] == 'v16.0'
    
    def test_setup_headers(self, meta_handler):
        """測試設置請求標頭"""
        assert hasattr(meta_handler, 'headers')
        assert 'Authorization' in meta_handler.headers
        assert 'Bearer test_access_token' in meta_handler.headers['Authorization']
        assert meta_handler.headers['Content-Type'] == 'application/json'
    
    def test_initialization_disabled(self):
        """測試停用時的初始化"""
        config = {
            'enabled': False,
            'access_token': 'test_token',
            'app_secret': 'test_secret',
            'verify_token': 'test_verify'
        }
        
        handler = self.ConcreteMetaHandler(config)
        assert not handler.is_enabled()
    
    def test_signature_verification_with_string_body(self, meta_handler):
        """測試字串格式請求體的簽名驗證"""
        request_body = '{"test": "data"}'
        
        # 計算正確的簽名
        expected_signature = hmac.new(
            'test_app_secret'.encode('utf-8'),
            request_body.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        signature = f'sha256={expected_signature}'
        
        result = meta_handler._verify_signature(request_body, signature)
        assert result == True
    
    def test_signature_verification_with_bytes_body(self, meta_handler):
        """測試位元組格式請求體的簽名驗證"""
        request_body = b'{"test": "data"}'
        
        # 計算正確的簽名
        expected_signature = hmac.new(
            'test_app_secret'.encode('utf-8'),
            request_body,
            hashlib.sha256
        ).hexdigest()
        signature = f'sha256={expected_signature}'
        
        result = meta_handler._verify_signature(request_body, signature)
        assert result == True
    
    def test_signature_verification_exception_handling(self, meta_handler):
        """測試簽名驗證異常處理"""
        # 使用會導致異常的數據
        with patch('src.platforms.meta_base_handler.hmac.new', side_effect=Exception("HMAC error")):
            result = meta_handler._verify_signature('test_body', 'sha256=test_signature')
            assert result == False