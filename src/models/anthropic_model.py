"""
Anthropic Claude Model 實作
使用 Anthropic Messages API 提供聊天功能

📋 架構職責分工：
✅ RESPONSIBILITIES (模型層職責):
  - 實作統一的 FullLLMInterface 接口
  - 提供 chat_with_user() 文字對話功能
  - 提供 transcribe_audio() 音訊轉錄功能 (透過外部服務)
  - 管理對話歷史和上下文
  - 處理 Anthropic API 限流和重試邏輯

❌ NEVER DO (絕對禁止):
  - 知道訊息來源平台 (LINE、Telegram 等)
  - 處理平台特定的訊息格式
  - 直接處理 webhook 或網路請求
  - 路由訊息或協調服務

🔄 統一接口：
  - chat_with_user(user_id, message, platform) -> (bool, str, str)
  - transcribe_audio(file_path) -> (bool, str, str)
  - clear_user_history(user_id, platform) -> (bool, str)
  - check_connection() -> (bool, str)

🎯 模型特色：
  - 使用 Claude 的 Messages API
  - 支援長對話和複雜推理
  - 優秀的程式碼和文字生成能力
  - 對話歷史儲存在資料庫

⚠️ 功能限制：
  - 音訊轉錄: 需配置外部服務 (Deepgram/AssemblyAI)
  - 圖片生成: 不支援 (返回 "Anthropic does not support image generation")
"""

import requests
import json
import time
import uuid
from ..core.logger import get_logger
from typing import List, Dict, Tuple, Optional, Any
from .base import (
    FullLLMInterface, 
    ModelProvider, 
    ChatMessage, 
    ChatResponse, 
    ThreadInfo, 
    FileInfo,
    RAGResponse
)
from ..utils.retry import retry_on_rate_limit
from ..services.conversation import get_conversation_manager
from ..core.bounded_cache import FileCache

logger = get_logger(__name__)

