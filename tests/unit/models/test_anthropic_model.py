import pytest
from unittest.mock import Mock, patch, call
import os
import tempfile

from src.models.anthropic_model import AnthropicModel
from src.models.base import FileInfo, RAGResponse, ChatMessage, ChatResponse, ModelProvider, ThreadInfo

@pytest.fixture
def model() -> AnthropicModel:
    """Provides a fresh, mocked instance of AnthropicModel for each test."""
    with patch('src.models.anthropic_model.get_conversation_manager', return_value=Mock()) as mock_get_manager:
        instance = AnthropicModel(api_key='test_key')
        instance.conversation_manager = mock_get_manager.return_value
        yield instance

class TestAnthropicModel:

    def test_init(self, model):
        assert model.api_key == 'test_key'
        assert model.get_provider() == ModelProvider.ANTHROPIC
        assert model.conversation_manager is not None

    @patch.object(AnthropicModel, 'chat_completion')
    def test_check_connection(self, mock_chat, model):
        mock_chat.return_value = (True, Mock(), None)
        success, error = model.check_connection()
        assert success
        assert error is None
        mock_chat.assert_called_once()

    @patch.object(AnthropicModel, '_request')
    def test_chat_completion(self, mock_request, model):
        mock_request.return_value = (True, {'content': [{'text': 'Test'}], 'stop_reason': 'end_turn', 'usage': {}}, None)
        success, response, _ = model.chat_completion([ChatMessage(role='user', content='Hi')])
        assert success
        assert response.content == 'Test'

    @patch.object(AnthropicModel, 'query_with_rag')
    def test_chat_with_user(self, mock_query, model):
        model.conversation_manager.get_recent_conversations.return_value = []
        mock_query.return_value = (True, RAGResponse(answer='Hello there', sources=[], metadata={}), None)
        
        success, response, _ = model.chat_with_user('user1', 'Hi')
        
        assert success
        assert response.answer == 'Hello there'
        model.conversation_manager.add_message.assert_has_calls([
            call('user1', 'anthropic', 'user', 'Hi', 'line'),
            call('user1', 'anthropic', 'assistant', 'Hello there', 'line')
        ])
        model.query_with_rag.assert_called_once()

    @patch.object(AnthropicModel, '_perform_rag_query')
    def test_query_with_rag(self, mock_perform, model):
        mock_perform.return_value = (True, RAGResponse(answer='RAG answer', sources=[]), None)
        success, response, _ = model.query_with_rag('some query')
        assert success
        assert response.answer == 'RAG answer'
        mock_perform.assert_called_once_with([ChatMessage(role='user', content='some query')])

    @patch.object(AnthropicModel, 'chat_completion')
    def test_perform_rag_query(self, mock_chat, model):
        mock_chat.return_value = (True, ChatResponse(content='Final Answer', metadata={}), None)
        model.file_cache['file1'] = FileInfo(file_id='file1', filename='doc.txt')
        
        success, response, _ = model._perform_rag_query([ChatMessage(role='user', content='q')])
        
        assert success
        assert response.answer == 'Final Answer'
        args, kwargs = mock_chat.call_args
        assert 'Use the following documents' in kwargs['system']
        assert 'doc.txt' in kwargs['system']

    def test_assistant_interface_compliance(self, model):
        """Tests that the assistant methods are present but not implemented."""
        success, thread_info, _ = model.create_thread()
        assert success
        assert isinstance(thread_info, ThreadInfo)

        success, _ = model.delete_thread('t1')
        assert success

        success, _ = model.add_message_to_thread('t1', ChatMessage(role='user', content='m1'))
        assert success

        success, _, error = model.run_assistant('t1')
        assert not success
        assert error == "Not implemented. Use chat_with_user for conversation."

    @patch.object(AnthropicModel, '_request')
    def test_get_knowledge_files_from_cache(self, mock_request, model):
        model.file_cache['file1'] = FileInfo(file_id='file1', filename='doc.txt')
        success, files, _ = model.get_knowledge_files()
        assert success
        assert len(files) == 1
        assert files[0].filename == 'doc.txt'
        mock_request.assert_not_called()

    def test_get_file_references_empty(self, model):
        assert model.get_file_references() == {}

    def test_clear_user_history_failure(self, model):
        model.conversation_manager.clear_user_history.return_value = (False, "DB error")
        success, error = model.clear_user_history('user1')
        assert not success

    def test_transcribe_audio_failure(self, model):
        mock_service = Mock()
        mock_service.transcribe.side_effect = Exception("Transcription failed")
        model.set_speech_service(mock_service)
        success, _, error = model.transcribe_audio('file.wav')
        assert not success
        assert "Transcription failed" in error

    def test_build_files_context_empty(self, model):
        assert "Knowledge Base Context" not in model._build_files_context()

    def test_extract_sources_no_match(self, model):
        model.file_cache['file1'] = FileInfo(file_id='file1', filename='doc.txt')
        assert model._extract_sources_from_response('no citations') == []

    @patch.object(AnthropicModel, 'query_with_rag')
    def test_chat_with_user_rag_fails(self, mock_query, model):
        model.conversation_manager.get_recent_conversations.return_value = []
        mock_query.return_value = (False, None, "RAG Error")
        success, _, error = model.chat_with_user('user1', 'Hi')
        assert not success
        assert error == "RAG Error"

    @patch.object(AnthropicModel, '_request')
    def test_upload_knowledge_file_success(self, mock_request, model):
        mock_request.return_value = (True, {'id': 'file_123', 'purpose': 'knowledge_base'}, None)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write('Test content')
            temp_file = f.name
        
        try:
            success, file_info, _ = model.upload_knowledge_file(temp_file)
            assert success
            assert file_info.file_id == 'file_123'
            assert 'file_123' in model.file_cache
        finally:
            os.unlink(temp_file)

    def test_upload_knowledge_file_too_large(self, model):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write('Test content')
            temp_file = f.name
        
        try:
            with patch('os.path.getsize', return_value=101 * 1024 * 1024):  # 101MB
                success, _, error = model.upload_knowledge_file(temp_file)
                assert not success
                assert '檔案過大' in error
        finally:
            os.unlink(temp_file)

    @patch.object(AnthropicModel, '_request')
    def test_get_knowledge_files_from_api(self, mock_request, model):
        mock_request.return_value = (True, {
            'data': [{
                'id': 'file_456', 'filename': 'test.txt', 'bytes': 1000,
                'purpose': 'knowledge_base', 'created_at': '2024-01-01T00:00:00Z'
            }]
        }, None)
        
        success, files, _ = model.get_knowledge_files()
        assert success
        assert len(files) == 1
        assert files[0].file_id == 'file_456'
        assert 'file_456' in model.file_cache

    def test_get_file_references(self, model):
        model.file_cache['file1'] = FileInfo(file_id='file1', filename='document.txt')
        model.file_cache['file2'] = FileInfo(file_id='file2', filename='report.json')
        
        refs = model.get_file_references()
        assert refs == {'file1': 'document', 'file2': 'report'}

    def test_extract_sources_from_response(self, model):
        model.file_cache['file1'] = FileInfo(file_id='file1', filename='document.txt')
        model.file_cache['file2'] = FileInfo(file_id='file2', filename='report.txt')
        
        response = "Based on [document.txt] and [report.txt], the answer is..."
        sources = model._extract_sources_from_response(response)
        
        assert len(sources) == 2
        assert any(s['filename'] == 'document.txt' for s in sources)
        assert any(s['filename'] == 'report.txt' for s in sources)

    def test_build_files_context_with_files(self, model):
        model.file_cache['file1'] = FileInfo(file_id='file1', filename='doc1.txt')
        model.file_cache['file2'] = FileInfo(file_id='file2', filename='doc2.txt')
        
        context = model._build_files_context()
        assert 'Use the following documents' in context
        assert 'doc1.txt' in context
        assert 'doc2.txt' in context

    def test_transcribe_audio_no_service(self, model):
        success, _, error = model.transcribe_audio('test.wav')
        assert not success
        assert error == "Speech service not configured"

    def test_transcribe_audio_success(self, model):
        mock_service = Mock()
        mock_service.transcribe.return_value = (True, 'Transcribed text', None)
        model.set_speech_service(mock_service)
        
        success, text, _ = model.transcribe_audio('test.wav')
        assert success
        assert text == 'Transcribed text'

    def test_generate_image_not_supported(self, model):
        success, _, error = model.generate_image('Test prompt')
        assert not success
        assert 'does not support image generation' in error

    @patch.object(AnthropicModel, '_request')
    def test_request_error_handling(self, mock_request, model):
        mock_request.return_value = (False, None, 'API Error')
        
        success, _, error = model.get_knowledge_files()
        assert not success
        assert error == 'API Error'

    def test_clear_user_history_success(self, model):
        model.conversation_manager.clear_user_history.return_value = (True, None)
        success, error = model.clear_user_history('user1')
        assert success
        assert error is None

    def test_build_conversation_context(self, model):
        conversations = [
            {'role': 'user', 'content': 'Hello'},
            {'role': 'assistant', 'content': 'Hi there'}
        ]
        
        messages = model._build_conversation_context(conversations, 'New message')
        
        assert len(messages) == 3
        assert messages[0].content == 'Hello'
        assert messages[1].content == 'Hi there'
        assert messages[2].content == 'New message'
        assert messages[2].role == 'user'

    def test_get_recent_conversations(self, model):
        model.conversation_manager.get_recent_conversations.return_value = [
            {'role': 'user', 'content': 'Test'}
        ]
        
        convs = model._get_recent_conversations('user1', 'line', 5)
        assert len(convs) == 1
        assert convs[0]['content'] == 'Test'
