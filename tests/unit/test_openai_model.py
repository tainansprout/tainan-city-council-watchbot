"""
測試 OpenAI 模型的單元測試
"""
import pytest
import json
import time
from unittest.mock import Mock, patch, MagicMock, mock_open
from requests.exceptions import RequestException
from src.models.openai_model import OpenAIModel
from src.models.base import (
    ModelProvider, ChatMessage, ChatResponse, ThreadInfo, 
    FileInfo, RAGResponse
)


class TestOpenAIModelInitialization:
    """測試 OpenAIModel 初始化"""
    
    def test_openai_model_initialization_basic(self):
        """測試基本初始化"""
        model = OpenAIModel(
            api_key="test_api_key",
            assistant_id="test_assistant_id"
        )
        
        assert model.api_key == "test_api_key"
        assert model.assistant_id == "test_assistant_id"
        assert model.base_url == "https://api.openai.com/v1"
    
    def test_openai_model_initialization_with_custom_base_url(self):
        """測試使用自定義 base URL 初始化"""
        custom_url = "https://custom-api.example.com/v1"
        model = OpenAIModel(
            api_key="test_api_key",
            assistant_id="test_assistant_id",
            base_url=custom_url
        )
        
        assert model.base_url == custom_url
    
    def test_get_provider(self):
        """測試獲取模型提供商"""
        model = OpenAIModel("test_key", "test_assistant")
        assert model.get_provider() == ModelProvider.OPENAI


class TestConnectionCheck:
    """測試連線檢查"""
    
    @pytest.fixture
    def model(self):
        return OpenAIModel("test_key", "test_assistant")
    
    def test_check_connection_success(self, model):
        """測試成功的連線檢查"""
        mock_response = {"data": [{"id": "model-1", "object": "model"}]}
        
        with patch.object(model, '_request', return_value=(True, mock_response, None)):
            success, error = model.check_connection()
            
            assert success is True
            assert error is None
    
    def test_check_connection_failure(self, model):
        """測試失敗的連線檢查"""
        error_message = "API key invalid"
        
        with patch.object(model, '_request', return_value=(False, None, error_message)):
            success, error = model.check_connection()
            
            assert success is False
            assert error == error_message
    
    def test_check_connection_exception(self, model):
        """測試連線檢查異常"""
        with patch.object(model, '_request', side_effect=Exception("Network error")):
            success, error = model.check_connection()
            
            assert success is False
            assert "Network error" in error


class TestChatCompletion:
    """測試聊天完成功能"""
    
    @pytest.fixture
    def model(self):
        return OpenAIModel("test_key", "test_assistant")
    
    def test_chat_completion_success(self, model):
        """測試成功的聊天完成"""
        messages = [
            ChatMessage(role="user", content="Hello"),
            ChatMessage(role="assistant", content="Hi there!")
        ]
        
        mock_response = {
            "choices": [{
                "message": {"content": "Hello! How can I help you?"},
                "finish_reason": "stop"
            }],
            "usage": {"total_tokens": 50}
        }
        
        with patch.object(model, '_request', return_value=(True, mock_response, None)):
            success, chat_response, error = model.chat_completion(messages)
            
            assert success is True
            assert isinstance(chat_response, ChatResponse)
            assert chat_response.content == "Hello! How can I help you?"
            assert chat_response.finish_reason == "stop"
            assert chat_response.metadata['usage'] == {"total_tokens": 50}
            assert error is None
    
    def test_chat_completion_with_parameters(self, model):
        """測試帶參數的聊天完成"""
        messages = [ChatMessage(role="user", content="Test")]
        
        mock_response = {
            "choices": [{"message": {"content": "Response"}, "finish_reason": "stop"}]
        }
        
        with patch.object(model, '_request', return_value=(True, mock_response, None)) as mock_request:
            model.chat_completion(messages, model="gpt-4", temperature=0.7)
            
            call_args = mock_request.call_args
            json_body = call_args[1]['body']
            assert json_body['model'] == 'gpt-4'
            assert json_body['temperature'] == 0.7
    
    def test_chat_completion_failure(self, model):
        """測試聊天完成失敗"""
        messages = [ChatMessage(role="user", content="Hello")]
        error_message = "Rate limit exceeded"
        
        with patch.object(model, '_request', return_value=(False, None, error_message)):
            success, chat_response, error = model.chat_completion(messages)
            
            assert success is False
            assert chat_response is None
            assert error == error_message
    
    def test_chat_completion_exception(self, model):
        """測試聊天完成異常"""
        messages = [ChatMessage(role="user", content="Hello")]
        
        with patch.object(model, '_request', side_effect=Exception("API error")):
            success, chat_response, error = model.chat_completion(messages)
            
            assert success is False
            assert chat_response is None
            assert "API error" in error


