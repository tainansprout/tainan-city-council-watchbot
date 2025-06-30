import pytest
from unittest.mock import Mock, patch, MagicMock
import requests

from src.models.openai_model import OpenAIModel
from src.models.anthropic_model import AnthropicModel
from src.models.gemini_model import GeminiModel
from src.models.ollama_model import OllamaModel
from src.models.factory import ModelFactory
from src.models.base import ModelProvider, ChatMessage, ChatResponse, FileInfo


class TestOpenAIModel:
    """OpenAI 模型單元測試"""
    
    @pytest.fixture
    def openai_model(self):
        return OpenAIModel(
            api_key="test_api_key",
            assistant_id="test_assistant_id"
        )
    
    def test_get_provider(self, openai_model):
        assert openai_model.get_provider() == ModelProvider.OPENAI
    
    @patch('requests.get')
    def test_check_connection_success(self, mock_get, openai_model):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'object': 'list', 'data': []}
        mock_get.return_value = mock_response
        
        is_successful, error = openai_model.check_connection()
        
        assert is_successful is True
        assert error is None
    
    @patch('requests.get')
    def test_check_connection_failure(self, mock_get, openai_model):
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            'error': {'message': 'Invalid API key'}
        }
        mock_get.return_value = mock_response
        
        is_successful, error = openai_model.check_connection()
        
        assert is_successful is False
        assert 'Invalid API key' in error
    
    @patch('requests.post')
    def test_chat_completion_success(self, mock_post, openai_model):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{
                'message': {'content': 'Hello! How can I help you?'},
                'finish_reason': 'stop'
            }],
            'usage': {'total_tokens': 20}
        }
        mock_post.return_value = mock_response
        
        messages = [ChatMessage(role="user", content="Hello")]
        is_successful, response, error = openai_model.chat_completion(messages)
        
        assert is_successful is True
        assert response.content == 'Hello! How can I help you?'
        assert response.finish_reason == 'stop'
        assert error is None
    
    @patch('requests.post')
    def test_create_thread_success(self, mock_post, openai_model):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'id': 'thread_123',
            'object': 'thread',
            'created_at': 1234567890
        }
        mock_post.return_value = mock_response
        
        is_successful, thread_info, error = openai_model.create_thread()
        
        assert is_successful is True
        assert thread_info.thread_id == 'thread_123'
        assert error is None
    
    @patch('builtins.open', create=True)
    @patch('requests.post')
    def test_upload_knowledge_file_success(self, mock_post, mock_open, openai_model):
        mock_open.return_value.__enter__.return_value.read.return_value = "test content"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'id': 'file_123',
            'filename': 'test.txt',
            'bytes': 1024,
            'status': 'processed',
            'purpose': 'assistants'
        }
        mock_post.return_value = mock_response
        
        is_successful, file_info, error = openai_model.upload_knowledge_file('test.txt')
        
        assert is_successful is True
        assert file_info.file_id == 'file_123'
        assert file_info.filename == 'test.txt'
        assert error is None


class TestAnthropicModel:
    """Anthropic 模型單元測試"""
    
    @pytest.fixture
    def anthropic_model(self):
        return AnthropicModel(api_key="test_api_key")
    
    def test_get_provider(self, anthropic_model):
        assert anthropic_model.get_provider() == ModelProvider.ANTHROPIC
    
    @patch('requests.post')
    def test_chat_completion_success(self, mock_post, anthropic_model):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'content': [{'text': 'Hello! How can I assist you?'}],
            'stop_reason': 'end_turn',
            'usage': {'input_tokens': 10, 'output_tokens': 15}
        }
        mock_post.return_value = mock_response
        
        messages = [ChatMessage(role="user", content="Hello")]
        is_successful, response, error = anthropic_model.chat_completion(messages)
        
        assert is_successful is True
        assert response.content == 'Hello! How can I assist you?'
        assert error is None
    
    def test_upload_knowledge_file_success(self, anthropic_model, temp_file):
        is_successful, file_info, error = anthropic_model.upload_knowledge_file(temp_file)
        
        assert is_successful is True
        assert file_info.filename == temp_file.split('/')[-1]
        assert file_info.purpose == 'knowledge_base'
        assert error is None
    
    def test_query_with_rag_no_sources(self, anthropic_model):
        # 沒有知識庫的情況
        with patch.object(anthropic_model, 'chat_completion') as mock_chat:
            mock_chat.return_value = (
                True, 
                ChatResponse(content="I don't have specific information about that.", finish_reason="stop"),
                None
            )
            
            is_successful, rag_response, error = anthropic_model.query_with_rag("What is the weather?")
            
            assert is_successful is True
            assert "don't have specific information" in rag_response.answer
            assert len(rag_response.sources) == 0


