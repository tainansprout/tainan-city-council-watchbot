"""
Instagram Business Cloud API 處理器
繼承自 MetaBaseHandler，實現 Instagram 特定的功能

🎯 平台特色：
  - 使用 Instagram 用戶 ID 作為識別
  - 支援 Instagram 直接訊息功能
  - 支援多媒體訊息和 Story 回覆
  - 使用 page_access_token 進行身份驗證
  - 媒體檔案可直接從 URL 下載
"""

import requests
from typing import List, Optional, Any, Dict
from ..core.logger import get_logger
from .base import PlatformType, PlatformUser, PlatformMessage
from .meta_base_handler import MetaBaseHandler

logger = get_logger(__name__)


class InstagramHandler(MetaBaseHandler):
    """
    Instagram Business Cloud API 處理器
    使用 Meta 官方的 Instagram Business Cloud API
    """
    
    def get_platform_type(self) -> PlatformType:
        return PlatformType.INSTAGRAM
    
    def get_platform_name(self) -> str:
        return "INSTAGRAM"
    
    def get_default_api_version(self) -> str:
        return 'v19.0'
    
    def get_webhook_object_type(self) -> str:
        return 'instagram'
    
    def _setup_platform_config(self):
        """Instagram 特定配置"""
        self.app_id = self.get_config('app_id')
        self.page_access_token = self.get_config('page_access_token')
    
    def get_required_config_fields(self) -> List[str]:
        return ['app_id', 'app_secret', 'page_access_token', 'verify_token']
    
    def _get_recipient_id(self, message: PlatformMessage) -> str:
        """Instagram 使用用戶 ID 作為接收者 ID"""
        return message.user.user_id
    
    def _download_media(self, media_url: str) -> Optional[bytes]:
        """下載媒體檔案 (向後兼容方法名)"""
        return self._download_media_from_url(media_url)
    
    # =============================================================================
    # Webhook 訊息處理 (Instagram 特定)
    # =============================================================================
    
    def _process_webhook_messages(self, webhook_data: Dict[str, Any]) -> List[PlatformMessage]:
        """處理 Instagram webhook 訊息"""
        messages: List[PlatformMessage] = []
        
        try:
            for entry in webhook_data.get('entry', []):
                for messaging_item in entry.get('messaging', []):
                    # Instagram messaging 結構與 Messenger 類似，但包裝在 entry 中
                    event = {
                        'object': 'instagram',
                        'entry': [{'messaging': [messaging_item]}]
                    }
                    message = self.parse_message(event)
                    if message:
                        messages.append(message)
        except Exception as e:
            logger.error(f"[INSTAGRAM] Webhook message processing error: {e}")
        
        return messages
    
    def parse_message(self, event: Any) -> Optional[PlatformMessage]:
        """解析 Instagram webhook 事件"""
        try:
            if isinstance(event, str):
                import json
                event = json.loads(event)
            
            logger.debug(f"[INSTAGRAM] parse_message received event: {event}")
            
            # 檢查是否為 Instagram 事件
            if event.get('object') != 'instagram':
                logger.debug("[INSTAGRAM] parse_message skipping non-Instagram event")
                return None
            
            # 取得 entry 資料
            entry = event.get('entry', [])
            if not entry:
                logger.debug("[INSTAGRAM] parse_message no entry data")
                return None
            
            # 取得 messaging 資料
            messaging = entry[0].get('messaging', [])
            if not messaging:
                logger.debug("[INSTAGRAM] parse_message no messaging data")
                return None
            
            # 解析第一個訊息
            messaging_item = messaging[0]
            sender = messaging_item.get('sender', {})
            recipient = messaging_item.get('recipient', {})
            timestamp = messaging_item.get('timestamp', 0)
            
            sender_id = sender.get('id')
            if not sender_id:
                logger.debug("[INSTAGRAM] parse_message no sender ID")
                return None
            
            # 獲取用戶資訊
            display_name = self._get_user_info(sender_id)
            
            # 建立用戶資訊
            user = PlatformUser(
                user_id=sender_id,
                platform=PlatformType.INSTAGRAM,
                display_name=display_name,
                metadata={
                    'recipient_id': recipient.get('id'),
                    'timestamp': timestamp
                }
            )
            
            message_id = messaging_item.get('message', {}).get('mid', f"instagram_{sender_id}_{timestamp}")
            content = ""
            message_type = "text"
            raw_data = None
            
            # 處理不同類型的訊息
            if 'message' in messaging_item:
                message_data = messaging_item['message']
                
                # 文字訊息
                if 'text' in message_data:
                    content = message_data['text']
                    logger.debug(f"[INSTAGRAM] Text message from {sender_id}: {content}")
                
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
                                    logger.debug(f"[INSTAGRAM] Audio message from {sender_id}, size: {len(raw_data)} bytes")
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
                        
                        elif attachment_type == 'story_reply':
                            message_type = 'story_reply'
                            content = '[Story Reply]'
                        
                        else:
                            content = f'[{attachment_type.upper()} Message]'
                            logger.debug(f"[INSTAGRAM] Unsupported attachment type: {attachment_type}")
            
            else:
                logger.debug(f"[INSTAGRAM] Unknown message structure: {messaging_item}")
                return None
            
            return PlatformMessage(
                message_id=message_id,
                user=user,
                content=content,
                message_type=message_type,
                raw_data=raw_data,
                metadata={
                    'instagram_event': event,
                    'sender_id': sender_id,
                    'recipient_id': recipient.get('id'),
                    'timestamp': timestamp
                }
            )
            
        except Exception as e:
            logger.error(f"[INSTAGRAM] parse_message error: {e}")
            return None
    
    def _get_user_info(self, user_id: str) -> Optional[str]:
        """獲取 Instagram 用戶資訊"""
        try:
            url = f"{self.base_url}/{user_id}"
            params = {'fields': 'name,username'}
            
            response = requests.get(url, params=params, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                user_data = response.json()
                return user_data.get('name')
            else:
                logger.warning(f"[INSTAGRAM] Failed to get user info for {user_id}: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"[INSTAGRAM] Error getting user info: {e}")
            return None
    
    # =============================================================================
    # 發送訊息 (Instagram 特定)
    # =============================================================================
    
    def _send_text_message(self, recipient_id: str, text: str) -> bool:
        """發送 Instagram 文字訊息"""
        try:
            url = f"{self.base_url}/me/messages"
            
            payload = {
                "recipient": {"id": recipient_id},
                "message": {"text": text}
            }
            
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                logger.debug(f"[INSTAGRAM] _send_text_message success to {recipient_id}")
                return True
            else:
                logger.error(f"[INSTAGRAM] _send_text_message failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"[INSTAGRAM] _send_text_message error: {e}")
            return False
    
    def _send_audio_message(self, recipient_id: str, audio_data: bytes) -> bool:
        """發送 Instagram 音訊訊息（暫未實現）"""
        logger.warning(f"[INSTAGRAM] Audio message sending not implemented for {recipient_id}")
        return False
    
    def send_story_reply(self, recipient_id: str, story_id: str, text: str) -> bool:
        """發送 Story 回覆"""
        try:
            url = f"{self.base_url}/me/messages"
            
            payload = {
                "recipient": {"id": recipient_id},
                "message": {"text": text},
                "messaging_type": "MESSAGE_TAG",
                "tag": "STORY_MENTION"
            }
            
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                logger.debug(f"[INSTAGRAM] Story reply sent to {recipient_id}")
                return True
            else:
                logger.error(f"[INSTAGRAM] Story reply failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"[INSTAGRAM] Story reply error: {e}")
            return False
    
    # =============================================================================
    # Webhook 資訊 (Instagram 特定)
    # =============================================================================
    
    def get_webhook_info(self) -> Dict[str, Any]:
        """取得 Instagram webhook 資訊"""
        base_info = super().get_webhook_info()
        base_info.update({
            'app_id': self.app_id,
        })
        return base_info