class TestThreadManagement:
    """測試對話串管理"""
    
    @pytest.fixture
    def model(self):
        return OpenAIModel("test_key", "test_assistant")
    
    def test_create_thread_success(self, model):
        """測試成功創建對話串"""
        mock_response = {
            "id": "thread_12345",
            "object": "thread",
            "created_at": 1699000000
        }
        
        with patch.object(model, '_request', return_value=(True, mock_response, None)):
            success, thread_info, error = model.create_thread()
            
            assert success is True
            assert isinstance(thread_info, ThreadInfo)
            assert thread_info.thread_id == "thread_12345"
            assert thread_info.created_at == 1699000000
            assert error is None
    
    def test_create_thread_failure(self, model):
        """測試創建對話串失敗"""
        error_message = "Failed to create thread"
        
        with patch.object(model, '_request', return_value=(False, None, error_message)):
            success, thread_info, error = model.create_thread()
            
            assert success is False
            assert thread_info is None
            assert error == error_message
    
    def test_delete_thread_success(self, model):
        """測試成功刪除對話串"""
        thread_id = "thread_12345"
        
        with patch.object(model, '_request', return_value=(True, {"deleted": True}, None)):
            success, error = model.delete_thread(thread_id)
            
            assert success is True
            assert error is None
    
    def test_delete_thread_failure(self, model):
        """測試刪除對話串失敗"""
        thread_id = "thread_12345"
        error_message = "Thread not found"
        
        with patch.object(model, '_request', return_value=(False, None, error_message)):
            success, error = model.delete_thread(thread_id)
            
            assert success is False
            assert error == error_message
    
    def test_add_message_to_thread_success(self, model):
        """測試成功添加訊息到對話串"""
        thread_id = "thread_12345"
        message = ChatMessage(role="user", content="Hello")
        
        with patch.object(model, '_request', return_value=(True, {"id": "msg_123"}, None)):
            success, error = model.add_message_to_thread(thread_id, message)
            
            assert success is True
            assert error is None
    
    def test_add_message_to_thread_failure(self, model):
        """測試添加訊息到對話串失敗"""
        thread_id = "thread_12345"
        message = ChatMessage(role="user", content="Hello")
        error_message = "Thread not found"
        
        with patch.object(model, '_request', return_value=(False, None, error_message)):
            success, error = model.add_message_to_thread(thread_id, message)
            
            assert success is False
            assert error == error_message


class TestAssistantExecution:
    """測試助理執行"""
    
    @pytest.fixture
    def model(self):
        return OpenAIModel("test_key", "test_assistant_123")
    
    def test_run_assistant_success(self, model):
        """測試成功執行助理"""
        thread_id = "thread_12345"
        
        mock_run_response = {"id": "run_123", "status": "queued"}
        mock_final_response = {"status": "completed"}
        mock_messages_response = {
            "data": [{
                "role": "assistant",
                "content": [{"text": {"value": "Assistant response"}}]
            }]
        }
        
        with patch.object(model, '_request', return_value=(True, mock_run_response, None)), \
             patch.object(model, '_wait_for_run_completion', return_value=mock_final_response), \
             patch.object(model, '_get_thread_messages', return_value=(True, ChatResponse(content="Assistant response"), None)):
            
            success, chat_response, error = model.run_assistant(thread_id)
            
            assert success is True
            assert isinstance(chat_response, ChatResponse)
            assert chat_response.content == "Assistant response"
            assert error is None
    
    def test_run_assistant_run_creation_failure(self, model):
        """測試助理執行創建失敗"""
        thread_id = "thread_12345"
        error_message = "Failed to create run"
        
        with patch.object(model, '_request', return_value=(False, None, error_message)):
            success, chat_response, error = model.run_assistant(thread_id)
            
            assert success is False
            assert chat_response is None
            assert error == error_message
    
    def test_run_assistant_run_failed_status(self, model):
        """測試助理執行失敗狀態"""
        thread_id = "thread_12345"
        
        mock_run_response = {"id": "run_123", "status": "queued"}
        mock_final_response = {"status": "failed"}
        
        with patch.object(model, '_request', return_value=(True, mock_run_response, None)), \
             patch.object(model, '_wait_for_run_completion', return_value=mock_final_response):
            
            success, chat_response, error = model.run_assistant(thread_id)
            
            assert success is False
            assert chat_response is None
            assert "Assistant run failed with status: failed" in error