class TestGeminiModel:
    """Gemini 模型單元測試"""
    
    @pytest.fixture
    def gemini_model(self):
        return GeminiModel(api_key="test_api_key")
    
    def test_get_provider(self, gemini_model):
        assert gemini_model.get_provider() == ModelProvider.GEMINI
    
    @patch('requests.post')
    def test_chat_completion_success(self, mock_post, gemini_model):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'candidates': [{
                'content': {
                    'parts': [{'text': 'Hello! How can I help you today?'}]
                },
                'finishReason': 'STOP'
            }],
            'usageMetadata': {'promptTokenCount': 5, 'candidatesTokenCount': 10}
        }
        mock_post.return_value = mock_response
        
        messages = [ChatMessage(role="user", content="Hello")]
        is_successful, response, error = gemini_model.chat_completion(messages)
        
        assert is_successful is True
        assert response.content == 'Hello! How can I help you today?'
        assert error is None


class TestOllamaModel:
    """Ollama 模型單元測試"""
    
    @pytest.fixture
    def ollama_model(self):
        return OllamaModel(model_name="llama2")
    
    def test_get_provider(self, ollama_model):
        assert ollama_model.get_provider() == ModelProvider.OLLAMA
    
    @patch('requests.get')
    def test_check_connection_success(self, mock_get, ollama_model):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'models': [
                {'name': 'llama2:latest'},
                {'name': 'mistral:latest'}
            ]
        }
        mock_get.return_value = mock_response
        
        is_successful, error = ollama_model.check_connection()
        
        assert is_successful is True
        assert error is None
    
    @patch('requests.post')
    def test_chat_completion_success(self, mock_post, ollama_model):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'message': {'content': 'Hello! How can I assist you?'},
            'done_reason': 'stop',
            'model': 'llama2',
            'total_duration': 1000000,
            'eval_count': 20
        }
        mock_post.return_value = mock_response
        
        messages = [ChatMessage(role="user", content="Hello")]
        is_successful, response, error = ollama_model.chat_completion(messages)
        
        assert is_successful is True
        assert response.content == 'Hello! How can I assist you?'
        assert error is None
    
    def test_cosine_similarity(self, ollama_model):
        vec1 = [1, 0, 0]
        vec2 = [0, 1, 0]
        vec3 = [1, 0, 0]
        
        # 垂直向量相似度應該接近 0
        similarity_orthogonal = ollama_model._cosine_similarity(vec1, vec2)
        assert abs(similarity_orthogonal) < 0.001
        
        # 相同向量相似度應該是 1
        similarity_same = ollama_model._cosine_similarity(vec1, vec3)
        assert abs(similarity_same - 1.0) < 0.001


class TestModelFactory:
    """模型工廠單元測試"""
    
    def test_create_openai_model(self):
        config = {
            'provider': 'openai',
            'api_key': 'test_key',
            'assistant_id': 'test_id'
        }
        
        model = ModelFactory.create_from_config(config)
        
        assert isinstance(model, OpenAIModel)
        assert model.api_key == 'test_key'
        assert model.assistant_id == 'test_id'
    
    def test_create_anthropic_model(self):
        config = {
            'provider': 'anthropic',
            'api_key': 'test_key',
            'model': 'claude-3-sonnet-20240229'
        }
        
        model = ModelFactory.create_from_config(config)
        
        assert isinstance(model, AnthropicModel)
        assert model.api_key == 'test_key'
        assert model.model_name == 'claude-3-sonnet-20240229'
    
    def test_create_gemini_model(self):
        config = {
            'provider': 'gemini',
            'api_key': 'test_key'
        }
        
        model = ModelFactory.create_from_config(config)
        
        assert isinstance(model, GeminiModel)
        assert model.api_key == 'test_key'
    
    def test_create_ollama_model(self):
        config = {
            'provider': 'ollama',
            'model': 'llama2'
        }
        
        model = ModelFactory.create_from_config(config)
        
        assert isinstance(model, OllamaModel)
        assert model.model_name == 'llama2'
    
    def test_invalid_provider(self):
        config = {
            'provider': 'invalid_provider',
            'api_key': 'test_key'
        }
        
        with pytest.raises(ValueError, match="Unknown provider"):
            ModelFactory.create_from_config(config)
    
    def test_missing_api_key(self):
        config = {
            'provider': 'openai'
            # 缺少 api_key
        }
        
        with pytest.raises(ValueError, match="API key is required"):
            ModelFactory.create_from_config(config)