import pytest
from unittest.mock import Mock, patch, call, MagicMock, AsyncMock
import os
import tempfile
import json
import asyncio
import requests
from requests.exceptions import RequestException, HTTPError, ConnectionError
from unittest.mock import PropertyMock

from src.models.anthropic_model import AnthropicModel
from src.models.base import FileInfo, RAGResponse, ChatMessage, ChatResponse, ModelProvider, ThreadInfo

@pytest.fixture
def model() -> AnthropicModel:
    """Provides a fresh, mocked instance of AnthropicModel for each test."""
    with patch('src.models.anthropic_model.get_conversation_manager', return_value=Mock()) as mock_get_manager:
        with patch('src.core.config.get_value', return_value=False):
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


class TestAnthropicModelMCP:
    """Test MCP-related functionality"""
    
    @pytest.fixture
    def mcp_enabled_model(self):
        """Create a model with MCP enabled"""
        with patch('src.models.anthropic_model.get_conversation_manager', return_value=Mock()):
            with patch('src.core.config.get_value') as mock_config:
                mock_config.side_effect = lambda key, default=None: {
                    'features.enable_mcp': True,
                    'mcp.enabled': True,
                    'mcp.system_prompt': 'You are a helpful assistant.'
                }.get(key, default)
                
                with patch('src.services.mcp_service.get_mcp_service') as mock_mcp:
                    mock_service = Mock()
                    mock_service.is_enabled = True
                    mock_service.get_function_schemas_for_anthropic.return_value = "test schema"
                    mock_mcp.return_value = mock_service
                    
                    model = AnthropicModel(api_key='test_key', enable_mcp=True)
                    yield model
    
    @pytest.fixture
    def mcp_disabled_model(self):
        """Create a model with MCP disabled"""
        with patch('src.models.anthropic_model.get_conversation_manager', return_value=Mock()):
            with patch('src.core.config.get_value', return_value=False):  # Disable MCP
                model = AnthropicModel(api_key='test_key', enable_mcp=False)
                yield model
    
    def test_mcp_config_read_error(self):
        """Test MCP configuration read error handling (line 81-83)"""
        with patch('src.models.anthropic_model.get_conversation_manager', return_value=Mock()):
            with patch('src.core.config.get_value', side_effect=Exception("Config error")):
                with patch('src.models.anthropic_model.logger') as mock_logger:
                    model = AnthropicModel(api_key='test_key')
                    
                    # Should set enable_mcp to False on config error
                    assert model.enable_mcp is False
                    mock_logger.warning.assert_called_with("Error reading MCP config: Config error")
    
    def test_mcp_service_init_failure(self):
        """Test MCP service initialization failure (line 105-110)"""
        with patch('src.models.anthropic_model.get_conversation_manager', return_value=Mock()):
            with patch('src.core.config.get_value', return_value=True):
                with patch('src.services.mcp_service.get_mcp_service', side_effect=Exception("MCP init failed")):
                    with patch('src.models.anthropic_model.logger') as mock_logger:
                        model = AnthropicModel(api_key='test_key', enable_mcp=True)
                        
                        # Should disable MCP on init failure
                        assert model.enable_mcp is False
                        mock_logger.warning.assert_called()
    
    def test_mcp_service_not_enabled(self):
        """Test MCP service not enabled scenario (line 105-110)"""
        with patch('src.models.anthropic_model.get_conversation_manager', return_value=Mock()):
            with patch('src.core.config.get_value', return_value=True):
                with patch('src.services.mcp_service.get_mcp_service') as mock_mcp:
                    mock_service = Mock()
                    mock_service.is_enabled = False
                    mock_mcp.return_value = mock_service
                    
                    with patch('src.models.anthropic_model.logger') as mock_logger:
                        model = AnthropicModel(api_key='test_key', enable_mcp=True)
                        
                        # Should disable MCP when service is not enabled
                        assert model.enable_mcp is False
                        mock_logger.warning.assert_called_with("Anthropic Model: MCP service is not enabled")
    
    @patch.object(AnthropicModel, 'query_with_rag_and_mcp')
    def test_chat_with_user_mcp_enabled(self, mock_query_mcp, mcp_enabled_model):
        """Test chat_with_user with MCP enabled (line 158-159)"""
        mcp_enabled_model.conversation_manager.get_recent_conversations.return_value = []
        
        # Mock the asyncio.run call
        mock_query_mcp.return_value = (True, RAGResponse(answer='MCP answer', sources=[], metadata={}), None)
        
        with patch('asyncio.run', return_value=(True, RAGResponse(answer='MCP answer', sources=[], metadata={}), None)):
            success, response, error = mcp_enabled_model.chat_with_user('user1', 'Test message')
            
            assert success
            assert response.answer == 'MCP answer'
    
    @patch.object(AnthropicModel, 'query_with_rag_and_mcp')
    def test_chat_with_user_mcp_async_error(self, mock_query_mcp, mcp_enabled_model):
        """Test chat_with_user with MCP async error"""
        mcp_enabled_model.conversation_manager.get_recent_conversations.return_value = []
        
        with patch('asyncio.run', side_effect=Exception("Async error")):
            with patch('src.models.anthropic_model.logger') as mock_logger:
                success, response, error = mcp_enabled_model.chat_with_user('user1', 'Test message')
                
                assert not success
                assert error == "Async error"
                mock_logger.error.assert_called()
    
    @patch.object(AnthropicModel, '_perform_rag_query_with_mcp')
    def test_query_with_rag_and_mcp(self, mock_perform_mcp, mcp_enabled_model):
        """Test query_with_rag_and_mcp method (line 177-178)"""
        mock_perform_mcp.return_value = (True, RAGResponse(answer='MCP RAG answer', sources=[], metadata={}), None)
        
        # This should be async
        result = asyncio.run(mcp_enabled_model.query_with_rag_and_mcp('Test query'))
        
        success, response, error = result
        assert success
        assert response.answer == 'MCP RAG answer'
        mock_perform_mcp.assert_called_once()
    
    @patch.object(AnthropicModel, 'chat_completion_with_mcp')
    def test_perform_rag_query_with_mcp(self, mock_chat_mcp, mcp_enabled_model):
        """Test _perform_rag_query_with_mcp method (line 182-216)"""
        mock_chat_mcp.return_value = (True, ChatResponse(content='MCP response', metadata={}), None)
        
        # Mock file cache
        mcp_enabled_model.file_cache['file1'] = FileInfo(file_id='file1', filename='test.txt')
        
        success, response, error = asyncio.run(mcp_enabled_model._perform_rag_query_with_mcp([ChatMessage(role='user', content='Test')]))
        
        assert success
        assert response.answer == 'MCP response'
        mock_chat_mcp.assert_called_once()
    
    @patch.object(AnthropicModel, 'chat_completion_with_mcp')
    def test_perform_rag_query_with_mcp_failure(self, mock_chat_mcp, mcp_enabled_model):
        """Test _perform_rag_query_with_mcp failure (line 182-216)"""
        mock_chat_mcp.return_value = (False, None, "MCP chat failed")
        
        success, response, error = asyncio.run(mcp_enabled_model._perform_rag_query_with_mcp([ChatMessage(role='user', content='Test')]))
        
        assert not success
        assert error == "MCP chat failed"
    
    @patch.object(AnthropicModel, 'chat_completion_with_mcp')
    def test_perform_rag_query_with_mcp_exception(self, mock_chat_mcp, mcp_enabled_model):
        """Test _perform_rag_query_with_mcp exception handling (line 182-216)"""
        mock_chat_mcp.side_effect = Exception("MCP exception")
        
        with patch('src.models.anthropic_model.logger') as mock_logger:
            success, response, error = asyncio.run(mcp_enabled_model._perform_rag_query_with_mcp([ChatMessage(role='user', content='Test')]))
            
            assert not success
            assert "MCP exception" in error
            mock_logger.error.assert_called()
    
    def test_build_system_prompt_mcp_config_error(self, mcp_enabled_model):
        """Test _build_system_prompt with MCP config error (line 332-333)"""
        mcp_enabled_model.mcp_service.get_function_schemas_for_anthropic.side_effect = Exception("Config error")
        
        with patch('src.models.anthropic_model.logger') as mock_logger:
            prompt = mcp_enabled_model._build_system_prompt()
            
            # Should return base prompt without MCP additions
            assert prompt is not None
            mock_logger.error.assert_called()
    
    def test_build_system_prompt_mcp_schema_error(self, mcp_enabled_model):
        """Test _build_system_prompt with schema addition error (line 369-370)"""
        mcp_enabled_model.mcp_service.get_function_schemas_for_anthropic.return_value = "invalid schema"
        
        with patch('src.models.anthropic_model.logger') as mock_logger:
            # This should trigger the schema addition error
            prompt = mcp_enabled_model._build_system_prompt()
            
            assert prompt is not None
    
    def test_has_function_calls_true(self, mcp_enabled_model):
        """Test _has_function_calls with function calls present (line 376-379)"""
        response = '```json\n{"function_name": "test", "arguments": {"arg": "value"}}\n```'
        
        result = mcp_enabled_model._has_function_calls(response)
        assert result is True
    
    def test_has_function_calls_false(self, mcp_enabled_model):
        """Test _has_function_calls with no function calls (line 376-379)"""
        response = 'Just regular text without function calls'
        
        result = mcp_enabled_model._has_function_calls(response)
        assert result is False
    
    def test_extract_function_calls_valid(self, mcp_enabled_model):
        """Test _extract_function_calls with valid JSON (line 383-411)"""
        response = '```json\n{"function_name": "search", "arguments": {"query": "test"}}\n```'
        
        # Mock the regex pattern to work correctly
        with patch('re.findall') as mock_findall:
            mock_findall.return_value = ['{"function_name": "search", "arguments": {"query": "test"}}']
            
            calls = mcp_enabled_model._extract_function_calls(response)
            
            assert len(calls) == 1
            assert calls[0]['function_name'] == 'search'
            assert calls[0]['arguments']['query'] == 'test'
    
    def test_extract_function_calls_invalid_json(self, mcp_enabled_model):
        """Test _extract_function_calls with invalid JSON (line 383-411)"""
        response = '```json\n{"function_name": "search", "arguments": invalid}\n```'
        
        # Mock the regex pattern to return invalid JSON
        with patch('re.findall') as mock_findall:
            mock_findall.return_value = ['{"function_name": "search", "arguments": invalid}']
            
            with patch('src.models.anthropic_model.logger') as mock_logger:
                calls = mcp_enabled_model._extract_function_calls(response)
                
                assert len(calls) == 0
                mock_logger.warning.assert_called()
    
    def test_extract_function_calls_missing_fields(self, mcp_enabled_model):
        """Test _extract_function_calls with missing required fields (line 383-411)"""
        response = '```json\n{"function_name": "search"}\n```'
        
        # Mock the regex pattern to return JSON missing arguments
        with patch('re.findall') as mock_findall:
            mock_findall.return_value = ['{"function_name": "search"}']
            
            with patch('src.models.anthropic_model.logger') as mock_logger:
                calls = mcp_enabled_model._extract_function_calls(response)
                
                assert len(calls) == 0
                mock_logger.warning.assert_called()
    
    @patch.object(AnthropicModel, 'chat_completion')
    def test_chat_completion_with_mcp_no_function_calls(self, mock_chat, mcp_enabled_model):
        """Test chat_completion_with_mcp without function calls (line 415-505)"""
        mock_chat.return_value = (True, ChatResponse(content='Normal response', metadata={}), None)
        
        with patch.object(mcp_enabled_model, '_has_function_calls', return_value=False):
            success, response, error = asyncio.run(mcp_enabled_model.chat_completion_with_mcp([ChatMessage(role='user', content='Test')]))
            
            assert success
            assert response.content == 'Normal response'
    
    @patch.object(AnthropicModel, 'chat_completion')
    def test_chat_completion_with_mcp_with_function_calls(self, mock_chat, mcp_enabled_model):
        """Test chat_completion_with_mcp with function calls (line 415-505)"""
        # First call returns function call
        mock_chat.side_effect = [
            (True, ChatResponse(content='```json\n{"function_name": "search", "arguments": {"query": "test"}}\n```', metadata={}), None),
            (True, ChatResponse(content='Final response', metadata={}), None)
        ]
        
        # Mock MCP service
        mcp_enabled_model.mcp_service.handle_function_call_sync.return_value = {
            'success': True,
            'data': 'Function result',
            'metadata': {'sources': []}
        }
        
        # Mock the function call extraction to return valid calls
        with patch.object(mcp_enabled_model, '_extract_function_calls') as mock_extract:
            mock_extract.return_value = [{'function_name': 'search', 'arguments': {'query': 'test'}}]
            
            success, response, error = asyncio.run(mcp_enabled_model.chat_completion_with_mcp([ChatMessage(role='user', content='Test')]))
            
            assert success
            assert response.content == 'Final response'
            assert 'function_calls' in response.metadata
            assert 'sources' in response.metadata
    
    @patch.object(AnthropicModel, 'chat_completion')
    def test_chat_completion_with_mcp_function_call_error(self, mock_chat, mcp_enabled_model):
        """Test chat_completion_with_mcp with function call error handling (line 503-505)"""
        mock_chat.side_effect = [
            (True, ChatResponse(content='```json\n{"function_name": "search", "arguments": {"query": "test"}}\n```', metadata={}), None),
            (True, ChatResponse(content='Final response', metadata={}), None)
        ]
        
        # Mock MCP service to return error
        mcp_enabled_model.mcp_service.handle_function_call_sync.return_value = {
            'success': False,
            'error': 'Function call failed'
        }
        
        # Mock the function call extraction to return valid calls
        with patch.object(mcp_enabled_model, '_extract_function_calls') as mock_extract:
            mock_extract.return_value = [{'function_name': 'search', 'arguments': {'query': 'test'}}]
            
            success, response, error = asyncio.run(mcp_enabled_model.chat_completion_with_mcp([ChatMessage(role='user', content='Test')]))
            
            assert success
            assert response.content == 'Final response'
            assert 'function_calls' in response.metadata
    
    def test_format_function_results_success(self, mcp_enabled_model):
        """Test _format_function_results method - success case (line 509-522)"""
        results = [
            {'function_name': 'search', 'result': {'success': True, 'data': 'Search result'}},
            {'function_name': 'calculate', 'result': {'success': True, 'data': '42'}}
        ]
        
        formatted = mcp_enabled_model._format_function_results(results)
        
        assert '1. search: Search result' in formatted
        assert '2. calculate: 42' in formatted
    
    def test_format_function_results_error(self, mcp_enabled_model):
        """Test _format_function_results method - error case (line 518-520)"""
        results = [
            {'function_name': 'search', 'result': {'success': False, 'error': 'Not found'}}
        ]
        
        formatted = mcp_enabled_model._format_function_results(results)
        
        assert '1. search: Error - Not found' in formatted
    
    def test_extract_sources_from_function_results_success(self, mcp_enabled_model):
        """Test _extract_sources_from_function_results method - success case (line 526-534)"""
        results = [
            {'result': {'success': True, 'metadata': {'sources': [{'filename': 'test1.txt'}]}}},
            {'result': {'success': True, 'metadata': {'sources': [{'filename': 'test2.txt'}]}}},
            {'result': {'success': False, 'metadata': {}}}  # No sources
        ]
        
        sources = mcp_enabled_model._extract_sources_from_function_results(results)
        
        assert len(sources) == 2
        assert any(s['filename'] == 'test1.txt' for s in sources)
        assert any(s['filename'] == 'test2.txt' for s in sources)
    
    def test_extract_sources_from_function_results_empty(self, mcp_enabled_model):
        """Test _extract_sources_from_function_results method - empty results (line 526-534)"""
        results = []
        
        sources = mcp_enabled_model._extract_sources_from_function_results(results)
        
        assert len(sources) == 0
    
    def test_get_mcp_status(self, mcp_enabled_model):
        """Test get_mcp_status method (line 538)"""
        status = mcp_enabled_model.get_mcp_status()
        
        assert 'enabled' in status
        assert 'service_available' in status
        assert status['enabled'] is True
        assert status['service_available'] is True
    
    def test_get_mcp_status_disabled(self, mcp_disabled_model):
        """Test get_mcp_status when MCP is disabled"""
        status = mcp_disabled_model.get_mcp_status()
        
        assert status['enabled'] is False
        assert status['service_available'] is False
    
    def test_reload_mcp_config_success(self, mcp_enabled_model):
        """Test reload_mcp_config success (line 546-553)"""
        mcp_enabled_model.mcp_service.reload_config.return_value = True
        
        with patch('src.models.anthropic_model.logger') as mock_logger:
            result = mcp_enabled_model.reload_mcp_config()
            
            assert result is True
            mock_logger.info.assert_called_with("Anthropic Model: MCP config reloaded and system prompt updated")
    
    def test_reload_mcp_config_failure(self, mcp_enabled_model):
        """Test reload_mcp_config failure (line 546-553)"""
        mcp_enabled_model.mcp_service.reload_config.return_value = False
        
        result = mcp_enabled_model.reload_mcp_config()
        
        assert result is False
    
    def test_reload_mcp_config_disabled(self, mcp_disabled_model):
        """Test reload_mcp_config when MCP is disabled"""
        result = mcp_disabled_model.reload_mcp_config()
        
        assert result is False


