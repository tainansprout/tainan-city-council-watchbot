"""
Telegram 處理器單元測試
"""
import pytest
import asyncio
import json
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from src.platforms.base import PlatformType, PlatformUser, PlatformMessage, PlatformResponse
from src.platforms.telegram_handler import TelegramHandler, TelegramUtils


class TestTelegramHandler:
    """測試 Telegram 處理器"""
    
    def setup_method(self):
        """每個測試方法前的設置"""
        self.valid_config = {
            'platforms': {
                'telegram': {
                    'enabled': True,
                    'bot_token': 'test_telegram_token',
                    'webhook_secret': 'test_secret'
                }
            }
        }
        
        self.invalid_config = {
            'platforms': {
                'telegram': {
                    'enabled': True,
                    # 缺少必要的 bot_token
                }
            }
        }
        
        self.disabled_config = {
            'platforms': {
                'telegram': {
                    'enabled': False,
                    'bot_token': 'test_telegram_token'
                }
            }
        }
    
    @patch('src.platforms.telegram_handler.TELEGRAM_AVAILABLE', False)
    def test_telegram_handler_initialization_without_telegram_bot(self):
        """測試在沒有 python-telegram-bot 的情況下初始化"""
        handler = TelegramHandler(self.valid_config)
        
        assert handler.get_platform_type() == PlatformType.TELEGRAM
        assert not hasattr(handler, 'bot') or handler.bot is None
        assert not hasattr(handler, 'application') or handler.application is None
    
    @patch('src.platforms.telegram_handler.TELEGRAM_AVAILABLE', True)
    def test_telegram_handler_initialization_with_valid_config(self):
        """測試使用有效配置初始化"""
        handler = TelegramHandler(self.valid_config)
        
        assert handler.get_platform_type() == PlatformType.TELEGRAM
        assert handler.bot_token == 'test_telegram_token'
        assert handler.webhook_secret == 'test_secret'
        # 由於沒有真正的 Telegram SDK，不檢查 bot 實例
    
    def test_telegram_handler_initialization_with_invalid_config(self):
        """測試使用無效配置初始化"""
        handler = TelegramHandler(self.invalid_config)
        
        assert handler.get_platform_type() == PlatformType.TELEGRAM
        assert not handler.validate_config()
    
    def test_telegram_handler_initialization_with_disabled_config(self):
        """測試使用禁用配置初始化"""
        handler = TelegramHandler(self.disabled_config)
        
        assert handler.get_platform_type() == PlatformType.TELEGRAM
        assert not handler.is_enabled()
    
    def test_get_required_config_fields(self):
        """測試取得必要配置欄位"""
        handler = TelegramHandler(self.valid_config)
        required_fields = handler.get_required_config_fields()
        
        assert 'bot_token' in required_fields
        assert len(required_fields) == 1
    
    @patch('src.platforms.telegram_handler.TELEGRAM_AVAILABLE', True)
    def test_parse_message_simple(self):
        """測試解析訊息（簡化版）"""
        handler = TelegramHandler(self.valid_config)
        
        # 測試 None 輸入
        result = handler.parse_message(None)
        assert result is None
        
        # 測試字符串輸入（無效）
        result = handler.parse_message("invalid")
        assert result is None
    
    @patch('src.platforms.telegram_handler.TELEGRAM_AVAILABLE', True)
    def test_send_response_no_bot(self):
        """測試沒有 bot 時發送回應"""
        handler = TelegramHandler(self.valid_config)
        handler.bot = None
        
        user = PlatformUser(user_id="123", platform=PlatformType.TELEGRAM)
        message = PlatformMessage(
            message_id="msg_123",
            user=user,
            content="Hello",
            metadata={'chat_id': '987654321'}
        )
        
        response = PlatformResponse(content="Hello back!")
        
        result = handler.send_response(response, message)
        
        assert result is False
    
    @patch('src.platforms.telegram_handler.TELEGRAM_AVAILABLE', True)
    def test_send_response_no_chat_id(self):
        """測試沒有 chat_id 時發送回應"""
        handler = TelegramHandler(self.valid_config)
        handler.bot = Mock()
        
        user = PlatformUser(user_id="123", platform=PlatformType.TELEGRAM)
        message = PlatformMessage(
            message_id="msg_123",
            user=user,
            content="Hello",
            metadata={}  # 沒有 chat_id
        )
        
        response = PlatformResponse(content="Hello back!")
        
        result = handler.send_response(response, message)
        
        assert result is False
    
    @patch('src.platforms.telegram_handler.TELEGRAM_AVAILABLE', True)
    def test_handle_webhook_no_bot(self):
        """測試沒有 bot 時處理 webhook"""
        handler = TelegramHandler(self.valid_config)
        handler.bot = None
        handler.application = None
        
        messages = handler.handle_webhook("test_body", "test_signature")
        
        assert messages == []
    
    @patch('src.platforms.telegram_handler.TELEGRAM_AVAILABLE', True)
    def test_verify_webhook_signature_valid(self):
        """測試驗證有效的 webhook 簽名"""
        handler = TelegramHandler(self.valid_config)
        handler.webhook_secret = 'test_secret'
        
        request_body = "test_body"
        signature = 'test_secret'
        
        result = handler._verify_webhook_signature(request_body, signature)
        
        assert result is True
    
    @patch('src.platforms.telegram_handler.TELEGRAM_AVAILABLE', True)
    def test_verify_webhook_signature_invalid(self):
        """測試驗證無效的 webhook 簽名"""
        handler = TelegramHandler(self.valid_config)
        handler.webhook_secret = 'test_secret'
        
        request_body = "test_body"
        signature = 'invalid_secret'
        
        result = handler._verify_webhook_signature(request_body, signature)
        
        assert result is False
    
    @patch('src.platforms.telegram_handler.TELEGRAM_AVAILABLE', True)
    def test_verify_webhook_signature_no_secret(self):
        """測試沒有密鑰時驗證簽名"""
        handler = TelegramHandler(self.valid_config)
        handler.webhook_secret = ''
        
        request_body = "test_body"
        signature = 'any_signature'
        
        result = handler._verify_webhook_signature(request_body, signature)
        
        assert result is True  # 沒有密鑰時跳過驗證
    
    @patch('src.platforms.telegram_handler.TELEGRAM_AVAILABLE', True)
    def test_set_webhook_no_bot(self):
        """測試沒有 bot 時設定 webhook"""
        handler = TelegramHandler(self.valid_config)
        handler.bot = None
        
        webhook_url = "https://example.com/webhook"
        
        result = handler.set_webhook(webhook_url)
        
        assert result is False
    
    @patch('src.platforms.telegram_handler.TELEGRAM_AVAILABLE', True)
    def test_delete_webhook_no_bot(self):
        """測試沒有 bot 時刪除 webhook"""
        handler = TelegramHandler(self.valid_config)
        handler.bot = None
        
        result = handler.delete_webhook()
        
        assert result is False
    
    @patch('src.platforms.telegram_handler.TELEGRAM_AVAILABLE', True)
    def test_get_bot_info_no_bot(self):
        """測試沒有 bot 時取得 bot 資訊"""
        handler = TelegramHandler(self.valid_config)
        handler.bot = None
        
        bot_info = handler.get_bot_info()
        
        assert bot_info is None


