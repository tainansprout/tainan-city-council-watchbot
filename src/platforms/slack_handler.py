"""
Slack 平台處理器
使用 Slack Bolt for Python 2024 最新版本，支援最新的 Slack API 和事件處理
"""
import json
import hmac
import hashlib
import time
from typing import List, Optional, Any, Dict
from urllib.parse import parse_qs
from ..core.logger import get_logger

try:
    from slack_bolt import App, BoltRequest, BoltResponse
    from slack_bolt.adapter.flask import SlackRequestHandler
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
    SLACK_AVAILABLE = True
except ImportError:
    SLACK_AVAILABLE = False

from .base import BasePlatformHandler, PlatformType, PlatformUser, PlatformMessage, PlatformResponse

logger = get_logger(__name__)


class SlackHandler(BasePlatformHandler):
    """
    Slack 平台處理器
    使用 Slack Bolt 框架的最新架構，支援事件 API 和互動式組件
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        if not SLACK_AVAILABLE:
            logger.error("slack-bolt not installed. Install with: pip install slack-bolt")
            return
            
        self.bot_token = self.get_config('bot_token')
        self.signing_secret = self.get_config('signing_secret')
        self.app_token = self.get_config('app_token', '')  # 用於 Socket Mode
        
        # 初始化 Slack app 和客戶端
        self.app = None
        self.client = None
        self.request_handler = None
        
        if self.is_enabled() and self.validate_config():
            self._setup_slack_app()
            logger.info("Slack handler initialized")
        elif self.is_enabled():
            logger.error("Slack handler initialization failed due to invalid config")
    
    def get_platform_type(self) -> PlatformType:
        return PlatformType.SLACK
    
    def get_required_config_fields(self) -> List[str]:
        return ['bot_token', 'signing_secret']
    
    def _setup_slack_app(self):
        """設置 Slack 應用程式"""
        try:
            # 創建 Slack Bolt App
            self.app = App(
                token=self.bot_token,
                signing_secret=self.signing_secret,
                process_before_response=True  # 在回應前處理事件
            )
            
            # 創建 Web Client
            self.client = WebClient(token=self.bot_token)
            
            # 創建 Flask 請求處理器
            self.request_handler = SlackRequestHandler(self.app)
            
            # 註冊事件處理器
            self._register_event_handlers()
            
            logger.info("Slack app setup completed")
            
        except Exception as e:
            logger.error(f"Error setting up Slack app: {e}")
            self.app = None
            self.client = None
    
    def _register_event_handlers(self):
        """註冊 Slack 事件處理器"""
        if not self.app:
            return
        
        # 處理應用程式提及 (@botname message)
        @self.app.event("app_mention")
        def handle_app_mention(event, say, logger):
            # 這個事件會被 webhook 處理流程處理
            pass
        
        # 處理直接訊息
        @self.app.event("message")
        def handle_message_events(event, say, logger):
            # 這個事件會被 webhook 處理流程處理
            pass
        
        logger.debug("Slack event handlers registered")
    
    def parse_message(self, slack_event: Any) -> Optional[PlatformMessage]:
        """解析 Slack 事件為統一格式"""
        if not isinstance(slack_event, dict):
            return None
        
        # 處理事件包裝
        event_data = slack_event
        if 'event' in slack_event:
            event_data = slack_event['event']
        
        # 檢查是否為訊息事件
        if event_data.get('type') not in ['message', 'app_mention']:
            return None
        
        # 忽略 bot 訊息和子類型訊息（如檔案分享等）
        if event_data.get('subtype') or event_data.get('bot_id'):
            return None
        
        user_id = event_data.get('user')
        if not user_id:
            return None
        
        # 取得用戶資訊
        user_info = self._get_user_info(user_id)
        
        user = PlatformUser(
            user_id=user_id,
            platform=PlatformType.SLACK,
            display_name=user_info.get('display_name', user_info.get('real_name', 'Unknown')),
            username=user_info.get('name', user_id),
            metadata={
                'team_id': event_data.get('team'),
                'channel_id': event_data.get('channel'),
                'channel_type': event_data.get('channel_type'),
                'is_bot': user_info.get('is_bot', False),
                'timezone': user_info.get('tz'),
                'profile': user_info.get('profile', {})
            }
        )
        
        message_text = event_data.get('text', '')
        message_ts = event_data.get('ts', '')
        
        # 處理應用程式提及（移除 bot 提及）
        if event_data.get('type') == 'app_mention':
            # 移除 <@BOTID> 提及
            import re
            message_text = re.sub(r'<@\w+>\s*', '', message_text).strip()
        
        # 檢查是否為語音訊息或音訊檔案
        files = event_data.get('files', [])
        for file_info in files:
            if file_info.get('mimetype', '').startswith('audio/'):
                try:
                    audio_content = self._download_slack_file(file_info)
                    
                    return PlatformMessage(
                        message_id=message_ts,
                        user=user,
                        content="[Audio Message]",
                        message_type="audio",
                        raw_data=audio_content,
                        metadata={
                            'slack_event': slack_event,
                            'channel_id': event_data.get('channel'),
                            'thread_ts': event_data.get('thread_ts'),
                            'file_info': file_info
                        }
                    )
                except Exception as e:
                    logger.error(f"Error downloading Slack audio file: {e}")
        
        # 處理文字訊息
        if message_text:
            return PlatformMessage(
                message_id=message_ts,
                user=user,
                content=message_text,
                message_type="text",
                metadata={
                    'slack_event': slack_event,
                    'channel_id': event_data.get('channel'),
                    'thread_ts': event_data.get('thread_ts'),
                    'event_ts': event_data.get('event_ts')
                }
            )
        
        return None
    
    def _get_user_info(self, user_id: str) -> Dict[str, Any]:
        """取得 Slack 用戶資訊"""
        try:
            if self.client:
                response = self.client.users_info(user=user_id)
                return response['user']
        except Exception as e:
            logger.error(f"Error getting Slack user info: {e}")
        except Exception as e:
            logger.error(f"Unexpected error getting user info: {e}")
        
        return {'name': user_id, 'real_name': 'Unknown User'}
    
    def _download_slack_file(self, file_info: Dict[str, Any]) -> bytes:
        """下載 Slack 檔案"""
        try:
            if self.client:
                # 使用 Slack API 下載檔案
                file_url = file_info.get('url_private_download') or file_info.get('url_private')
                if file_url:
                    import requests
                    headers = {'Authorization': f'Bearer {self.bot_token}'}
                    response = requests.get(file_url, headers=headers)
                    response.raise_for_status()
                    return response.content
        except Exception as e:
            logger.error(f"Error downloading Slack file: {e}")
        
        return b''
    
    def send_response(self, response: PlatformResponse, message: PlatformMessage) -> bool:
        """發送回應到 Slack"""
        if not self.client:
            logger.error("Slack client not initialized")
            return False
        
        try:
            channel_id = message.metadata.get('channel_id')
            if not channel_id:
                logger.error("No channel_id in message metadata")
                return False
            
            # 準備訊息參數
            message_args = {
                'channel': channel_id,
                'text': response.content
            }
            
            # 如果是回覆訊息，設置 thread_ts
            thread_ts = message.metadata.get('thread_ts')
            if thread_ts:
                message_args['thread_ts'] = thread_ts
            elif message.message_id:
                # 如果沒有 thread_ts 但有原始訊息 ID，作為新 thread 回覆
                message_args['thread_ts'] = message.message_id
            
            # 檢查訊息長度（Slack 限制）
            if len(response.content) > 4000:
                # 分割長訊息
                chunks = [response.content[i:i+4000] for i in range(0, len(response.content), 4000)]
                for i, chunk in enumerate(chunks):
                    chunk_args = message_args.copy()
                    chunk_args['text'] = chunk
                    if i > 0:
                        # 後續消息作為 thread 回覆
                        chunk_args['thread_ts'] = message_args.get('thread_ts', message.message_id)
                    
                    result = self.client.chat_postMessage(**chunk_args)
                    if not result.get('ok'):
                        logger.error(f"Failed to send Slack message chunk {i}: {result}")
                        return False
            else:
                # 支援 Markdown 格式
                message_args['mrkdwn'] = True
                
                result = self.client.chat_postMessage(**message_args)
                if not result.get('ok'):
                    logger.error(f"Failed to send Slack message: {result}")
                    return False
            
            logger.debug(f"Sent Slack message to channel {channel_id}")
            return True
            
        except Exception as e:
            logger.error(f"Slack API error sending response: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending Slack response: {e}")
            return False
    
    def handle_webhook(self, request_body: str, signature: str) -> List[PlatformMessage]:
        """處理 Slack webhook"""
        if not self.app or not self.request_handler:
            logger.error("Slack app not initialized")
            return []
        
        messages = []
        
        try:
            # 驗證 Slack 請求簽名
            if not self._verify_slack_signature(request_body, signature):
                logger.warning("Invalid Slack webhook signature")
                return []
            
            # 處理不同類型的 Slack 請求
            try:
                # 嘗試解析為 JSON（事件 API）
                webhook_data = json.loads(request_body)
                
                # 處理 URL 驗證挑戰
                if webhook_data.get('type') == 'url_verification':
                    logger.info("Slack URL verification challenge received")
                    return []  # URL 驗證不產生訊息
                
                # 處理事件
                if webhook_data.get('type') == 'event_callback':
                    parsed_message = self.parse_message(webhook_data)
                    if parsed_message:
                        messages.append(parsed_message)
                
            except json.JSONDecodeError:
                # 可能是表單編碼的請求（互動式組件）
                try:
                    from urllib.parse import parse_qs
                    form_data = parse_qs(request_body)
                    if 'payload' in form_data:
                        payload = json.loads(form_data['payload'][0])
                        # 處理互動式組件（按鈕、選單等）
                        logger.debug(f"Received Slack interactive payload: {payload.get('type')}")
                        # 這裡可以擴展處理互動式組件
                except Exception as e:
                    logger.error(f"Error parsing Slack form data: {e}")
        
        except Exception as e:
            logger.error(f"Error processing Slack webhook: {e}")
        
        return messages
    
    def _verify_slack_signature(self, request_body: str, signature: str) -> bool:
        """驗證 Slack 請求簽名"""
        if not self.signing_secret or not signature:
            return False
        
        try:
            # Slack 簽名驗證
            timestamp = str(int(time.time()))
            
            # 如果簽名包含時間戳，提取它
            if '=' in signature:
                signature_parts = signature.split('=')
                if len(signature_parts) == 2:
                    signature = signature_parts[1]
            
            # 構建簽名字符串
            sig_basestring = f'v0:{timestamp}:{request_body}'
            
            # 計算 HMAC
            my_signature = hmac.new(
                self.signing_secret.encode(),
                sig_basestring.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # 比較簽名
            return hmac.compare_digest(my_signature, signature)
            
        except Exception as e:
            logger.error(f"Error verifying Slack signature: {e}")
            return False
    
    def get_app_info(self) -> Optional[Dict[str, Any]]:
        """取得 Slack 應用資訊"""
        if not self.client:
            return None
        
        try:
            auth_response = self.client.auth_test()
            if auth_response.get('ok'):
                return {
                    'user_id': auth_response.get('user_id'),
                    'team': auth_response.get('team'),
                    'team_id': auth_response.get('team_id'),
                    'user': auth_response.get('user'),
                    'bot_id': auth_response.get('bot_id')
                }
        except Exception as e:
            logger.error(f"Error getting Slack app info: {e}")
        except Exception as e:
            logger.error(f"Unexpected error getting app info: {e}")
        
        return None
    
    def create_bolt_request(self, flask_request):
        """創建 Bolt 請求物件（用於 Flask 整合）"""
        if not self.request_handler:
            raise ValueError("Slack request handler not initialized")
        
        if not SLACK_AVAILABLE:
            return None
            
        return BoltRequest(
            body=flask_request.get_data(as_text=True),
            headers=dict(flask_request.headers),
            mode='http'
        )
    
    def handle_bolt_request(self, bolt_request):
        """處理 Bolt 請求（用於 Flask 整合）"""
        if not self.app:
            raise ValueError("Slack app not initialized")
        
        return self.app.dispatch(bolt_request)


# Slack 特定的工具函數
class SlackUtils:
    """Slack 相關的工具函數"""
    
    @staticmethod
    def escape_slack_text(text: str) -> str:
        """轉義 Slack 特殊字符"""
        replacements = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;'
        }
        for char, replacement in replacements.items():
            text = text.replace(char, replacement)
        return text
    
    @staticmethod
    def format_user_mention(user_id: str) -> str:
        """格式化用戶提及"""
        return f'<@{user_id}>'
    
    @staticmethod
    def format_channel_mention(channel_id: str) -> str:
        """格式化頻道提及"""
        return f'<#{channel_id}>'
    
    @staticmethod
    def format_link(url: str, text: str = None) -> str:
        """格式化連結"""
        if text:
            return f'<{url}|{text}>'
        return f'<{url}>'
    
    @staticmethod
    def create_blocks(elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """創建 Slack 區塊格式"""
        return elements
    
    @staticmethod
    def create_text_block(text: str, block_type: str = "section") -> Dict[str, Any]:
        """創建文字區塊"""
        return {
            "type": block_type,
            "text": {
                "type": "mrkdwn",
                "text": text
            }
        }


def get_slack_utils():
    """取得 Slack 工具函數"""
    return SlackUtils