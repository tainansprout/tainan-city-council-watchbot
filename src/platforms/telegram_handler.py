
"""
Telegram 平台處理器
使用 python-telegram-bot v22.2 最新版本，支援 async/await 和完整的 Telegram Bot API

📋 架構職責分工：
✅ RESPONSIBILITIES (平台層職責):
  - 解析 Telegram webhook updates
  - 透過 Bot API 下載語音/音訊檔案
  - 使用 Bot API 發送訊息
  - 處理 Telegram 特有的訊息類型

❌ NEVER DO (絕對禁止):
  - 呼叫 AI 模型 API (音訊轉錄、文字生成)
  - 處理對話邏輯或歷史記錄
  - 知道或依賴特定的 AI 模型類型
  - 直接調用 AudioService 或 ChatService

🔄 資料流向：
  Telegram Webhook → parse_message() → PlatformMessage → app.py
  app.py → send_response() → Telegram Bot API

🎯 平台特色：
  - 支援群組和私人聊天
  - 語音訊息 (.ogg) 和音訊檔案分別處理
  - 使用 chat_id 進行訊息路由
  - 不需要 webhook 簽名驗證 (通過 bot token 安全性)
  - 異步下載媒體檔案
"""
import json
import asyncio
from typing import List, Optional, Any, Dict
from ..core.logger import get_logger

try:
    from telegram import Update, Bot
    from telegram.ext import Application, MessageHandler, filters
    TELEGRAM_AVAILABLE = True
except ImportError:
    Update = None
    Bot = None
    Application = None
    MessageHandler = None
    filters = None
    TELEGRAM_AVAILABLE = False

from .base import BasePlatformHandler, PlatformType, PlatformUser, PlatformMessage, PlatformResponse

logger = get_logger(__name__)


