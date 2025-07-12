"""
Webhook 相關的工具函數
統一的 Meta (Facebook/Messenger/Instagram/WhatsApp) webhook 驗證模組
"""
import hmac
import hashlib
from typing import Optional

def verify_meta_signature(app_secret: str, request_body: bytes, signature: Optional[str]) -> bool:
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

def verify_meta_signature_legacy(app_secret: str, request_body: str, signature: Optional[str]) -> bool:
    """
    舊版 Meta webhook 簽名驗證（使用 string body）
    主要用於相容性支援
    """
    if isinstance(request_body, str):
        request_body = request_body.encode('utf-8')
    return verify_meta_signature(app_secret, request_body, signature)