class TestAnthropicModelErrorHandling:
    """Test error handling scenarios"""
    
    @pytest.fixture
    def model(self):
        with patch('src.models.anthropic_model.get_conversation_manager', return_value=Mock()):
            with patch('src.core.config.get_value', return_value=False):
                yield AnthropicModel(api_key='test_key')
    
    def test_check_connection_exception(self, model):
        """Test check_connection exception handling (line 116-118)"""
        with patch.object(model, 'chat_completion', side_effect=Exception("Connection failed")):
            with patch('src.models.anthropic_model.logger') as mock_logger:
                success, error = model.check_connection()
                
                assert not success
                assert error == "Connection failed"
                mock_logger.error.assert_called_with("Anthropic connection check failed: Connection failed")
    
    @patch.object(AnthropicModel, '_request')
    def test_chat_completion_exception(self, mock_request, model):
        """Test chat_completion exception handling (line 146-148)"""
        mock_request.side_effect = Exception("API request failed")
        
        with patch('src.models.anthropic_model.logger') as mock_logger:
            success, response, error = model.chat_completion([ChatMessage(role='user', content='Test')])
            
            assert not success
            assert error == "API request failed"
            mock_logger.error.assert_called()
    
    @patch.object(AnthropicModel, 'query_with_rag')
    def test_chat_with_user_exception(self, mock_query, model):
        """Test chat_with_user exception handling (line 171-173)"""
        model.conversation_manager.get_recent_conversations.return_value = []
        mock_query.side_effect = Exception("Query failed")
        
        with patch('src.models.anthropic_model.logger') as mock_logger:
            success, response, error = model.chat_with_user('user1', 'Test')
            
            assert not success
            assert error == "Query failed"
            mock_logger.error.assert_called()
    
    @patch.object(AnthropicModel, 'chat_completion')
    def test_perform_rag_query_failure(self, mock_chat, model):
        """Test _perform_rag_query failure (line 226)"""
        mock_chat.return_value = (False, None, "Chat completion failed")
        
        success, response, error = model._perform_rag_query([ChatMessage(role='user', content='Test')])
        
        assert not success
        assert error == "Chat completion failed"
    
    @patch.object(AnthropicModel, '_request')
    def test_upload_knowledge_file_exception(self, mock_request, model):
        """Test upload_knowledge_file exception handling (line 259-261)"""
        mock_request.side_effect = Exception("Upload failed")
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write('Test content')
            temp_file = f.name
        
        try:
            with patch('src.models.anthropic_model.logger') as mock_logger:
                success, file_info, error = model.upload_knowledge_file(temp_file)
                
                assert not success
                assert "Upload failed" in error
                mock_logger.error.assert_called()
        finally:
            os.unlink(temp_file)
    
    @patch.object(AnthropicModel, '_request')
    def test_get_knowledge_files_exception(self, mock_request, model):
        """Test get_knowledge_files exception handling (line 279-281)"""
        mock_request.side_effect = Exception("API call failed")
        
        with patch('src.models.anthropic_model.logger') as mock_logger:
            success, files, error = model.get_knowledge_files()
            
            assert not success
            assert "API call failed" in error
            mock_logger.error.assert_called()


