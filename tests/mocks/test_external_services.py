import pytest
from unittest.mock import Mock, patch, MagicMock
import requests
import json

from src.models.openai_model import OpenAIModel
from src.models.anthropic_model import AnthropicModel
from src.models.gemini_model import GeminiModel
from src.models.ollama_model import OllamaModel


class TestOpenAIMocks:
    """OpenAI API 模擬測試"""
    
    @pytest.fixture
    def openai_model(self):
        return OpenAIModel(api_key="test_key")
    
    @patch('requests.post')
    def test_mock_chat_completion_success(self, mock_post, openai_model):
        """測試模擬 OpenAI 聊天完成 API"""
        # 設定模擬回應
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{
                'message': {
                    'content': 'Hello! How can I help you today?',
                    'role': 'assistant'
                },
                'finish_reason': 'stop'
            }],
            'usage': {
                'prompt_tokens': 10,
                'completion_tokens': 15,
                'total_tokens': 25
            },
            'model': 'gpt-4'
        }
        mock_post.return_value = mock_response
        
        # 執行測試
        from src.models.base import ChatMessage
        messages = [ChatMessage(role="user", content="Hello")]
        is_successful, response, error = openai_model.chat_completion(messages)
        
        # 驗證結果
        assert is_successful is True
        assert response.content == 'Hello! How can I help you today?'
        assert response.finish_reason == 'stop'
        assert error is None
        
        # 驗證 API 調用
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert 'https://api.openai.com/v1/chat/completions' in call_args[0][0]
    
    @patch('requests.post')
    def test_mock_chat_completion_error(self, mock_post, openai_model):
        """測試模擬 OpenAI API 錯誤回應"""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.json.return_value = {
            'error': {
                'message': 'Rate limit exceeded',
                'type': 'rate_limit_exceeded',
                'code': 'rate_limit_exceeded'
            }
        }
        mock_post.return_value = mock_response
        
        from src.models.base import ChatMessage
        messages = [ChatMessage(role="user", content="Hello")]
        is_successful, response, error = openai_model.chat_completion(messages)
        
        assert is_successful is False
        assert response is None
        assert 'Rate limit exceeded' in error
    
    def test_mock_assistant_api_create_thread(self, openai_model):
        """測試模擬 Conversations API 建立對話（取代 Assistant API Thread）"""
        mock_conversation = Mock()
        mock_conversation.id = 'conv_abc123'
        mock_conversation.object = 'conversation'
        mock_conversation.created_at = 1234567890

        with patch.object(openai_model.client.conversations, 'create', return_value=mock_conversation):
            is_successful, thread_info, error = openai_model.create_thread()

        assert is_successful is True
        assert thread_info.thread_id == 'conv_abc123'
        assert error is None

    def test_mock_assistant_api_run_thread(self, openai_model):
        """測試模擬 Responses API 執行對話（取代 Assistant API Run）"""
        # 模擬 Responses API 回應
        mock_response = Mock()
        mock_response.id = 'resp_456'
        mock_response.output_text = 'Assistant response here'
        mock_response.output = []  # 無 annotations

        # Mock create_thread and _create_response
        mock_conversation = Mock()
        mock_conversation.id = 'conv_abc123'
        mock_conversation.object = 'conversation'
        mock_conversation.created_at = 1234567890

        with patch.object(openai_model.client.conversations, 'create', return_value=mock_conversation), \
             patch.object(openai_model, '_create_response', return_value=mock_response):
            is_successful, rag_response, error = openai_model.query_with_rag(
                "Test query",
                thread_id="conv_abc123"
            )

        # 驗證成功執行
        assert is_successful is True
        assert rag_response is not None


class TestAnthropicMocks:
    """Anthropic API 模擬測試"""
    
    @pytest.fixture
    def anthropic_model(self):
        return AnthropicModel(api_key="test_key")
    
    @patch('requests.request')
    def test_mock_anthropic_completion(self, mock_request, anthropic_model):
        """測試模擬 Anthropic 完成 API"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'content': [{
                'type': 'text',
                'text': 'Hello! I can help you with that.'
            }],
            'stop_reason': 'end_turn',
            'usage': {
                'input_tokens': 12,
                'output_tokens': 18
            }
        }
        mock_request.return_value = mock_response
        
        from src.models.base import ChatMessage
        messages = [ChatMessage(role="user", content="Hello")]
        is_successful, response, error = anthropic_model.chat_completion(messages)
        
        assert is_successful is True
        assert response.content == 'Hello! I can help you with that.'
        assert error is None
        
        # 驗證 API 調用
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert 'anthropic.com' in call_args[0][1]
    
    @patch('requests.request')
    def test_mock_anthropic_error(self, mock_request, anthropic_model):
        """測試模擬 Anthropic API 錯誤"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'error': {
                'type': 'invalid_request_error',
                'message': 'Invalid request format'
            }
        }
        mock_request.return_value = mock_response
        
        from src.models.base import ChatMessage
        messages = [ChatMessage(role="user", content="")]  # 空訊息可能導致錯誤
        is_successful, response, error = anthropic_model.chat_completion(messages)
        
        assert is_successful is False
        assert 'Invalid request format' in error


