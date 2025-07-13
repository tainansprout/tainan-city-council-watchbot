"""
Facebook Messenger Platform 處理器
繼承自 MetaBaseHandler，實現 Messenger 特定的功能

🎯 平台特色：
  - 使用 Facebook 用戶 ID 作為識別
  - 支援豐富的訊息類型和快速回覆
  - 支援多媒體訊息和模板訊息
  - 使用 page_access_token 進行身份驗證
  - 媒體檔案可直接從 URL 下載
  - 支援 Quick Replies 和 Postback 事件
"""

import requests
from typing import List, Optional, Any, Dict
from ..core.logger import get_logger
from .base import PlatformType, PlatformUser, PlatformMessage
from .meta_base_handler import MetaBaseHandler

logger = get_logger(__name__)


class MessengerHandler(MetaBaseHandler):
    """
    Facebook Messenger Platform 處理器
    使用 Meta 官方的 Messenger Platform API
    """
    
    def get_platform_type(self) -> PlatformType:
        return PlatformType.MESSENGER
    
    def get_platform_name(self) -> str:
        return "MESSENGER"
    
    def get_default_api_version(self) -> str:
        return 'v19.0'
    
    def get_webhook_object_type(self) -> str:
        return 'page'
    
    def _setup_platform_config(self):
        """Messenger 特定配置"""
        self.app_id = self.get_config('app_id')
        self.page_access_token = self.get_config('page_access_token')
    
    def get_required_config_fields(self) -> List[str]:
        return ['app_id', 'app_secret', 'page_access_token', 'verify_token']
    
    def _get_recipient_id(self, message: PlatformMessage) -> str:
        """Messenger 使用用戶 ID 作為接收者 ID"""
        return message.user.user_id
    
    def _download_media(self, media_url: str) -> Optional[bytes]:
        """下載媒體檔案 (向後兼容方法名)"""
        return self._download_media_from_url(media_url)
    
    # =============================================================================
    # Webhook 訊息處理 (Messenger 特定)
    # =============================================================================
    
    def _process_webhook_messages(self, webhook_data: Dict[str, Any]) -> List[PlatformMessage]:
        """處理 Messenger webhook 訊息"""
        messages: List[PlatformMessage] = []
        
        try:
            for entry in webhook_data.get('entry', []):
                for messaging_item in entry.get('messaging', []):
                    # 跳過 echo 訊息 (bot 自己發送的訊息)
                    if messaging_item.get('message', {}).get('is_echo'):
                        continue
                    
                    # Messenger messaging 結構包裝為完整事件
                    event = {
                        'object': 'page',
                        'entry': [{'messaging': [messaging_item]}]
                    }
                    message = self.parse_message(event)
                    if message:
                        messages.append(message)
        except Exception as e:
            logger.error(f"[MESSENGER] Webhook message processing error: {e}")
        
        return messages
    
    def parse_message(self, event: Any) -> Optional[PlatformMessage]:
        """解析 Messenger webhook 事件"""
        try:
            if isinstance(event, str):
                import json
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
            messaging_item = messaging[0]
            
            # 跳過 echo 訊息 (bot 自己發送的訊息)
            if messaging_item.get('message', {}).get('is_echo'):
                logger.debug("[MESSENGER] parse_message skipping echo message")
                return None
            
            sender = messaging_item.get('sender', {})
            recipient = messaging_item.get('recipient', {})
            timestamp = messaging_item.get('timestamp', 0)
            
            sender_id = sender.get('id')
            if not sender_id:
                logger.debug("[MESSENGER] parse_message no sender ID")
                return None
            
            # 獲取用戶資訊
            display_name = self._get_user_info(sender_id)
            
            # 建立用戶資訊
            user = PlatformUser(
                user_id=sender_id,
                platform=PlatformType.MESSENGER,
                display_name=display_name,
                metadata={
                    'recipient_id': recipient.get('id'),
                    'timestamp': timestamp
                }
            )
            
            message_id = messaging_item.get('message', {}).get('mid', f"messenger_{sender_id}_{timestamp}")
            content = ""
            message_type = "text"
            raw_data = None
            
            # 處理不同類型的事件
            if 'message' in messaging_item:
                message_data = messaging_item['message']
                
                # 文字訊息
                if 'text' in message_data:
                    content = message_data['text']
                    
                    # 檢查是否有 Quick Reply
                    if 'quick_reply' in message_data:
                        quick_reply = message_data['quick_reply']
                        payload = quick_reply.get('payload', 'N/A')
                        content += f" [Quick Reply: {payload}]"
                        message_type = 'text'
                    
                    logger.debug(f"[MESSENGER] Text message from {sender_id}: {content}")
                
                # 附件訊息
                elif 'attachments' in message_data:
                    attachments = message_data['attachments']
                    if attachments:
                        attachment = attachments[0]
                        attachment_type = attachment.get('type', 'unknown')
                        payload = attachment.get('payload', {})
                        
                        if attachment_type == 'image':
                            message_type = 'image'
                            content = '[Image Message]'
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
                            lat = coordinates.get('lat', 'N/A')
                            long = coordinates.get('long', 'N/A')
                            content = f'[Location: {lat}, {long}]'
                        
                        else:
                            content = f'[{attachment_type.upper()} Message]'
                            logger.debug(f"[MESSENGER] Unknown attachment type: {attachment_type}")
            
            # Postback 事件
            elif 'postback' in messaging_item:
                postback_data = messaging_item['postback']
                payload = postback_data.get('payload', 'N/A')
                title = postback_data.get('title', 'N/A')
                content = f"[Postback: {title} ({payload})]"
                message_type = 'postback'
                logger.debug(f"[MESSENGER] Postback from {sender_id}: {payload}")
            
            else:
                logger.debug(f"[MESSENGER] Unknown event type: {messaging_item}")
                return None
            
            return PlatformMessage(
                message_id=message_id,
                user=user,
                content=content,
                message_type=message_type,
                raw_data=raw_data,
                metadata={
                    'messenger_event': event,
                    'sender_id': sender_id,
                    'recipient_id': recipient.get('id'),
                    'timestamp': timestamp
                }
            )
            
        except Exception as e:
            logger.error(f"[MESSENGER] parse_message error: {e}")
            return None
    
    def _get_user_info(self, user_id: str) -> Optional[str]:
        """獲取 Messenger 用戶資訊"""
        try:
            url = f"{self.base_url}/{user_id}"
            params = {'fields': 'first_name,last_name'}
            
            response = requests.get(url, params=params, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                user_data = response.json()
                first_name = user_data.get('first_name', '')
                last_name = user_data.get('last_name', '')
                return f"{first_name} {last_name}".strip() or None
            else:
                logger.warning(f"[MESSENGER] Failed to get user info for {user_id}: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"[MESSENGER] Error getting user info: {e}")
            return None
    
    # =============================================================================
    # 發送訊息 (Messenger 特定)
    # =============================================================================
    
    def _send_text_message(self, recipient_id: str, text: str) -> bool:
        """發送 Messenger 文字訊息"""
        try:
            url = f"{self.base_url}/me/messages"
            
            payload = {
                "recipient": {"id": recipient_id},
                "message": {"text": text}
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
        """發送 Messenger 音訊訊息（暫未實現）"""
        logger.warning(f"[MESSENGER] Audio message sending not implemented for {recipient_id}")
        return False
    
    def send_quick_replies(self, recipient_id: str, text: str, quick_replies: List[Dict[str, Any]]) -> bool:
        """發送帶有快速回覆選項的訊息"""
        try:
            url = f"{self.base_url}/me/messages"
            
            payload = {
                "recipient": {"id": recipient_id},
                "message": {
                    "text": text,
                    "quick_replies": quick_replies
                }
            }
            
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                logger.debug(f"[MESSENGER] Quick replies sent successfully to {recipient_id}")
                return True
            else:
                logger.error(f"[MESSENGER] Quick replies failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"[MESSENGER] Send quick replies error: {e}")
            return False
    
    # =============================================================================
    # Webhook 資訊 (Messenger 特定)
    # =============================================================================
    
    def get_webhook_info(self) -> Dict[str, Any]:
        """取得 Messenger webhook 資訊"""
        base_info = super().get_webhook_info()
        base_info.update({
            'app_id': self.app_id,
        })
        return base_info