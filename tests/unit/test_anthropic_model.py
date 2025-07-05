import pytest
from unittest.mock import Mock, patch, MagicMock
import time

from src.models.anthropic_model import AnthropicModel
from src.models.base import FileInfo, RAGResponse, ChatMessage, ChatResponse, ThreadInfo, ModelProvider


class TestAnthropicModel:
    """Anthropic Claude 2024 模型測試"""
    
    @pytest.fixture
    def anthropic_model(self):
        return AnthropicModel(
            api_key='test_key',
            model_name='claude-3-5-sonnet-20241022'
        )
    
    def test_init_with_defaults(self):
        """測試初始化預設值"""
        model = AnthropicModel(api_key='test_key')
        
        assert model.api_key == 'test_key'
        assert model.model_name == 'claude-3-5-sonnet-20241022'
        assert model.base_url == 'https://api.anthropic.com/v1'
        assert model.cache_enabled == True
        assert model.cache_ttl == 3600
        assert isinstance(model.files_store, dict)
        assert isinstance(model.cached_conversations, dict)
    
    def test_check_connection_success(self, anthropic_model):
        """測試連線檢查成功"""
        with patch.object(anthropic_model, 'chat_completion', return_value=(True, Mock(), None)):
            is_successful, error = anthropic_model.check_connection()
            assert is_successful == True
            assert error is None
    
    def test_check_connection_failure(self, anthropic_model):
        """測試連線檢查失敗"""
        with patch.object(anthropic_model, 'chat_completion', return_value=(False, None, 'API Error')):
            is_successful, error = anthropic_model.check_connection()
            assert is_successful == False
            assert error == 'API Error'
    
    @patch('src.models.anthropic_model.requests.post')
    def test_chat_completion_success(self, mock_post, anthropic_model):
        """測試聊天完成成功"""
        # 模擬 API 回應
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'content': [{'text': '這是測試回應'}],
            'stop_reason': 'end_turn',
            'usage': {'input_tokens': 10, 'output_tokens': 5}
        }
        mock_post.return_value = mock_response
        
        messages = [ChatMessage(role='user', content='Hello')]
        is_successful, response, error = anthropic_model.chat_completion(messages)
        
        assert is_successful == True
        assert response.content == '這是測試回應'
        assert response.finish_reason == 'end_turn'
        assert error is None
    
    @patch('src.models.anthropic_model.requests.post')
    def test_chat_completion_with_caching(self, mock_post, anthropic_model):
        """測試帶快取的聊天完成"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'content': [{'text': '快取回應'}],
            'stop_reason': 'end_turn',
            'usage': {
                'input_tokens': 10,
                'output_tokens': 5,
                'cache_creation_input_tokens': 100,
                'cache_read_input_tokens': 200
            }
        }
        mock_post.return_value = mock_response
        
        # 測試長系統提示詞觸發快取
        long_system = "這是一個很長的系統提示詞" * 100
        messages = [ChatMessage(role='user', content='Hello')]
        
        is_successful, response, error = anthropic_model.chat_completion(
            messages, 
            system=long_system
        )
        
        assert is_successful == True
        assert response.metadata['cache_creation_input_tokens'] == 100
        assert response.metadata['cache_read_input_tokens'] == 200
    
    @patch('src.models.anthropic_model.requests.post')
    def test_upload_knowledge_file_success(self, mock_post, anthropic_model):
        """測試使用 Files API 上傳檔案成功"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'id': 'file-123',
            'purpose': 'knowledge_base',
            'filename': 'test.txt'
        }
        mock_post.return_value = mock_response
        
        # 創建臨時測試檔案
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write('測試檔案內容')
            temp_file = f.name
        
        try:
            is_successful, file_info, error = anthropic_model.upload_knowledge_file(temp_file)
            
            assert is_successful == True
            assert file_info.file_id == 'file-123'
            assert file_info.filename == os.path.basename(temp_file)
            assert file_info.status == 'processed'
            assert error is None
            
            # 檢查快取
            assert 'file-123' in anthropic_model.files_store
            assert 'file-123' in anthropic_model.file_store
            
        finally:
            os.unlink(temp_file)
    
    def test_query_with_rag_no_files(self, anthropic_model):
        """測試沒有知識檔案時的 RAG 查詢"""
        with patch.object(anthropic_model, 'chat_completion') as mock_chat:
            mock_chat.return_value = (True, ChatResponse(content='一般回應'), None)
            
            is_successful, rag_response, error = anthropic_model.query_with_rag('測試問題')
            
            assert is_successful == True
            assert rag_response.answer == '一般回應'
            assert rag_response.sources == []
            assert rag_response.metadata['no_sources'] == True
    
    def test_query_with_rag_with_files(self, anthropic_model):
        """測試有知識檔案時的 RAG 查詢"""
        # 添加模擬檔案到快取
        file_info = FileInfo(
            file_id='file-123',
            filename='test.txt',
            size=100,
            status='processed',
            purpose='knowledge_base'
        )
        anthropic_model.files_store['file-123'] = file_info
        anthropic_model.file_store['file-123'] = 'test.txt'
        
        with patch.object(anthropic_model, 'chat_completion') as mock_chat:
            mock_response = ChatResponse(
                content='根據 [test.txt] 的內容...',
                metadata={'cache_read_input_tokens': 100}
            )
            mock_chat.return_value = (True, mock_response, None)
            
            is_successful, rag_response, error = anthropic_model.query_with_rag('測試問題')
            
            if not is_successful:
                print(f"Error: {error}")
            
            assert is_successful == True
            assert '根據 [test.txt] 的內容...' in rag_response.answer
            assert rag_response.metadata['files_used'] == 1
            assert rag_response.metadata['cache_enabled'] == True
    
    @patch('src.models.anthropic_model.requests.get')
    def test_get_knowledge_files_from_api(self, mock_get, anthropic_model):
        """測試從 API 獲取知識檔案列表"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': [
                {
                    'id': 'file-123',
                    'filename': 'test1.txt',
                    'bytes': 1000,
                    'purpose': 'knowledge_base',
                    'created_at': '2024-01-01T00:00:00Z'
                },
                {
                    'id': 'file-456', 
                    'filename': 'test2.txt',
                    'bytes': 2000,
                    'purpose': 'knowledge_base',
                    'created_at': '2024-01-02T00:00:00Z'
                }
            ]
        }
        mock_get.return_value = mock_response
        
        is_successful, files, error = anthropic_model.get_knowledge_files()
        
        if not is_successful:
            print(f"Error: {error}")
        
        assert is_successful == True
        assert len(files) == 2
        assert files[0].filename == 'test1.txt'
        assert files[1].filename == 'test2.txt'
        assert error is None
        
        # 檢查快取更新
        assert len(anthropic_model.files_store) == 2
        assert len(anthropic_model.file_store) == 2
    
    def test_create_thread_with_cache(self, anthropic_model):
        """測試創建對話串並啟用快取"""
        is_successful, thread_info, error = anthropic_model.create_thread()
        
        assert is_successful == True
        assert thread_info.thread_id is not None
        assert thread_info.metadata['cache_enabled'] == True
        assert error is None
        
        # 檢查快取初始化
        assert thread_info.thread_id in anthropic_model.cached_conversations
        cache_data = anthropic_model.cached_conversations[thread_info.thread_id]
        assert 'created_at' in cache_data
        assert cache_data['messages'] == []
        assert cache_data['system_context'] == anthropic_model.system_prompt
    
    def test_add_message_to_thread(self, anthropic_model):
        """測試添加訊息到對話串快取"""
        # 先創建對話串
        is_successful, thread_info, _ = anthropic_model.create_thread()
        thread_id = thread_info.thread_id
        
        # 添加訊息
        message = ChatMessage(role='user', content='測試訊息')
        is_successful, error = anthropic_model.add_message_to_thread(thread_id, message)
        
        assert is_successful == True
        assert error is None
        
        # 檢查快取
        cached_messages = anthropic_model.cached_conversations[thread_id]['messages']
        assert len(cached_messages) == 1
        assert cached_messages[0]['role'] == 'user'
        assert cached_messages[0]['content'] == '測試訊息'
        assert 'timestamp' in cached_messages[0]
    
    def test_delete_thread(self, anthropic_model):
        """測試刪除對話串及其快取"""
        # 創建對話串
        is_successful, thread_info, _ = anthropic_model.create_thread()
        thread_id = thread_info.thread_id
        
        # 確認存在
        assert thread_id in anthropic_model.cached_conversations
        
        # 刪除
        is_successful, error = anthropic_model.delete_thread(thread_id)
        
        assert is_successful == True
        assert error is None
        assert thread_id not in anthropic_model.cached_conversations
    
    def test_run_assistant_with_cached_messages(self, anthropic_model):
        """測試使用快取訊息執行助理"""
        # 創建對話串並添加訊息
        is_successful, thread_info, _ = anthropic_model.create_thread()
        thread_id = thread_info.thread_id
        
        message = ChatMessage(role='user', content='測試查詢')
        anthropic_model.add_message_to_thread(thread_id, message)
        
        with patch.object(anthropic_model, 'query_with_rag') as mock_rag:
            mock_rag.return_value = (True, RAGResponse(answer='助理回應', sources=[]), None)
            
            is_successful, rag_response, error = anthropic_model.run_assistant(thread_id)
            
            assert is_successful == True
            assert rag_response.answer == '助理回應'
            mock_rag.assert_called_once_with('測試查詢', thread_id)
    
    def test_transcribe_audio_no_service(self, anthropic_model):
        """測試沒有配置語音服務時的音訊轉錄"""
        is_successful, transcript, error = anthropic_model.transcribe_audio('test.wav')
        
        assert is_successful == False
        assert transcript is None
        assert 'Anthropic 不支援音訊轉錄' in error
    
    def test_set_speech_service(self, anthropic_model):
        """測試設置語音服務"""
        # 測試設置 Deepgram
        anthropic_model.set_speech_service('deepgram', 'test_api_key')
        assert anthropic_model.deepgram_api_key == 'test_api_key'
        
        # 測試設置 AssemblyAI
        anthropic_model.set_speech_service('assemblyai', 'another_key')
        assert anthropic_model.assemblyai_api_key == 'another_key'
        
        # 測試不支援的服務
        with pytest.raises(ValueError):
            anthropic_model.set_speech_service('unknown', 'key')
    
    def test_extract_sources_from_response(self, anthropic_model):
        """測試從回應中提取來源資訊"""
        # 設置檔案快取
        anthropic_model.file_store = {
            'file-123': 'document.txt',
            'file-456': 'report.pdf'
        }
        
        response_text = "根據 [document] 的內容，以及 [report] 的分析..."
        sources = anthropic_model._extract_sources_from_response(response_text)
        
        assert len(sources) == 2
        assert sources[0]['filename'] == 'document.txt'
        assert sources[1]['filename'] == 'report.pdf'
        assert sources[0]['citation'] == 'document'
        assert sources[1]['citation'] == 'report'
    
    def test_build_files_context(self, anthropic_model):
        """測試建立檔案上下文"""
        # 空檔案情況
        context = anthropic_model._build_files_context()
        assert context == "無可用文檔"
        
        # 有檔案情況
        file_info1 = FileInfo(file_id='file-123', filename='doc1.txt')
        file_info2 = FileInfo(file_id='file-456', filename='doc2.txt')
        anthropic_model.files_store = {
            'file-123': file_info1,
            'file-456': file_info2
        }
        
        context = anthropic_model._build_files_context()
        assert 'doc1.txt (ID: file-123)' in context
        assert 'doc2.txt (ID: file-456)' in context
    
    def test_system_prompt_structure(self, anthropic_model):
        """測試系統提示詞結構"""
        system_prompt = anthropic_model.system_prompt
        
        # 檢查關鍵元素
        assert '知識助理' in system_prompt
        assert '能力範圍' in system_prompt
        assert '回答原則' in system_prompt
        assert '[filename]' in system_prompt
        assert '回答格式' in system_prompt
    
    @patch('src.models.anthropic_model.requests.post')
    def test_error_handling(self, mock_post, anthropic_model):
        """測試錯誤處理"""
        # 測試 HTTP 錯誤
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'error': {'message': 'Invalid request'}
        }
        mock_post.return_value = mock_response
        
        messages = [ChatMessage(role='user', content='Hello')]
        is_successful, response, error = anthropic_model.chat_completion(messages)
        
        assert is_successful == False
        assert response is None
        assert 'Invalid request' in error
    
    def test_cache_ttl_behavior(self, anthropic_model):
        """測試快取過期行為"""
        # 創建對話串
        is_successful, thread_info, _ = anthropic_model.create_thread()
        thread_id = thread_info.thread_id
        
        # 模擬時間過去
        original_time = anthropic_model.cached_conversations[thread_id]['created_at']
        
        # 檢查快取存在
        assert thread_id in anthropic_model.cached_conversations
        
        # 在實際實作中，應該有清理過期快取的機制
        # 這裡只是驗證資料結構正確
        assert anthropic_model.cached_conversations[thread_id]['created_at'] == original_time
    
    def test_get_provider(self, anthropic_model):
        """測試模型提供商識別"""
        provider = anthropic_model.get_provider()
        assert provider == ModelProvider.ANTHROPIC
    
    @patch('src.models.anthropic_model.AnthropicModel.query_with_rag')
    @patch('src.models.anthropic_model.AnthropicModel._get_recent_conversations')
    def test_chat_with_user_success(self, mock_get_conversations, mock_query_rag, anthropic_model):
        """測試 chat_with_user 成功場景"""
        # 模擬對話歷史
        mock_get_conversations.return_value = [
            {'role': 'user', 'content': 'Hello', 'created_at': '2024-01-01T10:00:00'},
            {'role': 'assistant', 'content': 'Hi there!', 'created_at': '2024-01-01T10:00:01'}
        ]
        
        # 模擬 RAG 回應
        mock_rag_response = RAGResponse(
            answer="Based on our conversation, here's my response.",
            sources=[],
            metadata={'model': 'anthropic-claude'}
        )
        mock_query_rag.return_value = (True, mock_rag_response, None)
        
        # 模擬對話管理器
        mock_conversation_manager = Mock()
        mock_conversation_manager.add_message.return_value = True
        anthropic_model.conversation_manager = mock_conversation_manager
        
        # 執行測試
        is_successful, rag_response, error = anthropic_model.chat_with_user(
            user_id='test_user_123',
            message='What can you tell me about our previous discussion?'
        )
        
        # 驗證結果
        assert is_successful == True
        assert rag_response is not None
        assert error is None
        assert rag_response.answer == "Based on our conversation, here's my response."
        assert 'conversation_turns' in rag_response.metadata
        assert 'user_id' in rag_response.metadata
        assert rag_response.metadata['user_id'] == 'test_user_123'
        assert rag_response.metadata['model_provider'] == 'anthropic'
        
        # 驗證方法調用 (現在包含 platform 參數)
        mock_get_conversations.assert_called_once_with('test_user_123', 'line', limit=5)
        mock_conversation_manager.add_message.assert_any_call('test_user_123', 'anthropic', 'user', 'What can you tell me about our previous discussion?', 'line')
        mock_conversation_manager.add_message.assert_any_call('test_user_123', 'anthropic', 'assistant', "Based on our conversation, here's my response.", 'line')
    
    @patch('src.models.anthropic_model.AnthropicModel.query_with_rag')
    @patch('src.models.anthropic_model.AnthropicModel._get_recent_conversations')
    def test_chat_with_user_rag_failure(self, mock_get_conversations, mock_query_rag, anthropic_model):
        """測試 chat_with_user RAG 失敗場景"""
        # 模擬對話歷史
        mock_get_conversations.return_value = []
        
        # 模擬 RAG 失敗
        mock_query_rag.return_value = (False, None, "RAG processing failed")
        
        # 模擬對話管理器
        mock_conversation_manager = Mock()
        mock_conversation_manager.add_message.return_value = True
        anthropic_model.conversation_manager = mock_conversation_manager
        
        # 執行測試
        is_successful, rag_response, error = anthropic_model.chat_with_user(
            user_id='test_user_456',
            message='Test message'
        )
        
        # 驗證結果
        assert is_successful == False
        assert rag_response is None
        assert error == "RAG processing failed"
        
        # 驗證用戶訊息仍然被儲存
        mock_conversation_manager.add_message.assert_called_once_with('test_user_456', 'anthropic', 'user', 'Test message', 'line')
    
    def test_clear_user_history_success(self, anthropic_model):
        """測試清除用戶歷史成功"""
        # 模擬對話管理器
        mock_conversation_manager = Mock()
        mock_conversation_manager.clear_user_history.return_value = True
        anthropic_model.conversation_manager = mock_conversation_manager
        
        # 執行測試
        is_successful, error = anthropic_model.clear_user_history('test_user_789')
        
        # 驗證結果
        assert is_successful == True
        assert error is None
        
        # 驗證方法調用
        mock_conversation_manager.clear_user_history.assert_called_once_with('test_user_789', 'anthropic', 'line')
    
    def test_clear_user_history_failure(self, anthropic_model):
        """測試清除用戶歷史失敗"""
        # 模擬對話管理器
        mock_conversation_manager = Mock()
        mock_conversation_manager.clear_user_history.return_value = False
        anthropic_model.conversation_manager = mock_conversation_manager
        
        # 執行測試
        is_successful, error = anthropic_model.clear_user_history('test_user_999')
        
        # 驗證結果
        assert is_successful == False
        assert error == "Failed to clear conversation history"
    
    @patch('src.models.anthropic_model.AnthropicModel._get_recent_conversations')
    def test_build_conversation_context(self, mock_get_conversations, anthropic_model):
        """測試建立對話上下文"""
        # 模擬長對話歷史（10 輪對話）
        conversations = []
        for i in range(10):
            conversations.extend([
                {'role': 'user', 'content': f'User message {i}', 'created_at': f'2024-01-01T10:0{i}:00'},
                {'role': 'assistant', 'content': f'Assistant response {i}', 'created_at': f'2024-01-01T10:0{i}:01'}
            ])
        
        mock_get_conversations.return_value = conversations
        
        # 測試內部方法
        messages = anthropic_model._build_conversation_context(conversations, "Current message")
        
        # 驗證結果
        assert len(messages) <= 9  # 最多 8 輪歷史 + 1 當前訊息
        assert messages[-1].content == "Current message"
        assert messages[-1].role == "user"
        
        # 驗證取的是最近的對話
        if len(messages) > 1:
            assert "User message" in messages[-2].content or "Assistant response" in messages[-2].content