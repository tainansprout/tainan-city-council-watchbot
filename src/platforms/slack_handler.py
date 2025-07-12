"""
Slack 平台處理器
使用 Slack Bolt for Python 2024 最新版本，支援最新的 Slack API 和事件處理
"""
import json
from typing import List, Optional, Any, Dict
from ..core.logger import get_logger

try:
    from slack_bolt import App
    from slack_bolt.adapter.flask import SlackRequestHandler
    from slack_bolt.request import BoltRequest
    from slack_sdk import WebClient
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
            self.app = App(
                token=self.bot_token,
                signing_secret=self.signing_secret,
                process_before_response=True
            )
            self.client = WebClient(token=self.bot_token)
            self.request_handler = SlackRequestHandler(self.app)
            self._register_event_handlers()
            logger.info("Slack app setup completed")
        except Exception as e:
            logger.error(f"Error setting up Slack app: {e}")
            self.app = self.client = self.request_handler = None

    def _register_event_handlers(self):
        """註冊 Slack 事件處理器"""
        if not self.app:
            return

        @self.app.event("message")
        def handle_message_events(event, say):
            # Webhook 處理流程會調用 parse_message，這裡不需要實作
            pass
        
        logger.debug("Slack event handlers registered")

    def parse_message(self, slack_event: Any) -> Optional[PlatformMessage]:
        """解析 Slack 事件為統一格式"""
        if not isinstance(slack_event, dict):
            return None
        
        event_data = slack_event.get('event', slack_event)
        if event_data.get('type') not in ['message', 'app_mention'] or event_data.get('bot_id'):
            return None

        user_id = event_data.get('user')
        if not user_id:
            return None

        user_info = self._get_user_info(user_id)
        user = PlatformUser(
            user_id=user_id,
            platform=PlatformType.SLACK,
            display_name=user_info.get('display_name', user_info.get('real_name', 'Unknown')),
            username=user_info.get('name', user_id),
            metadata={
                'team_id': event_data.get('team'),
                'channel_id': event_data.get('channel'),
                'is_bot': user_info.get('is_bot', False)
            }
        )

        message_ts = event_data.get('ts', '')
        content = event_data.get('text', '')
        message_type = "text"
        raw_data = None

        if event_data.get('type') == 'app_mention':
            import re
            content = re.sub(r'<@\w+>\s*', '', content).strip()

        files = event_data.get('files', [])
        for file_info in files:
            if file_info.get('mimetype', '').startswith('audio/'):
                message_type = "audio"
                try:
                    audio_content = self._download_slack_file(file_info)
                    content = "[Audio Message]"
                    raw_data = audio_content
                    logger.debug(f"[SLACK] Audio message from {user.user_id}, size: {len(audio_content)} bytes")
                except Exception as e:
                    logger.error(f"Error downloading Slack audio: {e}")
                    content = "[Audio Message - Download Failed]"
                    raw_data = None
                break # 只處理第一個音訊檔案

        return PlatformMessage(
            message_id=message_ts,
            user=user,
            content=content,
            message_type=message_type,
            raw_data=raw_data,
            metadata={
                'slack_event': slack_event,
                'channel_id': event_data.get('channel'),
                'thread_ts': event_data.get('thread_ts')
            }
        )

    def _get_user_info(self, user_id: str) -> Dict[str, Any]:
        """取得 Slack 用戶資訊"""
        try:
            if self.client:
                response = self.client.users_info(user=user_id)
                return response['user']
        except Exception as e:
            logger.error(f"Error getting Slack user info: {e}")
        return {'name': user_id, 'real_name': 'Unknown User'}

    def _download_slack_file(self, file_info: Dict[str, Any]) -> bytes:
        """下載 Slack 檔案"""
        if not self.client:
            return b''
        file_url = file_info.get('url_private_download')
        if not file_url:
            return b''
        import requests
        headers = {'Authorization': f'Bearer {self.bot_token}'}
        try:
            response = requests.get(file_url, headers=headers)
            response.raise_for_status()
            return response.content
        except requests.RequestException as e:
            logger.error(f"Error downloading Slack file: {e}")
            return b''

    def send_response(self, response: PlatformResponse, message: PlatformMessage) -> bool:
        """發送回應到 Slack"""
        if not self.client:
            logger.error("Slack client not initialized")
            return False
        
        channel_id = message.metadata.get('channel_id')
        if not channel_id:
            logger.error("No channel_id in message metadata")
            return False

        try:
            message_args = {
                'channel': channel_id,
                'text': response.content,
                'thread_ts': message.metadata.get('thread_ts') or message.message_id
            }
            self.client.chat_postMessage(**message_args)
            logger.debug(f"Sent Slack message to channel {channel_id}")
            return True
        except Exception as e:
            logger.error(f"Error sending Slack response: {e}")
            return False

    def handle_webhook(self, request_body: str, headers: Dict[str, str]) -> List[PlatformMessage]:
        """
        處理 Slack webhook。
        使用 slack-bolt 的 SlackRequestHandler 進行驗證。
        """
        if not self.request_handler:
            logger.error("Slack request handler not initialized")
            return []

        # 建立 BoltRequest 以便驗證
        bolt_req = BoltRequest(body=request_body, headers=headers)

        # 驗證請求
        if not self.request_handler.app.authenticator.is_valid(bolt_req):
            logger.warning("Invalid Slack webhook signature.")
            return []

        try:
            webhook_data = json.loads(request_body)
            
            # URL 驗證
            if webhook_data.get('type') == 'url_verification':
                logger.info("Slack URL verification challenge received.")
                # 實際的 challenge 回應應由 app 層處理
                return []

            # 處理事件回調
            if webhook_data.get('type') == 'event_callback':
                message = self.parse_message(webhook_data)
                return [message] if message else []

        except json.JSONDecodeError:
            logger.error("Error decoding Slack webhook JSON")
        except Exception as e:
            logger.error(f"Error processing Slack webhook: {e}")
        
        return []
    
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