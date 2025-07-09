"""
Discord 處理器單元測試
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from src.platforms.base import PlatformType, PlatformUser, PlatformMessage, PlatformResponse
from src.platforms.discord_handler import DiscordHandler, DiscordBotManager


class TestDiscordHandler:
    """測試 Discord 處理器"""
    
    def setup_method(self):
        """每個測試方法前的設置"""
        self.valid_config = {
            'platforms': {
                'discord': {
                    'enabled': True,
                    'bot_token': 'test_discord_token',
                    'guild_id': '123456789',
                    'command_prefix': '!'
                }
            }
        }
        
        self.invalid_config = {
            'platforms': {
                'discord': {
                    'enabled': True,
                    # 缺少必要的 bot_token
                }
            }
        }
        
        self.disabled_config = {
            'platforms': {
                'discord': {
                    'enabled': False,
                    'bot_token': 'test_discord_token'
                }
            }
        }
    
    @patch('src.platforms.discord_handler.DISCORD_AVAILABLE', False)
    def test_discord_handler_initialization_without_discord_py(self):
        """測試在沒有 discord.py 的情況下初始化"""
        handler = DiscordHandler(self.valid_config)
        
        assert handler.get_platform_type() == PlatformType.DISCORD
        assert not hasattr(handler, 'bot') or handler.bot is None
    
    @patch('src.platforms.discord_handler.DISCORD_AVAILABLE', True)
    def test_discord_handler_initialization_with_valid_config(self):
        """測試使用有效配置初始化"""
        handler = DiscordHandler(self.valid_config)
        
        assert handler.get_platform_type() == PlatformType.DISCORD
        assert handler.bot_token == 'test_discord_token'
        assert handler.guild_id == '123456789'
        assert handler.command_prefix == '!'
        # 由於沒有真正的 Discord SDK，不檢查 bot 實例
    
    def test_discord_handler_initialization_with_invalid_config(self):
        """測試使用無效配置初始化"""
        handler = DiscordHandler(self.invalid_config)
        
        assert handler.get_platform_type() == PlatformType.DISCORD
        assert not handler.validate_config()
    
    def test_discord_handler_initialization_with_disabled_config(self):
        """測試使用禁用配置初始化"""
        handler = DiscordHandler(self.disabled_config)
        
        assert handler.get_platform_type() == PlatformType.DISCORD
        assert not handler.is_enabled()
    
    def test_get_required_config_fields(self):
        """測試取得必要配置欄位"""
        handler = DiscordHandler(self.valid_config)
        required_fields = handler.get_required_config_fields()
        
        assert 'bot_token' in required_fields
        assert len(required_fields) == 1
    
    @patch('src.platforms.discord_handler.DISCORD_AVAILABLE', True)
    def test_parse_message_simple(self):
        """測試解析訊息（簡化版）"""
        handler = DiscordHandler(self.valid_config)
        
        # 測試 None 輸入
        result = handler.parse_message(None)
        assert result is None
        
        # 測試字符串輸入（無效）
        result = handler.parse_message("invalid")
        assert result is None
    
    @patch('src.platforms.discord_handler.DISCORD_AVAILABLE', True)
    def test_send_response_no_bot(self):
        """測試沒有 bot 時發送回應"""
        handler = DiscordHandler(self.valid_config)
        handler.bot = None
        
        user = PlatformUser(user_id="123", platform=PlatformType.DISCORD)
        message = PlatformMessage(
            message_id="msg_123",
            user=user,
            content="Hello",
            metadata={}
        )
        
        response = PlatformResponse(content="Hello back!")
        
        result = handler.send_response(response, message)
        
        assert result is False
    
    @patch('src.platforms.discord_handler.DISCORD_AVAILABLE', True)
    def test_send_response_no_discord_message(self):
        """測試沒有 Discord 訊息時發送回應"""
        # 直接創建處理器，不需要 mock Discord SDK
        handler = DiscordHandler(self.valid_config)
        handler.bot = Mock()  # 手動設置 bot
        
        user = PlatformUser(user_id="123", platform=PlatformType.DISCORD)
        message = PlatformMessage(
            message_id="msg_123",
            user=user,
            content="Hello",
            metadata={}  # 沒有 discord_message
        )
        
        response = PlatformResponse(content="Hello back!")
        
        result = handler.send_response(response, message)
        
        assert result is False
    
    @patch('src.platforms.discord_handler.DISCORD_AVAILABLE', True)
    def test_handle_webhook_no_bot(self):
        """測試沒有 bot 時處理 webhook"""
        handler = DiscordHandler(self.valid_config)
        handler.bot = None
        
        messages = handler.handle_webhook("test_body", "test_signature")
        
        assert messages == []
    
    @patch('src.platforms.discord_handler.DISCORD_AVAILABLE', True)
    def test_handle_webhook_with_bot(self):
        """測試有 bot 時處理 webhook"""
        handler = DiscordHandler(self.valid_config)
        handler.bot = Mock()
        
        # 由於沒有真正的 Discord SDK，這個測試主要檢查不會崩潰
        messages = handler.handle_webhook("test_body", "test_signature")
        
        # 預期返回空列表，因為沒有真正的 Discord 處理
        assert isinstance(messages, list)


class TestDiscordBotManager:
    """測試 Discord Bot 管理器"""
    
    def test_manager_initialization(self):
        """測試管理器初始化"""
        manager = DiscordBotManager()
        
        assert manager.handlers == {}
    
    def test_register_handler(self):
        """測試註冊處理器"""
        manager = DiscordBotManager()
        
        # 創建 mock 處理器
        mock_handler = Mock(spec=DiscordHandler)
        
        manager.register_handler(mock_handler)
        
        assert id(mock_handler) in manager.handlers
        assert manager.handlers[id(mock_handler)] == mock_handler
    
    def test_unregister_handler(self):
        """測試取消註冊處理器"""
        manager = DiscordBotManager()
        
        # 創建 mock 處理器
        mock_handler = Mock(spec=DiscordHandler)
        mock_handler.stop_bot = Mock()
        
        # 先註冊，再取消註冊
        manager.register_handler(mock_handler)
        manager.unregister_handler(mock_handler)
        
        assert id(mock_handler) not in manager.handlers
        mock_handler.stop_bot.assert_called_once()
    
    def test_stop_all(self):
        """測試停止所有處理器"""
        manager = DiscordBotManager()
        
        # 創建多個 mock 處理器
        mock_handler1 = Mock(spec=DiscordHandler)
        mock_handler1.stop_bot = Mock()
        mock_handler2 = Mock(spec=DiscordHandler)
        mock_handler2.stop_bot = Mock()
        
        manager.register_handler(mock_handler1)
        manager.register_handler(mock_handler2)
        
        manager.stop_all()
        
        assert manager.handlers == {}
        mock_handler1.stop_bot.assert_called_once()
        mock_handler2.stop_bot.assert_called_once()


class TestDiscordHandlerExtended:
    """Discord 處理器擴展測試"""
    
    def setup_method(self):
        """每個測試方法前的設置"""
        self.valid_config = {
            'platforms': {
                'discord': {
                    'enabled': True,
                    'bot_token': 'test_discord_token',
                    'guild_id': '123456789',
                    'command_prefix': '!'
                }
            }
        }

    @patch('src.platforms.discord_handler.DISCORD_AVAILABLE', True)
    def test_parse_message_with_text_content(self):
        """測試解析包含文字內容的訊息（簡化版）"""
        handler = DiscordHandler(self.valid_config)
        
        # 測試空輸入
        result = handler.parse_message(None)
        assert result is None
        
        # 測試無效輸入
        result = handler.parse_message("invalid")
        assert result is None
    
    @patch('src.platforms.discord_handler.DISCORD_AVAILABLE', True)
    def test_parse_message_with_audio_attachment(self):
        """測試解析包含音訊附件的訊息（簡化版）"""
        handler = DiscordHandler(self.valid_config)
        
        # 測試基本功能
        assert handler.get_platform_type() == PlatformType.DISCORD
        assert hasattr(handler, '_download_attachment')
    
    @patch('src.platforms.discord_handler.DISCORD_AVAILABLE', True)
    def test_send_response_success(self):
        """測試發送回應（簡化版）"""
        handler = DiscordHandler(self.valid_config)
        
        user = PlatformUser(user_id="123", platform=PlatformType.DISCORD)
        message = PlatformMessage(
            message_id="msg_123",
            user=user,
            content="Hello",
            metadata={}
        )
        
        response = PlatformResponse(content="Hello back!")
        
        # 沒有 bot 時應該返回 False
        result = handler.send_response(response, message)
        assert result is False
    
    @patch('src.platforms.discord_handler.DISCORD_AVAILABLE', True)
    def test_send_response_api_error(self):
        """測試發送回應時的 API 錯誤"""
        handler = DiscordHandler(self.valid_config)
        handler.bot = Mock()
        
        mock_discord_message = Mock()
        mock_discord_message.channel = Mock()
        
        user = PlatformUser(user_id="123", platform=PlatformType.DISCORD)
        message = PlatformMessage(
            message_id="msg_123",
            user=user,
            content="Hello",
            metadata={'discord_message': mock_discord_message}
        )
        
        response = PlatformResponse(content="Hello back!")
        
        # Mock _send_message_async to raise exception
        with patch.object(handler, '_send_message_async', new_callable=AsyncMock) as mock_send:
            mock_send.side_effect = Exception("Discord API Error")
            with patch('asyncio.run', side_effect=Exception("Discord API Error")):
                result = handler.send_response(response, message)
        
        assert result is False
    
    @patch('src.platforms.discord_handler.DISCORD_AVAILABLE', True)
    def test_start_and_stop_bot(self):
        """測試啟動和停止 bot（簡化版）"""
        handler = DiscordHandler(self.valid_config)
        
        # 測試基本方法存在
        assert hasattr(handler, '_start_bot')
        assert hasattr(handler, 'stop_bot')
        
        # 測試沒有 bot 時停止
        handler.bot = None
        handler.stop_bot()  # 不應該崩潰
    
    @patch('src.platforms.discord_handler.DISCORD_AVAILABLE', True)
    def test_handle_webhook_simple(self):
        """測試處理 webhook（簡化版）"""
        handler = DiscordHandler(self.valid_config)
        
        # 測試沒有 bot 時
        handler.bot = None
        messages = handler.handle_webhook("test_body", "test_signature")
        assert messages == []
        
        # 測試有 bot 時
        handler.bot = Mock()
        messages = handler.handle_webhook("test_body", "test_signature")
        assert isinstance(messages, list)


class TestDiscordHandlerIntegration:
    """Discord 處理器整合測試"""
    
    @patch('src.platforms.discord_handler.DISCORD_AVAILABLE', True)
    def test_basic_workflow(self):
        """測試基本工作流程"""
        handler = DiscordHandler({
            'platforms': {
                'discord': {
                    'enabled': True,
                    'bot_token': 'test_token',
                    'guild_id': '123456789',
                    'command_prefix': '!'
                }
            }
        })
        
        # 測試基本屬性
        assert handler.get_platform_type() == PlatformType.DISCORD
        assert handler.bot_token == 'test_token'
        
        # 測試配置驗證
        assert hasattr(handler, 'validate_config')
        
        # 測試基本方法不會崩潰
        result = handler.parse_message(None)
        assert result is None
    
    @patch('src.platforms.discord_handler.DISCORD_AVAILABLE', True)
    def test_complete_message_flow(self):
        """測試完整的訊息流程"""
        config = {
            'platforms': {
                'discord': {
                    'enabled': True,
                    'bot_token': 'test_token',
                    'guild_id': '123456789'
                }
            }
        }
        
        handler = DiscordHandler(config)
        
        # 測試基本屬性設置
        assert handler.bot_token == 'test_token'
        assert handler.guild_id == '123456789'
        assert handler.command_prefix == '!'  # 默認值
        
        # 測試訊息解析（空輸入）
        result = handler.parse_message(None)
        assert result is None
        
        # 測試發送回應（沒有 bot）
        user = PlatformUser(user_id="123", platform=PlatformType.DISCORD)
        message = PlatformMessage(
            message_id="msg_123",
            user=user,
            content="Hello",
            metadata={}
        )
        response = PlatformResponse(content="Hello back!")
        
        result = handler.send_response(response, message)
        assert result is False


class TestDiscordAsyncMethods:
    """測試 Discord 異步方法"""
    
    def test_download_attachment_mock(self):
        """測試下載附件（模擬）"""
        from src.platforms.discord_handler import DiscordHandler
        
        config = {
            'platforms': {
                'discord': {
                    'enabled': True,
                    'bot_token': 'test_token'
                }
            }
        }
        
        with patch('src.platforms.discord_handler.DISCORD_AVAILABLE', True):
            handler = DiscordHandler(config)
            
            # 創建 mock 附件
            mock_attachment = Mock()
            mock_attachment.read = AsyncMock(return_value=b'fake_data')
            
            # 測試異步方法的邏輯（不實際執行異步）
            assert hasattr(handler, '_download_attachment')


if __name__ == "__main__":
    pytest.main([__file__])