"""
WhatsApp Business Cloud API 平台處理器
使用 Meta 官方的 WhatsApp Business Cloud API
"""
import json
import requests
import hmac
import hashlib
from typing import List, Optional, Any, Dict
from ..core.logger import get_logger
from .base import BasePlatformHandler, PlatformType, PlatformUser, PlatformMessage, PlatformResponse

logger = get_logger(__name__)


class WhatsAppHandler(BasePlatformHandler):
    """
    WhatsApp Business Cloud API 平台處理器
    使用 Meta 官方的 WhatsApp Business Cloud API
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.access_token = self.get_config('access_token')
        self.phone_number_id = self.get_config('phone_number_id')
        self.app_secret = self.get_config('app_secret')
        self.verify_token = self.get_config('verify_token')
        self.api_version = self.get_config('api_version', 'v13.0')
        self.base_url = f'https://graph.facebook.com/{self.api_version}'
        
        if self.is_enabled() and self.validate_config():
            self.headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            logger.info("WhatsApp Business Cloud API handler initialized")
        elif self.is_enabled():
            logger.error("WhatsApp handler initialization failed due to invalid config")

    def get_platform_type(self) -> PlatformType:
        return PlatformType.WHATSAPP

    def get_required_config_fields(self) -> List[str]:
        return ['access_token', 'phone_number_id', 'verify_token']

    def parse_message(self, event: Any) -> Optional[PlatformMessage]:
        """解析 WhatsApp webhook 事件"""
        try:
            if isinstance(event, str):
                event = json.loads(event)
            
            logger.debug(f"[WHATSAPP] parse_message received event: {event}")
            
            # 檢查是否為 WhatsApp 事件
            if event.get('object') != 'whatsapp_business_account':
                logger.debug("[WHATSAPP] parse_message skipping non-WhatsApp event")
                return None
            
            # 取得 entry 資料
            entry = event.get('entry', [])
            if not entry:
                logger.debug("[WHATSAPP] parse_message no entry data")
                return None
            
            # 取得 changes 資料
            changes = entry[0].get('changes', [])
            if not changes:
                logger.debug("[WHATSAPP] parse_message no changes data")
                return None
            
            # 取得 value 資料
            value = changes[0].get('value', {})
            messages = value.get('messages', [])
            
            if not messages:
                logger.debug("[WHATSAPP] parse_message no messages data")
                return None
            
            # 解析第一個訊息
            message_data = messages[0]
            contacts = value.get('contacts', [])
            metadata = value.get('metadata', {})
            
            # 建立用戶資訊
            from_number = message_data.get('from', '')
            display_name = None
            
            # 從 contacts 取得用戶名稱
            if contacts:
                contact = contacts[0]
                profile = contact.get('profile', {})
                display_name = profile.get('name')
            
            user = PlatformUser(
                user_id=from_number,
                platform=PlatformType.WHATSAPP,
                display_name=display_name,
                metadata={
                    'phone_number_id': metadata.get('phone_number_id'),
                    'display_phone_number': metadata.get('display_phone_number'),
                    'wa_id': contacts[0].get('wa_id') if contacts else from_number
                }
            )
            
            # 解析訊息內容
            message_id = message_data.get('id', '')
            message_type = message_data.get('type', 'text')
            content = ''
            raw_data = None
            
            # 根據訊息類型解析內容
            if message_type == 'text':
                text_data = message_data.get('text', {})
                content = text_data.get('body', '')
                logger.debug(f"[WHATSAPP] parse_message text from {from_number}: {content}")
                
            elif message_type == 'audio':
                audio_data = message_data.get('audio', {})
                content = '[Audio Message]'
                # 可以在這裡下載音訊檔案
                media_id = audio_data.get('id')
                if media_id:
                    raw_data = self._download_media(media_id)
                logger.debug(f"[WHATSAPP] parse_message audio from {from_number}, media_id: {media_id}")
                
            elif message_type == 'image':
                image_data = message_data.get('image', {})
                content = '[Image Message]'
                media_id = image_data.get('id')
                if media_id:
                    raw_data = self._download_media(media_id)
                logger.debug(f"[WHATSAPP] parse_message image from {from_number}, media_id: {media_id}")
                
            elif message_type == 'document':
                document_data = message_data.get('document', {})
                filename = document_data.get('filename', 'document')
                content = f'[Document: {filename}]'
                media_id = document_data.get('id')
                if media_id:
                    raw_data = self._download_media(media_id)
                logger.debug(f"[WHATSAPP] parse_message document from {from_number}, filename: {filename}")
                
            elif message_type == 'location':
                location_data = message_data.get('location', {})
                latitude = location_data.get('latitude')
                longitude = location_data.get('longitude')
                content = f'[Location: {latitude}, {longitude}]'
                logger.debug(f"[WHATSAPP] parse_message location from {from_number}")
                
            else:
                content = f'[{message_type.upper()} Message]'
                logger.debug(f"[WHATSAPP] parse_message unsupported type {message_type} from {from_number}")
            
            return PlatformMessage(
                message_id=message_id,
                user=user,
                content=content,
                message_type=message_type,
                raw_data=raw_data,
                metadata={
                    'whatsapp_event': event,
                    'timestamp': message_data.get('timestamp'),
                    'from': from_number,
                    'phone_number_id': metadata.get('phone_number_id')
                }
            )
            
        except Exception as e:
            logger.error(f"[WHATSAPP] parse_message error: {e}")
            return None

    def _download_media(self, media_id: str) -> Optional[bytes]:
        """下載媒體檔案"""
        try:
            # 步驟 1: 取得媒體 URL
            url = f"{self.base_url}/{media_id}"
            response = requests.get(url, headers=self.headers, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"[WHATSAPP] _download_media failed to get media info: {response.status_code}")
                return None
            
            media_info = response.json()
            media_url = media_info.get('url')
            
            if not media_url:
                logger.error("[WHATSAPP] _download_media no media URL found")
                return None
            
            # 步驟 2: 下載媒體檔案
            media_response = requests.get(media_url, headers=self.headers, timeout=30)
            
            if media_response.status_code == 200:
                logger.debug(f"[WHATSAPP] _download_media success ({len(media_response.content)} bytes)")
                return media_response.content
            else:
                logger.error(f"[WHATSAPP] _download_media failed to download: {media_response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"[WHATSAPP] _download_media error: {e}")
            return None

    def send_response(self, response: PlatformResponse, message: PlatformMessage) -> bool:
        """發送回應到 WhatsApp"""
        try:
            to_number = message.user.user_id
            
            if response.response_type == "text":
                return self._send_text_message(to_number, response.content)
            elif response.response_type == "audio" and response.raw_response:
                return self._send_audio_message(to_number, response.raw_response)
            else:
                logger.warning(f"[WHATSAPP] send_response unsupported response type: {response.response_type}")
                return False
                
        except Exception as e:
            logger.error(f"[WHATSAPP] send_response error: {e}")
            return False

    def _send_text_message(self, to_number: str, text: str) -> bool:
        """發送文字訊息"""
        try:
            url = f"{self.base_url}/{self.phone_number_id}/messages"
            
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to_number,
                "type": "text",
                "text": {
                    "preview_url": False,
                    "body": text
                }
            }
            
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                logger.debug(f"[WHATSAPP] _send_text_message success to {to_number}")
                return True
            else:
                logger.error(f"[WHATSAPP] _send_text_message failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"[WHATSAPP] _send_text_message error: {e}")
            return False

    def _send_audio_message(self, to_number: str, audio_data: bytes) -> bool:
        """發送音訊訊息"""
        try:
            # WhatsApp Cloud API 需要先上傳媒體，然後使用 media_id 發送
            # 這需要實作媒體上傳功能
            logger.warning("[WHATSAPP] _send_audio_message not implemented yet")
            return False
                
        except Exception as e:
            logger.error(f"[WHATSAPP] _send_audio_message error: {e}")
            return False

    def handle_webhook(self, request_body: str, signature: str) -> List[PlatformMessage]:
        """處理 WhatsApp webhook 請求"""
        messages: List[PlatformMessage] = []
        
        try:
            logger.debug(f"[WHATSAPP] handle_webhook received body: {request_body}")
            
            # 驗證 webhook 簽名
            if self.app_secret and signature:
                if not self._verify_signature(request_body, signature):
                    logger.error("[WHATSAPP] handle_webhook signature verification failed")
                    return []
            
            # 解析 webhook 資料
            webhook_data = json.loads(request_body)
            
            # 檢查是否為驗證請求
            if 'hub.mode' in webhook_data:
                # 這是 webhook 驗證請求，不是訊息
                logger.debug("[WHATSAPP] handle_webhook received verification request")
                return []
            
            # 處理訊息事件
            message = self.parse_message(webhook_data)
            if message:
                messages.append(message)
                logger.debug(f"[WHATSAPP] handle_webhook parsed message from {message.user.user_id}")
                
        except json.JSONDecodeError as e:
            logger.error(f"[WHATSAPP] handle_webhook JSON decode error: {e}")
        except Exception as e:
            logger.error(f"[WHATSAPP] handle_webhook error: {e}")
        
        logger.debug(f"[WHATSAPP] handle_webhook returning {len(messages)} messages")
        return messages

    def _verify_signature(self, request_body: str, signature: str) -> bool:
        """驗證 webhook 簽名"""
        try:
            # WhatsApp 使用 HMAC-SHA256 驗證
            if not signature.startswith('sha256='):
                logger.error("[WHATSAPP] _verify_signature invalid signature format")
                return False
            
            signature_hash = signature[7:]  # 移除 'sha256=' 前綴
            expected_signature = hmac.new(
                self.app_secret.encode('utf-8'),
                request_body.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            is_valid = hmac.compare_digest(signature_hash, expected_signature)
            logger.debug(f"[WHATSAPP] _verify_signature result: {is_valid}")
            return is_valid
            
        except Exception as e:
            logger.error(f"[WHATSAPP] _verify_signature error: {e}")
            return False

    def verify_webhook(self, verify_token: str, challenge: str) -> Optional[str]:
        """驗證 webhook 設定"""
        try:
            if verify_token == self.verify_token:
                logger.info("[WHATSAPP] verify_webhook success")
                return challenge
            else:
                logger.error("[WHATSAPP] verify_webhook failed - invalid token")
                return None
                
        except Exception as e:
            logger.error(f"[WHATSAPP] verify_webhook error: {e}")
            return None

    def get_webhook_info(self) -> Dict[str, Any]:
        """取得 webhook 資訊"""
        return {
            'platform': 'whatsapp',
            'webhook_url': f'/webhooks/whatsapp',
            'verify_token': self.verify_token,
            'phone_number_id': self.phone_number_id,
            'api_version': self.api_version
        }