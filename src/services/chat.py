"""
核心聊天服務 - 平台無關的聊天邏輯
"""
import time
import os
import sys
from ..core.logger import get_logger
from typing import Dict, Any, Optional, Tuple
from ..models.base import FullLLMInterface, ModelProvider, RAGResponse
from ..database.connection import Database
from ..utils import preprocess_text, postprocess_text
from ..core.exceptions import ChatBotError, DatabaseError, ThreadError
from ..core.error_handler import ErrorHandler
from .response import ResponseFormatter
from ..platforms.base import PlatformMessage, PlatformResponse, PlatformUser

logger = get_logger(__name__)


class ChatService:
    """
    核心聊天服務 - 處理平台無關的聊天邏輯
    
    這個服務專注於：
    1. 模型交互
    2. 對話歷史管理  
    3. 文字處理
    4. 錯誤處理
    
    不包含任何平台特定的邏輯
    """
    
    def __init__(self, model: FullLLMInterface, database: Database, config: Dict[str, Any]):
        self.model = model
        self.database = database
        self.config = config
        self.error_handler = ErrorHandler()
        self.response_formatter = ResponseFormatter(config)
        try:
            provider = model.get_provider()
            provider_name = provider.value if hasattr(provider, 'value') else str(provider)
            logger.info(f"ChatService initialized with model: {provider_name}")
        except (ValueError, AttributeError):
            pass
    
    def handle_message(self, message: PlatformMessage) -> PlatformResponse:
        """
        處理平台訊息並返回統一的回應格式
        
        Args:
            message: 統一格式的平台訊息
            
        Returns:
            PlatformResponse: 統一格式的回應
        """
        user = message.user
        platform = user.platform.value
        try:
            logger.info(f'Processing message from {user.user_id} on {platform}: {message.content}')
        except Exception as e:
            # 如果 logger 失敗，至少在開發模式下印出到 stderr
            if os.getenv('DEV_MODE') == 'true':
                print(f"Logger error in handle_message: {e}", file=sys.stderr)

        # 處理不同類型的訊息
        if message.message_type == "text":
            return self._handle_text_message(user, message.content, platform)
        elif message.message_type == "audio":
            # 音訊處理由應用層的 AudioService 處理，ChatService 不應該接收到音訊訊息
            return PlatformResponse(
                content="系統錯誤：音訊訊息應由應用層處理。",
                response_type="text"
            )
        else:
            return PlatformResponse(
                content="抱歉，暫不支援此類型的訊息。",
                response_type="text"
            )
    
    def _handle_text_message(self, user: PlatformUser, text: str, platform: str) -> PlatformResponse:
        """處理文字訊息"""
        try:
            if text.startswith('/'):
                return self._handle_command(user, text, platform)
            else:
                return self._handle_chat_message(user, text, platform)
                
        except Exception as e:
            # 記錄詳細的錯誤 log
            try:
                logger.error(f"Error handling text message for user {user.user_id}: {type(e).__name__}: {e}")
            except Exception as log_err:
                if os.getenv('DEV_MODE') == 'true':
                    print(f"Logger error in _handle_text_message: {log_err}", file=sys.stderr)
            try:
                logger.error(f"Error details - Platform: {platform}, Message: {text[:100]}...")
            except Exception as log_err:
                if os.getenv('DEV_MODE') == 'true':
                    print(f"Logger error in _handle_text_message details: {log_err}", file=sys.stderr)
            
            # 檢查是否為測試用戶（來自 /chat 介面）
            is_test_user = user.user_id.startswith("U" + "0" * 32)
            
            if is_test_user:
                # 測試用戶：拋出異常讓上層 /ask 端點處理，顯示詳細錯誤
                raise
            else:
                # 實際平台用戶：使用簡化錯誤訊息
                error_message = self.error_handler.get_error_message(e, use_detailed=False)
                return PlatformResponse(
                    content=error_message,
                    response_type="text"
                )
    
    def _handle_command(self, user: PlatformUser, text: str, platform: str) -> PlatformResponse:
        """處理指令"""
        if text.startswith('/reset'):
            return self._handle_reset_command(user, platform)
        
        command = text[1:].split()[0]
        commands_config = self.config.get('commands', {})
        if command in commands_config:
            return PlatformResponse(
                content=commands_config[command] + "\n\n",
                response_type="text"
            )
        else:
            return PlatformResponse(
                content="Command not found.",
                response_type="text"
            )
    
    def _handle_reset_command(self, user: PlatformUser, platform: str) -> PlatformResponse:
        """處理重置指令 - 支援不同模型的重置策略"""
        try:
            # 使用統一接口清除對話歷史，thread_id 管理由模型層管理
            is_successful, error_message = self.model.clear_user_history(user.user_id, platform)
            if is_successful:
                return PlatformResponse(content='Reset The Chatbot.', response_type="text")
            else:
                try:
                    logger.warning(f"Failed to clear history for user {user.user_id}: {error_message}")
                except Exception as log_err:
                    if os.getenv('DEV_MODE') == 'true':
                        print(f"Logger error in _handle_reset_command: {log_err}", file=sys.stderr)
                return PlatformResponse(content='Reset completed (with warnings).', response_type="text")
        except Exception as e:
            try:
                logger.error(f"Error resetting for user {user.user_id}: {e}")
            except Exception as log_err:
                if os.getenv('DEV_MODE') == 'true':
                    print(f"Logger error in _handle_reset_command exception: {log_err}", file=sys.stderr)
            raise ThreadError(f"Failed to reset: {e}")
    
    def _handle_chat_message(self, user: PlatformUser, text: str, platform: str) -> PlatformResponse:
        """處理聊天訊息 - 支援統一接口和不同模型的對話管理策略"""
        try:
            # 預處理文字
            processed_text = preprocess_text(text, self.config)
            
            # 使用統一的對話處理邏輯，thread_id 等由模型層管理
            rag_response = self._process_conversation(user, processed_text, platform)
            
            # 格式化並後處理回應
            formatted_response = self.response_formatter.format_rag_response(rag_response)
            final_response = postprocess_text(formatted_response, self.config)
            
            try:
                logger.info(f'Response message to {user.user_id} on {platform}: {final_response}')
            except Exception as log_err:
                if os.getenv('DEV_MODE') == 'true':
                    print(f"Logger error in _handle_chat_message response: {log_err}", file=sys.stderr)

            # 🔥 提取 MCP 互動資訊，如果存在的話
            mcp_interactions = None
            if rag_response and rag_response.metadata:
                mcp_interactions = rag_response.metadata.get('mcp_interactions')
            
            return PlatformResponse(
                content=final_response,
                response_type="text",
                metadata={
                    "mcp_interactions": mcp_interactions
                } if mcp_interactions else None
            )
            
        except Exception as e:
            # 記錄詳細的錯誤 log
            try:
                logger.error(f"Error processing chat message for user {user.user_id}: {type(e).__name__}: {e}")
            except Exception as log_err:
                if os.getenv('DEV_MODE') == 'true':
                    print(f"Logger error in _handle_chat_message: {log_err}", file=sys.stderr)
            try:
                logger.error(f"Error details - Platform: {platform}, Processed text: {text[:100]}...")
            except Exception as log_err:
                if os.getenv('DEV_MODE') == 'true':
                    print(f"Logger error in _handle_chat_message details: {log_err}", file=sys.stderr)
            raise
    
    def _process_conversation(self, user: PlatformUser, text: str, platform: str) -> RAGResponse:
        """處理對話邏輯 - 使用統一的 chat_with_user 接口，thread_id 由模型層管理"""
        try:
            is_successful, rag_response, error_message = self.model.chat_with_user(
                user_id=user.user_id,
                message=text,
                platform=platform
            )
            if not is_successful:
                # 檢查原始錯誤訊息，保留原始錯誤類型
                if error_message and 'database' in error_message.lower():
                    raise DatabaseError(error_message)
                elif error_message and ('column' in error_message.lower() or 'sql' in error_message.lower()):
                    raise DatabaseError(error_message)
                else:
                    raise ChatBotError(f"Chat with user failed: {error_message}")
            
            try:
                formatted_response = self.response_formatter.format_rag_response(rag_response)
                logger.debug(f"Processed conversation response length: {len(formatted_response)}")
            except Exception as log_err:
                if os.getenv('DEV_MODE') == 'true':
                    print(f"Logger error in _process_conversation: {log_err}", file=sys.stderr)
            
            return rag_response
        except Exception as e:
            if isinstance(e, (ChatBotError, DatabaseError)):
                raise
            # 檢查是否為資料庫相關錯誤
            error_str = str(e).lower()
            if ('database' in error_str or 'sql' in error_str or 'column' in error_str or 
                'psycopg' in error_str or 'table' in error_str):
                raise DatabaseError(f"Database operation failed: {e}")
            raise ChatBotError(f"Conversation processing failed: {e}")