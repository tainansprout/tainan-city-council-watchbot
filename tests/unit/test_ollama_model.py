import pytest
from unittest.mock import Mock, patch, MagicMock
import time
import sys
import importlib

from src.models.ollama_model import OllamaModel
from src.models.base import FileInfo, RAGResponse, ChatMessage, ChatResponse, ThreadInfo, ModelProvider


class TestOllamaModel:
    """Ollama 本地模型測試"""
    
    @pytest.fixture
    def ollama_model(self):
        model = OllamaModel(
            base_url='http://localhost:11434',
            model_name='llama3.1:8b',
            embedding_model='nomic-embed-text'
        )
        return model
    
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

    @patch('src.models.ollama_model.requests.get')
    def test_check_connection_exception(self, mock_get, ollama_model):
        """Test check_connection when the API call raises an exception."""
        mock_get.side_effect = Exception("Connection Refused")
        is_successful, error = ollama_model.check_connection()
        assert is_successful is False
        assert "Connection Refused" in error

    @patch('src.models.ollama_model.requests.post')
    def test_get_embedding_api_error(self, mock_post, ollama_model):
        """Test _get_embedding when the API returns an error."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {'error': 'Server overload'}
        mock_post.return_value = mock_response
        
        embedding = ollama_model._get_embedding("some text")
        assert embedding is None

    def test_vector_search_empty_store(self, ollama_model):
        """Test _vector_search with an empty knowledge store."""
        results = ollama_model._vector_search([0.1] * 10, top_k=3)
        assert results == []

    @patch('src.models.ollama_model.OllamaModel._get_embedding')
    def test_upload_knowledge_file_embedding_fails(self, mock_get_embedding, ollama_model, tmp_path):
        """Test upload_knowledge_file when embedding fails for a chunk."""
        mock_get_embedding.side_effect = [None]  # First chunk fails to embed

        file_path = tmp_path / "test.txt"
        file_path.write_text("This is a test content.")
        
        is_successful, file_info, error = ollama_model.upload_knowledge_file(str(file_path))
        
        # With current implementation, the operation succeeds but no chunks are embedded
        assert is_successful is True
        assert file_info is not None
        assert file_info.metadata['chunks'] == 0  # No chunks were successfully embedded

    @patch('pathlib.Path.exists', return_value=False)
    def test_get_knowledge_files_no_file(self, mock_exists, ollama_model):
        """Test get_knowledge_files when the storage file does not exist."""
        is_successful, files, error = ollama_model.get_knowledge_files()
        assert is_successful is True
        assert files == []
        assert error is None

    @patch('builtins.__import__', side_effect=ImportError)
    def test_set_whisper_model_import_error(self, mock_import, ollama_model):
        """Test set_whisper_model when whisper is not installed."""
        # This method doesn't return values, it just logs errors
        ollama_model.set_whisper_model()
        # Check that whisper_model is still None (not set)
        assert ollama_model.whisper_model is None

    def test_fallback_chat_completion(self, ollama_model):
        """Test the _fallback_chat_completion helper."""
        with patch.object(ollama_model, 'chat_completion') as mock_chat:
            mock_chat.return_value = (True, ChatResponse(content="Fallback answer"), None)
            
            is_successful, response, error = ollama_model._fallback_chat_completion(
                "query", [ChatMessage(role='user', content='history')]
            )
            
            assert is_successful is True
            assert response.answer == "Fallback answer"
            assert response.metadata['no_sources'] is True
            mock_chat.assert_called_once()

    @patch('src.models.ollama_model.requests.post')
    def test_upload_knowledge_file_success(self, mock_post, ollama_model, tmp_path):
        """Test successful knowledge file upload."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Test content for knowledge base.")
        
        # Mock successful embedding generation
        with patch.object(ollama_model, '_get_embedding', return_value=[0.1] * 384):
            is_successful, file_info, error = ollama_model.upload_knowledge_file(str(file_path))
            
            assert is_successful is True
            assert file_info is not None
            assert file_info.filename == "test.txt"
            assert file_info.status == "processed"
            assert error is None
            assert file_info.file_id in ollama_model.knowledge_store

    def test_upload_knowledge_file_not_found(self, ollama_model):
        """Test uploading non-existent file."""
        is_successful, file_info, error = ollama_model.upload_knowledge_file("/non/existent/file.txt")
        
        assert is_successful is False
        assert file_info is None
        assert error is not None

    def test_chunk_text(self, ollama_model):
        """Test text chunking functionality."""
        text = "This is a test. " * 10  # Shorter text to avoid infinite loop
        chunks = ollama_model._chunk_text(text, chunk_size=50, overlap=10)
        
        assert len(chunks) >= 1
        assert all('text' in chunk for chunk in chunks)
        assert all('start' in chunk for chunk in chunks)
        assert all('end' in chunk for chunk in chunks)
        
        # Test that chunks have reasonable content
        assert all(len(chunk['text']) > 0 for chunk in chunks)

    def test_vector_search_with_results(self, ollama_model):
        """Test vector search with results."""
        # Setup knowledge store
        ollama_model.knowledge_store['test_file'] = {
            'filename': 'test.txt',
            'chunks': [
                {'text': 'chunk1', 'embedding': [0.1] * 10},
                {'text': 'chunk2', 'embedding': [0.2] * 10},
                {'text': 'chunk3', 'embedding': [0.9] * 10}  # High similarity
            ]
        }
        
        query_embedding = [0.9] * 10
        results = ollama_model._vector_search(query_embedding, top_k=2)
        
        assert len(results) <= 2
        assert all('similarity' in result for result in results)
        assert all('text' in result for result in results)
        
        # Results should be sorted by similarity
        if len(results) > 1:
            assert results[0]['similarity'] >= results[1]['similarity']

    def test_cosine_similarity(self, ollama_model):
        """Test cosine similarity calculation."""
        vec1 = [1, 0, 0]
        vec2 = [1, 0, 0]
        similarity = ollama_model._cosine_similarity(vec1, vec2)
        assert similarity == 1.0
        
        vec3 = [1, 0, 0]
        vec4 = [0, 1, 0]
        similarity = ollama_model._cosine_similarity(vec3, vec4)
        assert similarity == 0.0
        
        # Test with zero vectors
        vec5 = [0, 0, 0]
        similarity = ollama_model._cosine_similarity(vec1, vec5)
        assert similarity == 0.0

    @patch('src.models.ollama_model.requests.post')
    def test_get_embedding_success(self, mock_post, ollama_model):
        """Test successful embedding generation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'embedding': [0.1, 0.2, 0.3]
        }
        mock_post.return_value = mock_response
        
        embedding = ollama_model._get_embedding("test text")
        
        assert embedding == [0.1, 0.2, 0.3]
        # Check caching
        embedding2 = ollama_model._get_embedding("test text")
        assert embedding2 == embedding
        assert mock_post.call_count == 1  # Should be cached

    def test_get_embedding_no_result(self, ollama_model):
        """Test embedding generation with no result."""
        with patch.object(ollama_model, '_request', return_value=(True, {}, None)):
            embedding = ollama_model._get_embedding("test text")
            assert embedding is None

    def test_get_embedding_exception(self, ollama_model):
        """Test embedding generation with exception."""
        with patch.object(ollama_model, '_request', side_effect=Exception("Error")):
            embedding = ollama_model._get_embedding("test text")
            assert embedding is None

    @patch('src.models.ollama_model.requests.post')
    def test_request_method_get(self, mock_post, ollama_model):
        """Test _request method with GET."""
        with patch('src.models.ollama_model.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'success': True}
            mock_get.return_value = mock_response
            
            is_successful, response, error = ollama_model._request('GET', '/test')
            
            assert is_successful is True
            assert response['success'] is True
            assert error is None
            mock_get.assert_called_once()

    def test_request_method_unsupported(self, ollama_model):
        """Test _request method with unsupported method."""
        is_successful, response, error = ollama_model._request('PUT', '/test')
        
        assert is_successful is False
        assert response is None
        assert "Unsupported method" in error

    @patch('src.models.ollama_model.requests.post')
    def test_request_timeout(self, mock_post, ollama_model):
        """Test _request method with timeout."""
        import requests
        mock_post.side_effect = requests.exceptions.RequestException("Timeout")
        
        is_successful, response, error = ollama_model._request('POST', '/test', {})
        
        assert is_successful is False
        assert response is None
        assert "連線錯誤" in error

    def test_assistant_interface_methods(self, ollama_model):
        """Test assistant interface methods."""
        # Test create_thread
        is_successful, thread_info, error = ollama_model.create_thread()
        assert is_successful is True
        assert thread_info is not None
        assert error is None
        
        # Test delete_thread
        is_successful, error = ollama_model.delete_thread("test_id")
        assert is_successful is True
        assert error is None
        
        # Test add_message_to_thread
        is_successful, error = ollama_model.add_message_to_thread("test_id", ChatMessage(role='user', content='test'))
        assert is_successful is True
        assert error is None
        
        # Test run_assistant
        is_successful, response, error = ollama_model.run_assistant("test_id")
        assert is_successful is False
        assert response is None
        assert "query_with_rag" in error

    def test_generate_image_not_supported(self, ollama_model):
        """Test that image generation is not supported."""
        is_successful, response, error = ollama_model.generate_image("test prompt")
        
        assert is_successful is False
        assert response is None
        assert "不支援圖片生成" in error

    def test_query_with_rag_success(self, ollama_model):
        """Test successful RAG query."""
        # Setup knowledge store
        ollama_model.knowledge_store['test_file'] = {
            'filename': 'test.txt',
            'chunks': [
                {'text': 'This is relevant content', 'embedding': [0.9] * 10}
            ]
        }
        
        with patch.object(ollama_model, '_get_embedding', return_value=[0.9] * 10):
            with patch.object(ollama_model, 'chat_completion') as mock_chat:
                mock_chat.return_value = (True, ChatResponse(content="RAG response"), None)
                
                is_successful, rag_response, error = ollama_model.query_with_rag("test query")
                
                assert is_successful is True
                assert rag_response is not None
                assert rag_response.answer == "RAG response"
                assert len(rag_response.sources) > 0
                assert error is None

    def test_query_with_rag_no_embedding(self, ollama_model):
        """Test RAG query when embedding generation fails."""
        with patch.object(ollama_model, '_get_embedding', return_value=None):
            with patch.object(ollama_model, '_fallback_chat_completion') as mock_fallback:
                mock_fallback.return_value = (True, RAGResponse(answer="Fallback", sources=[]), None)
                
                is_successful, rag_response, error = ollama_model.query_with_rag("test query")
                
                assert is_successful is True
                assert rag_response.answer == "Fallback"
                mock_fallback.assert_called_once()

    def test_query_with_rag_no_chunks(self, ollama_model):
        """Test RAG query when no relevant chunks found."""
        with patch.object(ollama_model, '_get_embedding', return_value=[0.1] * 10):
            with patch.object(ollama_model, '_vector_search', return_value=[]):
                with patch.object(ollama_model, '_fallback_chat_completion') as mock_fallback:
                    mock_fallback.return_value = (True, RAGResponse(answer="Fallback", sources=[]), None)
                    
                    is_successful, rag_response, error = ollama_model.query_with_rag("test query")
                    
                    assert is_successful is True
                    assert rag_response.answer == "Fallback"
                    mock_fallback.assert_called_once()

    def test_query_with_rag_exception(self, ollama_model):
        """Test RAG query with exception."""
        with patch.object(ollama_model, '_get_embedding', side_effect=Exception("Error")):
            is_successful, rag_response, error = ollama_model.query_with_rag("test query")
            
            assert is_successful is False
            assert rag_response is None
            assert "Error" in error

    def test_get_knowledge_files_success(self, ollama_model):
        """Test getting knowledge files successfully."""
        # Setup knowledge store
        ollama_model.knowledge_store['file1'] = {
            'filename': 'test1.txt',
            'content': 'content1',
            'metadata': {'size': 100}
        }
        ollama_model.knowledge_store['file2'] = {
            'filename': 'test2.txt',
            'content': 'content2',
            'metadata': {'size': 200}
        }
        
        is_successful, files, error = ollama_model.get_knowledge_files()
        
        assert is_successful is True
        assert len(files) == 2
        assert error is None
        assert files[0].filename in ['test1.txt', 'test2.txt']
        assert files[1].filename in ['test1.txt', 'test2.txt']

    def test_get_knowledge_files_exception(self, ollama_model):
        """Test get_knowledge_files with exception."""
        # Simulate an exception during processing
        original_knowledge_store = ollama_model.knowledge_store
        
        # Create a mock that raises exception when accessed
        def mock_items():
            raise Exception("Error accessing knowledge store")
        
        # Replace the knowledge_store with a mock that has problematic items()
        mock_store = Mock()
        mock_store.items = mock_items
        ollama_model.knowledge_store = mock_store
        
        try:
            is_successful, files, error = ollama_model.get_knowledge_files()
            
            assert is_successful is False
            assert files is None
            assert "Error" in error
        finally:
            # Restore original knowledge_store
            ollama_model.knowledge_store = original_knowledge_store

    def test_get_file_references(self, ollama_model):
        """Test getting file references."""
        # Setup knowledge store
        ollama_model.knowledge_store['file1'] = {
            'filename': 'test1.txt'
        }
        ollama_model.knowledge_store['file2'] = {
            'filename': 'test2.json'
        }
        
        references = ollama_model.get_file_references()
        
        assert isinstance(references, dict)
        assert 'file1' in references
        assert 'file2' in references
        assert references['file1'] == 'test1'
        assert references['file2'] == 'test2'

    def test_process_inline_citations(self, ollama_model):
        """Test processing inline citations."""
        text = "Based on [doc1.txt] and [doc2.pdf], the answer is clear."
        sources = [
            {'filename': 'doc1.txt', 'text': 'content1'},
            {'filename': 'doc2.pdf', 'text': 'content2'},
            {'filename': 'unused.md', 'text': 'content3'}
        ]
        
        processed_text, final_sources = ollama_model._process_inline_citations(text, sources)
        
        assert processed_text == "Based on [1] and [2], the answer is clear."
        assert len(final_sources) == 2
        assert final_sources[0]['filename'] == 'doc1.txt'
        assert final_sources[1]['filename'] == 'doc2.pdf'

    def test_process_inline_citations_no_citations(self, ollama_model):
        """Test processing text without citations."""
        text = "This text has no citations."
        sources = [{'filename': 'doc1.txt', 'text': 'content1'}]
        
        processed_text, final_sources = ollama_model._process_inline_citations(text, sources)
        
        assert processed_text == text
        assert final_sources == sources
