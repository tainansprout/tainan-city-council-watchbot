"""
LINE 平台處理器
使用 Strategy Pattern 實作平台特定邏輯
"""
import json
import hashlib
import hmac
import base64
import logging
from typing import List, Optional, Any, Dict
from linebot import LineBotApi
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    ReplyMessageRequest,
    TextMessage as LineTextMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    AudioMessageContent
)

from .base import (
    BasePlatformHandler,
    PlatformType,
    PlatformUser,
    PlatformMessage,
    PlatformResponse
)

logger = logging.getLogger(__name__)


class LineHandler(BasePlatformHandler):
    """
    LINE 平台處理器
    
    實作 Strategy Pattern - 將 LINE 特定的處理邏輯封裝在這個類別中
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # LINE 特定設定
        self.channel_access_token = self.get_config('channel_access_token')
        self.channel_secret = self.get_config('channel_secret')
        
        # 初始化 LINE SDK (只在配置有效且平台啟用時)
        if self.is_enabled() and self.validate_config():
            self.configuration = Configuration(access_token=self.channel_access_token)
            self.handler = WebhookHandler(self.channel_secret)
            logger.info("LINE handler initialized successfully")
        elif self.is_enabled():
            # 只有在平台啟用時才記錄配置錯誤
            logger.error("LINE handler initialization failed due to invalid config")
    
    def get_platform_type(self) -> PlatformType:
        return PlatformType.LINE
    
    def get_required_config_fields(self) -> List[str]:
        return ['channel_access_token', 'channel_secret']
    
    
    def validate_signature(self, request_data: bytes, signature: str) -> bool:
        """驗證 LINE webhook 簽名"""
        try:
            hash_value = hmac.new(
                self.channel_secret.encode('utf-8'),
                request_data,
                hashlib.sha256
            ).digest()
            expected_signature = base64.b64encode(hash_value).decode('utf-8')
            return signature == f"sha256={expected_signature}"
        except Exception as e:
            logger.error(f"Error validating LINE signature: {e}")
            return False
    
    def parse_message(self, raw_event: Any) -> Optional[PlatformMessage]:
        """解析 LINE 事件為統一的 PlatformMessage 格式"""
        try:
            if not isinstance(raw_event, MessageEvent):
                logger.debug(f"Skipping non-message event: {type(raw_event)}")
                return None
            
            # 建立用戶物件
            user = PlatformUser(
                user_id=raw_event.source.user_id,
                platform=PlatformType.LINE,
                metadata={'source_type': raw_event.source.type}
            )
            
            # 處理不同類型的訊息
            if isinstance(raw_event.message, TextMessageContent):
                return PlatformMessage(
                    message_id=raw_event.message.id,
                    user=user,
                    content=raw_event.message.text,
                    message_type="text",
                    reply_token=raw_event.reply_token,
                    metadata={'line_event': raw_event}
                )
            
            elif isinstance(raw_event.message, AudioMessageContent):
                # 下載音訊內容
                with ApiClient(self.configuration) as api_client:
                    line_bot_blob_api = MessagingApiBlob(api_client)
                    audio_content = line_bot_blob_api.get_message_content(
                        message_id=raw_event.message.id
                    )
                
                return PlatformMessage(
                    message_id=raw_event.message.id,
                    user=user,
                    content="[Audio Message]",
                    message_type="audio",
                    raw_data=audio_content,
                    reply_token=raw_event.reply_token,
                    metadata={'line_event': raw_event}
                )
            
            else:
                logger.warning(f"Unsupported LINE message type: {type(raw_event.message)}")
                return None
                
        except Exception as e:
            # 記錄詳細的錯誤 log
            logger.error(f"Error parsing LINE message: {type(e).__name__}: {e}")
            logger.error(f"LINE parse error details - Event type: {type(raw_event).__name__}")
            return None
    
    def send_response(self, response: PlatformResponse, message: PlatformMessage) -> bool:
        """發送回應到 LINE"""
        try:
            reply_token = message.reply_token
            if not reply_token:
                logger.error("No reply token found in message")
                return False
            
            # 目前只支援文字回應，未來可擴展支援圖片、音訊等
            if response.response_type == "text":
                line_message = LineTextMessage(text=response.content)
            else:
                logger.warning(f"Unsupported response type for LINE: {response.response_type}")
                line_message = LineTextMessage(text=response.content)
            
            # 發送回應
            with ApiClient(self.configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.reply_message_with_http_info(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=[line_message]
                    )
                )
            
            logger.debug(f"Successfully sent LINE response to user {message.user.user_id}")
            return True
            
        except Exception as e:
            # 記錄詳細的錯誤 log
            logger.error(f"Error sending LINE response: {type(e).__name__}: {e}")
            logger.error(f"LINE send error details - User: {message.user.user_id}, Response type: {response.response_type}")
            return False
    
    def handle_webhook(self, request_body: str, signature: str) -> List[PlatformMessage]:
        """處理 LINE webhook 請求"""
        try:
            # 驗證簽名
            if not self.validate_signature(request_body.encode('utf-8'), signature):
                logger.warning("Invalid LINE webhook signature")
                return []
            
            # 解析 webhook 事件
            webhook_data = json.loads(request_body)
            events = webhook_data.get('events', [])
            
            messages = []
            for event_data in events:
                try:
                    # 將字典轉換為 LINE SDK 事件物件
                    event = self._dict_to_line_event(event_data)
                    if event:
                        message = self.parse_message(event)
                        if message:
                            messages.append(message)
                except Exception as e:
                    # 記錄詳細的錯誤 log
                    logger.error(f"Error processing LINE event: {type(e).__name__}: {e}")
                    logger.error(f"LINE event error details - Event data: {str(event_data)[:200]}...")
                    continue
            
            logger.info(f"Processed {len(messages)} valid messages from LINE webhook")
            return messages
            
        except Exception as e:
            # 記錄詳細的錯誤 log
            logger.error(f"Error handling LINE webhook: {type(e).__name__}: {e}")
            logger.error(f"LINE webhook error details - Request body size: {len(request_body)}")
            return []
    
    def _dict_to_line_event(self, event_data: Dict[str, Any]) -> Optional[MessageEvent]:
        """將字典數據轉換為 LINE SDK 事件物件"""
        try:
            event_type = event_data.get('type')
            if event_type != 'message':
                return None
            
            # 簡化版本 - 直接創建 MessageEvent
            # 實際實作可能需要更複雜的轉換邏輯
            from linebot.v3.webhooks import MessageEvent, Source, Message
            
            # 創建 Source 物件
            source_data = event_data.get('source', {})
            source = Source(
                type=source_data.get('type', 'user'),
                user_id=source_data.get('userId')
            )
            
            # 創建 Message 物件
            message_data = event_data.get('message', {})
            message_type = message_data.get('type')
            
            if message_type == 'text':
                message = TextMessageContent(
                    id=message_data.get('id'),
                    text=message_data.get('text', '')
                )
            elif message_type == 'audio':
                message = AudioMessageContent(
                    id=message_data.get('id'),
                    duration=message_data.get('duration', 0)
                )
            else:
                return None
            
            # 創建 MessageEvent
            return MessageEvent(
                reply_token=event_data.get('replyToken'),
                source=source,
                timestamp=event_data.get('timestamp'),
                message=message
            )
            
        except Exception as e:
            # 記錄詳細的錯誤 log
            logger.error(f"Error converting dict to LINE event: {type(e).__name__}: {e}")
            logger.error(f"LINE event conversion error details - Event data: {str(event_data)[:200]}...")
            return None


class LineHandlerFactory:
    """
    LINE Handler 工廠類別
    
    實作 Factory Pattern - 負責創建和配置 LINE 處理器
    """
    
    @staticmethod
    def create_handler(config: Dict[str, Any]) -> Optional[LineHandler]:
        """創建 LINE 處理器"""
        try:
            handler = LineHandler(config)
            if handler.validate_config() and handler.is_enabled():
                return handler
            else:
                logger.warning("LINE handler not enabled or invalid config")
                return None
        except Exception as e:
            # 記錄詳細的錯誤 log
            logger.error(f"Error creating LINE handler: {type(e).__name__}: {e}")
            logger.error(f"LINE handler creation error details - Config keys: {list(config.keys()) if config else 'None'}")
            return None
    
    @staticmethod
    def get_required_config() -> Dict[str, str]:
        """取得必要設定的說明"""
        return {
            'enabled': 'Whether LINE platform is enabled (true/false)',
            'channel_access_token': 'LINE Channel Access Token',
            'channel_secret': 'LINE Channel Secret'
        }