class TelegramHandler(BasePlatformHandler):
    """
    Telegram 平台處理器
    使用 python-telegram-bot 的最新 async/await 架構
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        if not TELEGRAM_AVAILABLE:
            logger.error("python-telegram-bot not installed. Install with: pip install python-telegram-bot")
            return
            
        self.bot_token = self.get_config('bot_token')
        self.webhook_secret = self.get_config('webhook_secret', '')
        
        self.bot = None
        self.application = None
        
        if self.is_enabled() and self.validate_config():
            self._setup_bot()
            logger.info("Telegram handler initialized")
        elif self.is_enabled():
            logger.error("Telegram handler initialization failed due to invalid config")
    
    def get_platform_type(self) -> PlatformType:
        return PlatformType.TELEGRAM
    
    def get_required_config_fields(self) -> List[str]:
        return ['bot_token']
    
    def _setup_bot(self):
        """設置 Telegram bot"""
        try:
            self.bot = Bot(token=self.bot_token)
            
            builder = Application.builder().token(self.bot_token)
            # python-telegram-bot v21+ 透過此參數自動處理簽名驗證
            if self.webhook_secret:
                builder.secret_token(self.webhook_secret)

            self.application = builder.build()
            logger.info("Telegram bot setup completed")
            
        except Exception as e:
            logger.error(f"Error setting up Telegram bot: {e}")
            self.bot = None
            self.application = None
    
    def parse_message(self, telegram_update: Any) -> Optional[PlatformMessage]:
        """解析 Telegram Update 為統一格式"""
        if not TELEGRAM_AVAILABLE or Update is None:
            return None
        
        if not isinstance(telegram_update, Update) or not telegram_update.message:
            return None
        
        message = telegram_update.message
        
        user = PlatformUser(
            user_id=str(message.from_user.id),
            platform=PlatformType.TELEGRAM,
            display_name=message.from_user.full_name,
            username=message.from_user.username,
            metadata={
                'first_name': message.from_user.first_name,
                'last_name': message.from_user.last_name,
                'language_code': message.from_user.language_code,
                'is_bot': message.from_user.is_bot,
                'chat_id': str(message.chat.id),
                'chat_type': message.chat.type
            }
        )
        
        content = ""
        message_type = "text"
        raw_data = None
        
        # 處理文字訊息
        if message.text:
            content = message.text
        
        # 處理語音或音訊訊息
        elif message.voice or message.audio:
            message_type = "audio"
            audio_source = message.voice or message.audio
            try:
                audio_content = asyncio.run(self._download_audio(audio_source))
                content = "[Audio Message]"
                raw_data = audio_content
                logger.debug(f"[TELEGRAM] Audio message from {user.user_id}, size: {len(audio_content)} bytes")
            except Exception as e:
                logger.error(f"Error downloading Telegram audio: {e}")
                content = "[Audio Message - Download Failed]"
                raw_data = None
        else:
            return None # 不處理其他類型的訊息

        return PlatformMessage(
            message_id=str(message.message_id),
            user=user,
            content=content,
            message_type=message_type,
            raw_data=raw_data,
            metadata={
                'telegram_message': message,
                'chat_id': str(message.chat.id),
                'message_thread_id': message.message_thread_id,
                'date': message.date
            }
        )
    
    async def _download_audio(self, audio_source) -> bytes:
        """下載 Telegram 語音或音訊檔案"""
        file = await self.bot.get_file(audio_source.file_id)
        byte_array = await file.download_as_bytearray()
        return bytes(byte_array)
    
    def send_response(self, response: PlatformResponse, message: PlatformMessage) -> bool:
        """發送回應到 Telegram"""
        if not self.bot:
            logger.error("Telegram bot not initialized")
            return False
        
        chat_id = message.metadata.get('chat_id')
        if not chat_id:
            logger.error("No chat_id in message metadata")
            return False
            
        try:
            asyncio.run(self._send_message_async(chat_id, response.content, message))
            return True
        except Exception as e:
            logger.error(f"Error sending Telegram response: {e}")
            return False
    
    async def _send_message_async(self, chat_id: str, content: str, original_message: PlatformMessage):
        """異步發送訊息到 Telegram"""
        try:
            # Telegram 訊息長度限制為 4096 字符
            chunks = [content[i:i+4096] for i in range(0, len(content), 4096)]
            for chunk in chunks:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=chunk,
                    reply_to_message_id=int(original_message.message_id),
                    parse_mode='Markdown'
                )
            logger.debug(f"Sent Telegram message to chat {chat_id}")
        except Exception as e:
            logger.error(f"Error in _send_message_async: {e}")
            raise

    def handle_webhook(self, request_body: str, headers: Dict[str, str]) -> List[PlatformMessage]:
        """
        處理 Telegram webhook。
        python-telegram-bot 的 Application 會自動處理簽名驗證。
        """
        if not self.application:
            logger.error("Telegram application not initialized")
            return []
        
        try:
            webhook_data = json.loads(request_body)
            update = Update.de_json(webhook_data, self.bot)
            
            # 官方推薦的異步處理方式
            # process_update 會進行簽名驗證 (如果 secret_token 已設定)
            asyncio.run(self.application.process_update(update))
            
            # 驗證成功後，解析訊息
            message = self.parse_message(update)
            return [message] if message else []
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in Telegram webhook: {e}")
            return []
        except Exception as e:
            logger.error(f"Error processing Telegram webhook: {e}")
            return []
    
    def set_webhook(self, webhook_url: str) -> bool:
        """設定 Telegram webhook"""
        if not self.bot:
            logger.error("Telegram bot not initialized")
            return False
        
        try:
            result = asyncio.run(self._set_webhook_async(webhook_url))
            return result
        except Exception as e:
            logger.error(f"Error setting Telegram webhook: {e}")
            return False
    
    async def _set_webhook_async(self, webhook_url: str) -> bool:
        """異步設定 webhook"""
        try:
            kwargs = {'url': webhook_url}
            
            # 如果有設定密鑰，加入 webhook 設定
            if self.webhook_secret:
                kwargs['secret_token'] = self.webhook_secret
            
            await self.bot.set_webhook(**kwargs)
            logger.info(f"Telegram webhook set to: {webhook_url}")
            return True
            
        except Exception as e:
            logger.error(f"Error in _set_webhook_async: {e}")
            return False
    
    def delete_webhook(self) -> bool:
        """刪除 Telegram webhook"""
        if not self.bot:
            logger.error("Telegram bot not initialized")
            return False
        
        try:
            result = asyncio.run(self.bot.delete_webhook())
            logger.info("Telegram webhook deleted")
            return True
        except Exception as e:
            logger.error(f"Error deleting Telegram webhook: {e}")
            return False
    
    def get_bot_info(self) -> Optional[Dict[str, Any]]:
        """取得 bot 資訊"""
        if not self.bot:
            return None
        
        try:
            bot_info = asyncio.run(self.bot.get_me())
            return {
                'id': bot_info.id,
                'username': bot_info.username,
                'first_name': bot_info.first_name,
                'can_join_groups': bot_info.can_join_groups,
                'can_read_all_group_messages': bot_info.can_read_all_group_messages,
                'supports_inline_queries': bot_info.supports_inline_queries
            }
        except Exception as e:
            logger.error(f"Error getting Telegram bot info: {e}")
            return None


# Telegram 特定的工具函數
class TelegramUtils:
    """Telegram 相關的工具函數"""
    
    @staticmethod
    def escape_markdown(text: str) -> str:
        """轉義 Markdown 特殊字符"""
        escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in escape_chars:
            text = text.replace(char, f'\\{char}')
        return text
    
    @staticmethod
    def format_user_mention(user_id: str, name: str) -> str:
        """格式化用戶提及"""
        return f"[{name}](tg://user?id={user_id})"
    
    @staticmethod
    def create_inline_keyboard(buttons: List[List[Dict[str, str]]]) -> str:
        """創建內聯鍵盤的 JSON 格式（用於自定義鍵盤）"""
        return json.dumps({'inline_keyboard': buttons})


def get_telegram_utils():
    """取得 Telegram 工具函數"""
    return TelegramUtils