class TestAnthropicModelHTTPRequests:
    """Test HTTP request handling"""
    
    @pytest.fixture
    def model(self):
        with patch('src.models.anthropic_model.get_conversation_manager', return_value=Mock()):
            with patch('src.core.config.get_value', return_value=False):
                yield AnthropicModel(api_key='test_key')
    
    @patch('src.models.anthropic_model.requests.request')
    def test_request_json_decode_error(self, mock_request, model):
        """Test _request with JSON decode error (line 587-588)"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = 'Invalid JSON'
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "doc", 0)
        mock_request.return_value = mock_response
        
        success, data, error = model._request('POST', '/messages', {})
        
        assert not success
        assert "Invalid JSON" in error
    
    @patch('src.models.anthropic_model.requests.request')
    def test_request_http_error(self, mock_request, model):
        """Test _request with HTTP error (line 582-589)"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = 'Bad Request'
        mock_response.json.return_value = {'error': {'message': 'Invalid request'}}
        mock_request.return_value = mock_response
        
        success, data, error = model._request('POST', '/messages', {})
        
        assert not success
        assert "Invalid request" in error
    
    @patch('src.models.anthropic_model.requests.request')
    def test_request_connection_error(self, mock_request, model):
        """Test _request with connection error handled by retry decorator"""
        mock_request.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        # The retry decorator will catch the exception and return (False, None, error_message)
        success, data, error = model._request('POST', '/messages', {})
        
        assert not success
        assert data is None
        assert "Connection failed" in error
    
    @patch('src.models.anthropic_model.requests.request')
    def test_request_timeout_error(self, mock_request, model):
        """Test _request with timeout error handled by retry decorator"""
        mock_request.side_effect = requests.exceptions.Timeout("Request timeout")
        
        # The retry decorator will catch the exception and return (False, None, error_message)
        success, data, error = model._request('POST', '/messages', {})
        
        assert not success
        assert data is None
        assert "Request timeout" in error
    
    @patch('src.models.anthropic_model.requests.request')
    def test_request_request_exception(self, mock_request, model):
        """Test _request with RequestException handled by retry decorator"""
        mock_request.side_effect = requests.exceptions.RequestException("Request error")
        
        # The retry decorator will catch the exception and return (False, None, error_message)
        success, data, error = model._request('POST', '/messages', {})
        
        assert not success
        assert data is None
        assert "Request error" in error
    
    @patch('src.models.anthropic_model.requests.request')
    def test_request_success(self, mock_request, model):
        """Test _request success case"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'content': [{'text': 'Success'}]}
        mock_request.return_value = mock_response
        
        success, data, error = model._request('POST', '/messages', {})
        
        assert success
        assert data['content'][0]['text'] == 'Success'
        assert error is None
    
    @patch('src.models.anthropic_model.requests.request')
    def test_request_http_error_response(self, mock_request, model):
        """Test _request with HTTPError exception (line 592-599)"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {'error': {'message': 'Bad request'}}
        
        http_error = HTTPError()
        http_error.response = mock_response
        mock_request.side_effect = http_error
        
        success, data, error = model._request('POST', '/messages', {})
        
        assert not success
        assert "Bad request" in error
    
    @patch('src.models.anthropic_model.requests.request')
    def test_request_http_error_invalid_json(self, mock_request, model):
        """Test _request with HTTPError and invalid JSON (line 597-598)"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = 'Bad request'
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "doc", 0)
        
        http_error = HTTPError()
        http_error.response = mock_response
        mock_request.side_effect = http_error
        
        success, data, error = model._request('POST', '/messages', {})
        
        assert not success
        assert "Bad request" in error
