"""
Hugging Face 模型單元測試
"""
import pytest
import json
import time
import requests
from unittest.mock import Mock, patch, MagicMock

from src.models.huggingface_model import HuggingFaceModel
from src.models.base import ModelProvider, ChatMessage, ChatResponse, FileInfo, RAGResponse, ThreadInfo


class TestHuggingFaceModel:
    """測試 Hugging Face 模型實作"""
    
    @pytest.fixture
    def hf_model(self):
        """創建測試用的 HuggingFace 模型實例"""
        return HuggingFaceModel(
            api_key='test_hf_key',
            model_name='mistralai/Mistral-7B-Instruct-v0.1',
            api_type='inference_api'
        )
    
    def test_init_with_defaults(self):
        """測試預設初始化"""
        model = HuggingFaceModel(api_key='test_key')
        
        assert model.api_key == 'test_key'
        assert model.model_name == 'mistralai/Mistral-7B-Instruct-v0.1'
        assert model.api_type == 'inference_api'
        assert model.base_url == 'https://api-inference.huggingface.co'
        assert model.embedding_model == 'sentence-transformers/all-MiniLM-L6-v2'
        assert model.speech_model == 'openai/whisper-large-v3'
        assert model.image_model == 'stabilityai/stable-diffusion-xl-base-1.0'
        assert isinstance(model.fallback_models, list)
        assert len(model.fallback_models) > 0

    def test_get_provider(self, hf_model):
        """測試模型提供商識別"""
        provider = hf_model.get_provider()
        assert provider == ModelProvider.HUGGINGFACE

    @patch('src.models.huggingface_model.requests.post')
    def test_check_connection_success(self, mock_post, hf_model):
        """測試連線檢查成功"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"generated_text": "Hello world"}]
        mock_post.return_value = mock_response
        
        is_successful, error = hf_model.check_connection()
        assert is_successful == True
        assert error is None

    @patch('src.models.huggingface_model.requests.post')
    def test_check_connection_failure(self, mock_post, hf_model):
        """測試連線檢查失敗"""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_post.return_value = mock_response
        
        is_successful, error = hf_model.check_connection()
        assert is_successful == False
        assert error is not None

    @patch('src.models.huggingface_model.requests.post')
    def test_chat_completion_success(self, mock_post, hf_model):
        """測試聊天完成成功"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"generated_text": "Hello! How can I help you today?"}]
        mock_post.return_value = mock_response
        
        messages = [ChatMessage(role='user', content='Hello')]
        is_successful, response, error = hf_model.chat_completion(messages)
        
        assert is_successful == True
        assert response is not None
        assert response.content == 'Hello! How can I help you today?'
        assert response.finish_reason == 'stop'
        assert response.metadata['provider'] == 'huggingface'
        assert error is None

    @patch('src.models.huggingface_model.requests.post')
    def test_chat_completion_model_loading(self, mock_post, hf_model):
        """測試模型載入中的情況"""
        # 第一次請求返回 503 (模型載入中)
        mock_response_503 = Mock()
        mock_response_503.status_code = 503
        
        # 第二次請求成功
        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = [{"generated_text": "Response after loading"}]
        
        # 設置連續的返回值
        mock_post.side_effect = [mock_response_503, mock_response_200]
        
        # Mock time.sleep 以避免實際等待
        with patch('time.sleep'):
            messages = [ChatMessage(role='user', content='Hello')]
            is_successful, response, error = hf_model.chat_completion(messages)
        
        assert is_successful == True
        assert response.content == 'Response after loading'

    def test_build_chat_prompt_mistral(self, hf_model):
        """測試 Mistral 格式的提示詞構建"""
        messages = [
            ChatMessage(role='system', content='You are a helpful assistant'),
            ChatMessage(role='user', content='Hello'),
            ChatMessage(role='assistant', content='Hi there!'),
            ChatMessage(role='user', content='How are you?')
        ]
        
        prompt = hf_model._build_chat_prompt(messages)
        
        # Mistral 格式應該包含 [INST] 和 [/INST] 標記
        assert '[INST]' in prompt
        assert '[/INST]' in prompt
        assert 'You are a helpful assistant' in prompt

    def test_build_chat_prompt_zephyr(self, hf_model):
        """測試 Zephyr 格式的提示詞構建"""
        hf_model.model_name = 'HuggingFaceH4/zephyr-7b-beta'
        
        messages = [
            ChatMessage(role='system', content='You are helpful'),
            ChatMessage(role='user', content='Hello')
        ]
        
        prompt = hf_model._build_chat_prompt(messages)
        
        # Zephyr 格式應該包含特殊標記
        assert '<|system|>' in prompt
        assert '<|user|>' in prompt
        assert '<|assistant|>' in prompt

    def test_build_chat_prompt_generic(self, hf_model):
        """測試通用格式的提示詞構建"""
        hf_model.model_name = 'some-generic-model'
        
        messages = [
            ChatMessage(role='user', content='Hello'),
            ChatMessage(role='assistant', content='Hi')
        ]
        
        prompt = hf_model._build_chat_prompt(messages)
        
        # 通用格式應該包含角色標記
        assert 'Human:' in prompt
        assert 'Assistant:' in prompt

    @patch('src.models.huggingface_model.HuggingFaceModel.query_with_rag')
    @patch('src.models.huggingface_model.HuggingFaceModel._get_recent_conversations')
    def test_chat_with_user_with_rag(self, mock_get_conversations, mock_query_rag, hf_model):
        """測試使用 RAG 的用戶對話"""
        # 設置知識庫
        hf_model.knowledge_store = {'file1': {'filename': 'test.txt'}}
        
        # 模擬對話歷史
        mock_get_conversations.return_value = [
            {'role': 'user', 'content': 'Previous question'},
            {'role': 'assistant', 'content': 'Previous answer'}
        ]
        
        # 模擬 RAG 回應
        mock_rag_response = RAGResponse(
            answer="This is a RAG response with citations [1]",
            sources=[{'file_id': 'file1', 'filename': 'test.txt', 'quote': 'relevant text'}],
            metadata={'rag_enabled': True}
        )
        mock_query_rag.return_value = (True, mock_rag_response, None)
        
        # 執行測試
        is_successful, rag_response, error = hf_model.chat_with_user(
            user_id='test_user',
            message='Tell me about the document',
            platform='line'
        )
        
        assert is_successful == True
        assert rag_response is not None
        assert rag_response.metadata['user_id'] == 'test_user'
        assert rag_response.metadata['platform'] == 'line'
        assert rag_response.metadata['model_provider'] == 'huggingface'

    def test_chat_with_user_reset_command(self, hf_model):
        """測試重置命令"""
        with patch.object(hf_model, 'clear_user_history', return_value=(True, None)):
            is_successful, rag_response, error = hf_model.chat_with_user(
                user_id='test_user',
                message='/reset',
                platform='line'
            )
        
        assert is_successful == True
        assert '已清除您的對話歷史' in rag_response.answer

    def test_clear_user_history(self, hf_model):
        """測試清除用戶歷史"""
        # 設置本地線程
        thread_key = "test_user:line"
        hf_model.local_threads[thread_key] = {"messages": []}
        
        # 模擬對話管理器
        mock_conversation_manager = Mock()
        mock_conversation_manager.clear_user_history.return_value = True
        hf_model.conversation_manager = mock_conversation_manager
        
        is_successful, error = hf_model.clear_user_history('test_user', 'line')
        
        assert is_successful == True
        assert error is None
        assert thread_key not in hf_model.local_threads

    def test_upload_knowledge_file_success(self, hf_model, tmp_path):
        """測試成功上傳知識文件"""
        # 創建測試文件
        test_file = tmp_path / "test.txt"
        test_file.write_text("This is test content for knowledge base.")
        
        # Mock 嵌入向量生成
        with patch.object(hf_model, '_get_embedding', return_value=[0.1] * 384):
            is_successful, file_info, error = hf_model.upload_knowledge_file(str(test_file))
        
        assert is_successful == True
        assert file_info is not None
        assert file_info.filename == "test.txt"
        assert file_info.status == "processed"
        assert error is None
        assert file_info.file_id in hf_model.knowledge_store

    def test_upload_knowledge_file_not_found(self, hf_model):
        """測試上傳不存在的文件"""
        is_successful, file_info, error = hf_model.upload_knowledge_file("/non/existent/file.txt")
        
        assert is_successful == False
        assert file_info is None
        assert "not found" in error.lower()

    @patch('src.models.huggingface_model.requests.post')
    def test_get_embedding_success(self, mock_post, hf_model):
        """測試成功生成嵌入向量"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [0.1, 0.2, 0.3]
        mock_post.return_value = mock_response
        
        embedding = hf_model._get_embedding("test text")
        
        assert embedding == [0.1, 0.2, 0.3]
        # 測試緩存
        embedding2 = hf_model._get_embedding("test text")
        assert embedding2 == embedding
        assert mock_post.call_count == 1  # 應該使用緩存

    def test_vector_search(self, hf_model):
        """測試向量搜索"""
        # 設置知識庫
        hf_model.knowledge_store = {
            'file1': {
                'filename': 'test.txt',
                'chunks': [
                    {'text': 'chunk1', 'embedding': [0.1, 0.2, 0.3]},
                    {'text': 'chunk2', 'embedding': [0.9, 0.8, 0.7]}
                ]
            }
        }
        
        query_embedding = [0.9, 0.8, 0.7]  # 與 chunk2 相似
        results = hf_model._vector_search(query_embedding, top_k=1, threshold=0.5)
        
        assert len(results) == 1
        assert results[0]['text'] == 'chunk2'
        assert results[0]['similarity'] > 0.5

    def test_cosine_similarity(self, hf_model):
        """測試餘弦相似度計算"""
        vec1 = [1, 0, 0]
        vec2 = [1, 0, 0]
        similarity = hf_model._cosine_similarity(vec1, vec2)
        assert similarity == 1.0
        
        vec3 = [1, 0, 0]
        vec4 = [0, 1, 0]
        similarity = hf_model._cosine_similarity(vec3, vec4)
        assert similarity == 0.0

    def test_query_with_rag_no_knowledge(self, hf_model):
        """測試沒有知識庫時的 RAG 查詢"""
        # 確保知識庫為空
        hf_model.knowledge_store = {}
        
        with patch.object(hf_model, '_fallback_chat_completion') as mock_fallback:
            mock_fallback.return_value = (True, RAGResponse(answer="Fallback response", sources=[]), None)
            
            is_successful, rag_response, error = hf_model.query_with_rag("test query")
            
            assert is_successful == True
            assert rag_response.answer == "Fallback response"
            mock_fallback.assert_called_once()

    def test_create_thread(self, hf_model):
        """測試創建對話線程"""
        is_successful, thread_info, error = hf_model.create_thread()
        
        assert is_successful == True
        assert thread_info is not None
        assert thread_info.thread_id.startswith('hf_thread_')
        assert thread_info.thread_id in hf_model.local_threads
        assert error is None

    def test_delete_thread(self, hf_model):
        """測試刪除對話線程"""
        # 先創建線程
        thread_id = "test_thread"
        hf_model.local_threads[thread_id] = {"messages": []}
        
        is_successful, error = hf_model.delete_thread(thread_id)
        
        assert is_successful == True
        assert error is None
        assert thread_id not in hf_model.local_threads

    def test_add_message_to_thread(self, hf_model):
        """測試添加訊息到線程"""
        # 先創建線程
        thread_id = "test_thread"
        hf_model.local_threads[thread_id] = {"messages": []}
        
        message = ChatMessage(role='user', content='Hello')
        is_successful, error = hf_model.add_message_to_thread(thread_id, message)
        
        assert is_successful == True
        assert error is None
        assert len(hf_model.local_threads[thread_id]["messages"]) == 1
        assert hf_model.local_threads[thread_id]["messages"][0]["content"] == 'Hello'

    def test_add_message_to_nonexistent_thread(self, hf_model):
        """測試添加訊息到不存在的線程"""
        message = ChatMessage(role='user', content='Hello')
        is_successful, error = hf_model.add_message_to_thread("nonexistent", message)
        
        assert is_successful == False
        assert "not found" in error

    @patch('src.models.huggingface_model.requests.post')
    def test_transcribe_audio_success(self, mock_post, hf_model, tmp_path):
        """測試語音轉文字成功"""
        # 創建測試音頻文件
        audio_file = tmp_path / "test_audio.wav"
        audio_file.write_bytes(b"fake audio data")
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"text": "Transcribed audio content"}
        mock_post.return_value = mock_response
        
        is_successful, text, error = hf_model.transcribe_audio(str(audio_file))
        
        assert is_successful == True
        assert text == "Transcribed audio content"
        assert error is None

    def test_transcribe_audio_file_not_found(self, hf_model):
        """測試轉錄不存在的音頻文件"""
        is_successful, text, error = hf_model.transcribe_audio("/nonexistent/audio.wav")
        
        assert is_successful == False
        assert text is None
        assert "not found" in error

    @patch('src.models.huggingface_model.requests.post')
    def test_generate_image_success(self, mock_post, hf_model):
        """測試圖片生成成功"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"fake image data"
        mock_post.return_value = mock_response
        
        is_successful, image_url, error = hf_model.generate_image("A beautiful sunset")
        
        assert is_successful == True
        assert image_url.startswith("data:image/png;base64,")
        assert error is None

    @patch('src.models.huggingface_model.requests.post')
    def test_generate_image_failure(self, mock_post, hf_model):
        """測試圖片生成失敗"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_post.return_value = mock_response
        
        is_successful, image_url, error = hf_model.generate_image("Invalid prompt")
        
        assert is_successful == False
        assert image_url is None
        assert "Bad request" in error

    def test_chunk_text(self, hf_model):
        """測試文本分塊"""
        text = "This is a test text that needs to be chunked into smaller pieces for processing."
        chunks = hf_model._chunk_text(text, chunk_size=30, overlap=10)
        
        assert len(chunks) > 1
        assert all('text' in chunk for chunk in chunks)
        assert all('start' in chunk for chunk in chunks)
        assert all('end' in chunk for chunk in chunks)

    def test_read_file_content_txt(self, hf_model, tmp_path):
        """測試讀取文本文件"""
        test_file = tmp_path / "test.txt"
        test_content = "這是測試內容"
        test_file.write_text(test_content, encoding='utf-8')
        
        content = hf_model._read_file_content(str(test_file))
        assert content == test_content

    def test_read_file_content_unsupported(self, hf_model, tmp_path):
        """測試讀取不支援的文件類型"""
        test_file = tmp_path / "test.xyz"
        test_file.write_bytes(b"some binary data")
        
        content = hf_model._read_file_content(str(test_file))
        assert content is None

    def test_get_knowledge_files(self, hf_model):
        """測試取得知識庫文件列表"""
        # 設置測試知識庫
        hf_model.knowledge_store = {
            'file1': {
                'filename': 'test1.txt',
                'metadata': {'size': 100}
            },
            'file2': {
                'filename': 'test2.txt',
                'metadata': {'size': 200}
            }
        }
        
        is_successful, files, error = hf_model.get_knowledge_files()
        
        assert is_successful == True
        assert len(files) == 2
        assert error is None
        assert files[0].filename in ['test1.txt', 'test2.txt']

    def test_get_file_references(self, hf_model):
        """測試取得文件引用映射"""
        hf_model.knowledge_store = {
            'file1': {'filename': 'document.txt'},
            'file2': {'filename': 'manual.pdf'}
        }
        
        references = hf_model.get_file_references()
        
        assert isinstance(references, dict)
        assert 'file1' in references
        assert 'file2' in references
        assert references['file1'] == 'document'
        assert references['file2'] == 'manual'

    def test_process_inline_citations(self, hf_model):
        """測試處理內聯引用"""
        text = "Based on [1] and [2], the answer is clear."
        relevant_chunks = [
            {'file_id': 'file1', 'filename': 'doc1.txt', 'text': 'content1'},
            {'file_id': 'file2', 'filename': 'doc2.txt', 'text': 'content2'}
        ]
        
        processed_text, sources = hf_model._process_inline_citations(text, relevant_chunks)
        
        assert processed_text == text  # 文本應該保持不變
        assert len(sources) == 2
        # 檢查來源檔案名，但不依賴順序
        source_filenames = {source['filename'] for source in sources}
        assert 'doc1.txt' in source_filenames
        assert 'doc2.txt' in source_filenames

    def test_build_rag_system_prompt(self, hf_model):
        """測試構建 RAG 系統提示"""
        relevant_chunks = [
            {'filename': 'doc1.txt', 'text': 'This is content from doc1'},
            {'filename': 'doc2.txt', 'text': 'This is content from doc2'}
        ]
        
        system_prompt = hf_model._build_rag_system_prompt(relevant_chunks)
        
        assert '[1] 來源文件: doc1.txt' in system_prompt
        assert '[2] 來源文件: doc2.txt' in system_prompt
        assert 'This is content from doc1' in system_prompt
        assert 'This is content from doc2' in system_prompt
        assert '在回答中使用 [1], [2] 等數字來標註引用來源' in system_prompt


class TestHuggingFaceModelIntegration:
    """Hugging Face 模型整合測試"""
    
    @pytest.fixture
    def configured_model(self):
        """創建配置完整的模型"""
        model = HuggingFaceModel(
            api_key='test_key',
            model_name='mistralai/Mistral-7B-Instruct-v0.1'
        )
        # 設置對話管理器的 Mock
        mock_conversation_manager = Mock()
        mock_conversation_manager.get_recent_conversations.return_value = []
        mock_conversation_manager.add_message.return_value = True
        mock_conversation_manager.clear_user_history.return_value = True
        model.conversation_manager = mock_conversation_manager
        return model
    
    def test_full_workflow_without_rag(self, configured_model):
        """測試完整工作流程（無 RAG）"""
        with patch.object(configured_model, 'chat_completion') as mock_chat:
            mock_chat_response = ChatResponse(
                content="Test response",
                finish_reason="stop",
                metadata={"model": "test", "provider": "huggingface"}
            )
            mock_chat.return_value = (True, mock_chat_response, None)
            
            is_successful, rag_response, error = configured_model.chat_with_user(
                user_id='test_user',
                message='Hello',
                platform='line'
            )
            
            assert is_successful == True
            assert rag_response.answer == "Test response"
            assert rag_response.metadata['rag_enabled'] == False

    def test_full_workflow_with_rag(self, configured_model, tmp_path):
        """測試完整工作流程（有 RAG）"""
        # 上傳測試文件
        test_file = tmp_path / "knowledge.txt"
        test_file.write_text("This is important knowledge content.")
        
        with patch.object(configured_model, '_get_embedding', return_value=[0.1] * 384):
            configured_model.upload_knowledge_file(str(test_file))
        
        # 測試 RAG 查詢 - 需要同時 patch 多個方法
        with patch.object(configured_model, 'chat_completion') as mock_chat, \
             patch.object(configured_model, '_get_embedding', return_value=[0.1] * 384) as mock_embedding:
            mock_chat_response = ChatResponse(
                content="Response based on knowledge [1]",
                finish_reason="stop",
                metadata={"model": "test", "provider": "huggingface"}
            )
            mock_chat.return_value = (True, mock_chat_response, None)
            
            is_successful, rag_response, error = configured_model.chat_with_user(
                user_id='test_user',
                message='What is the important content?',
                platform='line'
            )
            
            assert is_successful == True
            assert rag_response.metadata['rag_enabled'] == True
            assert len(rag_response.sources) > 0

    def test_error_handling(self, configured_model):
        """測試錯誤處理"""
        with patch.object(configured_model, 'chat_completion', side_effect=Exception("API Error")):
            is_successful, rag_response, error = configured_model.chat_with_user(
                user_id='test_user',
                message='Hello',
                platform='line'
            )
            
            assert is_successful == False
            assert rag_response is None
            assert "API Error" in error or "chat_with_user failed" in error


class TestHuggingFaceModelAdditionalCoverage:
    """額外的測試用於提高覆蓋率"""
    
    @pytest.fixture
    def hf_model(self):
        """創建測試用的 HuggingFace 模型實例"""
        return HuggingFaceModel(
            api_key='test_hf_key',
            model_name='mistralai/Mistral-7B-Instruct-v0.1',
            api_type='inference_api'
        )
    
    @pytest.fixture
    def hf_model_with_fallbacks(self):
        """創建有備用模型的 HuggingFace 模型"""
        model = HuggingFaceModel(
            api_key='test_key',
            model_name='mistralai/Mistral-7B-Instruct-v0.1'
        )
        model.fallback_models = [
            'microsoft/DialoGPT-medium',
            'HuggingFaceH4/zephyr-7b-beta'
        ]
        return model
    
    @patch('src.models.huggingface_model.requests.post')
    def test_chat_completion_with_fallback(self, mock_post, hf_model_with_fallbacks):
        """測試主模型失敗時使用備用模型"""
        # 第一次請求失敗
        mock_response_fail = Mock()
        mock_response_fail.status_code = 503
        mock_response_fail.text = "Service unavailable"
        
        # 第二次請求（備用模型）成功
        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = [{"generated_text": "Fallback response"}]
        
        mock_post.side_effect = [mock_response_fail, mock_response_success]
        
        # 設置重試計數器
        hf_model_with_fallbacks._retry_count = 0
        
        messages = [ChatMessage(role='user', content='Hello')]
        is_successful, response, error = hf_model_with_fallbacks.chat_completion(messages)
        
        assert is_successful == True
        assert response.content == "Fallback response"
    
    def test_vector_search_no_results(self, hf_model):
        """測試向量搜索無結果的情況"""
        # 設置知識庫但無匹配結果
        hf_model.knowledge_store = {
            'file1': {
                'filename': 'test.txt',
                'chunks': [
                    {'text': 'chunk1', 'embedding': [0.1, 0.2, 0.3]}
                ]
            }
        }
        
        # 搜索完全不相關的向量
        query_embedding = [0.9, 0.8, 0.7]
        results = hf_model._vector_search(query_embedding, top_k=1, threshold=0.9)
        
        assert len(results) == 0
    
    def test_cosine_similarity_edge_cases(self, hf_model):
        """測試餘弦相似度計算的邊界情況"""
        # 零向量測試
        zero_vec = [0, 0, 0]
        normal_vec = [1, 2, 3]
        similarity = hf_model._cosine_similarity(zero_vec, normal_vec)
        assert similarity == 0.0
        
        # 負向量測試
        neg_vec = [-1, -2, -3]
        pos_vec = [1, 2, 3]
        similarity = hf_model._cosine_similarity(neg_vec, pos_vec)
        assert similarity == -1.0
    
    def test_build_conversation_context_long_history(self, hf_model):
        """測試長對話歷史的上下文構建"""
        # 創建長對話歷史
        long_history = []
        for i in range(25):  # 超過限制的25輪對話
            long_history.extend([
                {'role': 'user', 'content': f'User message {i}'},
                {'role': 'assistant', 'content': f'Assistant response {i}'}
            ])
        
        messages = hf_model._build_conversation_context(long_history, "Current message")
        
        # 應該限制歷史對話數量（最多20輪，加上系統和當前訊息）
        assert len(messages) <= 42  # 1 system + 40 history + 1 current
        assert messages[0].role == "system"
        assert messages[-1].role == "user"
        assert messages[-1].content == "Current message"
    
    def test_read_file_content_encoding_fallback(self, hf_model, tmp_path):
        """測試文件編碼回退機制"""
        # 創建一個特殊編碼的文件
        test_file = tmp_path / "special_encoding.txt"
        test_content = "特殊編碼測試內容"
        test_file.write_text(test_content, encoding='big5')
        
        content = hf_model._read_file_content(str(test_file))
        assert content == test_content
    
    def test_read_file_content_pdf_missing_library(self, hf_model, tmp_path):
        """測試PDF文件處理當PyPDF2不可用時"""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf content")
        
        # Mock PyPDF2 import error
        with patch('builtins.__import__', side_effect=ImportError):
            content = hf_model._read_file_content(str(test_file))
            assert content is None
    
    def test_chunk_text_edge_cases(self, hf_model):
        """測試文本分塊的邊界情況"""
        # 空文本 - 根據實際實現，空文本會返回空列表
        chunks = hf_model._chunk_text("", chunk_size=100)
        assert len(chunks) == 0
        
        # 非常短的文本
        short_text = "Short"
        chunks = hf_model._chunk_text(short_text, chunk_size=100)
        assert len(chunks) == 1
        assert chunks[0]['text'] == short_text
        
        # 重疊超過塊大小的情況
        text = "This is a test text for chunking."
        chunks = hf_model._chunk_text(text, chunk_size=10, overlap=15)
        assert len(chunks) > 0
        # 確保沒有無限循環
        assert len(chunks) < 100
    
    def test_get_embedding_cache(self, hf_model):
        """測試嵌入向量緩存機制"""
        test_text = "test caching"
        expected_embedding = [0.1, 0.2, 0.3]
        
        with patch.object(hf_model, '_make_request', return_value=expected_embedding):
            # 第一次調用
            embedding1 = hf_model._get_embedding(test_text)
            assert embedding1 == expected_embedding
            
            # 第二次調用應該使用緩存
            embedding2 = hf_model._get_embedding(test_text)
            assert embedding2 == expected_embedding
            
            # _make_request 應該只被調用一次
            hf_model._make_request.assert_called_once()
    
    def test_make_request_timeout(self, hf_model):
        """測試API請求超時處理"""
        payload = {"inputs": "test"}
        
        with patch('src.models.huggingface_model.requests.post') as mock_post:
            mock_post.side_effect = requests.exceptions.Timeout()
            
            result = hf_model._make_request("test-model", payload)
            assert result is None
    
    def test_make_request_general_exception(self, hf_model):
        """測試API請求一般異常處理"""
        payload = {"inputs": "test"}
        
        with patch('src.models.huggingface_model.requests.post') as mock_post:
            mock_post.side_effect = Exception("General error")
            
            result = hf_model._make_request("test-model", payload)
            assert result is None
    
    def test_query_with_rag_no_embedding(self, hf_model):
        """測試RAG查詢當嵌入生成失敗時"""
        hf_model.knowledge_store = {'file1': {'filename': 'test.txt'}}
        
        with patch.object(hf_model, '_get_embedding', return_value=None):
            with patch.object(hf_model, '_fallback_chat_completion') as mock_fallback:
                mock_fallback.return_value = (True, RAGResponse(answer="Fallback", sources=[]), None)
                
                is_successful, rag_response, error = hf_model.query_with_rag("test query")
                
                assert is_successful == True
                mock_fallback.assert_called_once()
    
    def test_run_assistant_no_thread(self, hf_model):
        """測試助理運行當線程不存在時"""
        is_successful, rag_response, error = hf_model.run_assistant("nonexistent_thread")
        
        assert is_successful == False
        assert rag_response is None
        assert "not found" in error
    
    def test_run_assistant_no_user_message(self, hf_model):
        """測試助理運行當線程中沒有用戶訊息時"""
        thread_id = "test_thread"
        hf_model.local_threads[thread_id] = {"messages": [
            {"role": "assistant", "content": "Assistant message", "timestamp": time.time()}
        ]}
        
        is_successful, rag_response, error = hf_model.run_assistant(thread_id)
        
        assert is_successful == False
        assert rag_response is None
        assert "No user message" in error
    
    @patch('src.models.huggingface_model.requests.post')
    def test_generate_image_failure_response(self, mock_post, hf_model):
        """測試圖片生成失敗回應"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_post.return_value = mock_response
        
        is_successful, image_url, error = hf_model.generate_image("test prompt")
        
        assert is_successful == False
        assert image_url is None
        assert "Bad request" in error
    
    def test_transcribe_audio_file_not_found(self, hf_model):
        """測試音頻轉錄文件不存在"""
        is_successful, text, error = hf_model.transcribe_audio("/nonexistent/audio.wav")
        
        assert is_successful == False
        assert text is None
        assert "not found" in error.lower()


if __name__ == "__main__":
    pytest.main([__file__])