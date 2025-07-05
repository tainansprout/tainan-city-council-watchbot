"""
LINE 平台處理器
使用官方 LINE SDK v3 簡化簽名驗證與事件解析
"""
import logging
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

logger = logging.getLogger(__name__)


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
            except Exception:
                logger.error("[LINE] parse_message failed to download audio content", exc_info=True)
                return None

            return PlatformMessage(
                message_id=event.message.id,
                user=user,
                content="[Audio Message]",
                message_type="audio",
                raw_data=audio_content,
                reply_token=event.reply_token,
                metadata={'line_event': event}
            )

        return None

    def handle_webhook(self, request_body: str, signature: str) -> List[PlatformMessage]:
        messages: List[PlatformMessage] = []
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

        logger.debug(f"[LINE] handle_webhook returning {len(messages)} messages")
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