class TestFileOperations:
    """測試檔案操作"""
    
    @pytest.fixture
    def model(self):
        return OpenAIModel("test_key", "test_assistant")
    
    def test_upload_knowledge_file_success(self, model):
        """測試成功上傳知識檔案"""
        file_path = "/path/to/test.txt"
        mock_response = {
            "id": "file_123",
            "filename": "test.txt",
            "bytes": 1024,
            "status": "processed",
            "purpose": "assistants"
        }
        
        with patch('builtins.open', mock_open(read_data="test content")), \
             patch.object(model, '_request', return_value=(True, mock_response, None)):
            
            success, file_info, error = model.upload_knowledge_file(file_path)
            
            assert success is True
            assert isinstance(file_info, FileInfo)
            assert file_info.file_id == "file_123"
            assert file_info.filename == "test.txt"
            assert file_info.size == 1024
            assert error is None
    
    def test_upload_knowledge_file_failure(self, model):
        """測試上傳知識檔案失敗"""
        file_path = "/path/to/test.txt"
        error_message = "File upload failed"
        
        with patch('builtins.open', mock_open(read_data="test content")), \
             patch.object(model, '_request', return_value=(False, None, error_message)):
            
            success, file_info, error = model.upload_knowledge_file(file_path)
            
            assert success is False
            assert file_info is None
            assert error == error_message
    
    def test_list_files_success(self, model):
        """測試成功列出檔案"""
        mock_response = {
            "data": [
                {
                    "id": "file_1",
                    "filename": "doc1.txt",
                    "bytes": 1024,
                    "status": "processed",
                    "purpose": "assistants"
                },
                {
                    "id": "file_2", 
                    "filename": "doc2.txt",
                    "bytes": 2048,
                    "status": "processed",
                    "purpose": "assistants"
                }
            ]
        }
        
        with patch.object(model, '_request', return_value=(True, mock_response, None)):
            success, files, error = model.list_files()
            
            assert success is True
            assert len(files) == 2
            assert all(isinstance(f, FileInfo) for f in files)
            assert files[0].file_id == "file_1"
            assert files[1].filename == "doc2.txt"
            assert error is None
    
    def test_get_knowledge_files(self, model):
        """測試獲取知識檔案（別名方法）"""
        mock_files = [FileInfo(file_id="file_1", filename="test.txt")]
        
        with patch.object(model, 'list_files', return_value=(True, mock_files, None)):
            success, files, error = model.get_knowledge_files()
            
            assert success is True
            assert len(files) == 1
            assert files[0].file_id == "file_1"
    
    def test_get_file_references_success(self, model):
        """測試成功獲取檔案引用對應表"""
        mock_files = [
            FileInfo(file_id="file_1", filename="document1.txt"),
            FileInfo(file_id="file_2", filename="data.json")
        ]
        
        with patch.object(model, 'list_files', return_value=(True, mock_files, None)):
            references = model.get_file_references()
            
            assert references == {
                "file_1": "document1",
                "file_2": "data"
            }
    
    def test_get_file_references_failure(self, model):
        """測試獲取檔案引用失敗"""
        with patch.object(model, 'list_files', return_value=(False, None, "API error")), \
             patch('src.models.openai_model.logger') as mock_logger:
            
            references = model.get_file_references()
            
            assert references == {}
            mock_logger.warning.assert_called_once()
    
    def test_get_file_references_exception(self, model):
        """測試獲取檔案引用異常"""
        with patch.object(model, 'list_files', side_effect=Exception("Connection error")), \
             patch('src.models.openai_model.logger') as mock_logger:
            
            references = model.get_file_references()
            
            assert references == {}
            mock_logger.error.assert_called_once()


class TestRAGFunctionality:
    """測試 RAG 功能"""
    
    @pytest.fixture
    def model(self):
        return OpenAIModel("test_key", "test_assistant")
    
    def test_query_with_rag_with_existing_thread(self, model):
        """測試使用現有 thread 的 RAG 查詢"""
        query = "What is machine learning?"
        thread_id = "existing_thread_123"
        
        mock_chat_response = ChatResponse(
            content="Machine learning is...",
            metadata={'thread_messages': {'data': []}}
        )
        
        with patch.object(model, 'add_message_to_thread', return_value=(True, None)), \
             patch.object(model, 'run_assistant', return_value=(True, mock_chat_response, None)), \
             patch.object(model, '_process_openai_response', return_value=("Processed content", [])):
            
            success, rag_response, error = model.query_with_rag(query, thread_id)
            
            assert success is True
            assert isinstance(rag_response, RAGResponse)
            assert rag_response.answer == "Processed content"
            assert error is None
    
    def test_query_with_rag_create_new_thread(self, model):
        """測試創建新 thread 的 RAG 查詢"""
        query = "Explain AI"
        
        mock_thread_info = ThreadInfo(thread_id="new_thread_456")
        mock_chat_response = ChatResponse(
            content="AI explanation...",
            metadata={'thread_messages': {'data': []}}
        )
        
        with patch.object(model, 'create_thread', return_value=(True, mock_thread_info, None)), \
             patch.object(model, 'add_message_to_thread', return_value=(True, None)), \
             patch.object(model, 'run_assistant', return_value=(True, mock_chat_response, None)), \
             patch.object(model, '_process_openai_response', return_value=("AI explanation", [])):
            
            success, rag_response, error = model.query_with_rag(query)
            
            assert success is True
            assert rag_response.metadata['thread_id'] == "new_thread_456"
            assert error is None
    
    def test_query_with_rag_thread_creation_failure(self, model):
        """測試 RAG 查詢 thread 創建失敗"""
        query = "Test query"
        error_message = "Failed to create thread"
        
        with patch.object(model, 'create_thread', return_value=(False, None, error_message)):
            success, rag_response, error = model.query_with_rag(query)
            
            assert success is False
            assert rag_response is None
            assert "Failed to create thread" in error
    
    def test_query_with_rag_message_addition_failure(self, model):
        """測試 RAG 查詢訊息添加失敗"""
        query = "Test query"
        
        with patch.object(model, 'create_thread', return_value=(True, ThreadInfo(thread_id="thread_123"), None)), \
             patch.object(model, 'add_message_to_thread', return_value=(False, "Failed to add message")):
            
            success, rag_response, error = model.query_with_rag(query)
            
            assert success is False
            assert rag_response is None
            assert "Failed to add message to thread" in error


