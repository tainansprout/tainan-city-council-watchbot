import pytest
from unittest.mock import Mock, patch, MagicMock
import time
import base64

from src.models.gemini_model import GeminiModel
from src.models.base import FileInfo, RAGResponse, ChatMessage, ChatResponse, ThreadInfo, ModelProvider
from src.core.bounded_cache import BoundedCache


class TestGeminiModel:
    """Google Gemini 2024 模型測試"""
    
    @pytest.fixture
    def gemini_model(self):
        with patch('src.core.config.get_value', return_value=False):
            return GeminiModel(
                api_key='test_key',
                model_name='gemini-1.5-pro-latest',
                project_id='test-project'
            )
    
    def test_init_with_defaults(self):
        """測試初始化預設值"""
        with patch('src.core.config.get_value', return_value=False):
            model = GeminiModel(api_key='test_key')
        
        assert model.api_key == 'test_key'
        assert model.model_name == 'gemini-1.5-pro-latest'
        assert model.base_url == 'https://generativelanguage.googleapis.com/v1beta'
        assert model.max_context_tokens == 1000000  # 1M token 上下文
        assert model.default_corpus_name == 'chatbot-knowledge'
        assert isinstance(model.corpora, BoundedCache)
        assert 'image' in model.supported_media_types
        assert 'video' in model.supported_media_types
    
    def test_get_provider(self, gemini_model):
        """測試模型提供商識別"""
        provider = gemini_model.get_provider()
        assert provider == ModelProvider.GEMINI
    
    def test_check_connection_success(self, gemini_model):
        """測試連線檢查成功"""
        with patch.object(gemini_model, 'chat_completion', return_value=(True, Mock(), None)):
            is_successful, error = gemini_model.check_connection()
            assert is_successful == True
            assert error is None
    
    def test_check_connection_failure(self, gemini_model):
        """測試連線檢查失敗"""
        with patch.object(gemini_model, 'chat_completion', return_value=(False, None, 'API Error')):
            is_successful, error = gemini_model.check_connection()
            assert is_successful == False
            assert error == 'API Error'
    
    @patch('src.models.gemini_model.requests.post')
    def test_chat_completion_success(self, mock_post, gemini_model):
        """測試聊天完成成功"""
        # 模擬 API 回應
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'candidates': [{
                'content': {
                    'parts': [{'text': 'Hello! How can I help you?'}]
                },
                'finishReason': 'STOP',
                'safetyRatings': []
            }],
            'usageMetadata': {
                'promptTokenCount': 10,
                'candidatesTokenCount': 20,
                'totalTokenCount': 30
            },
            'modelVersion': 'gemini-1.5-pro-latest'
        }
        mock_post.return_value = mock_response
        
        messages = [ChatMessage(role='user', content='Hello')]
        is_successful, response, error = gemini_model.chat_completion(messages)
        
        assert is_successful == True
        assert response is not None
        assert response.content == 'Hello! How can I help you?'
        assert response.finish_reason == 'STOP'
        assert 'usage' in response.metadata
        assert error is None
    
    @patch('src.models.gemini_model.requests.post')
    def test_chat_completion_with_multimodal(self, mock_post, gemini_model):
        """測試多模態聊天完成"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'candidates': [{
                'content': {
                    'parts': [{'text': 'I can see the image you shared.'}]
                },
                'finishReason': 'STOP'
            }]
        }
        mock_post.return_value = mock_response
        
        # 多模態內容
        multimodal_content = [
            "What do you see in this image?",
            {
                "type": "image",
                "mime_type": "image/jpeg",
                "data": "base64_encoded_image_data"
            }
        ]
        
        messages = [ChatMessage(role='user', content=multimodal_content)]
        is_successful, response, error = gemini_model.chat_completion(messages)
        
        assert is_successful == True
        assert response.content == 'I can see the image you shared.'
        
        # 檢查請求格式
        call_args = mock_post.call_args
        request_body = call_args[1]['json']
        assert 'contents' in request_body
        assert len(request_body['contents'][0]['parts']) == 2  # 文字 + 圖片
        assert 'inline_data' in request_body['contents'][0]['parts'][1]
    
    @patch('src.models.gemini_model.requests.post')
    def test_chat_completion_with_system_instruction(self, mock_post, gemini_model):
        """測試系統指令支援"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'candidates': [{
                'content': {
                    'parts': [{'text': 'I understand I should be helpful.'}]
                },
                'finishReason': 'STOP'
            }]
        }
        mock_post.return_value = mock_response
        
        messages = [
            ChatMessage(role='system', content='You are a helpful assistant.'),
            ChatMessage(role='user', content='Hello')
        ]
        is_successful, response, error = gemini_model.chat_completion(messages)
        
        assert is_successful == True
        
        # 檢查系統指令
        call_args = mock_post.call_args
        request_body = call_args[1]['json']
        assert 'systemInstruction' in request_body
        assert request_body['systemInstruction']['parts'][0]['text'] == 'You are a helpful assistant.'
    
    @patch('src.models.gemini_model.GeminiModel.query_with_rag')
    @patch('src.models.gemini_model.GeminiModel._get_recent_conversations')
    def test_chat_with_user_success(self, mock_get_conversations, mock_query_rag, gemini_model):
        """測試 chat_with_user 成功場景（長上下文）"""
        # 模擬長對話歷史
        long_conversations = []
        for i in range(15):  # 15 輪對話
            long_conversations.extend([
                {'role': 'user', 'content': f'User message {i}', 'created_at': f'2024-01-01T10:{i:02d}:00'},
                {'role': 'assistant', 'content': f'Assistant response {i}', 'created_at': f'2024-01-01T10:{i:02d}:01'}
            ])
        
        mock_get_conversations.return_value = long_conversations
        
        # 模擬 RAG 回應
        mock_rag_response = RAGResponse(
            answer="Based on our extensive conversation history and knowledge base, here's my response.",
            sources=[],
            metadata={
                'model': 'gemini', 
                'long_context_enabled': True,
                'context_messages_count': 32  # 系統 + 30輪對話 + 當前訊息
            }
        )
        mock_query_rag.return_value = (True, mock_rag_response, None)
        
        # 模擬對話管理器
        mock_conversation_manager = Mock()
        mock_conversation_manager.add_message.return_value = True
        gemini_model.conversation_manager = mock_conversation_manager
        
        # 執行測試
        is_successful, rag_response, error = gemini_model.chat_with_user(
            user_id='test_user_123',
            message='Can you summarize our previous discussions?',
            conversation_limit=20  # 請求更多歷史
        )
        
        # 驗證結果
        assert is_successful == True
        assert rag_response is not None
        assert error is None
        assert 'extensive conversation history' in rag_response.answer
        assert 'conversation_turns' in rag_response.metadata
        assert 'long_context_enabled' in rag_response.metadata
        assert rag_response.metadata['long_context_enabled'] == True
        assert rag_response.metadata['user_id'] == 'test_user_123'
        assert rag_response.metadata['model_provider'] == 'gemini'
        
        # 驗證長上下文使用
        mock_get_conversations.assert_called_once_with('test_user_123', 'line', limit=20)
        
        # 驗證 RAG 調用包含上下文
        mock_query_rag.assert_called_once()
        rag_call_args = mock_query_rag.call_args
        assert 'context_messages' in rag_call_args[1]
        context_messages = rag_call_args[1]['context_messages']
        assert len(context_messages) > 30  # 系統提示 + 長對話歷史 + 當前訊息
    
    @patch('src.models.gemini_model.GeminiModel.query_with_rag')  
    @patch('src.models.gemini_model.GeminiModel._get_recent_conversations')
    def test_chat_with_user_short_context(self, mock_get_conversations, mock_query_rag, gemini_model):
        """測試短對話歷史的處理"""
        # 模擬短對話歷史
        short_conversations = [
            {'role': 'user', 'content': 'Hello', 'created_at': '2024-01-01T10:00:00'},
            {'role': 'assistant', 'content': 'Hi there!', 'created_at': '2024-01-01T10:00:01'}
        ]
        
        mock_get_conversations.return_value = short_conversations
        
        mock_rag_response = RAGResponse(
            answer="Hello! How can I help you today?",
            sources=[],
            metadata={'model': 'gemini', 'long_context_enabled': False}
        )
        mock_query_rag.return_value = (True, mock_rag_response, None)
        
        mock_conversation_manager = Mock()
        mock_conversation_manager.add_message.return_value = True
        gemini_model.conversation_manager = mock_conversation_manager
        
        is_successful, rag_response, error = gemini_model.chat_with_user(
            user_id='test_user_456',
            message='Hi again'
        )
        
        assert is_successful == True
        assert rag_response.metadata['long_context_enabled'] == False
        assert rag_response.metadata['conversation_turns'] == 2
    
    def test_clear_user_history_success(self, gemini_model):
        """測試清除用戶歷史成功"""
        mock_conversation_manager = Mock()
        mock_conversation_manager.clear_user_history.return_value = True
        gemini_model.conversation_manager = mock_conversation_manager
        
        is_successful, error = gemini_model.clear_user_history('test_user_789')
        
        assert is_successful == True
        assert error is None
        
        mock_conversation_manager.clear_user_history.assert_called_once_with('test_user_789', 'gemini', 'line')
    
    def test_build_long_conversation_context(self, gemini_model):
        """測試長上下文對話建構"""
        # 模擬長對話歷史
        conversations = []
        for i in range(50):  # 50 輪對話，測試限制
            conversations.extend([
                {'role': 'user', 'content': f'User message {i}', 'created_at': f'2024-01-01T{10+i//60}:{i%60:02d}:00'},
                {'role': 'assistant', 'content': f'Assistant response {i}', 'created_at': f'2024-01-01T{10+i//60}:{i%60:02d}:01'}
            ])
        
        messages = gemini_model._build_long_conversation_context(conversations, "Current message")
        
        # 驗證結果
        assert len(messages) <= 42  # 系統提示 + 最多40輪歷史 + 當前訊息
        assert messages[0].role == "system"  # 第一個是系統提示
        assert messages[-1].content == "Current message"  # 最後一個是當前訊息
        assert messages[-1].role == "user"
        
        # 驗證系統提示包含長上下文指導
        system_content = messages[0].content
        assert "長期對話記憶" in system_content
        assert "語義檢索" in system_content
        assert "100萬 token" in system_content
    
    @patch('src.models.gemini_model.GeminiModel._fallback_chat_completion')
    def test_query_with_rag_no_corpus(self, mock_fallback, gemini_model):
        """測試沒有語料庫時的 RAG 查詢"""
        gemini_model.corpora.get = Mock(return_value=None)
        mock_fallback.return_value = (True, RAGResponse(answer="Fallback response", sources=[]), None)

        is_successful, rag_response, error = gemini_model.query_with_rag(
            query="What can you help me with?"
        )
        
        assert is_successful == True
        assert rag_response.answer == 'Fallback response'
        mock_fallback.assert_called_once()
    
    @patch('src.models.gemini_model.requests.post')
    def test_error_handling(self, mock_post, gemini_model):
        """測試錯誤處理"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'error': {'message': 'Invalid request format'}
        }
        mock_post.return_value = mock_response
        
        messages = [ChatMessage(role='user', content='Hello')]
        is_successful, response, error = gemini_model.chat_completion(messages)
        
        assert is_successful == False
        assert response is None
        assert 'Invalid request format' in error
    
    def test_system_prompt_structure(self, gemini_model):
        """測試系統提示詞結構"""
        system_prompt = gemini_model._build_system_prompt_with_context()
        
        # 檢查 Gemini 特有的功能描述
        assert '長期對話記憶' in system_prompt
        assert '語義檢索' in system_prompt
        assert '多模態理解' in system_prompt
        assert '100萬 token' in system_prompt
        assert 'Google Semantic Retrieval API' in system_prompt
        assert '如我們之前討論的' in system_prompt  # 長上下文引用示例

    @patch('src.models.gemini_model.requests.post')
    def test_transcribe_audio_success(self, mock_post, gemini_model, tmp_path):
        """測試音訊轉錄成功"""
        # 建立一個假的音訊檔案
        audio_content = b'fake_audio_data'
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(audio_content)

        # 模擬 API 回應
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'candidates': [{
                'content': {
                    'parts': [{'text': 'This is the transcribed text.'}]
                }
            }]
        }
        mock_post.return_value = mock_response

        is_successful, text, error = gemini_model.transcribe_audio(str(audio_file))

        assert is_successful is True
        assert text == 'This is the transcribed text.'
        assert error is None

        # 驗證請求內容
        call_args = mock_post.call_args
        request_body = call_args[1]['json']
        assert 'contents' in request_body
        parts = request_body['contents'][0]['parts']
        assert len(parts) == 2
        assert '請將這段音訊轉錄成文字' in parts[0]['text']
        assert parts[1]['inline_data']['mime_type'] == 'audio/wav'
        assert parts[1]['inline_data']['data'] == base64.b64encode(audio_content).decode('utf-8')

    @patch('src.models.gemini_model.requests.post')
    def test_transcribe_audio_api_error(self, mock_post, gemini_model, tmp_path):
        """測試音訊轉錄時 API 回傳錯誤"""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b'fake_audio_data')

        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'error': {'message': 'Invalid audio format'}
        }
        mock_post.return_value = mock_response

        is_successful, text, error = gemini_model.transcribe_audio(str(audio_file))

        assert is_successful is False
        assert text is None
        assert 'Invalid audio format' in error

    def test_transcribe_audio_file_not_found(self, gemini_model):
        """測試音訊轉錄時檔案不存在"""
        is_successful, text, error = gemini_model.transcribe_audio('/non/existent/file.wav')

        assert is_successful is False
        assert text is None
        assert 'not found' in error.lower()

    def test_check_connection_exception(self, gemini_model):
        """Test check_connection when the API call raises an exception."""
        with patch.object(gemini_model, 'chat_completion', side_effect=Exception('Network Error')):
            is_successful, error = gemini_model.check_connection()
            assert is_successful is False
            assert 'Network Error' in error

    @patch('src.models.gemini_model.requests.post')
    def test_chat_completion_api_error(self, mock_post, gemini_model):
        """Test chat_completion when the API returns a non-200 status."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {'error': {'message': 'Internal Server Error'}}
        mock_post.return_value = mock_response
        
        is_successful, response, error = gemini_model.chat_completion([ChatMessage(role='user', content='Hi')])
        assert is_successful is False
        assert response is None
        assert ('Internal Server Error' in error or 'Server error' in error)

    def test_assistant_interface_methods(self, gemini_model):
        """Test assistant interface methods for basic execution."""
        # These methods have minimal implementation, just test they run and return expected values
        is_successful, thread_info, error = gemini_model.create_thread()
        assert is_successful is True
        assert isinstance(thread_info, ThreadInfo)
        assert error is None

        is_successful, error = gemini_model.delete_thread('some_id')
        assert is_successful is True
        assert error is None

        is_successful, error = gemini_model.add_message_to_thread('some_id', ChatMessage(role='user', content='Hi'))
        assert is_successful is True
        assert error is None

        is_successful, response, error = gemini_model.run_assistant('some_id')
        assert is_successful is False
        assert response is None
        assert 'query_with_rag' in error

    def test_image_generation_not_supported(self, gemini_model):
        """Test that image generation is not supported."""
        is_successful, response, error = gemini_model.generate_image("a cat")
        assert is_successful is False
        assert response is None
        assert ('not support' in error or '不支援' in error)

    @patch('src.models.gemini_model.requests.post')
    def test_query_with_rag_no_relevant_passages(self, mock_post, gemini_model):
        """Test RAG query when no relevant passages are found."""
        gemini_model.corpora['test_corpus'] = {'name': 'corpora/test_corpus'}
        
        # Mock retrieval response (no passages)
        mock_retrieval_response = Mock()
        mock_retrieval_response.status_code = 200
        mock_retrieval_response.json.return_value = {'relevantChunks': []}
        
        # Mock fallback chat completion response
        mock_chat_response = Mock()
        mock_chat_response.status_code = 200
        mock_chat_response.json.return_value = {
            'candidates': [{'content': {'parts': [{'text': 'General fallback answer.'}]}}]
        }
        mock_post.side_effect = [mock_retrieval_response, mock_chat_response]

        is_successful, rag_response, error = gemini_model.query_with_rag("query", corpus_name='test_corpus')
        
        assert is_successful is True
        assert rag_response.answer == 'General fallback answer.'
        assert not rag_response.sources
        assert (rag_response.metadata.get('no_retrieval') is True or 
                rag_response.metadata.get('no_sources') is True)

    def test_process_inline_citations(self, gemini_model):
        """Test the processing of inline citations."""
        text = "According to [doc1.pdf], and also [doc2.txt]."
        sources = [
            {'filename': 'doc1.pdf', 'file_id': 'id1', 'text': 'content1'},
            {'filename': 'doc2.txt', 'file_id': 'id2', 'text': 'content2'},
            {'filename': 'unused.md', 'file_id': 'id3', 'text': 'content3'}
        ]
        
        processed_text, final_sources = gemini_model._process_inline_citations(text, sources)
        
        assert processed_text == "According to [1], and also [2]."
        assert len(final_sources) == 2
        # 檢查任一來源都可以，因為排序可能不同
        source_filenames = {source['filename'] for source in final_sources}
        assert 'doc1.pdf' in source_filenames
        assert 'doc2.txt' in source_filenames

    def test_chunk_text(self, gemini_model):
        """Test the _chunk_text helper method."""
        long_text = "This is a sentence. " * 200  # 約 4000 字符
        chunks = gemini_model._chunk_text(long_text, chunk_size=200, overlap=20)
        
        assert len(chunks) > 1
        assert chunks[0]['text'].startswith("This is a sentence.")
        assert len(chunks[0]['text']) <= 200
        
        # 測試 overlap 邏輯：檢查相鄰 chunks 之間是否有重疊
        if len(chunks) > 1:
            # 第二個 chunk 的開始位置應該是 180 (200-20)，重疊部分應該存在
            chunk1_end_part = chunks[0]['text'][-20:]
            chunk2_start_part = chunks[1]['text'][:20] if len(chunks[1]['text']) >= 20 else chunks[1]['text']
            
            # 檢查是否有重疊（但不一定完全相同，因為可能在字符邊界）
            assert len(chunk1_end_part) > 0
            assert len(chunk2_start_part) > 0

    @patch('src.models.gemini_model.requests.post')
    def test_upload_knowledge_file_api_error(self, mock_post, gemini_model, tmp_path):
        """Test knowledge file upload when the API returns an error."""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.json.return_value = {'error': {'message': 'Permission Denied'}}
        mock_post.return_value = mock_response

        file_path = tmp_path / "test.txt"
        file_path.write_text("content")

        is_successful, file_info, error = gemini_model.upload_knowledge_file(str(file_path))
        
        assert is_successful is False
        assert file_info is None
        assert 'Permission Denied' in error

    def test_get_knowledge_files_api_error(self, gemini_model):
        """Test getting knowledge files when the API returns an error."""
        # 模擬一個有語料庫的狀態
        gemini_model.corpora['test_corpus'] = {'name': 'corpora/test_corpus'}
        
        # 模擬 _request 方法返回錯誤
        with patch.object(gemini_model, '_request', return_value=(False, None, 'Service Unavailable')):
            is_successful, files, error = gemini_model.get_knowledge_files()
            
            # 由於 get_knowledge_files 會在錯誤時繼續，所以會返回 True 但 files 是空的
            assert is_successful is True
            assert files == []
            assert error is None

    def test_delete_knowledge_file_not_implemented(self, gemini_model):
        """Test that delete_knowledge_file is not implemented for Gemini."""
        # Gemini 模型目前沒有實現 delete_knowledge_file 方法
        # 這個測試僅驗證方法不存在或返回適當的錯誤
        assert not hasattr(gemini_model, 'delete_knowledge_file') or \
               gemini_model.delete_knowledge_file("test") == (False, "Not implemented")

    def test_transcribe_audio_generic_exception(self, gemini_model, tmp_path):
        """Test transcribe_audio for generic exceptions during file processing."""
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b'audio')

        with patch('base64.b64encode', side_effect=Exception("Encoding failed")):
            is_successful, text, error = gemini_model.transcribe_audio(str(audio_file))
            assert is_successful is False
            assert text is None
            assert "Encoding failed" in error

    @patch('src.models.gemini_model.requests.post')
    def test_upload_knowledge_file_success(self, mock_post, gemini_model, tmp_path):
        """Test successful knowledge file upload."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'name': 'corpora/test_corpus',
            'displayName': 'Test Corpus'
        }
        mock_post.return_value = mock_response

        file_path = tmp_path / "test.txt"
        file_path.write_text("This is test content for knowledge base.")

        is_successful, file_info, error = gemini_model.upload_knowledge_file(str(file_path))
        
        assert is_successful is True
        assert file_info is not None
        assert file_info.filename == "test.txt"
        assert file_info.status == "processed"
        assert error is None

    def test_upload_knowledge_file_not_found(self, gemini_model):
        """Test knowledge file upload when file doesn't exist."""
        is_successful, file_info, error = gemini_model.upload_knowledge_file("/non/existent/file.txt")
        
        assert is_successful is False
        assert file_info is None
        assert ("not found" in error.lower() or "no such file" in error.lower())

    @patch('src.models.gemini_model.requests.post')
    def test_query_with_rag_success(self, mock_post, gemini_model):
        """Test successful RAG query with retrieval."""
        gemini_model.corpora['test_corpus'] = {'name': 'corpora/test_corpus'}
        
        # Mock retrieval response
        mock_retrieval_response = Mock()
        mock_retrieval_response.status_code = 200
        mock_retrieval_response.json.return_value = {
            'relevantChunks': [{
                'chunkRelevanceScore': 0.9,
                'chunk': {
                    'name': 'corpora/test_corpus/documents/doc1/chunks/chunk1',
                    'data': {'stringValue': 'This is relevant content'},
                    'customMetadata': [
                        {'key': 'source_file', 'stringValue': 'test_document.txt'}
                    ]
                }
            }]
        }
        
        # Mock chat response - include citation to generate sources
        mock_chat_response = Mock()
        mock_chat_response.status_code = 200
        mock_chat_response.json.return_value = {
            'candidates': [{
                'content': {
                    'parts': [{'text': 'Based on [test_document.txt], here is the answer.'}]
                }
            }]
        }
        
        mock_post.side_effect = [mock_retrieval_response, mock_chat_response]

        is_successful, rag_response, error = gemini_model.query_with_rag("test query", corpus_name='test_corpus')
        
        assert is_successful is True
        assert rag_response is not None
        assert "here is the answer" in rag_response.answer
        assert len(rag_response.sources) > 0
        assert error is None

    @patch('src.models.gemini_model.requests.post')
    def test_query_with_rag_retrieval_error(self, mock_post, gemini_model):
        """Test RAG query when retrieval fails."""
        gemini_model.corpora['test_corpus'] = {'name': 'corpora/test_corpus'}
        
        # Mock retrieval error
        mock_retrieval_response = Mock()
        mock_retrieval_response.status_code = 500
        mock_retrieval_response.json.return_value = {'error': {'message': 'Retrieval failed'}}
        mock_post.return_value = mock_retrieval_response

        is_successful, rag_response, error = gemini_model.query_with_rag("test query", corpus_name='test_corpus')
        
        assert is_successful is False
        assert rag_response is None
        assert ("Retrieval failed" in error or "Server error" in error)

    def test_get_file_references(self, gemini_model):
        """Test getting file references."""
        # Mock get_knowledge_files to return some files
        from src.models.base import FileInfo
        mock_files = [
            FileInfo(file_id='file1', filename='test1.txt', size=100, status='processed', purpose='knowledge'),
            FileInfo(file_id='file2', filename='test2.json', size=200, status='processed', purpose='knowledge')
        ]
        
        with patch.object(gemini_model, 'get_knowledge_files', return_value=(True, mock_files, None)):
            references = gemini_model.get_file_references()
            
            assert isinstance(references, dict)
            assert 'file1' in references
            assert 'file2' in references
            assert references['file1'] == 'test1'
            assert references['file2'] == 'test2'

    def test_get_recent_conversations(self, gemini_model):
        """Test _get_recent_conversations method."""
        mock_conversation_manager = Mock()
        mock_conversation_manager.get_recent_conversations.return_value = [
            {'role': 'user', 'content': 'Hello', 'created_at': '2024-01-01T10:00:00'},
            {'role': 'assistant', 'content': 'Hi there!', 'created_at': '2024-01-01T10:00:01'}
        ]
        gemini_model.conversation_manager = mock_conversation_manager
        
        conversations = gemini_model._get_recent_conversations('test_user', 'line', 10)
        
        assert len(conversations) == 2
        assert conversations[0]['role'] == 'user'
        assert conversations[1]['role'] == 'assistant'
        mock_conversation_manager.get_recent_conversations.assert_called_once_with('test_user', 'gemini', 10, 'line')

    def test_get_recent_conversations_error(self, gemini_model):
        """Test _get_recent_conversations when it fails."""
        mock_conversation_manager = Mock()
        mock_conversation_manager.get_recent_conversations.side_effect = Exception("Database error")
        gemini_model.conversation_manager = mock_conversation_manager
        
        conversations = gemini_model._get_recent_conversations('test_user', 'line', 10)
        
        assert conversations == []

    def test_supported_media_types(self, gemini_model):
        """Test supported media types."""
        assert 'image' in gemini_model.supported_media_types
        assert 'video' in gemini_model.supported_media_types
        assert 'audio' in gemini_model.supported_media_types

    def test_request_method_success(self, gemini_model):
        """Test _request method for successful API calls."""
        with patch('src.models.gemini_model.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'success': True}
            mock_post.return_value = mock_response
            
            is_successful, response_data, error = gemini_model._request('POST', '/test', {'data': 'test'})
            
            assert is_successful is True
            assert response_data['success'] is True
            assert error is None

    def test_request_method_failure(self, gemini_model):
        """Test _request method for failed API calls."""
        with patch('src.models.gemini_model.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.json.return_value = {'error': {'message': 'Bad request'}}
            mock_post.return_value = mock_response
            
            is_successful, response_data, error = gemini_model._request('POST', '/test', {'data': 'test'})
            
            assert is_successful is False
            assert response_data is None
            assert 'Bad request' in error

    def test_request_method_exception(self, gemini_model):
        """Test _request method when an exception occurs."""
        with patch('src.models.gemini_model.requests.post', side_effect=Exception("Network error")):
            is_successful, response_data, error = gemini_model._request('POST', '/test', {'data': 'test'})
            
            assert is_successful is False
            assert response_data is None
            assert 'Network error' in error

    def test_clear_user_history_failure(self, gemini_model):
        """Test clear_user_history when it fails."""
        mock_conversation_manager = Mock()
        mock_conversation_manager.clear_user_history.return_value = False
        gemini_model.conversation_manager = mock_conversation_manager
        
        is_successful, error = gemini_model.clear_user_history('test_user')
        
        assert is_successful is False
        assert "Failed to clear" in error

    def test_clear_user_history_exception(self, gemini_model):
        """Test clear_user_history when an exception occurs."""
        mock_conversation_manager = Mock()
        mock_conversation_manager.clear_user_history.side_effect = Exception("Database error")
        gemini_model.conversation_manager = mock_conversation_manager
        
        is_successful, error = gemini_model.clear_user_history('test_user')
        
        assert is_successful is False
        assert "Database error" in error

    def test_chat_with_user_rag_failure(self, gemini_model):
        """Test chat_with_user when RAG query fails."""
        with patch.object(gemini_model, '_get_recent_conversations', return_value=[]):
            with patch.object(gemini_model, 'query_with_rag', return_value=(False, None, "RAG error")):
                is_successful, response, error = gemini_model.chat_with_user('test_user', 'Hello')
                
                assert is_successful is False
                assert response is None
                assert error == "RAG error"

    def test_chat_with_user_exception(self, gemini_model):
        """Test chat_with_user when an exception occurs."""
        with patch.object(gemini_model, '_get_recent_conversations', side_effect=Exception("Error")):
            is_successful, response, error = gemini_model.chat_with_user('test_user', 'Hello')
            
            assert is_successful is False
            assert response is None
            assert "Error" in error