class TestTelegramUtils:
    """測試 Telegram 工具函數"""
    
    def test_escape_markdown(self):
        """測試轉義 Markdown 字符"""
        text = "Hello *world* with _underscores_ and [links](http://example.com)"
        escaped = TelegramUtils.escape_markdown(text)
        
        assert "*" not in escaped or "\\*" in escaped
        assert "_" not in escaped or "\\_" in escaped
        assert "[" not in escaped or "\\[" in escaped
        assert "]" not in escaped or "\\]" in escaped
    
    def test_format_user_mention(self):
        """測試格式化用戶提及"""
        user_id = "123456789"
        name = "Test User"
        mention = TelegramUtils.format_user_mention(user_id, name)
        
        assert mention == "[Test User](tg://user?id=123456789)"
    
    def test_create_inline_keyboard(self):
        """測試創建內聯鍵盤"""
        buttons = [
            [{"text": "Button 1", "callback_data": "data1"}],
            [{"text": "Button 2", "callback_data": "data2"}]
        ]
        
        keyboard_json = TelegramUtils.create_inline_keyboard(buttons)
        keyboard_data = json.loads(keyboard_json)
        
        assert "inline_keyboard" in keyboard_data
        assert len(keyboard_data["inline_keyboard"]) == 2
        assert keyboard_data["inline_keyboard"][0][0]["text"] == "Button 1"


class TestTelegramHandlerIntegration:
    """Telegram 處理器整合測試"""
    
    @patch('src.platforms.telegram_handler.TELEGRAM_AVAILABLE', True)
    def test_basic_workflow(self):
        """測試基本工作流程"""
        handler = TelegramHandler({
            'platforms': {
                'telegram': {
                    'enabled': True,
                    'bot_token': 'test_token',
                    'webhook_secret': 'test_secret'
                }
            }
        })
        
        # 測試基本屬性
        assert handler.get_platform_type() == PlatformType.TELEGRAM
        assert handler.bot_token == 'test_token'
        
        # 測試配置驗證
        assert hasattr(handler, 'validate_config')
        
        # 測試基本方法不會崩潰
        result = handler.parse_message(None)
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__])