class TestAudioTranscription:
    """測試音訊轉錄"""
    
    @pytest.fixture
    def model(self):
        return OpenAIModel("test_key", "test_assistant")
    
    def test_transcribe_audio_success(self, model):
        """測試成功的音訊轉錄"""
        audio_path = "/path/to/audio.mp3"
        mock_response = {"text": "Hello, this is a test audio."}
        
        with patch('builtins.open', mock_open()), \
             patch.object(model, '_request', return_value=(True, mock_response, None)):
            
            success, text, error = model.transcribe_audio(audio_path)
            
            assert success is True
            assert text == "Hello, this is a test audio."
            assert error is None
    
    def test_transcribe_audio_with_model_parameter(self, model):
        """測試帶模型參數的音訊轉錄"""
        audio_path = "/path/to/audio.mp3"
        mock_response = {"text": "Transcribed text"}
        
        with patch('builtins.open', mock_open()), \
             patch.object(model, '_request', return_value=(True, mock_response, None)) as mock_request:
            
            model.transcribe_audio(audio_path, model="whisper-1")
            
            # 檢查是否正確傳遞了模型參數
            call_kwargs = mock_request.call_args[1]
            files = call_kwargs['files']
            assert files['model'][1] == "whisper-1"
    
    def test_transcribe_audio_failure(self, model):
        """測試音訊轉錄失敗"""
        audio_path = "/path/to/audio.mp3"
        error_message = "Audio format not supported"
        
        with patch('builtins.open', mock_open()), \
             patch.object(model, '_request', return_value=(False, None, error_message)):
            
            success, text, error = model.transcribe_audio(audio_path)
            
            assert success is False
            assert text is None
            assert error == error_message
    
    def test_transcribe_audio_exception(self, model):
        """測試音訊轉錄異常"""
        audio_path = "/path/to/audio.mp3"
        
        with patch('builtins.open', side_effect=Exception("File not found")):
            success, text, error = model.transcribe_audio(audio_path)
            
            assert success is False
            assert text is None
            assert "File not found" in error


class TestImageGeneration:
    """測試圖片生成"""
    
    @pytest.fixture
    def model(self):
        return OpenAIModel("test_key", "test_assistant")
    
    def test_generate_image_success(self, model):
        """測試成功生成圖片"""
        prompt = "A beautiful sunset over mountains"
        mock_response = {
            "data": [{"url": "https://example.com/generated_image.png"}]
        }
        
        with patch.object(model, '_request', return_value=(True, mock_response, None)):
            success, image_url, error = model.generate_image(prompt)
            
            assert success is True
            assert image_url == "https://example.com/generated_image.png"
            assert error is None
    
    def test_generate_image_with_parameters(self, model):
        """測試帶參數的圖片生成"""
        prompt = "Test image"
        
        mock_response = {
            "data": [{"url": "https://example.com/test.png"}]
        }
        
        with patch.object(model, '_request', return_value=(True, mock_response, None)) as mock_request:
            model.generate_image(prompt, n=2, size="1024x1024")
            
            call_args = mock_request.call_args
            json_body = call_args[1]['body']
            assert json_body['n'] == 2
            assert json_body['size'] == "1024x1024"
    
    def test_generate_image_failure(self, model):
        """測試圖片生成失敗"""
        prompt = "Test image"
        error_message = "Image generation failed"
        
        with patch.object(model, '_request', return_value=(False, None, error_message)):
            success, image_url, error = model.generate_image(prompt)
            
            assert success is False
            assert image_url is None
            assert error == error_message


