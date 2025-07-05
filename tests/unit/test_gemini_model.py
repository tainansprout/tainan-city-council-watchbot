import pytest
from unittest.mock import Mock, patch, MagicMock
import time

from src.models.gemini_model import GeminiModel
from src.models.base import FileInfo, RAGResponse, ChatMessage, ChatResponse, ThreadInfo, ModelProvider


class TestGeminiModel:
    """Google Gemini 2024 模型測試"""
    
    @pytest.fixture
    def gemini_model(self):
        return GeminiModel(
            api_key='test_key',
            model_name='gemini-1.5-pro-latest',
            project_id='test-project'
        )
    
    def test_init_with_defaults(self):
        """測試初始化預設值"""
        model = GeminiModel(api_key='test_key')
        
        assert model.api_key == 'test_key'
        assert model.model_name == 'gemini-1.5-pro-latest'
        assert model.base_url == 'https://generativelanguage.googleapis.com/v1beta'
        assert model.max_context_tokens == 1000000  # 1M token 上下文
        assert model.default_corpus_name == 'chatbot-knowledge'
        assert isinstance(model.corpora, dict)
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
    
    @patch('src.models.gemini_model.requests.post')
    def test_query_with_rag_no_corpus(self, mock_post, gemini_model):
        """測試沒有語料庫時的 RAG 查詢"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'candidates': [{
                'content': {
                    'parts': [{'text': 'I can help you with general questions.'}]
                },
                'finishReason': 'STOP'
            }]
        }
        mock_post.return_value = mock_response
        
        # 測試長上下文
        context_messages = [
            ChatMessage(role='system', content='You are a helpful assistant.'),
            ChatMessage(role='user', content='Previous question'),
            ChatMessage(role='assistant', content='Previous answer'),
            ChatMessage(role='user', content='Current question')
        ]
        
        is_successful, rag_response, error = gemini_model.query_with_rag(
            query="What can you help me with?",
            context_messages=context_messages
        )
        
        assert is_successful == True
        assert rag_response.answer == 'I can help you with general questions.'
        assert rag_response.metadata['no_sources'] == True
        assert rag_response.metadata['context_messages_count'] == 4
        
        # 驗證使用了上下文訊息
        call_args = mock_post.call_args
        request_body = call_args[1]['json']
        assert len(request_body['contents']) == 3  # user-assistant-user (系統指令分別處理)
    
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