class TestGeminiMocks:
    """Gemini API 模擬測試"""
    
    @pytest.fixture
    def gemini_model(self):
        return GeminiModel(api_key="test_key")
    
    @patch('requests.post')
    def test_mock_gemini_completion(self, mock_post, gemini_model):
        """測試模擬 Gemini 完成 API"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'candidates': [{
                'content': {
                    'parts': [{
                        'text': 'Hello! How can I assist you today?'
                    }],
                    'role': 'model'
                },
                'finishReason': 'STOP',
                'safetyRatings': []
            }],
            'usageMetadata': {
                'promptTokenCount': 8,
                'candidatesTokenCount': 12,
                'totalTokenCount': 20
            }
        }
        mock_post.return_value = mock_response
        
        from src.models.base import ChatMessage
        messages = [ChatMessage(role="user", content="Hello")]
        is_successful, response, error = gemini_model.chat_completion(messages)
        
        assert is_successful is True
        assert response.content == 'Hello! How can I assist you today?'
        assert error is None
    
    @patch('requests.post')
    def test_mock_gemini_semantic_retrieval(self, mock_post, gemini_model):
        """測試模擬 Gemini 語義檢索 API"""
        responses = [
            # 建立語料庫回應
            Mock(status_code=200, json=lambda: {
                'name': 'corpora/test_corpus',
                'displayName': 'Test Corpus'
            }),
            # 查詢回應
            Mock(status_code=200, json=lambda: {
                'relevantChunks': [{
                    'chunkRelevanceScore': 0.85,
                    'chunk': {
                        'name': 'corpora/test_corpus/documents/doc1/chunks/chunk1',
                        'data': {
                            'stringValue': 'This is relevant content'
                        }
                    }
                }]
            })
        ]
        
        mock_post.side_effect = responses
        
        # 測試 RAG 查詢
        is_successful, rag_response, error = gemini_model.query_with_rag("Test query")
        
        # 檢查基本功能
        assert mock_post.call_count >= 1


class TestOllamaMocks:
    """Ollama API 模擬測試"""
    
    @pytest.fixture
    def ollama_model(self):
        return OllamaModel(model_name="llama2", base_url="http://localhost:11434")
    
    @patch('requests.post')
    def test_mock_ollama_completion(self, mock_post, ollama_model):
        """測試模擬 Ollama 完成 API"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'message': {
                'role': 'assistant',
                'content': 'Hello! I can help you with that.'
            },
            'done_reason': 'stop',
            'model': 'llama2',
            'created_at': '2024-01-15T10:30:00Z',
            'total_duration': 1500000,
            'load_duration': 500000,
            'prompt_eval_count': 10,
            'prompt_eval_duration': 300000,
            'eval_count': 20,
            'eval_duration': 700000
        }
        mock_post.return_value = mock_response
        
        from src.models.base import ChatMessage
        messages = [ChatMessage(role="user", content="Hello")]
        is_successful, response, error = ollama_model.chat_completion(messages)
        
        assert is_successful is True
        assert response.content == 'Hello! I can help you with that.'
        assert error is None
    
    @patch('requests.get')
    def test_mock_ollama_models_list(self, mock_get, ollama_model):
        """測試模擬 Ollama 模型列表 API"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'models': [
                {
                    'name': 'llama2:latest',
                    'modified_at': '2024-01-15T10:00:00Z',
                    'size': 3825819519,
                    'digest': 'sha256:abc123'
                },
                {
                    'name': 'mistral:latest',
                    'modified_at': '2024-01-14T15:30:00Z',
                    'size': 4109829632,
                    'digest': 'sha256:def456'
                }
            ]
        }
        mock_get.return_value = mock_response
        
        is_successful, error = ollama_model.check_connection()
        
        assert is_successful is True
        assert error is None
        mock_get.assert_called_once()
    
    @patch('requests.post')
    def test_mock_ollama_embeddings(self, mock_post, ollama_model):
        """測試模擬 Ollama 嵌入 API"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'embedding': [0.1, 0.2, 0.3, 0.4, 0.5]  # 簡化的嵌入向量
        }
        mock_post.return_value = mock_response
        
        # 測試生成嵌入
        embedding = ollama_model._get_embedding("test text")
        
        assert embedding == [0.1, 0.2, 0.3, 0.4, 0.5]
        mock_post.assert_called_once()


