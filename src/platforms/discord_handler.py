"""
Discord 平台處理器
使用 discord.py 2024 最新版本，支援 async/await 和最新的 Discord API
"""
import json
import asyncio
from threading import Thread
from typing import List, Optional, Any, Dict
from ..core.logger import get_logger

try:
    import discord
    from discord.ext import commands
    DISCORD_AVAILABLE = True
except ImportError:
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
        self.guild_id = self.get_config('guild_id')  # 可選，限制特定伺服器
        self.command_prefix = self.get_config('command_prefix', '!')
        
        # 訊息佇列，用於在 webhook 模式下處理訊息
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
        if not DISCORD_AVAILABLE:
            return
            
        try:
            # 設置必要的 intents（2024 年 Discord 要求）
            intents = discord.Intents.default()
            intents.message_content = True  # 必須啟用以讀取訊息內容
            intents.voice_states = True     # 語音功能
            
            # 創建 bot 實例
            self.bot = commands.Bot(
                command_prefix=self.command_prefix,
                intents=intents,
                help_command=None  # 禁用默認 help 命令
            )
            
            # 註冊事件處理器
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
            logger.info(f"Bot is in {len(self.bot.guilds)} guilds")
        
        @self.bot.event
        async def on_message(message):
            # 忽略 bot 自己的訊息
            if message.author == self.bot.user:
                return
            
            # 如果設定了特定 guild，只處理該 guild 的訊息
            if self.guild_id and str(message.guild.id) != str(self.guild_id):
                return
            
            # 將訊息加入佇列
            await self.message_queue.put(message)
            
            # 處理命令
            await self.bot.process_commands(message)
        
        @self.bot.event
        async def on_voice_state_update(member, before, after):
            """處理語音狀態更新（未來可擴展語音功能）"""
            logger.debug(f"Voice state update: {member.name}")
    
    def parse_message(self, discord_message: Any) -> Optional[PlatformMessage]:
        """解析 Discord 訊息為統一格式"""
        if not DISCORD_AVAILABLE:
            return None
            
        # 檢查是否有 Discord Message 類別可用
        try:
            import discord
            if not isinstance(discord_message, discord.Message):
                return None
        except ImportError:
            return None
        
        user = PlatformUser(
            user_id=str(discord_message.author.id),
            platform=PlatformType.DISCORD,
            display_name=discord_message.author.display_name,
            username=discord_message.author.name,
            metadata={
                'discriminator': discord_message.author.discriminator,
                'avatar_url': str(discord_message.author.avatar.url) if discord_message.author.avatar else None,
                'guild_id': str(discord_message.guild.id) if discord_message.guild else None,
                'channel_id': str(discord_message.channel.id)
            }
        )
        
        # 處理文字訊息
        if discord_message.content:
            return PlatformMessage(
                message_id=str(discord_message.id),
                user=user,
                content=discord_message.content,
                message_type="text",
                metadata={
                    'discord_message': discord_message,
                    'channel_id': str(discord_message.channel.id),
                    'guild_id': str(discord_message.guild.id) if discord_message.guild else None,
                    'channel_name': discord_message.channel.name if hasattr(discord_message.channel, 'name') else None
                }
            )
        
        # 處理語音訊息（Discord 不直接支援語音訊息，但可以處理語音附件）
        if discord_message.attachments:
            for attachment in discord_message.attachments:
                if attachment.content_type and attachment.content_type.startswith('audio/'):
                    try:
                        # 下載音訊內容
                        audio_content = asyncio.run(self._download_attachment(attachment))
                        
                        return PlatformMessage(
                            message_id=str(discord_message.id),
                            user=user,
                            content="[Audio Message]",
                            message_type="audio",
                            raw_data=audio_content,
                            metadata={
                                'discord_message': discord_message,
                                'attachment': attachment,
                                'channel_id': str(discord_message.channel.id),
                                'guild_id': str(discord_message.guild.id) if discord_message.guild else None
                            }
                        )
                    except Exception as e:
                        logger.error(f"Error downloading Discord audio attachment: {e}")
        
        return None
    
    async def _download_attachment(self, attachment) -> bytes:
        """下載 Discord 附件"""
        return await attachment.read()
    
    def send_response(self, response: PlatformResponse, message: PlatformMessage) -> bool:
        """發送回應到 Discord"""
        if not self.bot:
            logger.error("Discord bot not initialized")
            return False
        
        if not self.event_loop:
            logger.error("Discord event loop not available")
            return False
            
        try:
            # 從原始訊息中取得 channel
            discord_message = message.metadata.get('discord_message')
            if not discord_message:
                logger.error("No Discord message in metadata")
                return False
            
            # 使用 asyncio 發送訊息
            future = asyncio.run_coroutine_threadsafe(
                self._send_message_async(discord_message.channel, response.content),
                self.event_loop
            )
            
            # 等待結果
            result = future.result(timeout=30)
            return result
            
        except Exception as e:
            logger.error(f"Error sending Discord response: {e}")
            return False
    
    async def _send_message_async(self, channel, content: str) -> bool:
        """異步發送訊息到 Discord"""
        try:
            # Discord 訊息長度限制為 2000 字符
            if len(content) > 2000:
                # 分割長訊息
                chunks = [content[i:i+2000] for i in range(0, len(content), 2000)]
                for chunk in chunks:
                    await channel.send(chunk)
            else:
                await channel.send(content)
            
            logger.debug(f"Sent Discord message to channel {channel.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error in _send_message_async: {e}")
            return False
    
    def handle_webhook(self, request_body: str, signature: str) -> List[PlatformMessage]:
        """
        Discord 使用 WebSocket 而非 webhook，但我們實現這個方法以符合介面
        實際上會從訊息佇列中取得訊息
        """
        if not self.bot:
            logger.error("Discord bot not initialized")
            return []
        
        messages = []
        
        try:
            # 啟動 bot（如果尚未啟動）
            if not self.bot_thread or not self.bot_thread.is_alive():
                self._start_bot()
            
            # 從佇列中取得訊息（非阻塞）
            timeout = 1.0  # 1秒超時
            try:
                while True:
                    if not self.event_loop:
                        break
                    
                    future = asyncio.run_coroutine_threadsafe(
                        asyncio.wait_for(self.message_queue.get(), timeout=timeout),
                        self.event_loop
                    )
                    
                    discord_message = future.result(timeout=timeout + 1)
                    
                    parsed_message = self.parse_message(discord_message)
                    if parsed_message:
                        messages.append(parsed_message)
                        
            except asyncio.TimeoutError:
                # 超時是正常的，表示沒有新訊息
                pass
            except Exception as e:
                logger.error(f"Error getting messages from queue: {e}")
        
        except Exception as e:
            logger.error(f"Error in Discord handle_webhook: {e}")
        
        return messages
    
    def _start_bot(self):
        """在新線程中啟動 Discord bot"""
        if self.bot_thread and self.bot_thread.is_alive():
            return
        
        def run_bot():
            try:
                # 創建新的事件迴圈
                self.event_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.event_loop)
                
                # 啟動 bot
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
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self.bot.close(),
                    self.event_loop
                )
                future.result(timeout=10)
                logger.info("Discord bot stopped")
            except Exception as e:
                logger.error(f"Error stopping Discord bot: {e}")
    
    def __del__(self):
        """清理資源"""
        try:
            self.stop_bot()
        except:
            pass


# 為了支援 Discord 的特殊需求，我們還需要一個管理器
class DiscordBotManager:
    """Discord Bot 管理器，處理 bot 的生命週期"""
    
    def __init__(self):
        self.handlers = {}
    
    def register_handler(self, handler: DiscordHandler):
        """註冊 Discord 處理器"""
        self.handlers[id(handler)] = handler
    
    def unregister_handler(self, handler: DiscordHandler):
        """取消註冊 Discord 處理器"""
        handler_id = id(handler)
        if handler_id in self.handlers:
            handler.stop_bot()
            del self.handlers[handler_id]
    
    def stop_all(self):
        """停止所有 Discord bot"""
        for handler in self.handlers.values():
            handler.stop_bot()
        self.handlers.clear()


# 全域 Discord 管理器
discord_manager = DiscordBotManager()


def get_discord_manager():
    """取得全域 Discord 管理器"""
    return discord_manager