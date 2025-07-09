"""
Telegram 平台處理器
使用 python-telegram-bot v22.2 最新版本，支援 async/await 和完整的 Telegram Bot API
"""
import json
import asyncio
import hmac
import hashlib
from typing import List, Optional, Any, Dict
from urllib.parse import unquote
from ..core.logger import get_logger

try:
    from telegram import Update, Bot, Message, Voice, Audio, Document
    from telegram.ext import Application, MessageHandler, filters, ContextTypes
    TELEGRAM_AVAILABLE = True
except ImportError:
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
        self.webhook_secret = self.get_config('webhook_secret', '')  # 可選的 webhook 驗證密鑰
        
        # 初始化 bot 和 application
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
            # 創建 bot 實例
            self.bot = Bot(token=self.bot_token)
            
            # 創建 application（v20+ 的新架構）
            self.application = Application.builder().token(self.bot_token).build()
            
            # 註冊訊息處理器
            self._register_handlers()
            
            logger.info("Telegram bot setup completed")
            
        except Exception as e:
            logger.error(f"Error setting up Telegram bot: {e}")
            self.bot = None
            self.application = None
    
    def _register_handlers(self):
        """註冊 Telegram 訊息處理器"""
        if not self.application:
            return
        
        # 處理所有文字訊息
        text_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text_message)
        self.application.add_handler(text_handler)
        
        # 處理語音訊息
        voice_handler = MessageHandler(filters.VOICE, self._handle_voice_message)
        self.application.add_handler(voice_handler)
        
        # 處理音訊檔案
        audio_handler = MessageHandler(filters.AUDIO, self._handle_audio_message)
        self.application.add_handler(audio_handler)
        
        logger.debug("Telegram message handlers registered")
    
    async def _handle_text_message(self, update, context):
        """處理文字訊息（內部使用）"""
        # 這個方法會被 webhook 處理流程調用
        pass
    
    async def _handle_voice_message(self, update, context):
        """處理語音訊息（內部使用）"""
        # 這個方法會被 webhook 處理流程調用
        pass
    
    async def _handle_audio_message(self, update, context):
        """處理音訊訊息（內部使用）"""
        # 這個方法會被 webhook 處理流程調用
        pass
    
    def parse_message(self, telegram_update: Any) -> Optional[PlatformMessage]:
        """解析 Telegram Update 為統一格式"""
        if not TELEGRAM_AVAILABLE:
            return None
            
        # 檢查是否有 Update 類別可用
        try:
            from telegram import Update
            if not isinstance(telegram_update, Update) or not telegram_update.message:
                return None
        except ImportError:
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
        
        # 處理文字訊息
        if message.text:
            return PlatformMessage(
                message_id=str(message.message_id),
                user=user,
                content=message.text,
                message_type="text",
                metadata={
                    'telegram_message': message,
                    'chat_id': str(message.chat.id),
                    'message_thread_id': message.message_thread_id,
                    'date': message.date
                }
            )
        
        # 處理語音訊息
        if message.voice:
            try:
                audio_content = asyncio.run(self._download_voice_message(message.voice))
                
                return PlatformMessage(
                    message_id=str(message.message_id),
                    user=user,
                    content="[Voice Message]",
                    message_type="audio",
                    raw_data=audio_content,
                    metadata={
                        'telegram_message': message,
                        'voice_duration': message.voice.duration,
                        'voice_file_size': message.voice.file_size,
                        'chat_id': str(message.chat.id)
                    }
                )
            except Exception as e:
                logger.error(f"Error downloading Telegram voice message: {e}")
        
        # 處理音訊檔案
        if message.audio:
            try:
                audio_content = asyncio.run(self._download_audio_file(message.audio))
                
                return PlatformMessage(
                    message_id=str(message.message_id),
                    user=user,
                    content="[Audio File]",
                    message_type="audio",
                    raw_data=audio_content,
                    metadata={
                        'telegram_message': message,
                        'audio_duration': message.audio.duration,
                        'audio_title': message.audio.title,
                        'audio_performer': message.audio.performer,
                        'chat_id': str(message.chat.id)
                    }
                )
            except Exception as e:
                logger.error(f"Error downloading Telegram audio file: {e}")
        
        return None
    
    async def _download_voice_message(self, voice) -> bytes:
        """下載 Telegram 語音訊息"""
        file = await self.bot.get_file(voice.file_id)
        return await file.download_as_bytearray()
    
    async def _download_audio_file(self, audio) -> bytes:
        """下載 Telegram 音訊檔案"""
        file = await self.bot.get_file(audio.file_id)
        return await file.download_as_bytearray()
    
    def send_response(self, response: PlatformResponse, message: PlatformMessage) -> bool:
        """發送回應到 Telegram"""
        if not self.bot:
            logger.error("Telegram bot not initialized")
            return False
        
        try:
            chat_id = message.metadata.get('chat_id')
            if not chat_id:
                logger.error("No chat_id in message metadata")
                return False
            
            # 使用 asyncio 發送訊息
            result = asyncio.run(self._send_message_async(chat_id, response.content, message))
            return result
            
        except Exception as e:
            logger.error(f"Error sending Telegram response: {e}")
            return False
    
    async def _send_message_async(self, chat_id: str, content: str, original_message: PlatformMessage) -> bool:
        """異步發送訊息到 Telegram"""
        try:
            # Telegram 訊息長度限制為 4096 字符
            if len(content) > 4096:
                # 分割長訊息
                chunks = [content[i:i+4096] for i in range(0, len(content), 4096)]
                for chunk in chunks:
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=chunk,
                        parse_mode='Markdown'  # 支援 Markdown 格式
                    )
            else:
                # 回覆原始訊息（如果有 message_id）
                reply_to_message_id = None
                if original_message.metadata.get('telegram_message'):
                    reply_to_message_id = int(original_message.message_id)
                
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=content,
                    reply_to_message_id=reply_to_message_id,
                    parse_mode='Markdown'
                )
            
            logger.debug(f"Sent Telegram message to chat {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error in _send_message_async: {e}")
            return False
    
    def handle_webhook(self, request_body: str, signature: str) -> List[PlatformMessage]:
        """處理 Telegram webhook"""
        if not self.bot or not self.application:
            logger.error("Telegram bot not initialized")
            return []
        
        messages = []
        
        try:
            # 驗證 webhook（如果設定了密鑰）
            if self.webhook_secret and not self._verify_webhook_signature(request_body, signature):
                logger.warning("Invalid Telegram webhook signature")
                return []
            
            # 解析 webhook 資料
            try:
                webhook_data = json.loads(request_body)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in Telegram webhook: {e}")
                return []
            
            # 創建 Update 物件
            update = Update.de_json(webhook_data, self.bot)
            if not update:
                logger.warning("Failed to parse Telegram update")
                return []
            
            # 解析訊息
            parsed_message = self.parse_message(update)
            if parsed_message:
                messages.append(parsed_message)
                
                # 使用 application 處理更新（觸發已註冊的處理器）
                asyncio.run(self.application.process_update(update))
            
        except Exception as e:
            logger.error(f"Error processing Telegram webhook: {e}")
        
        return messages
    
    def _verify_webhook_signature(self, request_body: str, signature: str) -> bool:
        """驗證 Telegram webhook 簽名"""
        if not self.webhook_secret:
            return True  # 如果沒有設定密鑰，跳過驗證
        
        try:
            # Telegram webhook 驗證
            # 格式: X-Telegram-Bot-Api-Secret-Token
            return signature == self.webhook_secret
        except Exception as e:
            logger.error(f"Error verifying Telegram webhook signature: {e}")
            return False
    
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