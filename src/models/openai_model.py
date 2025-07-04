import requests
import logging
import re
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger(__name__)
from .base import (
    FullLLMInterface, 
    ModelProvider, 
    ChatMessage, 
    ChatResponse, 
    ThreadInfo, 
    FileInfo,
    KnowledgeBase,
    RAGResponse
)
from ..utils.retry import retry_with_backoff, retry_on_rate_limit, CircuitBreaker
from ..utils import s2t_converter


class OpenAIModel(FullLLMInterface):
    """OpenAI 模型實作"""
    
    def __init__(self, api_key: str, assistant_id: str = None, base_url: str = None):
        self.api_key = api_key
        self.assistant_id = assistant_id
        self.base_url = base_url or 'https://api.openai.com/v1'
    
    def get_provider(self) -> ModelProvider:
        return ModelProvider.OPENAI
    
    def check_connection(self) -> Tuple[bool, Optional[str]]:
        """檢查 OpenAI API 連線"""
        try:
            is_successful, response, error_message = self._request('GET', '/models')
            if is_successful:
                return True, None
            else:
                return False, error_message
        except Exception as e:
            return False, str(e)
    
    def chat_completion(self, messages: List[ChatMessage], **kwargs) -> Tuple[bool, Optional[ChatResponse], Optional[str]]:
        """OpenAI Chat Completion"""
        try:
            # 轉換訊息格式
            openai_messages = [
                {"role": msg.role, "content": msg.content} 
                for msg in messages
            ]
            
            json_body = {
                'model': kwargs.get('model', 'gpt-4'),
                'messages': openai_messages,
                'temperature': kwargs.get('temperature', 0)
            }
            
            is_successful, response, error_message = self._request('POST', '/chat/completions', body=json_body)
            
            if not is_successful:
                return False, None, error_message
            
            content = response['choices'][0]['message']['content']
            finish_reason = response['choices'][0].get('finish_reason')
            
            chat_response = ChatResponse(
                content=content,
                finish_reason=finish_reason,
                metadata={'usage': response.get('usage')}
            )
            
            return True, chat_response, None
            
        except Exception as e:
            return False, None, str(e)
    
    def create_thread(self) -> Tuple[bool, Optional[ThreadInfo], Optional[str]]:
        """建立 OpenAI Assistant 對話串"""
        try:
            is_successful, response, error_message = self._request('POST', '/threads', assistant=True)
            
            if not is_successful:
                return False, None, error_message
            
            thread_info = ThreadInfo(
                thread_id=response['id'],
                created_at=response.get('created_at'),
                metadata=response
            )
            
            return True, thread_info, None
            
        except Exception as e:
            return False, None, str(e)
    
    def delete_thread(self, thread_id: str) -> Tuple[bool, Optional[str]]:
        """刪除對話串"""
        try:
            endpoint = f'/threads/{thread_id}'
            is_successful, response, error_message = self._request('DELETE', endpoint, assistant=True)
            return is_successful, error_message
        except Exception as e:
            return False, str(e)
    
    def add_message_to_thread(self, thread_id: str, message: ChatMessage) -> Tuple[bool, Optional[str]]:
        """新增訊息到對話串"""
        try:
            endpoint = f'/threads/{thread_id}/messages'
            json_body = {
                'role': message.role,
                'content': message.content
            }
            is_successful, response, error_message = self._request('POST', endpoint, body=json_body, assistant=True)
            return is_successful, error_message
        except Exception as e:
            return False, str(e)
    
    def run_assistant(self, thread_id: str, **kwargs) -> Tuple[bool, Optional[ChatResponse], Optional[str]]:
        """執行 OpenAI Assistant"""
        try:
            # 啟動執行
            endpoint = f'/threads/{thread_id}/runs'
            json_body = {
                'assistant_id': self.assistant_id,
                'temperature': kwargs.get('temperature', 0)
            }
            
            is_successful, run_response, error_message = self._request('POST', endpoint, body=json_body, assistant=True)
            if not is_successful:
                return False, None, error_message
            
            # 等待完成
            run_id = run_response['id']
            final_response = self._wait_for_run_completion(thread_id, run_id)
            
            if final_response['status'] != 'completed':
                return False, None, f"Assistant run failed with status: {final_response['status']}"
            
            # 取得回應
            return self._get_thread_messages(thread_id)
            
        except Exception as e:
            return False, None, str(e)
    
    # === RAG 介面實作（使用 OpenAI Assistant API） ===
    
    def upload_knowledge_file(self, file_path: str, **kwargs) -> Tuple[bool, Optional[FileInfo], Optional[str]]:
        """上傳檔案到 OpenAI（用於 Assistant API）"""
        try:
            with open(file_path, 'rb') as f:
                files = {
                    'file': f,
                    'purpose': (None, 'assistants')
                }
                is_successful, response, error_message = self._request('POST', '/files', files=files)
            
            if not is_successful:
                return False, None, error_message
            
            file_info = FileInfo(
                file_id=response['id'],
                filename=response['filename'],
                size=response.get('bytes'),
                status=response.get('status'),
                purpose=response.get('purpose'),
                metadata=response
            )
            
            return True, file_info, None
            
        except Exception as e:
            return False, None, str(e)
    
    def query_with_rag(self, query: str, thread_id: str = None, **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        """使用 OpenAI Assistant API 進行 RAG 查詢"""
        try:
            # 如果沒有 thread_id，建立新的
            if not thread_id:
                is_successful, thread_info, error_message = self.create_thread()
                if not is_successful:
                    return False, None, error_message
                thread_id = thread_info.thread_id
            
            # 新增訊息到對話串
            message = ChatMessage(role='user', content=query)
            is_successful, error_message = self.add_message_to_thread(thread_id, message)
            if not is_successful:
                return False, None, error_message
            
            # 執行助理
            is_successful, chat_response, error_message = self.run_assistant(thread_id, **kwargs)
            if not is_successful:
                return False, None, error_message
            
            # 使用 OpenAI 特定的引用處理邏輯
            thread_messages = chat_response.metadata.get('thread_messages', {})
            formatted_content, sources = self._process_openai_response(thread_messages)
            
            rag_response = RAGResponse(
                answer=formatted_content,
                sources=sources,
                metadata={
                    'thread_id': thread_id,
                    'model': 'openai-assistant',
                    'thread_messages': thread_messages,
                    'raw_content': chat_response.content
                }
            )
            
            return True, rag_response, None
            
        except Exception as e:
            return False, None, str(e)
    
    def get_knowledge_files(self) -> Tuple[bool, Optional[List[FileInfo]], Optional[str]]:
        """取得 OpenAI 檔案列表"""
        return self.list_files()
    
    def list_files(self) -> Tuple[bool, Optional[List[FileInfo]], Optional[str]]:
        """列出檔案"""
        try:
            is_successful, response, error_message = self._request('GET', '/files', assistant=True)
            
            if not is_successful:
                return False, None, error_message
            
            files = [
                FileInfo(
                    file_id=file['id'],
                    filename=file['filename'],
                    size=file.get('bytes'),
                    status=file.get('status'),
                    purpose=file.get('purpose'),
                    metadata=file
                )
                for file in response['data']
            ]
            
            return True, files, None
            
        except Exception as e:
            return False, None, str(e)
    
    def get_file_references(self) -> Dict[str, str]:
        """取得檔案引用對應表"""
        try:
            is_successful, files, error_message = self.list_files()
            if not is_successful:
                logger.warning(f"Failed to get file references: {error_message}")
                return {}
            
            file_dict = {}
            for file in files:
                filename = file.filename.replace('.txt', '').replace('.json', '')
                file_dict[file.file_id] = filename
            
            logger.debug(f"Loaded {len(file_dict)} file references")
            return file_dict
            
        except Exception as e:
            logger.error(f"Error getting file references: {e}")
            return {}
    
    def _extract_sources_from_response(self, thread_messages: Dict) -> List[Dict[str, str]]:
        """從 OpenAI Assistant 回應中提取來源資訊"""
        sources = []
        seen_files = set()  # 避免重複檔案
        
        try:
            for message in thread_messages.get('data', []):
                if message.get('role') == 'assistant':
                    for content in message.get('content', []):
                        if content.get('type') == 'text':
                            annotations = content.get('text', {}).get('annotations', [])
                            for annotation in annotations:
                                if annotation.get('type') == 'file_citation':
                                    citation = annotation.get('file_citation', {})
                                    file_id = citation.get('file_id')
                                    
                                    # 避免重複添加相同檔案
                                    if file_id and file_id not in seen_files:
                                        seen_files.add(file_id)
                                        sources.append({
                                            'file_id': file_id,
                                            'quote': citation.get('quote', ''),
                                            'type': 'file_citation'
                                        })
        except Exception as e:
            logger.error(f"Error extracting sources: {e}")
        
        return sources
    
    def _process_openai_response(self, thread_messages: Dict) -> Tuple[str, List[Dict[str, str]]]:
        """
        處理 OpenAI Assistant API 的回應，包括引用格式化
        這個方法封裝了原本的 get_content_and_reference 邏輯
        """
        try:
            # 取得助理回應數據
            data = self._get_response_data(thread_messages)
            if not data:
                logger.debug("_process_openai_response: 沒有找到助理回應數據")
                return '', []
            
            text = data['content'][0]['text']['value']
            annotations = data['content'][0]['text']['annotations']
            
            logger.debug(f"_process_openai_response: 註解數量={len(annotations)}")
            
            # 檢查是否有複雜引用格式在原始文本中
            complex_citations = re.findall(r'【[^】]+】', text)
            if complex_citations:
                logger.debug(f"_process_openai_response: 發現 {len(complex_citations)} 個複雜引用格式")
            
            # 轉換為繁體中文
            text = s2t_converter.convert(text)
            
            # 取得檔案字典用於引用處理
            file_dict = self.get_file_references()
            
            # 替換註釋文本和建立來源清單
            sources = []
            
            for i, annotation in enumerate(annotations, 1):
                logger.debug(f"_process_openai_response: 處理註解 {i}: {annotation}")
                original_text = annotation['text']
                # 對 annotation 文本也進行 s2t 轉換，確保與主文本一致
                original_text = s2t_converter.convert(original_text)
                file_id = annotation['file_citation']['file_id']
                replacement_text = f"[{i}]"
                
                logger.debug(f"  替換 '{original_text}' → '{replacement_text}'")
                text = text.replace(original_text, replacement_text)
                
                # 建立來源清單（供 ResponseFormatter 統一處理）
                filename = file_dict.get(file_id, 'Unknown')
                sources.append({
                    'file_id': file_id,
                    'filename': filename,
                    'quote': annotation['file_citation'].get('quote', ''),
                    'type': 'file_citation'
                })
            
            # 檢查處理後是否還有複雜引用格式
            remaining_complex = re.findall(r'【[^】]+】', text)
            if remaining_complex:
                logger.warning(f"_process_openai_response: 處理後仍有 {len(remaining_complex)} 個未處理的複雜引用")
            
            # 直接返回處理後的文本，讓 ResponseFormatter 統一處理 sources
            final_text = text.strip()
            
            logger.debug(f"_process_openai_response: 最終文本長度={len(final_text)}, 生成了 {len(sources)} 個來源")
            
            return final_text, sources
            
        except Exception as e:
            logger.error(f"Error processing OpenAI response: {e}")
            return '', []
    
    def _get_response_data(self, response: Dict) -> Dict:
        """從 OpenAI 回應中提取助理數據"""
        try:
            for item in response.get('data', []):
                if item.get('role') == 'assistant' and item.get('content') and item['content'][0].get('type') == 'text':
                    return item
            return None
        except Exception as e:
            logger.error(f"Error getting response data: {e}")
            return None
    
    def transcribe_audio(self, audio_file_path: str, **kwargs) -> Tuple[bool, Optional[str], Optional[str]]:
        """音訊轉文字"""
        try:
            files = {
                'file': open(audio_file_path, 'rb'),
                'model': (None, kwargs.get('model', 'whisper-1')),
            }
            is_successful, response, error_message = self._request('POST', '/audio/transcriptions', files=files)
            
            if not is_successful:
                return False, None, error_message
            
            return True, response['text'], None
            
        except Exception as e:
            return False, None, str(e)
    
    def generate_image(self, prompt: str, **kwargs) -> Tuple[bool, Optional[str], Optional[str]]:
        """生成圖片"""
        try:
            json_body = {
                "prompt": prompt,
                "n": kwargs.get('n', 1),
                "size": kwargs.get('size', '512x512')
            }
            is_successful, response, error_message = self._request('POST', '/images/generations', body=json_body)
            
            if not is_successful:
                return False, None, error_message
            
            image_url = response['data'][0]['url']
            return True, image_url, None
            
        except Exception as e:
            return False, None, str(e)
    
    # === 向後相容的方法 ===
    def check_token_valid(self):
        """向後相容方法"""
        is_successful, error = self.check_connection()
        return is_successful, None, error
    
    def retrieve_thread(self, thread_id: str):
        """向後相容方法"""
        try:
            endpoint = f'/threads/{thread_id}'
            return self._request('GET', endpoint, assistant=True)
        except Exception as e:
            return False, None, str(e)
    
    def create_thread_message(self, thread_id: str, content: str):
        """向後相容方法"""
        message = ChatMessage(role='user', content=content)
        is_successful, error = self.add_message_to_thread(thread_id, message)
        return is_successful, None, error
    
    def create_thread_run(self, thread_id: str):
        """向後相容方法"""
        try:
            endpoint = f'/threads/{thread_id}/runs'
            json_body = {
                'assistant_id': self.assistant_id,
                'temperature': 0
            }
            return self._request('POST', endpoint, body=json_body, assistant=True)
        except Exception as e:
            return False, None, str(e)
    
    def retrieve_thread_run(self, thread_id: str, run_id: str):
        """向後相容方法"""
        try:
            endpoint = f'/threads/{thread_id}/runs/{run_id}'
            return self._request('GET', endpoint, assistant=True)
        except Exception as e:
            return False, None, str(e)
    
    def list_thread_messages(self, thread_id: str):
        """向後相容方法"""
        try:
            endpoint = f'/threads/{thread_id}/messages'
            return self._request('GET', endpoint, assistant=True)
        except Exception as e:
            return False, None, str(e)
    
    def audio_transcriptions(self, file_path: str, model: str):
        """向後相容方法"""
        return self.transcribe_audio(file_path, model=model)
    
    # === 內部方法 ===
    @retry_on_rate_limit(max_retries=3, base_delay=1.0)
    def _request(self, method: str, endpoint: str, body=None, files=None, assistant=False):
        """發送 HTTP 請求（帶重試機制）"""
        headers = {
            'Authorization': f'Bearer {self.api_key}'
        }
        
        try:
            if method == 'GET':
                if assistant:
                    headers['Content-Type'] = 'application/json'
                    headers['OpenAI-Beta'] = 'assistants=v2'
                r = requests.get(f'{self.base_url}{endpoint}', headers=headers, timeout=30)
            elif method == 'POST':
                if body:
                    headers['Content-Type'] = 'application/json'
                if assistant:
                    headers['OpenAI-Beta'] = 'assistants=v2'
                r = requests.post(f'{self.base_url}{endpoint}', headers=headers, json=body, files=files, timeout=30)
            elif method == 'DELETE':
                if assistant:
                    headers['OpenAI-Beta'] = 'assistants=v2'
                r = requests.delete(f'{self.base_url}{endpoint}', headers=headers, timeout=30)
            
            # 檢查 HTTP 狀態碼
            if r.status_code == 429:  # Rate limit
                raise requests.exceptions.RequestException(f"Rate limit exceeded: {r.status_code}")
            elif r.status_code >= 500:  # Server error
                raise requests.exceptions.RequestException(f"Server error: {r.status_code}")
            elif r.status_code >= 400:  # Client error
                try:
                    error_data = r.json()
                    error_msg = error_data.get('error', {}).get('message', f'HTTP {r.status_code}')
                    return False, None, error_msg
                except:
                    return False, None, f'HTTP {r.status_code}: {r.text[:200]}'
            
            response_data = r.json()
            if response_data.get('error'):
                return False, None, response_data.get('error', {}).get('message')
                
            return True, response_data, None
            
        except requests.exceptions.RequestException as e:
            # 網路相關錯誤會被重試裝飾器處理
            raise e
        except Exception as e:
            return False, None, f'OpenAI API 系統不穩定，請稍後再試: {str(e)}'
    
    def _wait_for_run_completion(self, thread_id: str, run_id: str, max_wait_time: int = 120):
        """等待執行完成"""
        import time
        start_time = time.time()
        
        while True:
            if time.time() - start_time > max_wait_time:
                raise Exception("Request timeout")
            
            is_successful, response, error_message = self.retrieve_thread_run(thread_id, run_id)
            if not is_successful:
                raise Exception(error_message)
            
            status = response['status']
            if status in ['completed', 'failed', 'expired', 'cancelled']:
                return response
            
            # 根據狀態調整等待時間
            if status == 'queued':
                time.sleep(10)
            else:
                time.sleep(3)
    
    def _get_thread_messages(self, thread_id: str) -> Tuple[bool, Optional[ChatResponse], Optional[str]]:
        """取得對話串訊息"""
        try:
            is_successful, response, error_message = self.list_thread_messages(thread_id)
            if not is_successful:
                return False, None, error_message
            
            # 記錄完整的API回應用於除錯
            logger.debug(f"OpenAI Assistant API 完整回應: {response}")
            
            # 取得最新的助理回應
            for message in response['data']:
                if message['role'] == 'assistant' and message['content']:
                    content = message['content'][0]['text']['value']
                    
                    # 詳細記錄助理訊息結構
                    logger.debug(f"助理訊息內容長度: {len(content)}")
                    logger.debug(f"助理訊息註解數量: {len(message['content'][0]['text'].get('annotations', []))}")
                    
                    # 記錄每個註解的詳細信息
                    annotations = message['content'][0]['text'].get('annotations', [])
                    for i, annotation in enumerate(annotations):
                        logger.debug(f"註解 {i+1}: 類型={annotation.get('type')}, 文本={annotation.get('text')}")
                        if 'file_citation' in annotation:
                            file_id = annotation['file_citation'].get('file_id')
                            logger.debug(f"  檔案ID: {file_id}")
                    
                    chat_response = ChatResponse(
                        content=content,
                        metadata={'thread_messages': response}
                    )
                    return True, chat_response, None
            
            return False, None, "No assistant response found"
            
        except Exception as e:
            return False, None, str(e)
    
    # === 🆕 新的用戶級對話管理接口 ===
    
    def chat_with_user(self, user_id: str, message: str, platform: str = 'line', **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        """
        主要對話接口：使用 OpenAI Assistant API 的 thread 系統
        
        OpenAI 使用原生 thread 管理，與其他模型的簡化對話歷史不同
        
        Args:
            user_id: 用戶 ID (如 Line user ID)
            message: 用戶訊息
            platform: 平台識別 (\'line\', \'discord\', \'telegram\')
            **kwargs: 額外參數
                
        Returns:
            (is_successful, rag_response, error_message)
        """
        try:
            # 1. 取得或創建用戶的 thread
            from ..database.connection import get_thread_id_by_user_id, save_thread_id
            
            thread_id = get_thread_id_by_user_id(user_id, platform)
            
            if not thread_id:
                # 創建新 thread
                is_successful, thread_info, error = self.create_thread()
                if not is_successful:
                    return False, None, f"Failed to create thread: {error}"
                
                thread_id = thread_info.thread_id
                save_thread_id(user_id, thread_id, platform)
                logger.info(f"Created new thread {thread_id} for user {user_id} on platform {platform}")
            
            # 2. 添加用戶訊息到 thread
            user_message = ChatMessage(role='user', content=message)
            is_successful, error = self.add_message_to_thread(thread_id, user_message)
            if not is_successful:
                return False, None, f"Failed to add message to thread: {error}"
            
            # 3. 執行 Assistant
            is_successful, chat_response, error = self.run_assistant(thread_id, **kwargs)
            if not is_successful:
                return False, None, error
            
            # 4. 處理 OpenAI 回應格式（引用等）
            thread_messages = chat_response.metadata.get('thread_messages', {})
            formatted_content, sources = self._process_openai_response(thread_messages)
            
            # 5. 將處理後的內容轉換為 RAGResponse
            rag_response = RAGResponse(
                answer=formatted_content,
                sources=sources,  # 傳遞 sources 給 ResponseFormatter 統一處理
                metadata={
                    'user_id': user_id,
                    'thread_id': thread_id,
                    'model_provider': 'openai',
                    'uses_native_threads': True,
                    'finish_reason': chat_response.finish_reason,
                    'raw_metadata': chat_response.metadata,
                    'raw_content': chat_response.content
                }
            )
            
            logger.info(f"Completed OpenAI chat with user {user_id}, thread {thread_id}, response length: {len(rag_response.answer) if rag_response else 0}")
            return True, rag_response, None
            
        except Exception as e:
            logger.error(f"Error in chat_with_user for user {user_id}: {e}")
            return False, None, str(e)
    
    def clear_user_history(self, user_id: str, platform: str = 'line') -> Tuple[bool, Optional[str]]:
        """清除用戶對話歷史（刪除 OpenAI thread）"""
        try:
            from ..database.connection import get_thread_id_by_user_id, delete_thread_id
            
            # 1. 取得用戶的 thread ID
            thread_id = get_thread_id_by_user_id(user_id, platform)
            if not thread_id:
                logger.info(f"No thread found for user {user_id} on platform {platform}")
                return True, None  # 沒有 thread 也算成功
            
            # 2. 刪除 OpenAI thread
            is_successful, error = self.delete_thread(thread_id)
            if not is_successful:
                logger.error(f"Failed to delete OpenAI thread {thread_id}: {error}")
                # 繼續執行，至少清除本地記錄
            
            # 3. 刪除本地 thread 記錄
            delete_thread_id(user_id, platform)
            
            logger.info(f"Cleared conversation history for user {user_id} on platform {platform}, thread {thread_id}")
            return True, None
            
        except Exception as e:
            logger.error(f"Error clearing history for user {user_id}: {e}")
            return False, str(e)