class TestResponseProcessing:
    """測試回應處理"""
    
    @pytest.fixture
    def model(self):
        return OpenAIModel("test_key", "test_assistant")
    
    def test_process_openai_response_with_citations(self, model):
        """測試處理帶引用的 OpenAI 回應"""
        thread_messages = {
            "data": [{
                "role": "assistant",
                "content": [{
                    "type": "text",
                    "text": {
                        "value": "根據文件【0†source】，這是答案。",
                        "annotations": [{
                            "text": "【0†source】",
                            "file_citation": {
                                "file_id": "file_123",
                                "quote": "relevant quote"
                            }
                        }]
                    }
                }]
            }]
        }
        
        with patch.object(model, 'get_file_references', return_value={"file_123": "document1"}), \
             patch('src.models.openai_model.s2t_converter') as mock_converter:
            
            mock_converter.convert.side_effect = lambda x: x  # 模擬轉換
            
            content, sources = model._process_openai_response(thread_messages)
            
            assert "[1]" in content
            assert len(sources) == 1
            assert sources[0]['file_id'] == "file_123"
            assert sources[0]['filename'] == "document1"
    
    def test_process_openai_response_no_data(self, model):
        """測試處理無數據的回應"""
        empty_messages = {"data": []}
        
        with patch.object(model, '_get_response_data', return_value=None):
            content, sources = model._process_openai_response(empty_messages)
            
            assert content == ""
            assert sources == []
    
    def test_process_openai_response_multiple_citations(self, model):
        """測試處理多個引用的回應"""
        thread_messages = {
            "data": [{
                "role": "assistant",
                "content": [{
                    "type": "text",
                    "text": {
                        "value": "根據【0†source】和【1†source】的資料",
                        "annotations": [
                            {
                                "text": "【0†source】",
                                "file_citation": {"file_id": "file_1", "quote": "quote1"}
                            },
                            {
                                "text": "【1†source】", 
                                "file_citation": {"file_id": "file_2", "quote": "quote2"}
                            }
                        ]
                    }
                }]
            }]
        }
        
        with patch.object(model, 'get_file_references', return_value={"file_1": "doc1", "file_2": "doc2"}), \
             patch('src.models.openai_model.s2t_converter') as mock_converter:
            
            mock_converter.convert.side_effect = lambda x: x
            content, sources = model._process_openai_response(thread_messages)
            
            assert "[1]" in content and "[2]" in content
            assert len(sources) == 2
    
    def test_process_openai_response_error_handling(self, model):
        """測試回應處理錯誤處理"""
        malformed_data = {"invalid": "format"}
        
        with patch('src.models.openai_model.logger') as mock_logger:
            content, sources = model._process_openai_response(malformed_data)
            
            assert content == ""
            assert sources == []
            mock_logger.error.assert_called_once()
    
    def test_get_response_data_success(self, model):
        """測試提取回應數據成功"""
        response = {
            "data": [
                {"role": "user", "content": [{"type": "text", "text": {"value": "Question"}}]},
                {"role": "assistant", "content": [{"type": "text", "text": {"value": "Answer"}}]}
            ]
        }
        
        data = model._get_response_data(response)
        
        assert data is not None
        assert data["role"] == "assistant"
        assert data["content"][0]["text"]["value"] == "Answer"
    
    def test_get_response_data_no_assistant(self, model):
        """測試無助理回應的數據提取"""
        response = {
            "data": [{
                "role": "user",
                "content": [{"type": "text", "text": {"value": "Question"}}]
            }]
        }
        
        data = model._get_response_data(response)
        assert data is None
    
    def test_get_response_data_exception(self, model):
        """測試數據提取異常"""
        malformed_response = {"invalid": "format"}
        
        with patch('src.models.openai_model.logger') as mock_logger:
            data = model._get_response_data(malformed_response)
            
            assert data is None
            mock_logger.error.assert_called_once()
    
    def test_extract_sources_duplicate_files(self, model):
        """測試提取來源時避免重複檔案"""
        thread_messages = {
            "data": [{
                "role": "assistant",
                "content": [{
                    "type": "text",
                    "text": {
                        "annotations": [
                            {
                                "type": "file_citation",
                                "file_citation": {"file_id": "file_123", "quote": "quote1"}
                            },
                            {
                                "type": "file_citation", 
                                "file_citation": {"file_id": "file_123", "quote": "quote2"}
                            }
                        ]
                    }
                }]
            }]
        }
        
        sources = model._extract_sources_from_response(thread_messages)
        
        # 應該只有一個來源（去重）
        assert len(sources) == 1
        assert sources[0]['file_id'] == "file_123"


class TestBackwardCompatibility:
    """測試向後相容方法"""
    
    @pytest.fixture
    def model(self):
        return OpenAIModel("test_key", "test_assistant")
    
    def test_check_token_valid(self, model):
        """測試 check_token_valid 向後相容方法"""
        with patch.object(model, 'check_connection', return_value=(True, None)):
            success, _, error = model.check_token_valid()
            
            assert success is True
            assert error is None
    
    def test_retrieve_thread(self, model):
        """測試 retrieve_thread 向後相容方法"""
        thread_id = "thread_123"
        
        with patch.object(model, '_request', return_value=(True, {"id": thread_id}, None)):
            success, response, error = model.retrieve_thread(thread_id)
            
            assert success is True
            assert response["id"] == thread_id
    
    def test_create_thread_message(self, model):
        """測試 create_thread_message 向後相容方法"""
        thread_id = "thread_123"
        content = "Test message"
        
        with patch.object(model, 'add_message_to_thread', return_value=(True, None)):
            success, _, error = model.create_thread_message(thread_id, content)
            
            assert success is True
            assert error is None
    
    def test_create_thread_run(self, model):
        """測試 create_thread_run 向後相容方法"""
        thread_id = "thread_123"
        
        with patch.object(model, '_request', return_value=(True, {"id": "run_123"}, None)):
            success, response, error = model.create_thread_run(thread_id)
            
            assert success is True
            assert response["id"] == "run_123"
    
    def test_retrieve_thread_run(self, model):
        """測試 retrieve_thread_run 向後相容方法"""
        thread_id = "thread_123"
        run_id = "run_456"
        
        with patch.object(model, '_request', return_value=(True, {"status": "completed"}, None)):
            success, response, error = model.retrieve_thread_run(thread_id, run_id)
            
            assert success is True
            assert response["status"] == "completed"
    
    def test_list_thread_messages(self, model):
        """測試 list_thread_messages 向後相容方法"""
        thread_id = "thread_123"
        
        with patch.object(model, '_request', return_value=(True, {"data": []}, None)):
            success, response, error = model.list_thread_messages(thread_id)
            
            assert success is True
            assert "data" in response
    
    def test_audio_transcriptions(self, model):
        """測試 audio_transcriptions 向後相容方法"""
        file_path = "/path/to/audio.mp3"
        model_name = "whisper-1"
        
        with patch.object(model, 'transcribe_audio', return_value=(True, "transcribed text", None)):
            result = model.audio_transcriptions(file_path, model_name)
            
            assert result == (True, "transcribed text", None)


