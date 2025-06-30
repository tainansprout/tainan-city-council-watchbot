import time
import logging
from typing import Dict, Any, Optional
from linebot.v3.messaging import TextMessage

from ..models.base import FullLLMInterface
from ..database import Database
from ..utils import preprocess_text, postprocess_text, get_content_and_reference, detect_none_references, get_file_dict
from ..core.exceptions import OpenAIError, DatabaseError, ThreadError
from ..core.error_handler import ErrorHandler

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self, model: FullLLMInterface, database: Database, config: Dict[str, Any]):
        self.model = model
        self.database = database
        self.config = config
        self.error_handler = ErrorHandler()
        self.file_dict = {}
        self._refresh_file_dict()
    
    def handle_message(self, user_id: str, text: str) -> TextMessage:
        """主要訊息處理入口"""
        try:
            logger.info(f'{user_id}: {text}')
            
            if text.startswith('/'):
                return self._handle_command(user_id, text)
            else:
                return self._handle_chat_message(user_id, text)
                
        except Exception as e:
            logger.error(f"Error handling message for user {user_id}: {e}")
            return self.error_handler.handle_error(e)
    
    def _handle_command(self, user_id: str, text: str) -> TextMessage:
        """處理指令"""
        if text.startswith('/reset'):
            return self._handle_reset_command(user_id)
        
        command = text[1:].split()[0]
        if command in self.config.get('commands', {}):
            return TextMessage(text=self.config['commands'][command] + "\n\n")
        else:
            return TextMessage(text="Command not found.")
    
    def _handle_reset_command(self, user_id: str) -> TextMessage:
        """處理重置指令"""
        try:
            thread_id = self.database.query_thread(user_id)
            if thread_id:
                self.model.delete_thread(thread_id)
                self.database.delete_thread(user_id)
                return TextMessage(text='Reset The Chatbot.')
            else:
                return TextMessage(text='Nothing to reset.')
        except Exception as e:
            logger.error(f"Error resetting thread for user {user_id}: {e}")
            raise ThreadError(f"Failed to reset thread: {e}")
    
    def _handle_chat_message(self, user_id: str, text: str) -> TextMessage:
        """處理聊天訊息"""
        try:
            # 預處理文字
            processed_text = preprocess_text(text, self.config)
            
            # 取得或建立對話串
            thread_id = self._get_or_create_thread(user_id)
            
            # 處理對話
            response_message = self._process_conversation(thread_id, processed_text)
            
            # 後處理回應
            final_response = postprocess_text(response_message, self.config)
            
            return TextMessage(text=final_response)
            
        except Exception as e:
            logger.error(f"Error processing chat message for user {user_id}: {e}")
            raise
    
    def _get_or_create_thread(self, user_id: str) -> str:
        """取得或建立對話串"""
        try:
            thread_id = self.database.query_thread(user_id)
            
            if thread_id:
                # 驗證現有對話串
                is_successful, response, error_message = self.model.retrieve_thread(thread_id)
                if not is_successful:
                    logger.warning(f"Thread {thread_id} is invalid, creating new thread")
                    self.database.delete_thread(user_id)
                    thread_id = None
            
            if not thread_id:
                # 建立新對話串
                is_successful, response, error_message = self.model.create_thread()
                if not is_successful:
                    raise OpenAIError(f"Failed to create thread: {error_message}")
                
                thread_id = response.thread_id
                self.database.save_thread(user_id, thread_id)
                logger.debug(f'Created new thread: {thread_id}')
            
            return thread_id
            
        except Exception as e:
            if isinstance(e, (OpenAIError, DatabaseError)):
                raise
            raise ThreadError(f"Failed to get or create thread: {e}")
    
    def _process_conversation(self, thread_id: str, text: str) -> str:
        """處理對話邏輯（支援不同模型的 RAG）"""
        try:
            # 使用統一的 RAG 介面
            is_successful, rag_response, error_message = self.model.query_with_rag(
                query=text, 
                thread_id=thread_id
            )
            
            if not is_successful:
                raise OpenAIError(f"RAG query failed: {error_message}")
            
            # 如果是 OpenAI Assistant API，使用舊版的引用處理
            if hasattr(self.model, 'assistant_id') and self.model.assistant_id:
                thread_messages = rag_response.metadata.get('thread_messages')
                if thread_messages:
                    # 使用舊版的 get_content_and_reference 處理引用格式
                    formatted_response = get_content_and_reference(thread_messages, self.file_dict)
                    
                    # 檢查是否有無效的檔案引用
                    if detect_none_references(formatted_response):
                        logger.info("Refreshing file dictionary due to invalid references")
                        self._refresh_file_dict()
                        formatted_response = get_content_and_reference(thread_messages, self.file_dict)
                    
                    return formatted_response
            
            # 其他模型的處理方式
            if rag_response.sources:
                source_text = self._format_sources(rag_response.sources)
                return f"{rag_response.answer}\n\n{source_text}"
            else:
                return rag_response.answer
                
        except Exception as e:
            if isinstance(e, OpenAIError):
                raise
            raise OpenAIError(f"Conversation processing failed: {e}")
    
    def _format_sources(self, sources: list) -> str:
        """格式化來源引用"""
        if not sources:
            return ""
        
        source_lines = []
        for i, source in enumerate(sources, 1):
            # 處理不同模型的來源格式
            filename = None
            
            if isinstance(source, dict):
                # 優先使用 filename
                if 'filename' in source:
                    filename = source['filename']
                # 其次使用 file_id 查詢
                elif 'file_id' in source and self.file_dict:
                    file_id = source['file_id']
                    filename = self.file_dict.get(file_id)
                # 最後使用 file_id 的簡短顯示
                elif 'file_id' in source:
                    file_id = source['file_id']
                    if isinstance(file_id, str) and len(file_id) > 8:
                        filename = f"File-{file_id[:8]}"
                    else:
                        filename = f"File-{file_id}"
            
            # 如果仍然沒有檔案名稱，使用預設值
            if not filename:
                filename = f"Source-{i}"
            
            # 移除副檔名並清理檔案名稱
            display_name = filename.replace('.txt', '').replace('.json', '').replace('.csv', '')
            
            source_lines.append(f"[{i}]: {display_name}")
        
        return '\n'.join(source_lines)
    
    def _wait_for_completion(self, thread_id: str, response: Dict[str, Any]) -> Dict[str, Any]:
        """等待 OpenAI 回應完成"""
        max_wait_time = 120  # 最大等待時間 2 分鐘
        start_time = time.time()
        
        while response['status'] not in ['completed', 'failed', 'expired', 'cancelled']:
            if time.time() - start_time > max_wait_time:
                raise OpenAIError("Request timeout")
            
            run_id = response['id']
            
            # 根據狀態調整等待時間
            if response['status'] == 'queued':
                time.sleep(10)
            else:
                time.sleep(3)
            
            is_successful, response, error_message = self.model.retrieve_thread_run(thread_id, run_id)
            if not is_successful:
                raise OpenAIError(f"Failed to retrieve run status: {error_message}")
            
            logger.debug(f"Run {run_id} status: {response['status']}")
        
        return response
    
    def _get_assistant_response(self, thread_id: str) -> str:
        """取得助理回應"""
        try:
            is_successful, response, error_message = self.model.list_thread_messages(thread_id)
            if not is_successful:
                raise OpenAIError(f"Failed to get messages: {error_message}")
            
            response_message = get_content_and_reference(response, self.file_dict)
            
            # 檢查是否有無效的檔案引用
            if detect_none_references(response_message):
                logger.info("Refreshing file dictionary due to invalid references")
                self._refresh_file_dict()
                response_message = get_content_and_reference(response, self.file_dict)
            
            return response_message
            
        except Exception as e:
            if isinstance(e, OpenAIError):
                raise
            raise OpenAIError(f"Failed to get assistant response: {e}")
    
    def _refresh_file_dict(self):
        """更新檔案字典（只對需要的模型）"""
        try:
            # 只有 OpenAI Assistant API 需要檔案字典
            if hasattr(self.model, 'assistant_id') and self.model.assistant_id:
                self.file_dict = get_file_dict(self.model)
                logger.debug("File dictionary refreshed for OpenAI Assistant")
            else:
                # 其他模型不需要檔案字典
                self.file_dict = {}
                logger.debug("File dictionary not needed for this model type")
        except Exception as e:
            logger.error(f"Failed to refresh file dictionary: {e}")
            self.file_dict = {}