"""
Meta 平台基礎處理器
包含所有 Meta (Facebook) 旗下平台的共同邏輯

🎯 共同功能:
  - Meta Graph API 基礎設置
  - Webhook 簽名驗證 (X-Hub-Signature-256)
  - 基礎的 webhook 處理流程
  - 媒體檔案下載 (兩種模式)
  - 統一的錯誤處理和日誌記錄

🔄 子類需實現:
  - 平台特定的配置設置
  - 訊息解析邏輯 (parse_message)
  - 發送邏輯 (_send_text_message)
  - Webhook object 類型驗證
"""

import json
import hmac
import hashlib
import requests
from abc import abstractmethod
from typing import List, Optional, Any, Dict
from ..core.logger import get_logger
from .base import BasePlatformHandler, PlatformMessage, PlatformResponse

logger = get_logger(__name__)


class MetaBaseHandler(BasePlatformHandler):
    """
    Meta 平台基礎處理器
    為所有 Meta 旗下平台提供共同的基礎功能
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # 共同的 Meta 配置
        self.app_secret = self.get_config('app_secret')
        self.verify_token = self.get_config('verify_token')
        self.api_version = self.get_config('api_version', self.get_default_api_version())
        self.base_url = f'https://graph.facebook.com/{self.api_version}'
        
        # 讓子類設置平台特定配置
        self._setup_platform_config()
        
        if self.is_enabled() and self.validate_config():
            self._setup_headers()
            self._post_initialization()
            logger.info(f"{self.get_platform_name()} handler initialized")
        elif self.is_enabled():
            logger.error(f"{self.get_platform_name()} handler initialization failed due to invalid config")
    
    @abstractmethod
    def get_default_api_version(self) -> str:
        """獲取平台默認 API 版本"""
        pass
    
    @abstractmethod
    def _setup_platform_config(self):
        """設置平台特定配置 (access_token, page_access_token 等)"""
        pass
    
    @abstractmethod
    def get_webhook_object_type(self) -> str:
        """獲取 webhook object 類型 (whatsapp_business_account, instagram, page)"""
        pass
    
    @abstractmethod
    def get_platform_name(self) -> str:
        """獲取平台名稱 (用於日誌)"""
        pass
    
    def _setup_headers(self):
        """設置請求標頭 (子類可覆蓋)"""
        access_token = getattr(self, 'access_token', None) or getattr(self, 'page_access_token', None)
        if access_token:
            self.headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
        else:
            logger.error(f"[{self.get_platform_name()}] No access token found for headers setup")
    
    def _post_initialization(self):
        """初始化後的處理 (子類可覆蓋)"""
        pass
    
    # =============================================================================
    # Webhook 處理 (共同邏輯)
    # =============================================================================
    
    def handle_webhook(self, request_body: str, headers: Dict[str, str]) -> List[PlatformMessage]:
        """統一的 webhook 處理流程"""
        # 1. 簽名驗證
        if not self._verify_webhook_signature(request_body, headers):
            return []
        
        # 2. 解析 JSON
        webhook_data = self._parse_webhook_data(request_body)
        if not webhook_data:
            return []
        
        # 3. 驗證 object 類型
        if not self._validate_webhook_object(webhook_data):
            return []
        
        # 4. 處理訊息 (委託給子類)
        return self._process_webhook_messages(webhook_data)
    
    def _verify_webhook_signature(self, request_body: str, headers: Dict[str, str]) -> bool:
        """統一的簽名驗證"""
        signature = headers.get('X-Hub-Signature') or headers.get('X-Hub-Signature-256')
        if self.app_secret and signature:
            return self._verify_signature(request_body, signature)
        return True
    
    def _verify_signature(self, request_body: str, signature: str) -> bool:
        """Meta 簽名驗證 (所有平台共同)"""
        try:
            body_bytes = request_body.encode('utf-8') if isinstance(request_body, str) else request_body
            return self._verify_meta_signature(self.app_secret, body_bytes, signature)
        except Exception as e:
            logger.error(f"[{self.get_platform_name()}] Signature verification error: {e}")
            return False
    
    def _verify_meta_signature(self, app_secret: str, request_body: bytes, signature: Optional[str]) -> bool:
        """
        根據 Meta 官方文件驗證 HMAC-SHA256 簽名
        支援 WhatsApp、Messenger 和 Instagram Business Cloud API
        """
        if not signature:
            return False
        
        if not app_secret:
            # 如果沒有設定 app_secret，則跳過驗證
            return True

        try:
            # 支援 sha256= 和 sha1= 前綴
            if signature.startswith('sha256='):
                signature_hash = signature.split('=', 1)[1]
                expected_signature = hmac.new(
                    app_secret.encode('utf-8'),
                    request_body,
                    hashlib.sha256
                ).hexdigest()
            elif signature.startswith('sha1='):
                # 某些舊版本的 Messenger API 使用 SHA1
                signature_hash = signature.split('=', 1)[1]
                expected_signature = hmac.new(
                    app_secret.encode('utf-8'),
                    request_body,
                    hashlib.sha1
                ).hexdigest()
            else:
                # 不支援的簽名格式
                return False
                
            return hmac.compare_digest(signature_hash, expected_signature)
        except Exception:
            return False
    
    def _parse_webhook_data(self, request_body: str) -> Optional[Dict[str, Any]]:
        """解析 webhook JSON 數據"""
        try:
            return json.loads(request_body)
        except json.JSONDecodeError as e:
            logger.error(f"[{self.get_platform_name()}] JSON decode error: {e}")
            return None
        except Exception as e:
            logger.error(f"[{self.get_platform_name()}] Webhook parsing error: {e}")
            return None
    
    def _validate_webhook_object(self, webhook_data: Dict[str, Any]) -> bool:
        """驗證 webhook object 類型"""
        expected_object = self.get_webhook_object_type()
        actual_object = webhook_data.get('object')
        
        if actual_object != expected_object:
            logger.debug(f"[{self.get_platform_name()}] Skipping non-{expected_object} webhook: {actual_object}")
            return False
        
        return True
    
    @abstractmethod
    def _process_webhook_messages(self, webhook_data: Dict[str, Any]) -> List[PlatformMessage]:
        """處理 webhook 訊息 (平台特定實現)"""
        pass
    
    # =============================================================================
    # 媒體處理 (共同邏輯)
    # =============================================================================
    
    def _download_media_from_url(self, media_url: str) -> Optional[bytes]:
        """從 URL 直接下載媒體 (Instagram/Messenger 模式)"""
        try:
            response = requests.get(media_url, headers=self.headers, timeout=30)
            if response.status_code == 200:
                logger.debug(f"[{self.get_platform_name()}] Media download success ({len(response.content)} bytes)")
                return response.content
            else:
                logger.error(f"[{self.get_platform_name()}] Media download failed: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"[{self.get_platform_name()}] Media download error: {e}")
            return None
    
    def _download_media_from_id(self, media_id: str) -> Optional[bytes]:
        """從 Media ID 下載媒體 (WhatsApp 模式)"""
        try:
            # Step 1: 獲取媒體 URL
            url = f"{self.base_url}/{media_id}"
            response = requests.get(url, headers=self.headers, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"[{self.get_platform_name()}] Failed to get media info: {response.status_code}")
                return None
            
            media_info = response.json()
            media_url = media_info.get('url')
            
            if not media_url:
                logger.error(f"[{self.get_platform_name()}] No media URL found")
                return None
            
            # Step 2: 下載媒體
            return self._download_media_from_url(media_url)
            
        except Exception as e:
            logger.error(f"[{self.get_platform_name()}] Media download error: {e}")
            return None
    
    # =============================================================================
    # 回應發送 (共同邏輯)
    # =============================================================================
    
    def send_response(self, response: PlatformResponse, message: PlatformMessage) -> bool:
        """統一的回應發送邏輯"""
        try:
            recipient_id = self._get_recipient_id(message)
            
            if response.response_type == "text":
                return self._send_text_message(recipient_id, response.content)
            elif response.response_type == "audio" and response.raw_response:
                return self._send_audio_message(recipient_id, response.raw_response)
            else:
                logger.warning(f"[{self.get_platform_name()}] Unsupported response type: {response.response_type}")
                return False
        except Exception as e:
            logger.error(f"[{self.get_platform_name()}] Send response error: {e}")
            return False
    
    @abstractmethod
    def _get_recipient_id(self, message: PlatformMessage) -> str:
        """獲取接收者 ID (平台特定)"""
        pass
    
    @abstractmethod
    def _send_text_message(self, recipient_id: str, text: str) -> bool:
        """發送文字訊息 (平台特定實現)"""
        pass
    
    def _send_audio_message(self, recipient_id: str, audio_data: bytes) -> bool:
        """發送音訊訊息 (默認實現，子類可覆蓋)"""
        logger.warning(f"[{self.get_platform_name()}] Audio message sending not implemented")
        return False
    
    # =============================================================================
    # Webhook 驗證 (共同邏輯)
    # =============================================================================
    
    def verify_webhook(self, verify_token: str, challenge: str) -> Optional[str]:
        """驗證 webhook 設定"""
        try:
            if verify_token == self.verify_token:
                logger.info(f"[{self.get_platform_name()}] Webhook verification success")
                return challenge
            else:
                logger.error(f"[{self.get_platform_name()}] Webhook verification failed - invalid token")
                return None
        except Exception as e:
            logger.error(f"[{self.get_platform_name()}] Webhook verification error: {e}")
            return None
    
    def get_webhook_info(self) -> Dict[str, Any]:
        """取得 webhook 資訊"""
        return {
            'platform': self.get_platform_name().lower(),
            'webhook_url': f'/webhooks/{self.get_platform_name().lower()}',
            'verify_token': self.verify_token,
            'api_version': self.api_version
        }