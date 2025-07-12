"""
Facebook Messenger Platform 處理器
使用 Meta 官方的 Messenger Platform API
"""
import json
import requests
from typing import List, Optional, Any, Dict
from ..core.logger import get_logger
from ..utils.webhook import verify_meta_signature
from .base import BasePlatformHandler, PlatformType, PlatformUser, PlatformMessage, PlatformResponse

logger = get_logger(__name__)


class MessengerHandler(BasePlatformHandler):
    """
    Facebook Messenger Platform 處理器
    使用 Meta 官方的 Messenger Platform API
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.app_id = self.get_config('app_id')
        self.app_secret = self.get_config('app_secret')
        self.page_access_token = self.get_config('page_access_token')
        self.verify_token = self.get_config('verify_token')
        self.api_version = self.get_config('api_version', 'v19.0')
        self.base_url = f'https://graph.facebook.com/{self.api_version}'
        
        
        if self.is_enabled() and self.validate_config():
            self.headers = {
                'Authorization': f'Bearer {self.page_access_token}',
                'Content-Type': 'application/json'
            }
            logger.info("Facebook Messenger Platform handler initialized")
        elif self.is_enabled():
            logger.error("Messenger handler initialization failed due to invalid config")

    def get_platform_type(self) -> PlatformType:
        return PlatformType.MESSENGER

    def get_required_config_fields(self) -> List[str]:
        return ['app_id', 'app_secret', 'page_access_token', 'verify_token']

    def parse_message(self, event: Any) -> Optional[PlatformMessage]:
        """解析 Messenger webhook 事件"""
        try:
            if isinstance(event, str):
                event = json.loads(event)
            
            logger.debug(f"[MESSENGER] parse_message received event: {event}")
            
            # 檢查是否為 Messenger 事件
            if event.get('object') != 'page':
                logger.debug("[MESSENGER] parse_message skipping non-page event")
                return None
            
            # 取得 entry 資料
            entry = event.get('entry', [])
            if not entry:
                logger.debug("[MESSENGER] parse_message no entry data")
                return None
            
            # 取得 messaging 資料
            messaging = entry[0].get('messaging', [])
            if not messaging:
                logger.debug("[MESSENGER] parse_message no messaging data")
                return None
            
            # 解析第一個訊息
            message_event = messaging[0]
            sender = message_event.get('sender', {})
            recipient = message_event.get('recipient', {})
            message_data = message_event.get('message', {})
            
            if not message_data:
                logger.debug("[MESSENGER] parse_message no message data")
                return None
            
            # 建立用戶資訊
            sender_id = sender.get('id', '')
            
            # 取得用戶詳細資訊（可選）
            display_name = None
            try:
                # 使用 Graph API 取得用戶名稱
                user_url = f"{self.base_url}/{sender_id}?fields=first_name,last_name"
                user_response = requests.get(user_url, headers=self.headers, timeout=10)
                if user_response.status_code == 200:
                    user_data = user_response.json()
                    first_name = user_data.get('first_name', '')
                    last_name = user_data.get('last_name', '')
                    display_name = f"{first_name} {last_name}".strip()
            except Exception as e:
                logger.warning(f"[MESSENGER] Failed to fetch user details: {e}")
            
            user = PlatformUser(
                user_id=sender_id,
                platform=PlatformType.MESSENGER,
                display_name=display_name,
                metadata={
                    'recipient_id': recipient.get('id'),
                    'timestamp': message_event.get('timestamp')
                }
            )
            
            # 解析訊息內容
            message_id = message_data.get('mid', '')
            content = ''
            message_type = 'text'
            raw_data = None
            
            # 處理文字訊息
            if 'text' in message_data:
                content = message_data.get('text', '')
                logger.debug(f"[MESSENGER] parse_message text from {sender_id}: {content}")
                
            # 處理附件
            elif 'attachments' in message_data:
                attachments = message_data.get('attachments', [])
                if attachments:
                    attachment = attachments[0]
                    attachment_type = attachment.get('type', '')
                    payload = attachment.get('payload', {})
                    
                    if attachment_type == 'image':
                        message_type = 'image'
                        content = '[Image Message]'
                        # 可以下載圖片
                        image_url = payload.get('url')
                        if image_url:
                            raw_data = self._download_media(image_url)
                    elif attachment_type == 'audio':
                        message_type = 'audio'
                        audio_url = payload.get('url')
                        if audio_url:
                            raw_data = self._download_media(audio_url)
                            if raw_data:
                                content = '[Audio Message]'
                                logger.debug(f"[MESSENGER] Audio message from {sender_id}, size: {len(raw_data)} bytes")
                            else:
                                content = '[Audio Message - Download Failed]'
                                raw_data = None
                        else:
                            content = '[Audio Message]'
                            raw_data = None
                    elif attachment_type == 'video':
                        message_type = 'video'
                        content = '[Video Message]'
                    elif attachment_type == 'file':
                        message_type = 'file'
                        content = '[File Message]'
                    elif attachment_type == 'location':
                        message_type = 'location'
                        coordinates = payload.get('coordinates', {})
                        lat = coordinates.get('lat')
                        lng = coordinates.get('long')
                        content = f'[Location: {lat}, {lng}]'
                    else:
                        content = f'[{attachment_type.upper()} Message]'
                        
                logger.debug(f"[MESSENGER] parse_message {attachment_type} from {sender_id}")
            
            # 處理快速回覆
            if 'quick_reply' in message_data:
                quick_reply = message_data.get('quick_reply', {})
                payload = quick_reply.get('payload', '')
                content += f" [Quick Reply: {payload}]"
            
            return PlatformMessage(
                message_id=message_id,
                user=user,
                content=content,
                message_type=message_type,
                raw_data=raw_data,
                metadata={
                    'messenger_event': event,
                    'timestamp': message_event.get('timestamp'),
                    'sender_id': sender_id,
                    'recipient_id': recipient.get('id'),
                    'is_echo': message_data.get('is_echo', False)
                }
            )
            
        except Exception as e:
            logger.error(f"[MESSENGER] parse_message error: {e}")
            return None

    def _download_media(self, media_url: str) -> Optional[bytes]:
        """下載媒體檔案"""
        try:
            response = requests.get(media_url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                logger.debug(f"[MESSENGER] _download_media success ({len(response.content)} bytes)")
                return response.content
            else:
                logger.error(f"[MESSENGER] _download_media failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"[MESSENGER] _download_media error: {e}")
            return None

    def send_response(self, response: PlatformResponse, message: PlatformMessage) -> bool:
        """發送回應到 Messenger"""
        try:
            recipient_id = message.user.user_id
            
            if response.response_type == "text":
                return self._send_text_message(recipient_id, response.content)
            elif response.response_type == "audio" and response.raw_response:
                return self._send_audio_message(recipient_id, response.raw_response)
            else:
                logger.warning(f"[MESSENGER] send_response unsupported response type: {response.response_type}")
                return False
                
        except Exception as e:
            logger.error(f"[MESSENGER] send_response error: {e}")
            return False

    def _send_text_message(self, recipient_id: str, text: str) -> bool:
        """發送文字訊息"""
        try:
            url = f"{self.base_url}/me/messages"
            
            payload = {
                "recipient": {
                    "id": recipient_id
                },
                "message": {
                    "text": text
                }
            }
            
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                logger.debug(f"[MESSENGER] _send_text_message success to {recipient_id}")
                return True
            else:
                logger.error(f"[MESSENGER] _send_text_message failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"[MESSENGER] _send_text_message error: {e}")
            return False

    def _send_audio_message(self, recipient_id: str, audio_data: bytes) -> bool:
        """發送音訊訊息"""
        try:
            # Messenger 需要先上傳媒體，然後使用 attachment_id 發送
            logger.warning("[MESSENGER] _send_audio_message not implemented yet")
            return False
                
        except Exception as e:
            logger.error(f"[MESSENGER] _send_audio_message error: {e}")
            return False

    def _verify_signature(self, request_body: str, signature: str) -> bool:
        """驗證 Messenger webhook 簽名"""
        try:
            if isinstance(request_body, str):
                body_bytes = request_body.encode('utf-8')
            else:
                body_bytes = request_body
            
            return verify_meta_signature(self.app_secret, body_bytes, signature)
        except Exception as e:
            logger.error(f"[MESSENGER] Signature verification error: {e}")
            return False

    def handle_webhook(self, request_body: str, headers: Dict[str, str]) -> List[PlatformMessage]:
        """處理 Messenger webhook 請求"""
        signature = headers.get('X-Hub-Signature') or headers.get('X-Hub-Signature-256')
        if self.app_secret and signature and not self._verify_signature(request_body, signature):
            logger.error("[MESSENGER] Webhook signature verification failed.")
            return []

        messages: List[PlatformMessage] = []
        try:
            webhook_data = json.loads(request_body)
            if webhook_data.get('object') != 'page':
                return []

            for entry in webhook_data.get('entry', []):
                for message_event in entry.get('messaging', []):
                    # 忽略 echo 訊息
                    if message_event.get('message', {}).get('is_echo'):
                        continue
                    
                    # Create a webhook event structure for parse_message
                    event = {
                        'object': 'page',
                        'entry': [{
                            'messaging': [message_event]
                        }]
                    }
                    message = self.parse_message(event)
                    if message:
                        messages.append(message)
                        
        except json.JSONDecodeError as e:
            logger.error(f"[MESSENGER] handle_webhook JSON decode error: {e}")
        except Exception as e:
            logger.error(f"[MESSENGER] handle_webhook error: {e}")
        
        return messages

    

    def verify_webhook(self, verify_token: str, challenge: str) -> Optional[str]:
        """驗證 webhook 設定"""
        try:
            if verify_token == self.verify_token:
                logger.info("[MESSENGER] verify_webhook success")
                return challenge
            else:
                logger.error("[MESSENGER] verify_webhook failed - invalid token")
                return None
                
        except Exception as e:
            logger.error(f"[MESSENGER] verify_webhook error: {e}")
            return None

    def get_webhook_info(self) -> Dict[str, Any]:
        """取得 webhook 資訊"""
        return {
            'platform': 'messenger',
            'webhook_url': f'/webhooks/messenger',
            'verify_token': self.verify_token,
            'app_id': self.app_id,
            'api_version': self.api_version
        }

    def send_quick_replies(self, recipient_id: str, text: str, quick_replies: List[Dict[str, str]]) -> bool:
        """發送帶有快速回覆的訊息"""
        try:
            url = f"{self.base_url}/me/messages"
            
            quick_replies_data = []
            for reply in quick_replies:
                quick_replies_data.append({
                    "content_type": "text",
                    "title": reply.get("title", ""),
                    "payload": reply.get("payload", "")
                })
            
            payload = {
                "recipient": {
                    "id": recipient_id
                },
                "message": {
                    "text": text,
                    "quick_replies": quick_replies_data
                }
            }
            
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                logger.debug(f"[MESSENGER] send_quick_replies success to {recipient_id}")
                return True
            else:
                logger.error(f"[MESSENGER] send_quick_replies failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"[MESSENGER] send_quick_replies error: {e}")
            return False