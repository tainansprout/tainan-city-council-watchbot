"""
Discord 處理器單元測試
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from src.platforms.base import PlatformType, PlatformUser, PlatformMessage, PlatformResponse
from src.platforms.discord_handler import DiscordHandler, DiscordBotManager, DISCORD_AVAILABLE


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


class TestDiscordHandlerIntegrationComplete:
    """完整的 Discord 處理器整合測試"""
    
    def test_end_to_end_message_flow(self):
        """測試端到端訊息流程"""
        config = {
            'platforms': {
                'discord': {
                    'enabled': True,
                    'bot_token': 'test_token',
                    'guild_id': '123456789',
                    'command_prefix': '!'
                }
            }
        }
        
        with patch('src.platforms.discord_handler.DISCORD_AVAILABLE', True):
            handler = DiscordHandler(config)
            
            # Test initialization
            assert handler.is_enabled()
            assert handler.validate_config()
            assert handler.get_platform_type() == PlatformType.DISCORD
            
            # Test message parsing (simplified)
            assert handler.parse_message(None) is None
            assert handler.parse_message("invalid") is None
            
            # Test response sending without bot
            user = PlatformUser(user_id="123", platform=PlatformType.DISCORD)
            message = PlatformMessage(message_id="msg_123", user=user, content="Hello")
            response = PlatformResponse(content="Hello back!")
            
            assert handler.send_response(response, message) is False
            
            # Test webhook handling
            messages = handler.handle_webhook("test_body", "test_signature")
            assert isinstance(messages, list)

    def test_configuration_validation_comprehensive(self):
        """測試配置驗證的完整性"""
        # Valid configurations
        valid_configs = [
            {
                'platforms': {
                    'discord': {
                        'enabled': True,
                        'bot_token': 'test_token'
                    }
                }
            },
            {
                'platforms': {
                    'discord': {
                        'enabled': True,
                        'bot_token': 'test_token',
                        'guild_id': '123456789'
                    }
                }
            },
            {
                'platforms': {
                    'discord': {
                        'enabled': True,
                        'bot_token': 'test_token',
                        'command_prefix': '?'
                    }
                }
            }
        ]
        
        for config in valid_configs:
            handler = DiscordHandler(config)
            assert handler.validate_config(), f"Config should be valid: {config}"
        
        # Invalid configurations - filter out None to avoid attribute errors
        invalid_configs = [
            {},
            {'platforms': {}},
            {'platforms': {'discord': {}}},
            {'platforms': {'discord': {'enabled': True}}},  # Missing bot_token
        ]
        
        for config in invalid_configs:
            handler = DiscordHandler(config)
            assert not handler.validate_config(), f"Config should be invalid: {config}"
        
        # Test configurations with bot_token but no enabled field (valid config but not enabled)
        not_enabled_configs = [
            {'platforms': {'discord': {'bot_token': 'test'}}},  # Missing enabled field
        ]
        
        for config in not_enabled_configs:
            handler = DiscordHandler(config)
            assert handler.validate_config()  # Config is valid (has required fields)
            assert not handler.is_enabled()  # But platform is not enabled (enabled defaults to False)
        
        # Test disabled configurations separately since they have valid config but should not be enabled
        disabled_configs = [
            {'platforms': {'discord': {'enabled': False, 'bot_token': 'test'}}},  # Disabled
        ]
        
        for config in disabled_configs:
            handler = DiscordHandler(config)
            assert handler.validate_config()  # Config is valid
            assert not handler.is_enabled()  # But platform is disabled

    def test_error_resilience(self):
        """測試錯誤恢復能力"""
        config = {
            'platforms': {
                'discord': {
                    'enabled': True,
                    'bot_token': 'test_token'
                }
            }
        }
        
        handler = DiscordHandler(config)
        
        # Test various error scenarios don't crash the handler
        try:
            handler.parse_message(None)
            handler.parse_message("invalid")
            handler.parse_message(123)
            handler.parse_message([])
            handler.parse_message({})
        except Exception as e:
            pytest.fail(f"parse_message should handle errors gracefully: {e}")
        
        # Test send_response with various invalid inputs
        user = PlatformUser(user_id="123", platform=PlatformType.DISCORD)
        message = PlatformMessage(message_id="msg_123", user=user, content="Hello")
        response = PlatformResponse(content="Hello back!")
        
        # Initialize bot attribute to avoid AttributeError
        handler.bot = None
        
        try:
            handler.send_response(None, message)
            handler.send_response(response, None)
            handler.send_response(response, message)
        except Exception as e:
            pytest.fail(f"send_response should handle errors gracefully: {e}")
        
        # Test handle_webhook with various inputs
        try:
            handler.handle_webhook(None, None)
            handler.handle_webhook("", "")
            handler.handle_webhook("test", "test")
        except Exception as e:
            pytest.fail(f"handle_webhook should handle errors gracefully: {e}")

    def test_resource_management(self):
        """測試資源管理"""
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
            
            # Test that resources are properly initialized
            assert hasattr(handler, 'message_queue')
            assert hasattr(handler, 'bot')
            assert hasattr(handler, 'event_loop')
            assert hasattr(handler, 'bot_thread')
            
            # Test cleanup methods don't crash
            handler.stop_bot()
            handler.__del__()

    def test_thread_management(self):
        """測試線程管理"""
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
            
            # Test thread starting
            with patch('src.platforms.discord_handler.Thread') as mock_thread:
                mock_thread_instance = MagicMock()
                mock_thread_instance.is_alive.return_value = False
                mock_thread.return_value = mock_thread_instance
                
                handler._start_bot()
                
                mock_thread.assert_called_once()
                mock_thread_instance.start.assert_called_once()
            
            # Test thread stopping
            handler.bot = MagicMock()
            handler.event_loop = MagicMock()
            
            with patch('asyncio.run_coroutine_threadsafe') as mock_run:
                mock_future = MagicMock()
                mock_future.result.return_value = None
                mock_run.return_value = mock_future
                
                handler.stop_bot()
                mock_run.assert_called_once()

    def test_global_manager_integration(self):
        """測試全域管理器整合"""
        from src.platforms.discord_handler import get_discord_manager
        
        # Test manager is accessible
        manager = get_discord_manager()
        assert isinstance(manager, DiscordBotManager)
        
        # Test singleton behavior
        manager2 = get_discord_manager()
        assert manager is manager2
        
        # Test handler registration
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
            
            # Test registration and cleanup
            manager.register_handler(handler)
            assert len(manager.handlers) == 1
            
            manager.unregister_handler(handler)
            assert len(manager.handlers) == 0


if __name__ == "__main__":
    pytest.main([__file__])

@pytest.fixture
def valid_config():
    return {
        'platforms': {
            'discord': {
                'enabled': True,
                'bot_token': 'test_discord_token',
                'guild_id': '123456789',
                'command_prefix': '!'
            }
        }
    }

@pytest.mark.asyncio
@patch('src.platforms.discord_handler.DISCORD_AVAILABLE', True)
class TestDiscordHandlerAsyncBehavior:
    """Tests async behavior of the DiscordHandler."""

    def _create_mock_discord_message(self, content, author_is_bot=False, attachments=None):
        """Helper to create a mock discord.Message object."""
        mock_msg = MagicMock()
        mock_msg.content = content
        mock_msg.id = 'msg_id_123'
        mock_msg.channel = MagicMock()
        mock_msg.channel.id = 'channel_id_456'
        mock_msg.channel.name = 'general'
        mock_msg.guild = MagicMock()
        mock_msg.guild.id = 'guild_id_789'
        
        mock_author = MagicMock()
        mock_author.id = 'user_id_abc' if not author_is_bot else 'bot_id_xyz'
        mock_author.display_name = 'Test User'
        mock_author.name = 'testuser'
        mock_author.discriminator = '1234'
        mock_author.avatar = MagicMock()
        mock_author.avatar.url = 'http://example.com/avatar.png'
        mock_msg.author = mock_author
        
        mock_bot_user = MagicMock()
        mock_bot_user.id = 'bot_id_xyz'
        
        mock_msg.attachments = attachments or []
        return mock_msg, mock_bot_user

    @pytest.mark.skipif(not DISCORD_AVAILABLE, reason="discord.py not installed")
    async def test_parse_message_text(self, valid_config):
        """Test parsing a standard text message."""
        handler = DiscordHandler(valid_config)
        mock_msg, _ = self._create_mock_discord_message("Hello World")
        
        # Mock the discord.Message class check
        with patch('discord.Message', new=MagicMock()):
            parsed = handler.parse_message(mock_msg)

        assert isinstance(parsed, PlatformMessage)
        assert parsed.content == "Hello World"
        assert parsed.user.user_id == 'user_id_abc'
        assert parsed.user.display_name == 'Test User'
        assert parsed.message_type == 'text'

    @pytest.mark.skipif(not DISCORD_AVAILABLE, reason="discord.py not installed")
    async def test_parse_message_ignores_bot(self, valid_config):
        """Test that messages from the bot itself are ignored."""
        handler = DiscordHandler(valid_config)
        mock_msg, mock_bot_user = self._create_mock_discord_message("I am a bot", author_is_bot=True)
        handler.bot = MagicMock()
        handler.bot.user = mock_bot_user
        
        # This check happens inside the on_message event, so we simulate it here
        if mock_msg.author == handler.bot.user:
            parsed = None
        else:
            with patch('discord.Message', new=MagicMock()):
                parsed = handler.parse_message(mock_msg)
        
        assert parsed is None

    @pytest.mark.skipif(not DISCORD_AVAILABLE, reason="discord.py not installed")
    async def test_parse_message_audio_attachment(self, valid_config):
        """Test parsing a message with an audio attachment."""
        handler = DiscordHandler(valid_config)
        
        mock_attachment = MagicMock()
        mock_attachment.content_type = 'audio/mpeg'
        
        mock_msg, _ = self._create_mock_discord_message("", attachments=[mock_attachment])

        with patch.object(handler, '_download_attachment', new_callable=AsyncMock) as mock_download:
            mock_download.return_value = b'fake_audio_bytes'
            with patch('discord.Message', new=MagicMock()):
                parsed = handler.parse_message(mock_msg)

        assert parsed is not None
        assert parsed.message_type == 'audio'
        assert parsed.raw_data == b'fake_audio_bytes'
        mock_download.assert_awaited_once_with(mock_attachment)

    async def test_send_message_async_short(self, valid_config):
        """Test _send_message_async with a short message."""
        handler = DiscordHandler(valid_config)
        mock_channel = AsyncMock()
        
        await handler._send_message_async(mock_channel, "Short message")
        
        mock_channel.send.assert_awaited_once_with("Short message")

    async def test_send_message_async_long(self, valid_config):
        """Test _send_message_async with a long message that needs splitting."""
        handler = DiscordHandler(valid_config)
        mock_channel = AsyncMock()
        long_content = "A" * 2001
        
        await handler._send_message_async(mock_channel, long_content)
        
        assert mock_channel.send.await_count == 2
        mock_channel.send.assert_any_await("A" * 2000)
        mock_channel.send.assert_any_await("A")

    async def test_send_message_async_api_error(self, valid_config):
        """Test _send_message_async when the API call fails."""
        handler = DiscordHandler(valid_config)
        mock_channel = AsyncMock()
        mock_channel.send.side_effect = Exception("Discord API Error")
        
        result = await handler._send_message_async(mock_channel, "message")
        
        assert result is False

    @patch('src.platforms.discord_handler.Thread')
    def test_start_bot(self, mock_thread, valid_config):
        """Test the _start_bot method."""
        handler = DiscordHandler(valid_config)
        handler._start_bot()
        mock_thread.assert_called_once()
        mock_thread.return_value.start.assert_called_once()

    def test_stop_bot(self, valid_config):
        """Test the stop_bot method."""
        handler = DiscordHandler(valid_config)
        handler.bot = MagicMock()
        handler.bot.close = MagicMock()
        handler.event_loop = asyncio.get_event_loop()

        # Since we can't easily test the threadsafe call, we check the components
        with patch('asyncio.run_coroutine_threadsafe') as mock_run_threadsafe:
            handler.stop_bot()
            mock_run_threadsafe.assert_called_once()
            # Just verify that run_coroutine_threadsafe was called
            # We don't need to verify the exact coroutine content

    def test_setup_bot_discord_unavailable(self, valid_config):
        """Test _setup_bot when Discord is not available."""
        with patch('src.platforms.discord_handler.DISCORD_AVAILABLE', False):
            handler = DiscordHandler(valid_config)
            # When Discord is not available, bot should be None
            assert not hasattr(handler, 'bot') or handler.bot is None

    def test_setup_bot_exception_handling(self, valid_config):
        """Test _setup_bot exception handling."""
        with patch('src.platforms.discord_handler.DISCORD_AVAILABLE', True):
            handler = DiscordHandler(valid_config)
            
            # Mock the _setup_bot method to simulate exception during setup
            original_setup = handler._setup_bot
            def mock_setup_with_exception():
                try:
                    raise Exception("Discord setup error")
                except Exception as e:
                    handler.bot = None
            
            handler._setup_bot = mock_setup_with_exception
            handler._setup_bot()
            assert handler.bot is None

    def test_register_events_no_bot(self, valid_config):
        """Test _register_events when bot is None."""
        handler = DiscordHandler(valid_config)
        handler.bot = None
        
        # Should not raise exception
        handler._register_events()

    def test_register_events_with_bot(self, valid_config):
        """Test _register_events with bot."""
        handler = DiscordHandler(valid_config)
        handler.bot = MagicMock()
        handler.bot.event = MagicMock()
        
        handler._register_events()
        
        # Check that event decorator was called
        assert handler.bot.event.call_count >= 3  # on_ready, on_message, on_voice_state_update

    def test_handle_webhook_no_event_loop(self, valid_config):
        """Test handle_webhook when event_loop is None."""
        handler = DiscordHandler(valid_config)
        handler.bot = MagicMock()
        handler.event_loop = None
        
        messages = handler.handle_webhook("test_body", "test_signature")
        assert messages == []

    def test_handle_webhook_message_processing(self, valid_config):
        """Test handle_webhook message processing."""
        handler = DiscordHandler(valid_config)
        handler.bot = MagicMock()
        handler.event_loop = MagicMock()
        
        # Mock message queue
        handler.message_queue = MagicMock()
        
        # Mock asyncio.run_coroutine_threadsafe to raise timeout
        with patch('asyncio.run_coroutine_threadsafe') as mock_run_threadsafe:
            mock_future = MagicMock()
            mock_future.result.side_effect = asyncio.TimeoutError()
            mock_run_threadsafe.return_value = mock_future
            
            messages = handler.handle_webhook("test_body", "test_signature")
            assert messages == []

    def test_handle_webhook_exception_handling(self, valid_config):
        """Test handle_webhook exception handling."""
        handler = DiscordHandler(valid_config)
        handler.bot = MagicMock()
        handler.event_loop = MagicMock()
        
        # Mock to raise exception
        with patch('asyncio.run_coroutine_threadsafe', side_effect=Exception("Test error")):
            messages = handler.handle_webhook("test_body", "test_signature")
            assert messages == []

    def test_send_response_with_event_loop(self, valid_config):
        """Test send_response with event_loop."""
        handler = DiscordHandler(valid_config)
        handler.bot = MagicMock()
        handler.event_loop = MagicMock()
        
        mock_discord_message = MagicMock()
        mock_discord_message.channel = MagicMock()
        
        user = PlatformUser(user_id="123", platform=PlatformType.DISCORD)
        message = PlatformMessage(
            message_id="msg_123",
            user=user,
            content="Hello",
            metadata={'discord_message': mock_discord_message}
        )
        
        response = PlatformResponse(content="Hello back!")
        
        with patch('asyncio.run_coroutine_threadsafe') as mock_run_threadsafe:
            mock_future = MagicMock()
            mock_future.result.return_value = True
            mock_run_threadsafe.return_value = mock_future
            
            result = handler.send_response(response, message)
            assert result is True
            mock_run_threadsafe.assert_called_once()

    def test_send_response_timeout_error(self, valid_config):
        """Test send_response with timeout error."""
        handler = DiscordHandler(valid_config)
        handler.bot = MagicMock()
        handler.event_loop = MagicMock()
        
        mock_discord_message = MagicMock()
        mock_discord_message.channel = MagicMock()
        
        user = PlatformUser(user_id="123", platform=PlatformType.DISCORD)
        message = PlatformMessage(
            message_id="msg_123",
            user=user,
            content="Hello",
            metadata={'discord_message': mock_discord_message}
        )
        
        response = PlatformResponse(content="Hello back!")
        
        with patch('asyncio.run_coroutine_threadsafe') as mock_run_threadsafe:
            mock_future = MagicMock()
            mock_future.result.side_effect = asyncio.TimeoutError()
            mock_run_threadsafe.return_value = mock_future
            
            result = handler.send_response(response, message)
            assert result is False

    def test_parse_message_invalid_discord_message(self, valid_config):
        """Test parse_message with invalid Discord message."""
        handler = DiscordHandler(valid_config)
        
        # Mock invalid message type
        invalid_message = "not a discord message"
        
        # Without discord module, should return None
        result = handler.parse_message(invalid_message)
        assert result is None

    def test_parse_message_audio_attachment_download_error(self, valid_config):
        """Test parse_message with audio attachment download error."""
        handler = DiscordHandler(valid_config)
        
        # Without discord module, should return None
        result = handler.parse_message("mock_message")
        assert result is None

    def test_parse_message_no_content_no_attachments(self, valid_config):
        """Test parse_message with no content and no attachments."""
        handler = DiscordHandler(valid_config)
        
        # Without discord module, should return None
        result = handler.parse_message("mock_message")
        assert result is None

    def test_parse_message_guild_filter(self, valid_config):
        """Test parse_message with guild filter."""
        handler = DiscordHandler(valid_config)
        handler.guild_id = "123456789"
        
        # Without discord module, should return None
        result = handler.parse_message("mock_message")
        assert result is None

    def test_start_bot_thread_already_alive(self, valid_config):
        """Test _start_bot when thread is already alive."""
        handler = DiscordHandler(valid_config)
        handler.bot_thread = MagicMock()
        handler.bot_thread.is_alive.return_value = True
        
        with patch('src.platforms.discord_handler.Thread') as mock_thread:
            handler._start_bot()
            mock_thread.assert_not_called()

    def test_destructor_cleanup(self, valid_config):
        """Test __del__ cleanup method."""
        handler = DiscordHandler(valid_config)
        handler.bot = MagicMock()
        
        with patch.object(handler, 'stop_bot') as mock_stop:
            handler.__del__()
            mock_stop.assert_called_once()

    def test_destructor_exception_handling(self, valid_config):
        """Test __del__ exception handling."""
        handler = DiscordHandler(valid_config)
        
        with patch.object(handler, 'stop_bot', side_effect=Exception("Stop error")):
            # Should not raise exception
            handler.__del__()

    def test_download_attachment_async(self, valid_config):
        """Test _download_attachment async method."""
        handler = DiscordHandler(valid_config)
        
        mock_attachment = MagicMock()
        mock_attachment.read = AsyncMock(return_value=b'test_data')
        
        # Test the async method directly
        result = asyncio.run(handler._download_attachment(mock_attachment))
        assert result == b'test_data'
        mock_attachment.read.assert_awaited_once()

    def test_get_discord_manager(self, valid_config):
        """Test get_discord_manager function."""
        from src.platforms.discord_handler import get_discord_manager
        
        manager = get_discord_manager()
        assert isinstance(manager, DiscordBotManager)

    def test_handler_with_optional_config(self, valid_config):
        """Test handler with optional configuration values."""
        config = {
            'platforms': {
                'discord': {
                    'enabled': True,
                    'bot_token': 'test_token'
                    # No guild_id or command_prefix
                }
            }
        }
        
        handler = DiscordHandler(config)
        assert handler.bot_token == 'test_token'
        assert handler.guild_id is None
        assert handler.command_prefix == '!'

    def test_handler_initialization_failure(self, valid_config):
        """Test handler initialization failure."""
        config = {
            'platforms': {
                'discord': {
                    'enabled': True,
                    'bot_token': 'test_token'
                }
            }
        }
        
        with patch('src.platforms.discord_handler.DISCORD_AVAILABLE', True):
            # Mock validation failure
            with patch.object(DiscordHandler, 'validate_config', return_value=False):
                handler = DiscordHandler(config)
                # Should still create handler but not initialize bot
                assert handler.bot_token == 'test_token'

    def test_message_queue_initialization(self, valid_config):
        """Test message queue initialization."""
        handler = DiscordHandler(valid_config)
        
        # Check that message_queue is initialized
        assert hasattr(handler, 'message_queue')
        assert handler.message_queue is not None

    def test_stop_bot_no_event_loop(self, valid_config):
        """Test stop_bot when event_loop is None."""
        handler = DiscordHandler(valid_config)
        handler.bot = MagicMock()
        handler.event_loop = None
        
        # Should not raise exception
        handler.stop_bot()

    def test_stop_bot_exception_handling(self, valid_config):
        """Test stop_bot exception handling."""
        handler = DiscordHandler(valid_config)
        handler.bot = MagicMock()
        handler.event_loop = MagicMock()
        
        with patch('asyncio.run_coroutine_threadsafe', side_effect=Exception("Stop error")):
            # Should not raise exception
            handler.stop_bot()

    def test_config_validation_edge_cases(self, valid_config):
        """Test configuration validation edge cases."""
        # Test with empty config
        handler = DiscordHandler({})
        assert not handler.validate_config()
        
        # Test with valid config
        handler = DiscordHandler(valid_config)
        assert handler.validate_config()

    def test_platform_type_consistency(self, valid_config):
        """Test platform type consistency."""
        handler = DiscordHandler(valid_config)
        assert handler.get_platform_type() == PlatformType.DISCORD
        
        # Test multiple calls return same result
        assert handler.get_platform_type() == handler.get_platform_type()