class TestInternalMethods:
    """測試內部方法"""
    
    @pytest.fixture
    def model(self):
        return OpenAIModel("test_key", "test_assistant")
    
    def test_request_get_method(self, model):
        """測試 GET 請求"""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": "test"}
            mock_get.return_value = mock_response
            
            success, data, error = model._request('GET', '/test', assistant=True)
            
            assert success is True
            assert data == {"data": "test"}
            assert error is None
            
            # 檢查請求頭
            call_args = mock_get.call_args
            headers = call_args[1]['headers']
            assert 'Authorization' in headers
            assert 'OpenAI-Beta' in headers
    
    def test_request_post_method(self, model):
        """測試 POST 請求"""
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"success": True}
            mock_post.return_value = mock_response
            
            body = {"message": "test"}
            success, data, error = model._request('POST', '/test', body=body)
            
            assert success is True
            assert data == {"success": True}
    
    def test_request_delete_method(self, model):
        """測試 DELETE 請求"""
        with patch('requests.delete') as mock_delete:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"deleted": True}
            mock_delete.return_value = mock_response
            
            success, data, error = model._request('DELETE', '/test', assistant=True)
            
            assert success is True
            assert data == {"deleted": True}
    
    def test_request_rate_limit_error(self, model):
        """測試速率限制錯誤"""
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 429
            mock_post.return_value = mock_response
            
            with pytest.raises(RequestException):
                model._request('POST', '/test')
    
    def test_request_server_error(self, model):
        """測試服務器錯誤"""
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_post.return_value = mock_response
            
            with pytest.raises(RequestException):
                model._request('POST', '/test')
    
    def test_request_client_error(self, model):
        """測試客戶端錯誤"""
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.json.return_value = {
                "error": {"message": "Bad request"}
            }
            mock_post.return_value = mock_response
            
            success, data, error = model._request('POST', '/test')
            
            assert success is False
            assert data is None
            assert error == "Bad request"
    
    def test_request_client_error_no_json(self, model):
        """測試客戶端錯誤無 JSON 格式"""
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.json.side_effect = ValueError("Invalid JSON")
            mock_response.text = "Bad Request Error"
            mock_post.return_value = mock_response
            
            success, data, error = model._request('POST', '/test')
            
            assert success is False
            assert "HTTP 400" in error
    
    def test_request_network_exception(self, model):
        """測試網路異常"""
        with patch('requests.post', side_effect=RequestException("Network error")):
            with pytest.raises(RequestException):
                model._request('POST', '/test')
    
    def test_request_general_exception(self, model):
        """測試一般異常"""
        with patch('requests.post', side_effect=Exception("General error")):
            success, data, error = model._request('POST', '/test')
            
            assert success is False
            assert data is None
            assert "OpenAI API 系統不穩定" in error
    
    def test_wait_for_run_completion_success(self, model):
        """測試等待執行完成 - 成功"""
        thread_id = "thread_123"
        run_id = "run_456"
        
        with patch.object(model, 'retrieve_thread_run') as mock_retrieve:
            # 模擬狀態變化：queued -> in_progress -> completed
            mock_retrieve.side_effect = [
                (True, {"status": "queued"}, None),
                (True, {"status": "in_progress"}, None),
                (True, {"status": "completed"}, None)
            ]
            
            with patch('time.sleep'):  # 避免實際等待
                result = model._wait_for_run_completion(thread_id, run_id, max_wait_time=120)
                
                assert result["status"] == "completed"
    
    def test_wait_for_run_completion_timeout(self, model):
        """測試等待執行完成 - 超時"""
        thread_id = "thread_123"
        run_id = "run_456"
        
        with patch.object(model, 'retrieve_thread_run', return_value=(True, {"status": "in_progress"}, None)), \
             patch('time.time', side_effect=[0, 130]):  # 模擬超時
            
            with pytest.raises(Exception, match="Request timeout"):
                model._wait_for_run_completion(thread_id, run_id, max_wait_time=120)
    
    def test_wait_for_run_completion_api_failure(self, model):
        """測試等待執行完成 - API 失敗"""
        thread_id = "thread_123"
        run_id = "run_456"
        
        with patch.object(model, 'retrieve_thread_run', return_value=(False, None, "API error")):
            with pytest.raises(Exception, match="API error"):
                model._wait_for_run_completion(thread_id, run_id)
    
    def test_wait_for_run_completion_queued_status(self, model):
        """測試等待執行完成 - 排隊狀態更長等待"""
        thread_id = "thread_123"
        run_id = "run_456"
        
        with patch.object(model, 'retrieve_thread_run') as mock_retrieve, \
             patch('time.sleep') as mock_sleep:
            
            mock_retrieve.side_effect = [
                (True, {"status": "queued"}, None),
                (True, {"status": "completed"}, None)
            ]
            
            result = model._wait_for_run_completion(thread_id, run_id)
            
            assert result["status"] == "completed"
            # 檢查排隊狀態時使用更長的等待時間
            assert mock_sleep.call_args_list[0][0][0] == 10
    
    def test_get_thread_messages_success(self, model):
        """測試獲取對話串訊息 - 成功"""
        thread_id = "thread_123"
        
        mock_response = {
            "data": [{
                "role": "assistant",
                "content": [{"text": {"value": "Assistant response"}}]
            }]
        }
        
        with patch.object(model, 'list_thread_messages', return_value=(True, mock_response, None)):
            success, chat_response, error = model._get_thread_messages(thread_id)
            
            assert success is True
            assert isinstance(chat_response, ChatResponse)
            assert chat_response.content == "Assistant response"
    
    def test_get_thread_messages_no_assistant_response(self, model):
        """測試獲取對話串訊息 - 無助理回應"""
        thread_id = "thread_123"
        
        mock_response = {
            "data": [{
                "role": "user",
                "content": [{"text": {"value": "User message"}}]
            }]
        }
        
        with patch.object(model, 'list_thread_messages', return_value=(True, mock_response, None)):
            success, chat_response, error = model._get_thread_messages(thread_id)
            
            assert success is False
            assert chat_response is None
            assert error == "No assistant response found"
    
    def test_get_thread_messages_api_failure(self, model):
        """測試獲取對話串訊息 - API 失敗"""
        thread_id = "thread_123"
        
        with patch.object(model, 'list_thread_messages', return_value=(False, None, "API error")):
            success, chat_response, error = model._get_thread_messages(thread_id)
            
            assert success is False
            assert chat_response is None
            assert error == "API error"


