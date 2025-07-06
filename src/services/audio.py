import os
import uuid
from ..core.logger import get_logger
from typing import Any
from linebot.v3.messaging import TextMessage

from ..models.base import FullLLMInterface
from ..core.exceptions import OpenAIError
from ..core.error_handler import ErrorHandler
from .chat import CoreChatService

logger = get_logger(__name__)


class AudioService:
    def __init__(self, model: FullLLMInterface, chat_service: CoreChatService):
        self.model = model
        self.chat_service = chat_service
        self.error_handler = ErrorHandler()
    
    def handle_audio_message(self, user_id: str, audio_content: bytes, platform: str = 'line') -> TextMessage:
        """處理音訊訊息"""
        input_audio_path = None
        
        try:
            # 儲存音訊檔案
            input_audio_path = self._save_audio_file(audio_content)
            
            # 轉錄音訊
            text = self._transcribe_audio(input_audio_path)
            logger.info(f"Audio transcribed for user {user_id}: {text}")
            
            # 使用聊天服務處理轉錄文字
            return self.chat_service.handle_message(user_id, text, platform)
            
        except Exception as e:
            logger.error(f"Error processing audio for user {user_id}: {e}")
            return self.error_handler.handle_error(e)
        
        finally:
            # 清理臨時檔案
            if input_audio_path and os.path.exists(input_audio_path):
                try:
                    os.remove(input_audio_path)
                    logger.debug(f"Cleaned up audio file: {input_audio_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean up audio file {input_audio_path}: {e}")
    
    def _save_audio_file(self, audio_content: bytes) -> str:
        """儲存音訊檔案到臨時位置"""
        try:
            input_audio_path = f'{str(uuid.uuid4())}.m4a'
            with open(input_audio_path, 'wb') as fd:
                fd.write(audio_content)
            logger.debug(f"Audio file saved: {input_audio_path}")
            return input_audio_path
        except Exception as e:
            raise OpenAIError(f"Failed to save audio file: {e}")
    
    def _transcribe_audio(self, input_audio_path: str) -> str:
        """轉錄音訊檔案 - 使用統一接口"""
        try:
            # 使用統一的音訊轉錄接口
            is_successful, transcribed_text, error_message = self.model.transcribe_audio(
                input_audio_path, 
                model='whisper-1'  # 各模型可以有不同的參數處理方式
            )
            
            if not is_successful:
                raise OpenAIError(f"Audio transcription failed: {error_message}")
            
            logger.info(f"Audio transcription resutl: {transcribed_text}")
            return transcribed_text
            
        except Exception as e:
            if isinstance(e, OpenAIError):
                raise
            raise OpenAIError(f"Audio transcription error: {e}")