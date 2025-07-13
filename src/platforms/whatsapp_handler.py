"""
WhatsApp Business Cloud API 平台處理器
繼承自 MetaBaseHandler，實現 WhatsApp 特定的功能

📋 架構職責分工：
✅ RESPONSIBILITIES (平台層職責):
  - 解析 WhatsApp Business webhooks
  - 透過 Graph API 下載媒體檔案 (音訊、圖片等)
  - 使用 Graph API 發送訊息
  - WhatsApp 特定的訊息類型處理

❌ NEVER DO (絕對禁止):
  - 呼叫 AI 模型 API (音訊轉錄、文字生成)
  - 處理對話邏輯或歷史記錄
  - 知道或依賴特定的 AI 模型類型
  - 直接調用 AudioService 或 ChatService

🔄 資料流向：
  WhatsApp Webhook → parse_message() → PlatformMessage → app.py
  app.py → send_response() → WhatsApp Business API

🎯 平台特色：
  - 使用手機號碼作為用戶識別
  - 支援多種媒體類型和互動式訊息
  - 需要商業驗證和 Meta 審核
  - 媒體檔案透過 Media ID 下載 (兩步驟)
  - 使用 phone_number_id 發送訊息
"""

import requests
from typing import List, Optional, Any, Dict
from ..core.logger import get_logger
from .base import PlatformType, PlatformUser, PlatformMessage
from .meta_base_handler import MetaBaseHandler

logger = get_logger(__name__)


class WhatsAppHandler(MetaBaseHandler):
    """
    WhatsApp Business Cloud API 平台處理器
    使用 Meta 官方的 WhatsApp Business Cloud API
    """
    
    def get_platform_type(self) -> PlatformType:
        return PlatformType.WHATSAPP
    
    def get_platform_name(self) -> str:
        return "WHATSAPP"
    
    def get_default_api_version(self) -> str:
        return 'v13.0'
    
    def get_webhook_object_type(self) -> str:
        return 'whatsapp_business_account'
    
    def _setup_platform_config(self):
        """WhatsApp 特定配置"""
        self.access_token = self.get_config('access_token')
        self.phone_number_id = self.get_config('phone_number_id')
    
    def get_required_config_fields(self) -> List[str]:
        return ['access_token', 'phone_number_id', 'verify_token']
    
    def _get_recipient_id(self, message: PlatformMessage) -> str:
        """WhatsApp 使用用戶的手機號碼作為接收者 ID"""
        return message.user.user_id
    
    def _download_media(self, media_id: str) -> Optional[bytes]:
        """下載媒體檔案 (向後兼容方法名)"""
        return self._download_media_from_id(media_id)
    
    # =============================================================================
    # Webhook 訊息處理 (WhatsApp 特定)
    # =============================================================================
    
    def _process_webhook_messages(self, webhook_data: Dict[str, Any]) -> List[PlatformMessage]:
        """處理 WhatsApp webhook 訊息"""
        messages: List[PlatformMessage] = []
        
        try:
            for entry in webhook_data.get('entry', []):
                for change in entry.get('changes', []):
                    value = change.get('value', {})
                    
                    # 建構完整的事件對象傳給 parse_message
                    event = {
                        'object': 'whatsapp_business_account',
                        'entry': [{'changes': [{'value': value}]}]
                    }
                    
                    for message_data in value.get('messages', []):
                        message = self.parse_message(event)
                        if message:
                            messages.append(message)
        except Exception as e:
            logger.error(f"[WHATSAPP] Webhook message processing error: {e}")
        
        return messages
    
    def parse_message(self, event: Any) -> Optional[PlatformMessage]:
        """解析 WhatsApp webhook 事件"""
        try:
            if isinstance(event, str):
                import json
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
                media_id = audio_data.get('id')
                if media_id:
                    raw_data = self._download_media(media_id)
                    if raw_data:
                        content = '[Audio Message]'
                        logger.debug(f"[WHATSAPP] Audio message from {from_number}, size: {len(raw_data)} bytes")
                    else:
                        content = '[Audio Message - Download Failed]'
                        raw_data = None
                else:
                    content = '[Audio Message]'
                    raw_data = None
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
    
    # =============================================================================
    # 發送訊息 (WhatsApp 特定)
    # =============================================================================
    
    def _send_text_message(self, to_number: str, text: str) -> bool:
        """發送 WhatsApp 文字訊息"""
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
    
    # =============================================================================
    # Webhook 資訊 (WhatsApp 特定)
    # =============================================================================
    
    def get_webhook_info(self) -> Dict[str, Any]:
        """取得 WhatsApp webhook 資訊"""
        base_info = super().get_webhook_info()
        base_info.update({
            'phone_number_id': self.phone_number_id,
        })
        return base_info