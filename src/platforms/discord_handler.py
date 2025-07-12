"""
Discord 平台處理器
使用 discord.py 2024 最新版本，支援 async/await 和最新的 Discord API
"""
import asyncio
from threading import Thread
from typing import List, Optional, Any, Dict
from ..core.logger import get_logger

try:
    import discord
    from discord.ext import commands
    DISCORD_AVAILABLE = True
except ImportError:
    discord = None
    commands = None
    DISCORD_AVAILABLE = False

from .base import BasePlatformHandler, PlatformType, PlatformUser, PlatformMessage, PlatformResponse

logger = get_logger(__name__)


class DiscordHandler(BasePlatformHandler):
    """
    Discord 平台處理器
    使用 discord.py 的最新 async/await 架構
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        if not DISCORD_AVAILABLE:
            logger.error("Discord.py not installed. Install with: pip install discord.py")
            return
            
        self.bot_token = self.get_config('bot_token')
        self.guild_id = self.get_config('guild_id')
        self.command_prefix = self.get_config('command_prefix', '!')
        
        self.message_queue = asyncio.Queue()
        self.bot = None
        self.event_loop = None
        self.bot_thread = None
        
        if self.is_enabled() and self.validate_config():
            self._setup_bot()
            logger.info("Discord handler initialized")
        elif self.is_enabled():
            logger.error("Discord handler initialization failed due to invalid config")
    
    def get_platform_type(self) -> PlatformType:
        return PlatformType.DISCORD
    
    def get_required_config_fields(self) -> List[str]:
        return ['bot_token']
    
    def _setup_bot(self):
        """設置 Discord bot"""
        if not DISCORD_AVAILABLE or discord is None:
            return
        try:
            intents = discord.Intents.default()
            intents.message_content = True
            intents.voice_states = True
            self.bot = commands.Bot(command_prefix=self.command_prefix, intents=intents, help_command=None)
            self._register_events()
            logger.info("Discord bot setup completed")
        except Exception as e:
            logger.error(f"Error setting up Discord bot: {e}")
            self.bot = None
    
    def _register_events(self):
        """註冊 Discord 事件處理器"""
        if not self.bot:
            return

        @self.bot.event
        async def on_ready():
            logger.info(f"Discord bot logged in as {self.bot.user}")

        @self.bot.event
        async def on_message(message):
            if message.author == self.bot.user:
                return
            if self.guild_id and str(message.guild.id) != str(self.guild_id):
                return
            await self.message_queue.put(message)
            await self.bot.process_commands(message)

    def parse_message(self, discord_message: Any) -> Optional[PlatformMessage]:
        """解析 Discord 訊息為統一格式"""
        if not DISCORD_AVAILABLE or discord is None:
            return None
        
        if not isinstance(discord_message, discord.Message):
            return None

        user = PlatformUser(
            user_id=str(discord_message.author.id),
            platform=PlatformType.DISCORD,
            display_name=discord_message.author.display_name,
            username=discord_message.author.name,
            metadata={
                'guild_id': str(discord_message.guild.id) if discord_message.guild else None,
                'channel_id': str(discord_message.channel.id)
            }
        )

        content = discord_message.content
        message_type = "text"
        raw_data = None

        if discord_message.attachments:
            for attachment in discord_message.attachments:
                if attachment.content_type and attachment.content_type.startswith('audio/'):
                    message_type = "audio"
                    try:
                        audio_content = asyncio.run(attachment.read())
                        content = "[Audio Message]"
                        raw_data = audio_content
                        logger.debug(f"[DISCORD] Audio message from {user.user_id}, size: {len(audio_content)} bytes")
                    except Exception as e:
                        logger.error(f"Error downloading Discord audio: {e}")
                        content = "[Audio Message - Download Failed]"
                        raw_data = None
                    break

        return PlatformMessage(
            message_id=str(discord_message.id),
            user=user,
            content=content,
            message_type=message_type,
            raw_data=raw_data,
            metadata={
                'discord_message': discord_message,
                'channel_id': str(discord_message.channel.id)
            }
        )

    def send_response(self, response: PlatformResponse, message: PlatformMessage) -> bool:
        """發送回應到 Discord"""
        if not self.bot or not self.event_loop:
            logger.error("Discord bot not initialized or event loop not available")
            return False
            
        discord_message = message.metadata.get('discord_message')
        if not discord_message:
            logger.error("No Discord message in metadata")
            return False

        future = asyncio.run_coroutine_threadsafe(
            self._send_message_async(discord_message.channel, response.content),
            self.event_loop
        )
        try:
            return future.result(timeout=30)
        except Exception as e:
            logger.error(f"Error sending Discord response: {e}")
            return False
    
    async def _send_message_async(self, channel, content: str) -> bool:
        """異步發送訊息到 Discord"""
        try:
            chunks = [content[i:i+2000] for i in range(0, len(content), 2000)]
            for chunk in chunks:
                await channel.send(chunk)
            logger.debug(f"Sent Discord message to channel {channel.id}")
            return True
        except Exception as e:
            logger.error(f"Error in _send_message_async: {e}")
            return False
    
    def handle_webhook(self, request_body: str, headers: Dict[str, str]) -> List[PlatformMessage]:
        """
        從訊息佇列中取得訊息 (WebSocket 模式)
        """
        if not self.bot:
            logger.error("Discord bot not initialized")
            return []
        
        if not self.bot_thread or not self.bot_thread.is_alive():
            self._start_bot()
        
        messages = []
        try:
            while not self.message_queue.empty():
                discord_message = self.message_queue.get_nowait()
                parsed_message = self.parse_message(discord_message)
                if parsed_message:
                    messages.append(parsed_message)
        except asyncio.QueueEmpty:
            pass
        except Exception as e:
            logger.error(f"Error getting messages from Discord queue: {e}")
        
        return messages
    
    def _start_bot(self):
        """在新線程中啟動 Discord bot"""
        if self.bot_thread and self.bot_thread.is_alive():
            return
        
        def run_bot():
            try:
                self.event_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.event_loop)
                self.event_loop.run_until_complete(self.bot.start(self.bot_token))
            except Exception as e:
                logger.error(f"Error running Discord bot: {e}")
            finally:
                if self.event_loop:
                    self.event_loop.close()
        
        self.bot_thread = Thread(target=run_bot, daemon=True)
        self.bot_thread.start()
        logger.info("Discord bot thread started")
    
    def stop_bot(self):
        """停止 Discord bot"""
        if self.bot and self.event_loop:
            asyncio.run_coroutine_threadsafe(self.bot.close(), self.event_loop).result(timeout=10)
            logger.info("Discord bot stopped")
    
    def __del__(self):
        try:
            self.stop_bot()
        except Exception:
            pass