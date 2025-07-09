import pytest
from unittest.mock import Mock, patch, MagicMock
import time
import sys

from src.models.ollama_model import OllamaModel
from src.models.base import FileInfo, RAGResponse, ChatMessage, ChatResponse, ThreadInfo, ModelProvider


class TestOllamaModel:
    """Ollama 本地模型測試"""
    
    @pytest.fixture
    def ollama_model(self):
        return OllamaModel(
            base_url='http://localhost:11434',
            model_name='llama3.1:8b',
            embedding_model='nomic-embed-text'
        )
    
    def test_init_with_defaults(self):
        """測試初始化預設值"""
        model = OllamaModel()
        
        assert model.base_url == 'http://localhost:11434'
        assert model.model_name == 'llama3.1:8b'
        assert model.embedding_model == 'nomic-embed-text'
        assert model.local_cache_enabled == True
        assert model.max_cache_size == 1000
        assert isinstance(model.knowledge_store, dict)
        assert isinstance(model.conversation_cache, dict)
        assert isinstance(model.embeddings_cache, dict)
    
    def test_get_provider(self, ollama_model):
        """測試模型提供商識別"""
        provider = ollama_model.get_provider()
        assert provider == ModelProvider.OLLAMA
    
    @patch('src.models.ollama_model.requests.get')
    def test_check_connection_success(self, mock_get, ollama_model):
        """測試連線檢查成功"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'models': [
                {'name': 'llama3.1:8b'},
                {'name': 'nomic-embed-text'}
            ]
        }
        mock_get.return_value = mock_response
        
        is_successful, error = ollama_model.check_connection()
        assert is_successful == True
        assert error is None
    
    @patch('src.models.ollama_model.requests.get')
    def test_check_connection_model_not_available(self, mock_get, ollama_model):
        """測試模型不可用"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'models': [
                {'name': 'llama2:7b'},
                {'name': 'mistral:7b'}
            ]
        }
        mock_get.return_value = mock_response
        
        is_successful, error = ollama_model.check_connection()
        assert is_successful == False
        assert 'llama3.1:8b' in error
        assert 'not available' in error.lower() or '不可用' in error
    
    @patch('src.models.ollama_model.requests.post')
    def test_chat_completion_success(self, mock_post, ollama_model):
        """測試聊天完成成功"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'message': {
                'content': 'Hello! How can I help you today?'
            },
            'done_reason': 'stop',
            'model': 'llama3.1:8b',
            'total_duration': 1000000,
            'load_duration': 100000,
            'prompt_eval_count': 10,
            'eval_count': 20
        }
        mock_post.return_value = mock_response
        
        messages = [ChatMessage(role='user', content='Hello')]
        is_successful, response, error = ollama_model.chat_completion(messages)
        
        assert is_successful == True
        assert response is not None
        assert response.content == 'Hello! How can I help you today?'
        assert response.finish_reason == 'stop'
        assert 'total_duration' in response.metadata
        assert 'eval_count' in response.metadata
        assert error is None
    
    @patch('src.models.ollama_model.OllamaModel.query_with_rag')
    @patch('src.models.ollama_model.OllamaModel._get_recent_conversations')
    def test_chat_with_user_privacy_mode(self, mock_get_conversations, mock_query_rag, ollama_model):
        """測試隱私模式的 chat_with_user"""
        # 模擬對話歷史
        local_conversations = [
            {'role': 'user', 'content': 'Previous question', 'timestamp': time.time() - 300},
            {'role': 'assistant', 'content': 'Previous answer', 'timestamp': time.time() - 299}
        ]
        
        mock_get_conversations.return_value = local_conversations
        
        # 模擬 RAG 回應
        mock_rag_response = RAGResponse(
            answer="This is a local, privacy-protected response.",
            sources=[],
            metadata={
                'model': 'ollama', 
                'local_processing': True,
                'privacy_protected': True,
                'embedding_model': 'nomic-embed-text'
            }
        )
        mock_query_rag.return_value = (True, mock_rag_response, None)
        
        # 模擬對話管理器
        mock_conversation_manager = Mock()
        mock_conversation_manager.add_message.return_value = True
        ollama_model.conversation_manager = mock_conversation_manager
        
        # 執行測試（隱私模式）
        is_successful, rag_response, error = ollama_model.chat_with_user(
            user_id='test_user_123',
            message='Tell me something while protecting my privacy',
            privacy_mode=True,  # 隱私模式啟用
            use_local_cache=True
        )
        
        # 驗證結果
        assert is_successful == True
        assert rag_response is not None
        assert error is None
        assert 'privacy-protected' in rag_response.answer
        assert rag_response.metadata['privacy_protected'] == True
        assert rag_response.metadata['local_processing'] == True
        assert rag_response.metadata['user_id'] == 'test_user_123'
        assert rag_response.metadata['model_provider'] == 'ollama'
        
        # 驗證隱私模式：不應該調用資料庫存儲
        mock_conversation_manager.add_message.assert_not_called()
        
        # 驗證本地快取使用
        assert 'test_user_123' in ollama_model.conversation_cache
        user_cache = ollama_model.conversation_cache['test_user_123']['messages']
        assert len(user_cache) == 2  # user message + assistant response
        assert user_cache[0]['role'] == 'user'
        assert user_cache[1]['role'] == 'assistant'
    
    @patch('src.models.ollama_model.OllamaModel.query_with_rag')
    @patch('src.models.ollama_model.OllamaModel._get_recent_conversations')
    def test_chat_with_user_database_mode(self, mock_get_conversations, mock_query_rag, ollama_model):
        """測試資料庫模式的 chat_with_user"""
        mock_get_conversations.return_value = []
        
        mock_rag_response = RAGResponse(
            answer="Database mode response",
            sources=[],
            metadata={'model': 'ollama'}
        )
        mock_query_rag.return_value = (True, mock_rag_response, None)
        
        mock_conversation_manager = Mock()
        mock_conversation_manager.add_message.return_value = True
        ollama_model.conversation_manager = mock_conversation_manager
        
        # 執行測試（非隱私模式）
        is_successful, rag_response, error = ollama_model.chat_with_user(
            user_id='test_user_456',
            message='Regular conversation',
            privacy_mode=False,  # 關閉隱私模式
            use_local_cache=True
        )
        
        assert is_successful == True
        assert rag_response.metadata['privacy_protected'] == False
        
        # 驗證資料庫存儲被調用
        assert mock_conversation_manager.add_message.call_count == 2  # user + assistant
        mock_conversation_manager.add_message.assert_any_call('test_user_456', 'ollama', 'user', 'Regular conversation', 'line')
        mock_conversation_manager.add_message.assert_any_call('test_user_456', 'ollama', 'assistant', 'Database mode response', 'line')
    
    def test_clear_user_history_local_and_db(self, ollama_model):
        """測試清除用戶歷史（本地快取 + 資料庫）"""
        # 設置本地快取
        ollama_model.conversation_cache['test_user_789'] = {
            'messages': [
                {'role': 'user', 'content': 'Test message', 'timestamp': time.time()}
            ],
            'created_at': time.time()
        }
        
        # 模擬對話管理器
        mock_conversation_manager = Mock()
        mock_conversation_manager.clear_user_history.return_value = True
        ollama_model.conversation_manager = mock_conversation_manager
        
        is_successful, error = ollama_model.clear_user_history('test_user_789')
        
        assert is_successful == True
        assert error is None
        
        # 驗證本地快取被清除
        assert 'test_user_789' not in ollama_model.conversation_cache
        
        # 驗證資料庫清除被調用
        mock_conversation_manager.clear_user_history.assert_called_once_with('test_user_789', 'ollama', 'line')
    
    def test_local_cache_operations(self, ollama_model):
        """測試本地快取操作"""
        user_id = 'test_cache_user'
        
        # 測試新增訊息到快取
        ollama_model._add_to_local_cache(user_id, 'user', 'Hello from cache')
        ollama_model._add_to_local_cache(user_id, 'assistant', 'Cache response')
        
        # 驗證快取內容
        assert user_id in ollama_model.conversation_cache
        messages = ollama_model.conversation_cache[user_id]['messages']
        assert len(messages) == 2
        assert messages[0]['role'] == 'user'
        assert messages[0]['content'] == 'Hello from cache'
        assert messages[1]['role'] == 'assistant'
        assert messages[1]['content'] == 'Cache response'
        
        # 測試快取大小限制
        ollama_model.max_cache_size = 4  # 設置小的限制
        for i in range(5):
            ollama_model._add_to_local_cache(user_id, 'user', f'Message {i}')
        
        # 驗證快取被清理
        messages = ollama_model.conversation_cache[user_id]['messages']
        assert len(messages) <= ollama_model.max_cache_size
    
    def test_build_local_conversation_context(self, ollama_model):
        """測試本地對話上下文建構"""
        conversations = []
        for i in range(25):  # 測試大量對話
            conversations.extend([
                {'role': 'user', 'content': f'User message {i}'},
                {'role': 'assistant', 'content': f'Assistant response {i}'}
            ])
        
        messages = ollama_model._build_local_conversation_context(conversations, "Current question")
        
        # 驗證結果
        assert len(messages) <= 22  # 系統提示 + 最多20輪歷史 + 當前訊息
        assert messages[0].role == "system"  # 第一個是系統提示
        assert messages[-1].content == "Current question"  # 最後一個是當前訊息
        assert messages[-1].role == "user"
        
        # 驗證系統提示包含本地化指導
        system_content = messages[0].content
        assert "本地化" in system_content
        assert "隱私保護" in system_content
        assert "本地運算" in system_content or "本地處理" in system_content
    
    @patch('src.models.ollama_model.OllamaModel._fallback_chat_completion')
    def test_query_with_rag_local_context(self, mock_fallback, ollama_model):
        """測試本地上下文的 RAG 查詢 - fallback"""
        # 模擬無法生成嵌入向量，觸發 fallback
        with patch.object(ollama_model, '_get_embedding', return_value=None):
            mock_fallback.return_value = (True, RAGResponse(answer="Local fallback response", sources=[]), None)

            is_successful, rag_response, error = ollama_model.query_with_rag(
                query="What can you tell me?"
            )

            assert is_successful == True
            assert rag_response.answer == 'Local fallback response'
            mock_fallback.assert_called_once()
    
    def test_get_privacy_stats(self, ollama_model):
        """測試隱私保護統計資訊"""
        user_id = 'privacy_test_user'
        
        # 設置測試資料
        ollama_model._add_to_local_cache(user_id, 'user', 'Test message')
        ollama_model.knowledge_store['test_file'] = {
            'chunks': [{'text': 'chunk1'}, {'text': 'chunk2'}]
        }
        ollama_model.embeddings_cache['test_embedding'] = [0.1] * 384
        
        stats = ollama_model.get_privacy_stats(user_id)
        
        assert stats['local_cache_messages'] == 1
        assert stats['knowledge_chunks'] == 2
        assert stats['embedding_cache_size'] == 1
        assert stats['privacy_protected'] == True
        assert stats['local_only'] == True
    
    def test_local_whisper_transcription(self, ollama_model):
        """測試本地 Whisper 語音轉錄"""
        # 直接設置模擬的 Whisper 模型
        mock_model = Mock()
        mock_model.transcribe.return_value = {"text": "This is a local transcription."}
        ollama_model.whisper_model = mock_model
        
        # 測試轉錄
        is_successful, text, error = ollama_model.transcribe_audio("/fake/audio/file.wav")
        
        assert is_successful == True
        assert text == "This is a local transcription."
        assert error is None
        
        # 驗證模型被調用
        mock_model.transcribe.assert_called_once_with("/fake/audio/file.wav")
    
    @patch('src.models.ollama_model.OllamaModel._transcribe_with_local_whisper')
    def test_local_whisper_not_installed(self, mock_transcribe, ollama_model):
        """測試 Whisper 未安裝的情況"""
        # 模擬 whisper 套件未安裝
        ollama_model.whisper_model = None
        with patch.dict('sys.modules', {'whisper': None}):
            is_successful, text, error = ollama_model.transcribe_audio("/fake/audio/file.wav")

        assert is_successful is False
        assert text is None
        assert "Whisper 套件未安裝" in error
        mock_transcribe.assert_not_called()
    
    @patch('src.models.ollama_model.requests.post')
    def test_error_handling(self, mock_post, ollama_model):
        """測試錯誤處理"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'error': 'Model not found'
        }
        mock_post.return_value = mock_response
        
        messages = [ChatMessage(role='user', content='Hello')]
        is_successful, response, error = ollama_model.chat_completion(messages)
        
        assert is_successful == False
        assert response is None
        assert 'Model not found' in error
    
    def test_system_prompt_structure(self, ollama_model):
        """測試本地化系統提示詞結構"""
        system_prompt = ollama_model._build_local_system_prompt()
        
        # 檢查本地化特性
        assert '本地化' in system_prompt
        assert '隱私保護' in system_prompt
        assert '本地運算' in system_prompt or '本地處理' in system_prompt

    @patch('src.models.ollama_model.OllamaModel._transcribe_with_local_whisper', return_value=(True, "Transcription success", None))
    def test_transcribe_audio_success_with_set_model(self, mock_transcribe, ollama_model):
        """測試使用 set_whisper_model 成功轉錄"""
        # 模擬 whisper 已安裝且模型已設定
        ollama_model.whisper_model = Mock()

        is_successful, text, error = ollama_model.transcribe_audio('/fake/path.mp3')

        assert is_successful is True
        assert text == "Transcription success"
        assert error is None
        mock_transcribe.assert_called_once_with('/fake/path.mp3')

    def test_transcribe_audio_whisper_not_installed(self, ollama_model):
        """測試 transcribe_audio 在 whisper 未安裝時的行為"""
        # 透過 patch 模擬 ImportError
        with patch.dict('sys.modules', {'whisper': None}):
            is_successful, text, error = ollama_model.transcribe_audio('/fake/path.mp3')
            assert is_successful is False
            assert text is None
            assert "Whisper 套件未安裝" in error

    @patch('src.models.ollama_model.OllamaModel._transcribe_with_local_whisper', side_effect=Exception("Whisper internal error"))
    def test_transcribe_audio_whisper_fails(self, mock_transcribe, ollama_model):
        """測試 whisper 轉錄過程中發生例外"""
        ollama_model.whisper_model = Mock()

        is_successful, text, error = ollama_model.transcribe_audio('/fake/path.mp3')

        assert is_successful is False
        assert text is None
        assert "Whisper internal error" in error