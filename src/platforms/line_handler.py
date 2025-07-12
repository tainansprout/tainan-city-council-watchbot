"""
LINE 平台處理器
使用官方 LINE SDK v3 簡化簽名驗證與事件解析

📋 架構職責分工：
✅ RESPONSIBILITIES (平台層職責):
  - 解析 LINE webhook events
  - 下載音訊/圖片等媒體檔案
  - 透過 LINE Messaging API 發送回應
  - 使用官方 SDK 進行簽名驗證

❌ NEVER DO (絕對禁止):
  - 呼叫 AI 模型 API (音訊轉錄、文字生成)
  - 處理對話邏輯或歷史記錄
  - 知道或依賴特定的 AI 模型類型
  - 直接調用 AudioService 或 ChatService

🔄 資料流向：
  LINE Webhook → parse_message() → PlatformMessage → app.py
  app.py → send_response() → LINE Messaging API

🎯 平台特色：
  - 使用 reply_token 機制回應訊息
  - 支援豐富的訊息類型 (文字、音訊、圖片、sticker等)
  - Webhook 簽名使用 HMAC-SHA256 驗證
  - 音訊檔案需透過 Blob API 下載
"""
from ..core.logger import get_logger
from typing import List, Optional, Any, Dict

from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    ReplyMessageRequest,
    TextMessage as LineTextMessage,
)
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhook import WebhookParser
from linebot.v3.webhooks import MessageEvent, TextMessageContent, AudioMessageContent

from .base import BasePlatformHandler, PlatformType, PlatformUser, PlatformMessage, PlatformResponse

logger = get_logger(__name__)


class LineHandler(BasePlatformHandler):
    """
    LINE 平台處理器
    利用 WebhookParser 處理簽名驗證與事件解析
    """
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.channel_access_token = self.get_config('channel_access_token')
        self.channel_secret = self.get_config('channel_secret')

        if self.is_enabled() and self.validate_config():
            self.parser = WebhookParser(self.channel_secret)
            self.configuration = Configuration(access_token=self.channel_access_token)
            logger.info("LINE handler initialized")
        elif self.is_enabled():
            logger.error("LINE handler initialization failed due to invalid config")

    def get_platform_type(self) -> PlatformType:
        return PlatformType.LINE

    def get_required_config_fields(self) -> List[str]:
        return ['channel_access_token', 'channel_secret']

    def parse_message(self, event: Any) -> Optional[PlatformMessage]:
        logger.debug(f"[LINE] parse_message received event type: {type(event).__name__}")
        if not isinstance(event, MessageEvent):
            logger.debug("[LINE] parse_message skipping non-MessageEvent")
            return None

        user = PlatformUser(
            user_id=event.source.user_id,
            platform=PlatformType.LINE,
            metadata={'source_type': event.source.type}
        )

        if isinstance(event.message, TextMessageContent):
            logger.debug(f"[LINE] parse_message TextMessage from {user.user_id}: {event.message.text}")
            return PlatformMessage(
                message_id=event.message.id,
                user=user,
                content=event.message.text,
                message_type="text",
                reply_token=event.reply_token,
                metadata={'line_event': event}
            )

        if isinstance(event.message, AudioMessageContent):
            logger.debug(f"[LINE] parse_message AudioMessageContent id={event.message.id}, duration={event.message.duration}")
            try:
                with ApiClient(self.configuration) as api_client:
                    blob_api = MessagingApiBlob(api_client)
                    audio_content = blob_api.get_message_content(message_id=event.message.id)
                logger.debug(f"[LINE] parse_message downloaded audio content ({len(audio_content)} bytes)")
                
                # 只標記為音訊訊息，不在此層進行轉錄
                content = "[Audio Message]"
                logger.debug(f"[LINE] Audio message from {user.user_id}, size: {len(audio_content)} bytes")
                    
            except Exception:
                logger.error("[LINE] parse_message failed to download audio content", exc_info=True)
                audio_content = None
                content = "[Audio Message - Download Failed]"

            return PlatformMessage(
                message_id=event.message.id,
                user=user,
                content=content,
                message_type="audio",
                raw_data=audio_content,
                reply_token=event.reply_token,
                metadata={'line_event': event}
            )

        return None

    def handle_webhook(self, request_body: str, headers: Dict[str, str]) -> List[PlatformMessage]:
        messages: List[PlatformMessage] = []
        signature = headers.get('X-Line-Signature')
        logger.debug(f"[LINE] handle_webhook start, signature={signature}, body_bytes={len(request_body)}")
        
        # 基本簽名格式檢查
        if not signature or not signature.strip():
            logger.warning("[LINE] No signature provided, ignoring webhook")
            return []
        
        try:
            # 使用 LINE SDK 的 parser 進行簽名驗證和事件解析
            events = self.parser.parse(request_body, signature)
            logger.debug(f"[LINE] handle_webhook parsed {len(events)} events")
        except InvalidSignatureError:
            logger.warning("[LINE] Invalid signature detected by LINE SDK")
            return []
        except Exception:
            logger.error("[LINE] Error parsing webhook events", exc_info=True)
            return []

        for event in events:
            logger.debug(f"[LINE] handle_webhook processing event: {event}")
            message = self.parse_message(event)
            if message:
                messages.append(message)
        
        return messages

    def send_response(self, response: PlatformResponse, message: PlatformMessage) -> bool:
        if not message.reply_token:
            logger.error("[LINE] send_response missing reply_token, aborted")
            return False

        if response.response_type != "text":
            logger.warning("[LINE] send_response non-text response, converting to text")

        line_message = LineTextMessage(text=response.content)

        logger.debug(f"[LINE] send_response to user={message.user.user_id}, reply_token={message.reply_token}")
        logger.debug(f"[LINE] send_response content={response.content}")
        try:
            with ApiClient(self.configuration) as api_client:
                MessagingApi(api_client).reply_message_with_http_info(
                    ReplyMessageRequest(reply_token=message.reply_token, messages=[line_message])
                )
            logger.debug("[LINE] send_response succeeded")
            return True
        except Exception:
            logger.error("[LINE] send_response failed", exc_info=True)
            return False