class TestUserLevelConversationManagement:
    """測試用戶級對話管理"""
    
    @pytest.fixture
    def model(self):
        return OpenAIModel("test_key", "test_assistant")
    
    def test_chat_with_user_existing_thread(self, model):
        """測試使用現有 thread 的用戶對話"""
        user_id = "user_123"
        message = "Hello, how are you?"
        platform = "line"
        existing_thread_id = "thread_456"
        
        mock_chat_response = ChatResponse(
            content="I'm doing well, thank you!",
            metadata={'thread_messages': {'data': []}}
        )
        
        with patch('src.models.openai_model.get_thread_id_by_user_id', return_value=existing_thread_id), \
             patch.object(model, 'add_message_to_thread', return_value=(True, None)), \
             patch.object(model, 'run_assistant', return_value=(True, mock_chat_response, None)), \
             patch.object(model, '_process_openai_response', return_value=("I'm doing well!", [])):
            
            success, rag_response, error = model.chat_with_user(user_id, message, platform)
            
            assert success is True
            assert isinstance(rag_response, RAGResponse)
            assert rag_response.answer == "I'm doing well!"
            assert rag_response.metadata['user_id'] == user_id
            assert rag_response.metadata['thread_id'] == existing_thread_id
            assert error is None
    
    def test_chat_with_user_create_new_thread(self, model):
        """測試創建新 thread 的用戶對話"""
        user_id = "new_user_789"
        message = "First message"
        platform = "discord"
        
        mock_thread_info = ThreadInfo(thread_id="new_thread_abc")
        mock_chat_response = ChatResponse(
            content="Welcome!",
            metadata={'thread_messages': {'data': []}}
        )
        
        with patch('src.models.openai_model.get_thread_id_by_user_id', return_value=None), \
             patch.object(model, 'create_thread', return_value=(True, mock_thread_info, None)), \
             patch('src.models.openai_model.save_thread_id') as mock_save, \
             patch.object(model, 'add_message_to_thread', return_value=(True, None)), \
             patch.object(model, 'run_assistant', return_value=(True, mock_chat_response, None)), \
             patch.object(model, '_process_openai_response', return_value=("Welcome!", [])):
            
            success, rag_response, error = model.chat_with_user(user_id, message, platform)
            
            assert success is True
            assert rag_response.metadata['thread_id'] == "new_thread_abc"
            mock_save.assert_called_once_with(user_id, "new_thread_abc", platform)
    
    def test_chat_with_user_thread_creation_failure(self, model):
        """測試用戶對話 thread 創建失敗"""
        user_id = "user_123"
        message = "Test message"
        
        with patch('src.models.openai_model.get_thread_id_by_user_id', return_value=None), \
             patch.object(model, 'create_thread', return_value=(False, None, "Thread creation failed")):
            
            success, rag_response, error = model.chat_with_user(user_id, message)
            
            assert success is False
            assert rag_response is None
            assert "Failed to create thread" in error
    
    def test_chat_with_user_exception(self, model):
        """測試用戶對話異常"""
        user_id = "user_123"
        message = "Test message"
        
        with patch('src.models.openai_model.get_thread_id_by_user_id', side_effect=Exception("Database error")), \
             patch('src.models.openai_model.logger') as mock_logger:
            
            success, rag_response, error = model.chat_with_user(user_id, message)
            
            assert success is False
            assert rag_response is None
            assert "Database error" in error
            mock_logger.error.assert_called_once()
    
    def test_clear_user_history_success(self, model):
        """測試成功清除用戶歷史"""
        user_id = "user_123"
        platform = "line"
        thread_id = "thread_456"
        
        with patch('src.models.openai_model.get_thread_id_by_user_id', return_value=thread_id), \
             patch.object(model, 'delete_thread', return_value=(True, None)), \
             patch('src.models.openai_model.delete_thread_id') as mock_delete:
            
            success, error = model.clear_user_history(user_id, platform)
            
            assert success is True
            assert error is None
            mock_delete.assert_called_once_with(user_id, platform)
    
    def test_clear_user_history_no_thread(self, model):
        """測試清除不存在的用戶歷史"""
        user_id = "user_123"
        platform = "line"
        
        with patch('src.models.openai_model.get_thread_id_by_user_id', return_value=None), \
             patch('src.models.openai_model.logger') as mock_logger:
            
            success, error = model.clear_user_history(user_id, platform)
            
            assert success is True
            assert error is None
            mock_logger.info.assert_called_once()
    
    def test_clear_user_history_delete_thread_failure(self, model):
        """測試刪除 thread 失敗但仍清除本地記錄"""
        user_id = "user_123"
        platform = "line"
        thread_id = "thread_456"
        
        with patch('src.models.openai_model.get_thread_id_by_user_id', return_value=thread_id), \
             patch.object(model, 'delete_thread', return_value=(False, "API error")), \
             patch('src.models.openai_model.delete_thread_id') as mock_delete, \
             patch('src.models.openai_model.logger') as mock_logger:
            
            success, error = model.clear_user_history(user_id, platform)
            
            assert success is True
            assert error is None
            mock_delete.assert_called_once_with(user_id, platform)
            mock_logger.error.assert_called_once()
    
    def test_clear_user_history_exception(self, model):
        """測試清除用戶歷史異常"""
        user_id = "user_123"
        platform = "line"
        
        with patch('src.models.openai_model.get_thread_id_by_user_id', side_effect=Exception("Database error")), \
             patch('src.models.openai_model.logger') as mock_logger:
            
            success, error = model.clear_user_history(user_id, platform)
            
            assert success is False
            assert "Database error" in error
            mock_logger.error.assert_called_once()