class TestDatabaseMocks:
    """資料庫模擬測試"""
    
    def test_mock_database_operations(self):
        """測試資料庫操作模擬"""
        from src.database import Database
        
        with patch('sqlalchemy.create_engine') as mock_engine, \
             patch('sqlalchemy.orm.sessionmaker') as mock_sessionmaker:
            
            # 建立模擬資料庫
            mock_session = Mock()
            mock_sessionmaker.return_value.return_value = mock_session
            
            db_config = {
                'host': 'localhost',
                'port': 5432,
                'db_name': 'test_db',
                'user': 'test_user',
                'password': 'test_password'
            }
            
            db = Database(db_config)
            
            # 測試模擬查詢
            with patch.object(db, 'get_session') as mock_get_session:
                mock_get_session.return_value.__enter__.return_value = mock_session
                mock_get_session.return_value.__exit__.return_value = None
                
                # 模擬查詢結果
                mock_user_thread = Mock()
                mock_user_thread.thread_id = 'test_thread_123'
                mock_session.query.return_value.filter.return_value.first.return_value = mock_user_thread
                
                result = db.query_thread('test_user')
                
                assert result == 'test_thread_123'
                mock_session.query.assert_called_once()


class TestLineBotMocks:
    """Line Bot API 模擬測試"""
    
    def test_mock_line_reply_api(self):
        """測試模擬 Line 回覆 API"""
        with patch('linebot.v3.messaging.MessagingApi.reply_message') as mock_reply:
            # 設定模擬回應
            mock_reply.return_value = None
            
            # 模擬回覆訊息
            from linebot.v3.messaging import TextMessage, ReplyMessageRequest
            
            reply_request = ReplyMessageRequest(
                reply_token='test_token',
                messages=[TextMessage(text='Test response')]
            )
            
            # 執行模擬調用
            mock_reply(reply_request)
            
            # 驗證調用
            mock_reply.assert_called_once_with(reply_request)
    
    def test_mock_line_webhook_parser(self):
        """測試模擬 Line Webhook 解析器"""
        with patch('linebot.v3.WebhookHandler.handle') as mock_handle:
            # 建立模擬事件
            mock_event = Mock()
            mock_event.type = 'message'
            mock_event.message.type = 'text'
            mock_event.message.text = 'Hello'
            mock_event.source.user_id = 'test_user'
            mock_event.reply_token = 'test_reply_token'
            
            mock_handle.return_value = [mock_event]
            
            # 模擬解析
            body = '{"events": [{"type": "message"}]}'
            signature = 'test_signature'
            
            events = mock_handle(body, signature)
            
            assert len(events) == 1
            assert events[0].type == 'message'
            mock_handle.assert_called_once_with(body, signature)


class TestExternalServiceIntegration:
    """外部服務整合模擬測試"""
    
    def test_mock_full_service_chain(self):
        """測試完整服務鏈的模擬（使用 Responses API + Conversations API）"""
        from src.models.openai_model import OpenAIModel
        from src.services.chat import ChatService
        from src.database import Database
        from src.models.base import RAGResponse
        from src.platforms.base import PlatformMessage, PlatformUser, PlatformType

        with patch('src.database.connection.create_engine'), \
             patch('src.database.connection.sessionmaker') as mock_sessionmaker:

            # 設定資料庫模擬
            mock_session = Mock()
            mock_sessionmaker.return_value.return_value = mock_session
            mock_session.query.return_value.filter.return_value.first.return_value = None

            db_config = {'host': 'localhost', 'port': 5432, 'db_name': 'test', 'user': 'test_user', 'password': 'test_password'}
            db = Database(db_config)

            model = OpenAIModel(api_key='test_key')

            chat_config = {
                'line': {
                    'reply': {
                        'help': 'Help message',
                        'reset': 'Reset message'
                    }
                }
            }

            # 模擬 model.chat_with_user 直接回傳結果（避免實際 API 呼叫）
            mock_rag_response = RAGResponse(answer='AI response', sources=[])
            model_chat_called = []

            def mock_chat_with_user(user_id, message, platform='line', **kwargs):
                model_chat_called.append((user_id, message))
                return True, mock_rag_response, None

            with patch.object(model, 'chat_with_user', side_effect=mock_chat_with_user), \
                 patch.object(db, 'get_session') as mock_get_session:
                mock_get_session.return_value.__enter__.return_value = mock_session
                mock_get_session.return_value.__exit__.return_value = None

                chat_service = ChatService(model, db, chat_config)

                platform_message = PlatformMessage(
                    message_id='test_msg_123',
                    content='Hello',
                    user=PlatformUser(user_id='test_user', platform=PlatformType.LINE, display_name='Test User'),
                    message_type='text'
                )
                response = chat_service.handle_message(platform_message)

                # 驗證整合結果
                assert response is not None
                # 驗證模型 API 被呼叫
                assert len(model_chat_called) >= 1  # model.chat_with_user 被調用