class AnthropicModel(FullLLMInterface):
    """
    Anthropic Claude 2024 模型實作
    """
    
    def __init__(self, api_key: str, model_name: str = "claude-3-5-sonnet-20240620", base_url: str = None):
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url or "https://api.anthropic.com/v1"
        self.file_cache = FileCache(max_files=300, file_ttl=3600)
        self.system_prompt = self._build_system_prompt()
        self.speech_service = None
        self.conversation_manager = get_conversation_manager()

    def get_provider(self) -> ModelProvider:
        return ModelProvider.ANTHROPIC

    def check_connection(self) -> Tuple[bool, Optional[str]]:
        try:
            is_successful, _, error = self.chat_completion([ChatMessage(role="user", content="Hello")], max_tokens=10)
            return is_successful, error
        except Exception as e:
            logger.error(f"Anthropic connection check failed: {e}")
            return False, str(e)

    @retry_on_rate_limit(max_retries=3, base_delay=1.0)
    def chat_completion(self, messages: List[ChatMessage], **kwargs) -> Tuple[bool, Optional[ChatResponse], Optional[str]]:
        try:
            claude_messages = [{"role": msg.role, "content": msg.content} for msg in messages if msg.role != "system"]
            system_message = next((msg.content for msg in messages if msg.role == "system"), kwargs.get('system', self.system_prompt))

            json_body = {
                "model": kwargs.get('model', self.model_name),
                "max_tokens": kwargs.get('max_tokens', 4000),
                "messages": claude_messages,
                "temperature": kwargs.get('temperature', 0.01),
                "system": system_message
            }
            
            is_successful, response, error_message = self._request('POST', '/messages', body=json_body)
            
            if not is_successful:
                return False, None, error_message
            
            content = response['content'][0]['text']
            chat_response = ChatResponse(
                content=content,
                finish_reason=response.get('stop_reason'),
                metadata={'usage': response.get('usage'), 'model': response.get('model')}
            )
            return True, chat_response, None
        except Exception as e:
            logger.error(f"Anthropic chat completion failed: {e}")
            return False, None, str(e)

    def chat_with_user(self, user_id: str, message: str, platform: str = 'line', **kwargs: Any) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        try:
            self.conversation_manager.add_message(user_id, 'anthropic', 'user', message, platform)
            conversations = self._get_recent_conversations(user_id, platform, kwargs.get('conversation_limit', 10))
            messages = self._build_conversation_context(conversations, message)
            
            is_successful, response, error = self.query_with_rag(message, context_messages=messages, **kwargs)
            
            if not is_successful:
                return False, None, error
            
            self.conversation_manager.add_message(user_id, 'anthropic', 'assistant', response.answer, platform)
            response.metadata.update({'user_id': user_id, 'model_provider': 'anthropic'})
            return True, response, None
        except Exception as e:
            logger.error(f"Error in chat_with_user for {user_id}: {e}")
            return False, None, str(e)

    def query_with_rag(self, query: str, context_messages: List[ChatMessage] = None, **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        messages = context_messages if context_messages else [ChatMessage(role="user", content=query)]
        return self._perform_rag_query(messages, **kwargs)

    def _perform_rag_query(self, messages: List[ChatMessage], **kwargs: Any) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        system_prompt = self._build_files_context() if self.file_cache else self.system_prompt
        is_successful, response, error = self.chat_completion(messages, system=system_prompt, **kwargs)
        if not is_successful:
            return False, None, error
        
        sources = self._extract_sources_from_response(response.content)
        return True, RAGResponse(answer=response.content, sources=sources, metadata=response.metadata), None

    def upload_knowledge_file(self, file_path: str, **kwargs) -> Tuple[bool, Optional[FileInfo], Optional[str]]:
        try:
            import os
            import mimetypes
            filename = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            if file_size > 100 * 1024 * 1024:
                return False, None, f"檔案過大: {file_size / 1024 / 1024:.1f}MB，超過 100MB 限制"
            
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            content_type, _ = mimetypes.guess_type(file_path)
            files = {'file': (filename, file_content, content_type or 'application/octet-stream')}
            data = {'purpose': kwargs.get('purpose', 'knowledge_base')}
            
            is_successful, response, error_message = self._request('POST', '/files', files=files, data=data)
            
            if not is_successful:
                return False, None, error_message
            
            file_info = FileInfo(
                file_id=response['id'], filename=filename, size=file_size, status='processed',
                purpose=response.get('purpose', 'knowledge_base'),
                metadata={'upload_time': time.time(), 'claude_file_id': response['id']}
            )
            self.file_cache[response['id']] = file_info
            return True, file_info, None
        except Exception as e:
            logger.error(f"Anthropic file upload failed for {file_path}: {e}")
            return False, None, str(e)

    def get_knowledge_files(self) -> Tuple[bool, Optional[List[FileInfo]], Optional[str]]:
        # This is a simplified implementation. A real-world scenario might involve pagination.
        try:
            if len(self.file_cache) > 0:
                return True, list(self.file_cache.values()), None
            is_successful, response, error = self._request('GET', '/files')
            if not is_successful:
                return False, None, error
            files = [FileInfo(
                file_id=f['id'], filename=f['filename'], size=f.get('bytes', 0),
                status='processed', purpose=f.get('purpose', 'knowledge_base'),
                metadata={'upload_time': f.get('created_at'), 'claude_file_id': f['id']}
            ) for f in response.get('data', [])]
            for file_info in files:
                self.file_cache[file_info.file_id] = file_info
            return True, files, None
        except Exception as e:
            logger.error(f"Failed to get knowledge files: {e}")
            return False, None, str(e)

    def get_file_references(self) -> Dict[str, str]:
        """Gets a map of file IDs to their clean names for citation."""
        return {info.file_id: info.filename.rsplit('.', 1)[0] for info in self.file_cache.values()}

    # Minimal implementation for interface compliance
    def create_thread(self) -> Tuple[bool, Optional[ThreadInfo], Optional[str]]:
        return True, ThreadInfo(thread_id=str(uuid.uuid4())), None

    def delete_thread(self, thread_id: str) -> Tuple[bool, Optional[str]]:
        return True, None

    def add_message_to_thread(self, thread_id: str, message: ChatMessage) -> Tuple[bool, Optional[str]]:
        return True, None

    def run_assistant(self, thread_id: str, **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        return False, None, "Not implemented. Use chat_with_user for conversation."

    def clear_user_history(self, user_id: str, platform: str = 'line') -> Tuple[bool, Optional[str]]:
        return self.conversation_manager.clear_user_history(user_id, 'anthropic', platform)

    def transcribe_audio(self, audio_file_path: str, **kwargs: Any) -> Tuple[bool, Optional[str], Optional[str]]:
        if not self.speech_service:
            return False, None, "Speech service not configured"
        try:
            return self.speech_service.transcribe(audio_file_path, **kwargs)
        except Exception as e:
            return False, None, str(e)

    def generate_image(self, prompt: str, **kwargs: Any) -> Tuple[bool, Optional[str], Optional[str]]:
        return False, None, "Anthropic does not support image generation."

    def set_speech_service(self, service: Any):
        self.speech_service = service

    def _get_recent_conversations(self, user_id: str, platform: str, limit: int) -> List[Dict]:
        return self.conversation_manager.get_recent_conversations(user_id, 'anthropic', limit, platform)

    def _build_conversation_context(self, recent_conversations: List[Dict], current_message: str) -> List[ChatMessage]:
        messages = [ChatMessage(role=conv['role'], content=conv['content']) for conv in recent_conversations]
        messages.append(ChatMessage(role='user', content=current_message))
        return messages

    def _build_system_prompt(self) -> str:
        return "You are a helpful assistant."

    def _build_files_context(self) -> str:
        files_context = "\n".join([f"- {info.filename}" for info in self.file_cache.values()])
        return f"{self.system_prompt}\n\nUse the following documents to answer the question:\n{files_context}"

    def _extract_sources_from_response(self, response_text: str) -> List[Dict[str, str]]:
        import re
        sources = []
        matches = set(re.findall(r'\[([^\]]+)\]', response_text))
        file_refs = {info.filename: info.file_id for info in self.file_cache.values()}
        for match in matches:
            if match in file_refs:
                sources.append({'file_id': file_refs[match], 'filename': match})
        return sources

    @retry_on_rate_limit(max_retries=3, base_delay=1.0)
    def _request(self, method: str, endpoint: str, body: Optional[Dict] = None, files: Optional[Dict] = None, data: Optional[Dict] = None) -> Tuple[bool, Optional[Dict], Optional[str]]:
        headers = {'x-api-key': self.api_key, 'anthropic-version': '2023-06-01'}
        if not files:
            headers['Content-Type'] = 'application/json'
        
        try:
            response = requests.request(
                method, f'{self.base_url}{endpoint}', headers=headers, json=body, 
                files=files, data=data, timeout=(30, 60)
            )
            
            # 檢查 HTTP 狀態碼但不拋出異常
            if response.status_code >= 400:
                error_msg = f"HTTP Error: {response.status_code}"
                try:
                    error_details = response.json()
                    error_msg = error_details.get('error', {}).get('message', error_msg)
                except json.JSONDecodeError:
                    error_msg = response.text
                return False, None, error_msg
            
            return True, response.json(), None
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP Error: {e.response.status_code}"
            try:
                error_details = e.response.json()
                error_msg = error_details.get('error', {}).get('message', error_msg)
            except json.JSONDecodeError:
                error_msg = e.response.text
            return False, None, error_msg
        except requests.exceptions.RequestException as e:
            raise e