class TestEdgeCases:
    """測試邊界情況和錯誤處理"""
    
    @pytest.fixture
    def model(self):
        return OpenAIModel("test_key", "test_assistant")
    
    def test_empty_api_key(self):
        """測試空 API key"""
        model = OpenAIModel("", "test_assistant")
        assert model.api_key == ""
    
    def test_empty_assistant_id(self):
        """測試空 assistant ID"""
        model = OpenAIModel("test_key", "")
        assert model.assistant_id == ""
    
    def test_none_parameters(self):
        """測試 None 參數"""
        model = OpenAIModel("test_key", None)
        assert model.assistant_id is None
    
    def test_empty_message_content(self, model):
        """測試空訊息內容"""
        messages = [ChatMessage(role="user", content="")]
        
        mock_response = {
            "choices": [{"message": {"content": "Please provide a message"}, "finish_reason": "stop"}]
        }
        
        with patch.object(model, '_request', return_value=(True, mock_response, None)):
            success, chat_response, error = model.chat_completion(messages)
            
            assert success is True
            assert chat_response.content == "Please provide a message"
    
    def test_very_long_message(self, model):
        """測試非常長的訊息"""
        long_message = "A" * 10000
        messages = [ChatMessage(role="user", content=long_message)]
        
        mock_response = {
            "choices": [{"message": {"content": "Response to long message"}, "finish_reason": "stop"}]
        }
        
        with patch.object(model, '_request', return_value=(True, mock_response, None)):
            success, chat_response, error = model.chat_completion(messages)
            
            assert success is True
    
    def test_special_characters_in_message(self, model):
        """測試特殊字符訊息"""
        special_message = "Hello! 你好 🎵 @#$%^&*()_+"
        messages = [ChatMessage(role="user", content=special_message)]
        
        mock_response = {
            "choices": [{"message": {"content": "Response with special chars"}, "finish_reason": "stop"}]
        }
        
        with patch.object(model, '_request', return_value=(True, mock_response, None)):
            success, chat_response, error = model.chat_completion(messages)
            
            assert success is True
    
    def test_network_timeout_handling(self, model):
        """測試網路超時處理"""
        with patch.object(model, '_request', side_effect=RequestException("Timeout")):
            success, error = model.check_connection()
            
            assert success is False
            assert "Timeout" in error
    
    def test_malformed_response_handling(self, model):
        """測試格式錯誤的回應處理"""
        # 模擬無效的 JSON 回應
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.side_effect = ValueError("Invalid JSON")
            mock_get.return_value = mock_response
            
            success, data, error = model._request('GET', '/test')
            
            assert success is False
            assert "OpenAI API 系統不穩定" in error
    
    def test_empty_response_content(self, model):
        """測試空回應內容"""
        mock_response = {
            "choices": [{"message": {"content": ""}, "finish_reason": "stop"}]
        }
        
        with patch.object(model, '_request', return_value=(True, mock_response, None)):
            success, chat_response, error = model.chat_completion([ChatMessage(role="user", content="test")])
            
            assert success is True
            assert chat_response.content == ""
    
    def test_missing_choices_in_response(self, model):
        """測試回應中缺少 choices"""
        mock_response = {"usage": {"total_tokens": 10}}
        
        with patch.object(model, '_request', return_value=(True, mock_response, None)):
            with pytest.raises((KeyError, IndexError)):
                model.chat_completion([ChatMessage(role="user", content="test")])
    
    def test_file_not_found_error(self, model):
        """測試檔案不存在錯誤"""
        with patch('builtins.open', side_effect=FileNotFoundError("File not found")):
            success, file_info, error = model.upload_knowledge_file("/nonexistent/file.txt")
            
            assert success is False
            assert file_info is None
            assert "File not found" in error


if __name__ == "__main__":
    pytest.main([__file__])