import requests
import json
import hashlib
import time
import uuid
from ..core.logger import get_logger
from typing import List, Dict, Tuple, Optional
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
from ..utils.retry import retry_on_rate_limit
from ..services.conversation import get_conversation_manager

logger = get_logger(__name__)


class AnthropicModel(FullLLMInterface):
    """
    Anthropic Claude 2024 模型實作
    
    特色功能：
    - Files API: 持久化文件管理，支援跨對話引用
    - Extended Prompt Caching: 最長1小時的提示快取，降低成本
    - 增強的 RAG 實作：使用 Files API 作為知識庫
    - 結構化系統提示詞
    """
    
    def __init__(self, api_key: str, model_name: str = "claude-3-5-sonnet-20241022", base_url: str = None):
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url or "https://api.anthropic.com/v1"
        
        # Files API 支援 - 使用有界快取
        from ..core.bounded_cache import FileCache, ConversationCache
        self.files_store = FileCache(max_files=300, file_ttl=3600)  # 300個檔案，1小時TTL
        self.file_store = FileCache(max_files=300, file_ttl=3600)   # 檔案名稱對應
        
        # Extended Prompt Caching 支援 - 使用對話快取
        self.cache_enabled = True
        self.cache_ttl = 3600  # 1小時
        self.cached_conversations = ConversationCache(max_conversations=1000, conversation_ttl=3600)  # 1000對話，1小時TTL
        
        # 系統提示詞配置
        self.system_prompt = self._build_system_prompt()
        
        # 第三方語音轉錄服務配置（預設為空，需要額外配置）
        self.speech_service = None  # 可整合 Deepgram 或 AssemblyAI
        
        # 對話歷史管理
        self.conversation_manager = get_conversation_manager()
    
    def get_provider(self) -> ModelProvider:
        return ModelProvider.ANTHROPIC
    
    def check_connection(self) -> Tuple[bool, Optional[str]]:
        """檢查 Anthropic API 連線"""
        try:
            test_message = [ChatMessage(role="user", content="Hello")]
            is_successful, response, error = self.chat_completion(test_message, max_tokens=10)
            return is_successful, error
        except Exception as e:
            return False, str(e)
    
    @retry_on_rate_limit(max_retries=3, base_delay=1.0)
    def chat_completion(self, messages: List[ChatMessage], **kwargs) -> Tuple[bool, Optional[ChatResponse], Optional[str]]:
        """Anthropic Claude Chat Completion with Extended Prompt Caching"""
        try:
            # 轉換訊息格式
            claude_messages = []
            system_message = kwargs.get('system', self.system_prompt)
            
            for msg in messages:
                if msg.role == "system":
                    system_message = msg.content
                else:
                    claude_messages.append({
                        "role": msg.role, 
                        "content": msg.content
                    })
            
            json_body = {
                "model": kwargs.get('model', self.model_name),
                "max_tokens": kwargs.get('max_tokens', 4000),
                "messages": claude_messages,
                "temperature": kwargs.get('temperature', 0.1)
            }
            
            # 系統提示詞處理
            if system_message:
                if self.cache_enabled and len(system_message) > 1000:  # 長提示詞啟用快取
                    json_body["system"] = [
                        {
                            "type": "text",
                            "text": system_message,
                            "cache_control": {"type": "ephemeral"}
                        }
                    ]
                else:
                    json_body["system"] = system_message
            
            # 額外參數
            if kwargs.get('stop_sequences'):
                json_body["stop_sequences"] = kwargs['stop_sequences']
            
            is_successful, response, error_message = self._request('POST', '/messages', body=json_body)
            
            if not is_successful:
                return False, None, error_message
            
            content = response['content'][0]['text']
            finish_reason = response.get('stop_reason')
            
            chat_response = ChatResponse(
                content=content,
                finish_reason=finish_reason,
                metadata={
                    'usage': response.get('usage'),
                    'model': response.get('model'),
                    'cache_creation_input_tokens': response.get('usage', {}).get('cache_creation_input_tokens', 0),
                    'cache_read_input_tokens': response.get('usage', {}).get('cache_read_input_tokens', 0)
                }
            )
            
            return True, chat_response, None
            
        except Exception as e:
            return False, None, str(e)
    
    # === RAG 介面實作（使用自建向量搜尋） ===
    
    def upload_knowledge_file(self, file_path: str, **kwargs) -> Tuple[bool, Optional[FileInfo], Optional[str]]:
        """使用 Claude Files API 上傳檔案到知識庫"""
        try:
            import os
            import mimetypes
            
            filename = os.path.basename(file_path)
            
            # 檢查檔案大小（Claude Files API 限制）
            file_size = os.path.getsize(file_path)
            if file_size > 100 * 1024 * 1024:  # 100MB 限制
                return False, None, f"檔案過大: {file_size / 1024 / 1024:.1f}MB，超過 100MB 限制"
            
            # 準備檔案上傳
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            # 偵測檔案類型
            content_type, _ = mimetypes.guess_type(file_path)
            if not content_type:
                content_type = 'text/plain'
            
            # 使用 Files API 上傳
            files = {
                'file': (filename, file_content, content_type)
            }
            
            data = {
                'purpose': kwargs.get('purpose', 'knowledge_base')
            }
            
            is_successful, response, error_message = self._request(
                'POST', '/files', files=files, data=data
            )
            
            if not is_successful:
                return False, None, error_message
            
            file_id = response['id']
            
            # 快取檔案資訊
            file_info = FileInfo(
                file_id=file_id,
                filename=filename,
                size=file_size,
                status='processed',
                purpose=response.get('purpose', 'knowledge_base'),
                metadata={
                    'upload_time': time.time(),
                    'content_type': content_type,
                    'claude_file_id': file_id
                }
            )
            
            self.files_store[file_id] = file_info
            self.file_store[file_id] = filename
            
            return True, file_info, None
            
        except Exception as e:
            return False, None, str(e)
    
    def query_with_rag(self, query: str, thread_id: str = None, **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        """使用 Files API + Extended Caching 實作 RAG"""
        try:
            # 檢查是否有可用的知識檔案
            if not self.files_store:
                # 沒有知識檔案，使用一般聊天
                messages = [ChatMessage(role="user", content=query)]
                is_successful, response, error = self.chat_completion(messages, **kwargs)
                
                if not is_successful:
                    return False, None, error
                
                rag_response = RAGResponse(
                    answer=response.content,
                    sources=[],
                    metadata={'model': 'anthropic-claude', 'no_sources': True}
                )
                return True, rag_response, None
            
            # 建立包含檔案引用的提示
            files_context = self._build_files_context()
            
            enhanced_query = f"""你是一個專業的知識助理。請根據提供的文檔內容回答問題。如果你引用文檔內容，請使用 [filename] 格式標註來源。

可用文檔：
{files_context}

用戶問題：{query}

請基於上述文檔內容提供精確的回答，如果文檔中沒有相關資訊，請明確說明。"""
            
            # 使用系統提示詞和快取
            messages = [ChatMessage(role="user", content=enhanced_query)]
            
            # 將檔案上下文作為系統提示詞的一部分，以充分利用 Extended Caching
            system_with_files = f"{self.system_prompt}\n\n知識庫上下文：\n{files_context}"
            
            is_successful, response, error = self.chat_completion(
                messages, 
                system=system_with_files,
                **kwargs
            )
            
            if not is_successful:
                return False, None, error
            
            # 提取來源資訊
            sources = self._extract_sources_from_response(response.content)
            
            rag_response = RAGResponse(
                answer=response.content,
                sources=sources,
                metadata={
                    'model': 'anthropic-claude',
                    'files_used': len(self.files_store),
                    'num_sources': len(sources),
                    'cache_enabled': self.cache_enabled,
                    'cache_tokens': response.metadata.get('cache_read_input_tokens', 0)
                }
            )
            
            return True, rag_response, None
            
        except Exception as e:
            return False, None, str(e)
    
    def get_knowledge_files(self) -> Tuple[bool, Optional[List[FileInfo]], Optional[str]]:
        """取得 Files API 檔案列表"""
        try:
            # 先從快取返回
            if self.files_store:
                return True, list(self.files_store.values()), None
            
            # 如果快取為空，從 API 獲取
            is_successful, response, error_message = self._request('GET', '/files')
            
            if not is_successful:
                return False, None, error_message
            
            files = []
            for file_data in response.get('data', []):
                file_info = FileInfo(
                    file_id=file_data['id'],
                    filename=file_data['filename'],
                    size=file_data.get('bytes', 0),
                    status='processed',
                    purpose=file_data.get('purpose', 'knowledge_base'),
                    metadata={
                        'upload_time': file_data.get('created_at'),
                        'claude_file_id': file_data['id']
                    }
                )
                files.append(file_info)
                
                # 更新快取
                self.files_store[file_data['id']] = file_info
                self.file_store[file_data['id']] = file_data['filename']
            
            return True, files, None
            
        except Exception as e:
            return False, None, str(e)
    
    def get_file_references(self) -> Dict[str, str]:
        """取得檔案引用對應表"""
        return {
            file_id: filename.replace('.txt', '').replace('.json', '')
            for file_id, filename in self.file_store.items()
        }
    
    
    @retry_on_rate_limit(max_retries=3, base_delay=1.0)
    def _request(self, method: str, endpoint: str, body=None, files=None, data=None):
        """發送 HTTP 請求到 Anthropic API"""
        headers = {
            'x-api-key': self.api_key,
            'anthropic-version': '2023-06-01'
        }
        
        # 檔案上傳請求不需要 Content-Type
        if not files:
            headers['Content-Type'] = 'application/json'
        
        try:
            if method == 'POST':
                if files:
                    # 檔案上傳
                    r = requests.post(
                        f'{self.base_url}{endpoint}', 
                        headers=headers, 
                        files=files, 
                        data=data, 
                        timeout=60
                    )
                else:
                    # JSON 請求
                    r = requests.post(
                        f'{self.base_url}{endpoint}', 
                        headers=headers, 
                        json=body, 
                        timeout=30
                    )
            else:
                r = requests.get(f'{self.base_url}{endpoint}', headers=headers, timeout=30)
            
            # 檢查 HTTP 狀態碼
            if r.status_code == 429:
                raise requests.exceptions.RequestException(f"Rate limit exceeded: {r.status_code}")
            elif r.status_code >= 500:
                raise requests.exceptions.RequestException(f"Server error: {r.status_code}")
            elif r.status_code >= 400:
                try:
                    error_data = r.json()
                    error_msg = error_data.get('error', {}).get('message', f'HTTP {r.status_code}')
                    return False, None, error_msg
                except:
                    return False, None, f'HTTP {r.status_code}: {r.text[:200]}'
            
            response_data = r.json()
            return True, response_data, None
            
        except requests.exceptions.RequestException as e:
            raise e
        except Exception as e:
            return False, None, f'Anthropic API 系統不穩定，請稍後再試: {str(e)}'
    
    # === 其他介面（暫未實作） ===
    
    def create_thread(self) -> Tuple[bool, Optional[ThreadInfo], Optional[str]]:
        """建立對話串 ID 並初始化快取"""
        thread_id = str(uuid.uuid4())
        
        # 初始化對話快取
        if self.cache_enabled:
            self.cached_conversations[thread_id] = {
                'created_at': time.time(),
                'messages': [],
                'system_context': self.system_prompt
            }
        
        thread_info = ThreadInfo(thread_id=thread_id, metadata={'cache_enabled': self.cache_enabled})
        return True, thread_info, None
    
    def delete_thread(self, thread_id: str) -> Tuple[bool, Optional[str]]:
        """刪除對話串及其快取"""
        if thread_id in self.cached_conversations:
            del self.cached_conversations[thread_id]
        return True, None
    
    def add_message_to_thread(self, thread_id: str, message: ChatMessage) -> Tuple[bool, Optional[str]]:
        """新增訊息到對話串快取"""
        if self.cache_enabled and thread_id in self.cached_conversations:
            self.cached_conversations[thread_id]['messages'].append({
                'role': message.role,
                'content': message.content,
                'timestamp': time.time()
            })
        return True, None
    
    def run_assistant(self, thread_id: str, **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        """執行助理功能使用快取的對話上下文"""
        try:
            if not self.cache_enabled or thread_id not in self.cached_conversations:
                return False, None, "無效的對話串 ID 或未啟用快取"
            
            conversation = self.cached_conversations[thread_id]
            
            # 檢查是否有最新訊息
            if not conversation['messages']:
                return False, None, "對話串中無訊息"
            
            # 取得最新的用戶訊息
            last_message = conversation['messages'][-1]
            if last_message['role'] != 'user':
                return False, None, "最新訊息不是用戶訊息"
            
            # 使用 RAG 處理查詢
            return self.query_with_rag(last_message['content'], thread_id, **kwargs)
            
        except Exception as e:
            return False, None, str(e)
    
    def transcribe_audio(self, audio_file_path: str, **kwargs) -> Tuple[bool, Optional[str], Optional[str]]:
        """使用第三方服務進行音訊轉錄"""
        try:
            # 如果有配置第三方語音服務，使用它
            if self.speech_service:
                return self.speech_service.transcribe(audio_file_path, **kwargs)
            
            # 否則嘗試使用 Deepgram（需要額外安裝和配置）
            try:
                return self._transcribe_with_deepgram(audio_file_path, **kwargs)
            except ImportError:
                pass
            
            # 最後嘗試 AssemblyAI
            try:
                return self._transcribe_with_assemblyai(audio_file_path, **kwargs)
            except ImportError:
                pass
            
            return False, None, "Anthropic 不支援音訊轉錄，請配置第三方語音服務（Deepgram 或 AssemblyAI）"
            
        except Exception as e:
            return False, None, str(e)
    
    def generate_image(self, prompt: str, **kwargs) -> Tuple[bool, Optional[str], Optional[str]]:
        """圖片生成（Anthropic 不支援）"""
        return False, None, "Anthropic Claude 不支援圖片生成，請使用其他支援圖片生成的模型"
    
    def _build_system_prompt(self) -> str:
        """建立結構化系統提示詞"""
        return """你是一個專業的知識助理，具有以下能力和特質：

## 能力範圍
- 基於提供的文檔內容進行精確分析和回答
- 提供結構化、適合繼續對話的回答
- 在無相關資料時明確說明限制

## 回答原則
1. 總是優先使用提供的文檔內容
2. 當引用文檔時，使用 [filename] 格式標註來源
3. 如文檔中無相關資訊，明確說明並提供一般性建議
4. 保持專業但友善的語調

## 回答格式
- 使用清晰的段落結構
- 重要資訊使用條列或編號
- 在回答末尾標註相關文檔來源

請始終保持這個角色設定，提供最高品質的知識服務。"""
    
    def _build_files_context(self) -> str:
        """建立檔案上下文信息"""
        if not self.files_store:
            return "無可用文檔"
        
        context_parts = []
        for file_info in self.files_store.values():
            context_parts.append(f"- {file_info.filename} (ID: {file_info.file_id})")
        
        return "\n".join(context_parts)
    
    def _extract_sources_from_response(self, response_text: str) -> List[Dict[str, str]]:
        """從回答中提取來源資訊"""
        import re
        sources = []
        
        # 搜尋 [filename] 格式的引用
        pattern = r'\[([^\]]+)\]'
        matches = re.findall(pattern, response_text)
        
        for match in matches:
            # 在檔案列表中尋找匹配的檔案
            for file_id, filename in self.file_store.items():
                if match.lower() in filename.lower() or filename.lower() in match.lower():
                    sources.append({
                        'file_id': file_id,
                        'filename': filename,
                        'text': f"引用文檔: {filename}",
                        'citation': match
                    })
                    break
        
        return sources
    
    def _transcribe_with_deepgram(self, audio_file_path: str, **kwargs) -> Tuple[bool, Optional[str], Optional[str]]:
        """使用 Deepgram 進行語音轉錄"""
        try:
            from deepgram import Deepgram
            
            # 需要配置API金鑰
            if not hasattr(self, 'deepgram_api_key') or not self.deepgram_api_key:
                return False, None, "未配置 Deepgram API 金鑰"
            
            dg_client = Deepgram(self.deepgram_api_key)
            
            with open(audio_file_path, 'rb') as audio:
                source = {'buffer': audio, 'mimetype': 'audio/wav'}
                options = {
                    'punctuate': True,
                    'language': kwargs.get('language', 'zh-CN'),
                    'model': 'nova-2'
                }
                
                response = dg_client.transcription.prerecorded(source, options)
                
                if response['results']['channels'][0]['alternatives']:
                    transcript = response['results']['channels'][0]['alternatives'][0]['transcript']
                    return True, transcript, None
                else:
                    return False, None, "無法轉錄音訊"
                    
        except ImportError:
            raise ImportError("Deepgram SDK 未安裝")
        except Exception as e:
            return False, None, str(e)
    
    def _transcribe_with_assemblyai(self, audio_file_path: str, **kwargs) -> Tuple[bool, Optional[str], Optional[str]]:
        """使用 AssemblyAI 進行語音轉錄"""
        try:
            import assemblyai as aai
            
            # 需要配置API金鑰
            if not hasattr(self, 'assemblyai_api_key') or not self.assemblyai_api_key:
                return False, None, "未配置 AssemblyAI API 金鑰"
            
            aai.settings.api_key = self.assemblyai_api_key
            
            transcriber = aai.Transcriber()
            transcript = transcriber.transcribe(audio_file_path)
            
            if transcript.status == aai.TranscriptStatus.completed:
                return True, transcript.text, None
            else:
                return False, None, f"轉錄失敗: {transcript.error}"
                
        except ImportError:
            raise ImportError("AssemblyAI SDK 未安裝")
        except Exception as e:
            return False, None, str(e)
    
    def set_speech_service(self, service_type: str, api_key: str):
        """配置第三方語音服務"""
        if service_type.lower() == 'deepgram':
            self.deepgram_api_key = api_key
        elif service_type.lower() == 'assemblyai':
            self.assemblyai_api_key = api_key
        else:
            raise ValueError(f"不支援的語音服務: {service_type}")
    
    # === 🆕 新的用戶級對話管理接口 ===
    
    def chat_with_user(self, user_id: str, message: str, platform: str = 'line', **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        """
        主要對話接口：簡單對話歷史 + Files API RAG
        
        Args:
            user_id: 用戶 ID (如 Line user ID)
            message: 用戶訊息
            platform: 平台識別 ('line', 'discord', 'telegram')
            **kwargs: 額外參數
            
        Returns:
            (is_successful, rag_response, error_message)
        """
        try:
            # 1. 取得最近的對話歷史
            recent_conversations = self._get_recent_conversations(user_id, platform, limit=kwargs.get('conversation_limit', 5))
            
            # 2. 儲存用戶訊息
            self.conversation_manager.add_message(user_id, 'anthropic', 'user', message, platform)
            
            # 3. 建立包含對話歷史的上下文
            messages = self._build_conversation_context(recent_conversations, message)
            
            # 4. 使用 Files API 進行 RAG 查詢
            is_successful, rag_response, error = self.query_with_rag(message, **kwargs)
            
            if not is_successful:
                return False, None, error
            
            # 5. 儲存助理回應
            self.conversation_manager.add_message(user_id, 'anthropic', 'assistant', rag_response.answer, platform)
            
            # 6. 更新 metadata
            rag_response.metadata.update({
                'conversation_turns': len(recent_conversations),
                'user_id': user_id,
                'model_provider': 'anthropic'
            })
            
            logger.info(f"Completed chat with user {user_id}, response length: {len(rag_response.answer)}")
            return True, rag_response, None
            
        except Exception as e:
            logger.error(f"Error in chat_with_user for user {user_id}: {e}")
            return False, None, str(e)
    
    def clear_user_history(self, user_id: str, platform: str = 'line') -> Tuple[bool, Optional[str]]:
        """清除用戶對話歷史"""
        try:
            success = self.conversation_manager.clear_user_history(user_id, 'anthropic', platform)
            if success:
                logger.info(f"Cleared conversation history for user {user_id}")
                return True, None
            else:
                return False, "Failed to clear conversation history"
        except Exception as e:
            logger.error(f"Error clearing history for user {user_id}: {e}")
            return False, str(e)
    
    def _get_recent_conversations(self, user_id: str, platform: str = 'line', limit: int = 5) -> List[Dict]:
        """取得用戶最近的對話歷史"""
        try:
            return self.conversation_manager.get_recent_conversations(user_id, 'anthropic', limit, platform)
        except Exception as e:
            logger.warning(f"Failed to get recent conversations for user {user_id}: {e}")
            return []
    
    def _build_conversation_context(self, recent_conversations: List[Dict], current_message: str) -> List[ChatMessage]:
        """建立包含對話歷史的上下文"""
        messages = []
        
        # 添加對話歷史
        for conv in recent_conversations[-8:]:  # 最多取最近 8 輪對話
            messages.append(ChatMessage(
                role=conv['role'],
                content=conv['content']
            ))
        
        # 添加當前訊息
        messages.append(ChatMessage(role='user', content=current_message))
        
        return messages