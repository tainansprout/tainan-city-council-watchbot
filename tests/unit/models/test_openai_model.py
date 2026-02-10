"""
測試 OpenAI 模型的單元測試
針對 Responses API + Conversations API 架構
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock, mock_open
from requests.exceptions import RequestException
from src.models.openai_model import OpenAIModel
from src.models.base import (
    ModelProvider, ChatMessage, ChatResponse, ThreadInfo,
    FileInfo, RAGResponse
)


# === Mock 工廠 ===

def make_mock_response(output_text="Test response", annotations=None, response_id="resp_123"):
    """建立 Responses API 的 mock 回應物件"""
    mock_content = Mock()
    mock_content.type = "output_text"
    mock_content.text = output_text
    mock_content.annotations = annotations or []

    mock_message = Mock()
    mock_message.type = "message"
    mock_message.content = [mock_content]

    mock_response = Mock()
    mock_response.id = response_id
    mock_response.output = [mock_message]
    mock_response.output_text = output_text
    mock_response.status = "completed"
    mock_response.usage = Mock()
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 50

    return mock_response


def make_mock_annotation(filename="test.pdf", file_id="file_123", index=10):
    """建立 mock file_citation annotation"""
    ann = Mock()
    ann.type = "file_citation"
    ann.filename = filename
    ann.file_id = file_id
    ann.index = index
    return ann


class TestOpenAIModelInitialization:
    """測試 OpenAIModel 初始化"""

    def test_openai_model_initialization_basic(self):
        """測試基本初始化"""
        with patch('src.core.config.get_value', return_value=False):
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
        with patch('src.core.config.get_value', return_value=False):
            model = OpenAIModel(
                api_key="test_api_key",
                assistant_id="test_assistant_id",
                base_url=custom_url
            )

        assert model.base_url == custom_url

    def test_get_provider(self):
        """測試獲取模型提供商"""
        with patch('src.core.config.get_value', return_value=False):
            model = OpenAIModel("test_key", "test_assistant")
        assert model.get_provider() == ModelProvider.OPENAI

    def test_load_model_params_from_config(self):
        """測試從設定檔載入模型參數"""
        def mock_get_value(key, default=None):
            config_values = {
                'openai.model': 'gpt-5',
                'openai.max_output_tokens': 8000,
                'openai.reasoning_effort': 'medium',
                'openai.temperature': 0.1,
                'openai.vector_store_id': 'vs_test123',
                'features.enable_mcp': False,
                'mcp.enabled': False,
            }
            return config_values.get(key, default)

        with patch('src.core.config.get_value', side_effect=mock_get_value):
            model = OpenAIModel("test_key", "test_assistant")

        assert model.model == 'gpt-5'
        assert model.max_output_tokens == 8000
        assert model.reasoning_effort == 'medium'
        assert model.temperature == 0.1
        assert model.vector_store_id == 'vs_test123'

    def test_load_model_params_exception_fallback(self):
        """測試設定檔載入失敗時的預設值"""
        with patch('src.core.config.get_value', side_effect=Exception("Config error")):
            model = OpenAIModel("test_key", "test_assistant")

        assert model.model == 'gpt-5'
        assert model.max_output_tokens == 8000
        assert model.reasoning_effort is None
        assert model.temperature == 0.1
        assert model.vector_store_id is None

    def test_get_model_params_with_reasoning(self):
        """測試有 reasoning_effort 時的模型參數"""
        with patch('src.core.config.get_value', return_value=False):
            model = OpenAIModel("test_key")
        model.model = 'gpt-5'
        model.max_output_tokens = 8000
        model.reasoning_effort = 'medium'
        model.temperature = 0.1

        params = model._get_model_params()

        assert params['model'] == 'gpt-5'
        assert params['max_output_tokens'] == 8000
        assert params['reasoning'] == {'effort': 'medium'}
        assert 'temperature' not in params

    def test_get_model_params_without_reasoning(self):
        """測試沒有 reasoning_effort 時的模型參數"""
        with patch('src.core.config.get_value', return_value=False):
            model = OpenAIModel("test_key")
        model.model = 'gpt-4o'
        model.max_output_tokens = 4000
        model.reasoning_effort = None
        model.temperature = 0.7

        params = model._get_model_params()

        assert params['model'] == 'gpt-4o'
        assert params['max_output_tokens'] == 4000
        assert params['temperature'] == 0.7
        assert 'reasoning' not in params


class TestConnectionCheck:
    """測試連線檢查"""

    @pytest.fixture
    def model(self):
        with patch('src.core.config.get_value', return_value=False):
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
        with patch('src.core.config.get_value', return_value=False):
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

    def test_chat_completion_empty_choices(self, model):
        """測試聊天完成 - 空 choices"""
        with patch.object(model, '_request', return_value=(True, {"choices": []}, None)):
            success, response, error = model.chat_completion([ChatMessage(role="user", content="Hi")])

            assert success is False
            assert response is None
            assert "list index out of range" in error

    def test_chat_completion_missing_choices(self, model):
        """測試聊天完成 - 缺少 choices"""
        with patch.object(model, '_request', return_value=(True, {"usage": {"total_tokens": 10}}, None)):
            success, response, error = model.chat_completion([ChatMessage(role="user", content="Hi")])

            assert success is False
            assert response is None
            assert "'choices'" in error


class TestThreadManagement:
    """測試對話管理（Conversations API）"""

    @pytest.fixture
    def model(self):
        with patch('src.core.config.get_value', return_value=False):
            return OpenAIModel("test_key", "test_assistant")

    def test_create_thread_success(self, model):
        """測試成功創建 Conversation"""
        mock_conversation = Mock()
        mock_conversation.id = "conv_12345"
        mock_conversation.created_at = 1699000000
        mock_conversation.object = "conversation"

        model.client.conversations.create = Mock(return_value=mock_conversation)

        success, thread_info, error = model.create_thread()

        assert success is True
        assert isinstance(thread_info, ThreadInfo)
        assert thread_info.thread_id == "conv_12345"
        assert thread_info.created_at == 1699000000
        assert error is None

    def test_create_thread_failure(self, model):
        """測試創建 Conversation 失敗"""
        model.client.conversations.create = Mock(side_effect=Exception("Failed to create conversation"))

        success, thread_info, error = model.create_thread()

        assert success is False
        assert thread_info is None
        assert "Failed to create conversation" in error

    def test_delete_thread_success(self, model):
        """測試成功刪除 Conversation"""
        model.client.conversations.delete = Mock(return_value=None)

        success, error = model.delete_thread("conv_12345")

        assert success is True
        assert error is None
        model.client.conversations.delete.assert_called_once_with("conv_12345")

    def test_delete_thread_failure(self, model):
        """測試刪除 Conversation 失敗"""
        model.client.conversations.delete = Mock(side_effect=Exception("Conversation not found"))

        success, error = model.delete_thread("conv_12345")

        assert success is False
        assert "Conversation not found" in error

    def test_add_message_to_thread_noop(self, model):
        """測試 add_message_to_thread 是 no-op（Responses API 不需要單獨添加訊息）"""
        message = ChatMessage(role="user", content="Hello")

        success, error = model.add_message_to_thread("conv_12345", message)

        assert success is True
        assert error is None


class TestAssistantExecution:
    """測試 Responses API 執行（run_assistant）"""

    @pytest.fixture
    def model(self):
        with patch('src.core.config.get_value', return_value=False):
            return OpenAIModel("test_key", "test_assistant_123")

    def test_run_assistant_success(self, model):
        """測試成功執行 Responses API"""
        mock_response = make_mock_response(output_text="Assistant response")

        with patch.object(model, '_create_response', return_value=mock_response), \
             patch.object(model, '_process_openai_response', return_value=("Assistant response", [])):

            success, chat_response, error = model.run_assistant("conv_12345", user_input="Hello")

            assert success is True
            assert isinstance(chat_response, ChatResponse)
            assert chat_response.content == "Assistant response"
            assert error is None

    def test_run_assistant_missing_user_input(self, model):
        """測試缺少 user_input"""
        success, chat_response, error = model.run_assistant("conv_12345")

        assert success is False
        assert chat_response is None
        assert "user_input is required" in error

    def test_run_assistant_api_failure(self, model):
        """測試 Responses API 呼叫失敗"""
        with patch.object(model, '_create_response', side_effect=Exception("API error")):
            success, chat_response, error = model.run_assistant("conv_12345", user_input="Hello")

            assert success is False
            assert chat_response is None
            assert "API error" in error

    def test_run_assistant_with_sources(self, model):
        """測試帶引用來源的回應"""
        mock_response = make_mock_response(output_text="Response with citations")
        sources = [{"file_id": "file_123", "filename": "doc.pdf", "quote": "", "type": "file_citation"}]

        with patch.object(model, '_create_response', return_value=mock_response), \
             patch.object(model, '_process_openai_response', return_value=("Response [1]", sources)):

            success, chat_response, error = model.run_assistant("conv_12345", user_input="Query")

            assert success is True
            assert chat_response.metadata['sources'] == sources
            assert chat_response.metadata['response_id'] == "resp_123"


class TestResponseProcessing:
    """測試 Responses API 回應處理"""

    @pytest.fixture
    def model(self):
        with patch('src.core.config.get_value', return_value=False):
            return OpenAIModel("test_key", "test_assistant")

    def test_process_response_with_citations(self, model):
        """測試處理帶引用的回應"""
        annotations = [
            make_mock_annotation(filename="document1.pdf", file_id="file_123", index=10),
        ]
        mock_response = make_mock_response(
            output_text="根據文件的資料，這是答案。",
            annotations=annotations
        )

        with patch('src.models.openai_model.s2t_converter') as mock_converter, \
             patch('src.models.openai_model.dedup_citation_blocks', side_effect=lambda x: x):
            mock_converter.convert.side_effect = lambda x: x

            content, sources = model._process_openai_response(mock_response)

            assert "[1]" in content
            assert len(sources) == 1
            assert sources[0]['file_id'] == "file_123"
            assert sources[0]['filename'] == "document1.pdf"

    def test_process_response_no_annotations(self, model):
        """測試處理無引用的回應"""
        mock_response = make_mock_response(output_text="Simple response")

        with patch('src.models.openai_model.s2t_converter') as mock_converter:
            mock_converter.convert.side_effect = lambda x: x

            content, sources = model._process_openai_response(mock_response)

            assert content == "Simple response"
            assert sources == []

    def test_process_response_multiple_citations(self, model):
        """測試處理多個引用的回應"""
        annotations = [
            make_mock_annotation(filename="doc1.pdf", file_id="file_1", index=5),
            make_mock_annotation(filename="doc2.pdf", file_id="file_2", index=20),
        ]
        mock_response = make_mock_response(
            output_text="根據文件A的資料和文件B的內容來回答",
            annotations=annotations
        )

        with patch('src.models.openai_model.s2t_converter') as mock_converter, \
             patch('src.models.openai_model.dedup_citation_blocks', side_effect=lambda x: x):
            mock_converter.convert.side_effect = lambda x: x

            content, sources = model._process_openai_response(mock_response)

            assert "[1]" in content and "[2]" in content
            assert len(sources) == 2

    def test_process_response_duplicate_files(self, model):
        """測試同一檔案的多個引用被去重"""
        annotations = [
            make_mock_annotation(filename="same_doc.pdf", file_id="file_123", index=5),
            make_mock_annotation(filename="same_doc.pdf", file_id="file_123", index=20),
        ]
        mock_response = make_mock_response(
            output_text="引用同一文件的第一段和引用同一文件的第二段",
            annotations=annotations
        )

        with patch('src.models.openai_model.s2t_converter') as mock_converter, \
             patch('src.models.openai_model.dedup_citation_blocks', side_effect=lambda x: x):
            mock_converter.convert.side_effect = lambda x: x

            content, sources = model._process_openai_response(mock_response)

            # 應該只有一個來源（filename 去重）
            assert len(sources) == 1
            assert sources[0]['filename'] == "same_doc.pdf"

    def test_process_response_empty_output(self, model):
        """測試空 output 的回應"""
        mock_response = Mock()
        mock_response.output = []
        mock_response.output_text = "Fallback text"

        with patch('src.models.openai_model.s2t_converter') as mock_converter:
            mock_converter.convert.side_effect = lambda x: x

            content, sources = model._process_openai_response(mock_response)

            assert content == "Fallback text"
            assert sources == []

    def test_process_response_non_file_citation_annotations(self, model):
        """測試有 annotation 但全部都不是 file_citation 的情況"""
        ann = Mock()
        ann.type = "url_citation"
        ann.url = "https://example.com"

        mock_content = Mock()
        mock_content.type = "output_text"
        mock_content.text = "Some text with url reference"
        mock_content.annotations = [ann]

        mock_message = Mock()
        mock_message.type = "message"
        mock_message.content = [mock_content]

        mock_response = Mock()
        mock_response.output = [mock_message]
        mock_response.output_text = "Some text with url reference"

        with patch('src.models.openai_model.s2t_converter') as mock_converter:
            mock_converter.convert.side_effect = lambda x: x

            content, sources = model._process_openai_response(mock_response)

            assert content == "Some text with url reference"
            assert sources == []

    def test_process_response_annotation_missing_index(self, model):
        """測試 annotation 缺少 index 屬性時跳過插入"""
        ann_no_index = Mock()
        ann_no_index.type = "file_citation"
        ann_no_index.filename = "doc.pdf"
        ann_no_index.file_id = "file_1"
        ann_no_index.index = None  # index is None

        mock_content = Mock()
        mock_content.type = "output_text"
        mock_content.text = "Text without citation markers"
        mock_content.annotations = [ann_no_index]

        mock_message = Mock()
        mock_message.type = "message"
        mock_message.content = [mock_content]

        mock_response = Mock()
        mock_response.output = [mock_message]
        mock_response.output_text = "Text without citation markers"

        with patch('src.models.openai_model.s2t_converter') as mock_converter, \
             patch('src.models.openai_model.dedup_citation_blocks', side_effect=lambda x: x):
            mock_converter.convert.side_effect = lambda x: x

            content, sources = model._process_openai_response(mock_response)

            # sources still collected, but no [N] marker inserted in text
            assert len(sources) == 1
            assert "[1]" not in content

    def test_process_response_exception_output_text_also_fails(self, model):
        """測試 _process_openai_response 異常且 output_text 也失敗時回傳空字串"""
        mock_response = Mock()
        mock_response.output.__iter__ = Mock(side_effect=Exception("Unexpected error"))
        # output_text property also raises
        type(mock_response).output_text = property(lambda self: (_ for _ in ()).throw(Exception("No output_text")))

        with patch('src.models.openai_model.logger'):
            content, sources = model._process_openai_response(mock_response)

            assert content == ''
            assert sources == []

    def test_process_response_exception_fallback(self, model):
        """測試回應處理異常時的 fallback"""
        mock_response = Mock()
        # Iterating output raises exception
        mock_response.output.__iter__ = Mock(side_effect=Exception("Unexpected error"))
        mock_response.output_text = "Fallback text"

        with patch('src.models.openai_model.logger'):
            content, sources = model._process_openai_response(mock_response)

            assert content == "Fallback text"
            assert sources == []


class TestCreateResponse:
    """測試 Responses API 核心呼叫"""

    @pytest.fixture
    def model(self):
        with patch('src.core.config.get_value', return_value=False):
            m = OpenAIModel("test_key", "test_assistant")
        m.model = 'gpt-5'
        m.max_output_tokens = 8000
        m.reasoning_effort = 'medium'
        m.temperature = 0.1
        m.vector_store_id = 'vs_test123'
        m.system_prompt = "You are a test assistant."
        return m

    def test_create_response_basic(self, model):
        """測試基本 Responses API 呼叫"""
        mock_response = make_mock_response()
        model.client.responses.create = Mock(return_value=mock_response)

        result = model._create_response("conv_123", "Hello")

        assert result == mock_response
        call_kwargs = model.client.responses.create.call_args[1]
        assert call_kwargs['instructions'] == "You are a test assistant."
        assert call_kwargs['input'] == "Hello"
        assert call_kwargs['conversation'] == "conv_123"
        assert call_kwargs['store'] is True
        assert call_kwargs['model'] == 'gpt-5'

    def test_create_response_with_vector_store(self, model):
        """測試包含 file_search 工具的呼叫"""
        mock_response = make_mock_response()
        model.client.responses.create = Mock(return_value=mock_response)

        model._create_response("conv_123", "查詢議會資料")

        call_kwargs = model.client.responses.create.call_args[1]
        tools = call_kwargs['tools']
        assert any(t['type'] == 'file_search' for t in tools)
        assert call_kwargs.get('include') == ["file_search_call.results"]

    def test_create_response_without_vector_store(self, model):
        """測試不包含 file_search 工具的呼叫"""
        model.vector_store_id = None
        mock_response = make_mock_response()
        model.client.responses.create = Mock(return_value=mock_response)

        model._create_response("conv_123", "Hello")

        call_kwargs = model.client.responses.create.call_args[1]
        # 沒有 tools 時不會傳入 tools 和 include 參數
        assert 'tools' not in call_kwargs
        assert 'include' not in call_kwargs

    def test_create_response_with_reasoning(self, model):
        """測試 reasoning effort 參數"""
        mock_response = make_mock_response()
        model.client.responses.create = Mock(return_value=mock_response)

        model._create_response("conv_123", "複雜問題")

        call_kwargs = model.client.responses.create.call_args[1]
        assert call_kwargs['reasoning'] == {'effort': 'medium'}
        assert 'temperature' not in call_kwargs

    def test_create_response_without_reasoning(self, model):
        """測試無 reasoning 時使用 temperature"""
        model.reasoning_effort = None
        mock_response = make_mock_response()
        model.client.responses.create = Mock(return_value=mock_response)

        model._create_response("conv_123", "簡單問題")

        call_kwargs = model.client.responses.create.call_args[1]
        assert call_kwargs['temperature'] == 0.1
        assert 'reasoning' not in call_kwargs


class TestFileOperations:
    """測試檔案操作"""

    @pytest.fixture
    def model(self):
        with patch('src.core.config.get_value', return_value=False):
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
                {"id": "file_1", "filename": "doc1.txt", "bytes": 1024, "status": "processed", "purpose": "assistants"},
                {"id": "file_2", "filename": "doc2.txt", "bytes": 2048, "status": "processed", "purpose": "assistants"}
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

    def test_list_files_failure(self, model):
        """測試列出檔案失敗"""
        with patch.object(model, '_request', return_value=(False, None, "API error")):
            success, files, error = model.list_files()

            assert success is False
            assert files is None
            assert error == "API error"

    def test_list_files_exception(self, model):
        """測試列出檔案異常"""
        with patch.object(model, '_request', side_effect=Exception("Network error")):
            success, files, error = model.list_files()

            assert success is False
            assert files is None
            assert "Network error" in error

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
        with patch('src.core.config.get_value', return_value=False):
            return OpenAIModel("test_key", "test_assistant")

    def test_query_with_rag_with_existing_thread(self, model):
        """測試使用現有 conversation 的 RAG 查詢"""
        query = "What is machine learning?"
        thread_id = "conv_123"

        mock_response = make_mock_response(output_text="Machine learning is...")

        with patch.object(model, '_create_response', return_value=mock_response), \
             patch.object(model, '_process_openai_response', return_value=("Machine learning is...", [])):

            success, rag_response, error = model.query_with_rag(query, thread_id)

            assert success is True
            assert isinstance(rag_response, RAGResponse)
            assert rag_response.answer == "Machine learning is..."
            assert error is None

    def test_query_with_rag_create_new_thread(self, model):
        """測試創建新 conversation 的 RAG 查詢"""
        query = "Explain AI"

        mock_thread_info = ThreadInfo(thread_id="conv_456")
        mock_response = make_mock_response(output_text="AI explanation...")

        with patch.object(model, 'create_thread', return_value=(True, mock_thread_info, None)), \
             patch.object(model, '_create_response', return_value=mock_response), \
             patch.object(model, '_process_openai_response', return_value=("AI explanation", [])):

            success, rag_response, error = model.query_with_rag(query)

            assert success is True
            assert rag_response.metadata['thread_id'] == "conv_456"
            assert error is None

    def test_query_with_rag_thread_creation_failure(self, model):
        """測試 RAG 查詢 conversation 創建失敗"""
        query = "Test query"
        error_message = "Failed to create conversation"

        with patch.object(model, 'create_thread', return_value=(False, None, error_message)):
            success, rag_response, error = model.query_with_rag(query)

            assert success is False
            assert rag_response is None
            assert "Failed to create" in error

    def test_query_with_rag_api_failure(self, model):
        """測試 RAG 查詢 API 呼叫失敗"""
        query = "Test query"
        thread_id = "conv_123"

        with patch.object(model, '_create_response', side_effect=Exception("API error")):
            success, rag_response, error = model.query_with_rag(query, thread_id)

            assert success is False
            assert rag_response is None
            assert "API error" in error


class TestAudioTranscription:
    """測試音訊轉錄"""

    @pytest.fixture
    def model(self):
        with patch('src.core.config.get_value', return_value=False):
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
        with patch('src.core.config.get_value', return_value=False):
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

    def test_generate_image_no_data(self, model):
        """測試生成圖片無數據返回"""
        with patch.object(model, '_request', return_value=(True, {"data": []}, None)):
            success, image_url, error = model.generate_image("A test image")

            assert success is False
            assert image_url is None
            assert "list index out of range" in error

    def test_generate_image_no_url(self, model):
        """測試生成圖片無 URL 返回"""
        with patch.object(model, '_request', return_value=(True, {"data": [{"revised_prompt": "A revised prompt"}]}, None)):
            success, image_url, error = model.generate_image("A test image")

            assert success is False
            assert image_url is None
            assert "'url'" in error


class TestBackwardCompatibility:
    """測試向後相容方法"""

    @pytest.fixture
    def model(self):
        with patch('src.core.config.get_value', return_value=False):
            return OpenAIModel("test_key", "test_assistant")

    def test_check_token_valid(self, model):
        """測試 check_token_valid 向後相容方法"""
        with patch.object(model, 'check_connection', return_value=(True, None)):
            success, _, error = model.check_token_valid()

            assert success is True
            assert error is None


class TestInternalMethods:
    """測試內部方法"""

    @pytest.fixture
    def model(self):
        with patch('src.core.config.get_value', return_value=False):
            return OpenAIModel("test_key", "test_assistant")

    def test_request_get_method(self, model):
        """測試 GET 請求"""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": "test"}
            mock_get.return_value = mock_response

            success, data, error = model._request('GET', '/test')

            assert success is True
            assert data == {"data": "test"}
            assert error is None

            # 檢查請求頭
            call_args = mock_get.call_args
            headers = call_args[1]['headers']
            assert 'Authorization' in headers
            # Responses API 不再需要 OpenAI-Beta header
            assert 'OpenAI-Beta' not in headers

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

            success, data, error = model._request('DELETE', '/test')

            assert success is True
            assert data == {"deleted": True}

    def test_request_rate_limit_error(self, model):
        """測試速率限制錯誤"""
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 429
            mock_response.json.return_value = {"error": {"message": "Rate limit exceeded"}}
            mock_post.return_value = mock_response

            success, data, error = model._request('POST', '/test')

            assert success is False
            assert data is None
            assert "Rate limit exceeded" in error

    def test_request_server_error(self, model):
        """測試服務器錯誤"""
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.json.return_value = {"error": {"message": "Server error"}}
            mock_post.return_value = mock_response

            success, data, error = model._request('POST', '/test')

            assert success is False
            assert data is None
            assert "Server error" in error

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
            success, data, error = model._request('POST', '/test')

            assert success is False
            assert data is None
            assert "Network error" in error

    def test_request_get_with_body(self, model):
        """測試 GET 請求帶 body（設定 Content-Type header）"""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": "test"}
            mock_get.return_value = mock_response

            success, data, error = model._request('GET', '/test', body={"key": "value"})

            assert success is True
            call_args = mock_get.call_args
            headers = call_args[1]['headers']
            assert headers['Content-Type'] == 'application/json'

    def test_request_get_models_endpoint(self, model):
        """測試 GET 請求到 models endpoint 使用 model_list timeout"""
        with patch('requests.get') as mock_get, \
             patch('src.models.openai_model.SmartTimeoutConfig') as mock_timeout:
            mock_timeout.get_timeout_for_model.return_value = 30
            mock_timeout.get_timeout.return_value = 10

            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": []}
            mock_get.return_value = mock_response

            model._request('GET', '/models')

            mock_timeout.get_timeout.assert_called_with('model_list')

    def test_request_post_with_files(self, model):
        """測試 POST 請求帶 files（使用 file_upload timeout）"""
        with patch('requests.post') as mock_post, \
             patch('src.models.openai_model.SmartTimeoutConfig') as mock_timeout:
            mock_timeout.get_timeout_for_model.return_value = 30
            mock_timeout.get_timeout.return_value = 120

            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"id": "file_123"}
            mock_post.return_value = mock_response

            files = {"file": ("test.txt", b"content")}
            model._request('POST', '/files', files=files)

            mock_timeout.get_timeout.assert_called_with('file_upload')

    def test_request_response_with_error_key(self, model):
        """測試回應 JSON 包含 error key"""
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "error": {"message": "Invalid model specified"}
            }
            mock_post.return_value = mock_response

            success, data, error = model._request('POST', '/test', body={"test": True})

            assert success is False
            assert data is None
            assert error == "Invalid model specified"

    def test_request_general_exception(self, model):
        """測試一般異常"""
        with patch('requests.post', side_effect=Exception("General error")):
            success, data, error = model._request('POST', '/test')

            assert success is False
            assert data is None
            assert "OpenAI API 系統不穩定" in error


class TestUserLevelConversationManagement:
    """測試用戶級對話管理"""

    @pytest.fixture
    def model(self):
        with patch('src.core.config.get_value', return_value=False):
            return OpenAIModel("test_key", "test_assistant")

    def test_chat_with_user_existing_thread(self, model):
        """測試使用現有 conversation 的用戶對話"""
        user_id = "user_123"
        message = "Hello, how are you?"
        platform = "line"
        existing_thread_id = "conv_456"

        mock_response = make_mock_response(output_text="I'm doing well!")

        with patch('src.database.connection.get_thread_id_by_user_id', return_value=existing_thread_id), \
             patch.object(model, '_create_response', return_value=mock_response), \
             patch.object(model, '_process_openai_response', return_value=("I'm doing well!", [])):

            success, rag_response, error = model.chat_with_user(user_id, message, platform)

            assert success is True
            assert isinstance(rag_response, RAGResponse)
            assert rag_response.answer == "I'm doing well!"
            assert rag_response.metadata['user_id'] == user_id
            assert rag_response.metadata['thread_id'] == existing_thread_id
            assert error is None

    def test_chat_with_user_create_new_thread(self, model):
        """測試創建新 conversation 的用戶對話"""
        user_id = "new_user_789"
        message = "First message"
        platform = "discord"

        mock_thread_info = ThreadInfo(thread_id="conv_abc")
        mock_response = make_mock_response(output_text="Welcome!")

        with patch('src.database.connection.get_thread_id_by_user_id', return_value=None), \
             patch.object(model, 'create_thread', return_value=(True, mock_thread_info, None)), \
             patch('src.database.connection.save_thread_id') as mock_save, \
             patch.object(model, '_create_response', return_value=mock_response), \
             patch.object(model, '_process_openai_response', return_value=("Welcome!", [])):

            success, rag_response, error = model.chat_with_user(user_id, message, platform)

            assert success is True
            assert rag_response.metadata['thread_id'] == "conv_abc"
            mock_save.assert_called_once_with(user_id, "conv_abc", platform)

    def test_chat_with_user_thread_creation_failure(self, model):
        """測試用戶對話 conversation 創建失敗"""
        user_id = "user_123"
        message = "Test message"

        with patch('src.database.connection.get_thread_id_by_user_id', return_value=None), \
             patch.object(model, 'create_thread', return_value=(False, None, "Thread creation failed")):

            success, rag_response, error = model.chat_with_user(user_id, message)

            assert success is False
            assert rag_response is None
            assert "Failed to create conversation" in error

    def test_chat_with_user_exception(self, model):
        """測試用戶對話異常"""
        user_id = "user_123"
        message = "Test message"

        with patch('src.database.connection.get_thread_id_by_user_id', side_effect=Exception("Database error")), \
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
        thread_id = "conv_456"

        with patch('src.database.connection.get_thread_id_by_user_id', return_value=thread_id), \
             patch.object(model, 'delete_thread', return_value=(True, None)), \
             patch('src.database.connection.delete_thread_id') as mock_delete:

            success, error = model.clear_user_history(user_id, platform)

            assert success is True
            assert error is None
            mock_delete.assert_called_once_with(user_id, platform)

    def test_clear_user_history_no_thread(self, model):
        """測試清除不存在的用戶歷史"""
        user_id = "user_123"
        platform = "line"

        with patch('src.database.connection.get_thread_id_by_user_id', return_value=None), \
             patch('src.models.openai_model.logger') as mock_logger:

            success, error = model.clear_user_history(user_id, platform)

            assert success is True
            assert error is None
            mock_logger.info.assert_called_once()

    def test_clear_user_history_delete_thread_failure(self, model):
        """測試刪除 conversation 失敗但仍清除本地記錄"""
        user_id = "user_123"
        platform = "line"
        thread_id = "conv_456"

        with patch('src.database.connection.get_thread_id_by_user_id', return_value=thread_id), \
             patch.object(model, 'delete_thread', return_value=(False, "API error")), \
             patch('src.database.connection.delete_thread_id') as mock_delete, \
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

        with patch('src.database.connection.get_thread_id_by_user_id', side_effect=Exception("Database error")), \
             patch('src.models.openai_model.logger') as mock_logger:

            success, error = model.clear_user_history(user_id, platform)

            assert success is False
            assert "Database error" in error
            mock_logger.error.assert_called_once()


class TestEdgeCases:
    """測試邊界情況和錯誤處理"""

    @pytest.fixture
    def model(self):
        with patch('src.core.config.get_value', return_value=False):
            return OpenAIModel("test_key", "test_assistant")

    def test_empty_api_key(self):
        """測試空 API key"""
        with patch('src.models.openai_model.OpenAI'):
            with patch('src.core.config.get_value', return_value=False):
                model = OpenAIModel("", "test_assistant")
        assert model.api_key == ""

    def test_empty_assistant_id(self):
        """測試空 assistant ID"""
        with patch('src.core.config.get_value', return_value=False):
            model = OpenAIModel("test_key", "")
        assert model.assistant_id == ""

    def test_none_parameters(self):
        """測試 None 參數"""
        with patch('src.core.config.get_value', return_value=False):
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
        special_message = "Hello! 你好 @#$%^&*()_+"
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
            success, chat_response, error = model.chat_completion([ChatMessage(role="user", content="test")])

            assert success is False
            assert chat_response is None
            assert "choices" in error

    def test_file_not_found_error(self, model):
        """測試檔案不存在錯誤"""
        with patch('builtins.open', side_effect=FileNotFoundError("File not found")):
            success, file_info, error = model.upload_knowledge_file("/nonexistent/file.txt")

            assert success is False
            assert file_info is None
            assert "File not found" in error


class TestOpenAIModelMCP:
    """測試 OpenAI Model MCP 相關功能"""

    @pytest.fixture
    def mcp_enabled_model(self):
        """創建啟用 MCP 的模型"""
        with patch('src.core.config.get_value') as mock_config:
            mock_config.side_effect = lambda key, default=None: {
                'features.enable_mcp': True,
                'mcp.enabled': True
            }.get(key, default)

            with patch('src.services.mcp_service.get_mcp_service') as mock_mcp:
                mock_service = Mock()
                mock_service.is_enabled = True
                mock_service.get_function_schemas_for_openai.return_value = [
                    {"type": "function", "name": "search_data", "description": "Search for data", "parameters": {"type": "object"}}
                ]
                mock_mcp.return_value = mock_service

                model = OpenAIModel(api_key="test_key", assistant_id="test_assistant", enable_mcp=True)
                yield model

    def test_mcp_config_read_error(self):
        """測試 MCP 配置讀取錯誤"""
        with patch('src.core.config.get_value', side_effect=Exception("Config error")):
            with patch('src.models.openai_model.logger') as mock_logger:
                model = OpenAIModel(api_key="test_key", assistant_id="test_assistant")

                assert model.enable_mcp is False
                mock_logger.warning.assert_called_with("Error reading MCP config: Config error")

    def test_mcp_service_not_enabled(self):
        """測試 MCP 服務未啟用"""
        with patch('src.core.config.get_value', return_value=True):
            with patch('src.services.mcp_service.get_mcp_service') as mock_mcp:
                mock_service = Mock()
                mock_service.is_enabled = False
                mock_mcp.return_value = mock_service

                with patch('src.models.openai_model.logger') as mock_logger:
                    model = OpenAIModel(api_key="test_key", assistant_id="test_assistant", enable_mcp=True)

                    assert model.enable_mcp is False
                    mock_logger.warning.assert_called_with("OpenAI Model: MCP service is not enabled")

    def test_mcp_service_init_exception(self):
        """測試 MCP 服務初始化異常"""
        with patch('src.core.config.get_value', return_value=True):
            with patch('src.services.mcp_service.get_mcp_service', side_effect=Exception("Init error")):
                with patch('src.models.openai_model.logger') as mock_logger:
                    model = OpenAIModel(api_key="test_key", assistant_id="test_assistant", enable_mcp=True)

                    assert model.enable_mcp is False
                    assert model.mcp_service is None
                    mock_logger.warning.assert_called_with("OpenAI Model: Failed to initialize MCP service: Init error")

    def test_get_mcp_status(self, mcp_enabled_model):
        """測試取得 MCP 服務狀態"""
        status = mcp_enabled_model.get_mcp_status()

        assert status['enabled'] is True
        assert status['service_available'] is True

    def test_reload_mcp_config(self, mcp_enabled_model):
        """測試重新載入 MCP 設定"""
        mcp_enabled_model.mcp_service.reload_config.return_value = True

        result = mcp_enabled_model.reload_mcp_config()

        assert result is True

    def test_reload_mcp_config_no_service(self):
        """測試沒有 MCP service 時 reload 回傳 False"""
        with patch('src.core.config.get_value', return_value=False):
            model = OpenAIModel("test_key")
        model.mcp_service = None

        result = model.reload_mcp_config()

        assert result is False

    def test_handle_mcp_function_calls_no_function_calls(self, mcp_enabled_model):
        """測試沒有 function call 時直接返回"""
        mock_response = make_mock_response()

        result = mcp_enabled_model._handle_mcp_function_calls(mock_response)

        assert result == mock_response

    def test_handle_mcp_function_calls_success(self, mcp_enabled_model):
        """測試成功處理 function call"""
        # First response has a function_call
        fc_item = Mock()
        fc_item.type = "function_call"
        fc_item.name = "search_data"
        fc_item.arguments = '{"query": "test"}'
        fc_item.call_id = "call_123"

        first_response = Mock()
        first_response.id = "resp_1"
        first_response.output = [fc_item]

        # Second response is the final message
        final_response = make_mock_response(output_text="Found results")

        mcp_enabled_model.mcp_service.handle_function_call_sync.return_value = {
            "success": True,
            "data": "test results"
        }
        mcp_enabled_model.client.responses.create = Mock(return_value=final_response)

        result = mcp_enabled_model._handle_mcp_function_calls(first_response)

        assert result == final_response
        mcp_enabled_model.mcp_service.handle_function_call_sync.assert_called_once_with(
            "search_data", {"query": "test"}
        )

        # 驗證 function_call_output 格式
        create_kwargs = mcp_enabled_model.client.responses.create.call_args[1]
        input_items = create_kwargs['input']
        assert len(input_items) == 1
        assert input_items[0]['type'] == 'function_call_output'
        assert input_items[0]['call_id'] == 'call_123'
        assert create_kwargs['previous_response_id'] == 'resp_1'

    def test_handle_mcp_function_calls_result_failed(self, mcp_enabled_model):
        """測試 function call 回傳 success=False"""
        fc_item = Mock()
        fc_item.type = "function_call"
        fc_item.name = "search_data"
        fc_item.arguments = '{"query": "test"}'
        fc_item.call_id = "call_123"

        first_response = Mock()
        first_response.id = "resp_1"
        first_response.output = [fc_item]

        final_response = make_mock_response(output_text="Function failed")

        mcp_enabled_model.mcp_service.handle_function_call_sync.return_value = {
            "success": False,
            "error": "No results found"
        }
        mcp_enabled_model.client.responses.create = Mock(return_value=final_response)

        with patch('src.models.openai_model.logger') as mock_logger:
            result = mcp_enabled_model._handle_mcp_function_calls(first_response)

        assert result == final_response
        # Should log error for failed function
        mock_logger.error.assert_called_once()
        assert "No results found" in mock_logger.error.call_args[0][0]

    def test_handle_mcp_function_calls_error(self, mcp_enabled_model):
        """測試 function call 執行失敗"""
        fc_item = Mock()
        fc_item.type = "function_call"
        fc_item.name = "search_data"
        fc_item.arguments = '{"query": "test"}'
        fc_item.call_id = "call_123"

        first_response = Mock()
        first_response.id = "resp_1"
        first_response.output = [fc_item]

        final_response = make_mock_response(output_text="Error occurred")

        mcp_enabled_model.mcp_service.handle_function_call_sync.side_effect = Exception("Tool error")
        mcp_enabled_model.client.responses.create = Mock(return_value=final_response)

        with patch('src.models.openai_model.logger'):
            result = mcp_enabled_model._handle_mcp_function_calls(first_response)

        assert result == final_response

        # 驗證錯誤訊息被傳回
        create_kwargs = mcp_enabled_model.client.responses.create.call_args[1]
        input_items = create_kwargs['input']
        output_data = json.loads(input_items[0]['output'])
        assert output_data['success'] is False
        assert "Tool error" in output_data['error']

    def test_handle_mcp_function_calls_max_iterations(self, mcp_enabled_model):
        """測試 function call 超過最大迭代次數"""
        fc_item = Mock()
        fc_item.type = "function_call"
        fc_item.name = "search_data"
        fc_item.arguments = '{"query": "test"}'
        fc_item.call_id = "call_123"

        # Every response returns a function_call (infinite loop scenario)
        loop_response = Mock()
        loop_response.id = "resp_loop"
        loop_response.output = [fc_item]

        mcp_enabled_model.mcp_service.handle_function_call_sync.return_value = {"success": True}
        mcp_enabled_model.client.responses.create = Mock(return_value=loop_response)

        with patch('src.models.openai_model.logger') as mock_logger:
            result = mcp_enabled_model._handle_mcp_function_calls(loop_response, max_iterations=3)

        mock_logger.warning.assert_called()
        # Should have called responses.create 3 times (max_iterations)
        assert mcp_enabled_model.client.responses.create.call_count == 3

    def test_create_response_includes_mcp_tools(self, mcp_enabled_model):
        """測試 _create_response 包含 MCP function tools"""
        mcp_enabled_model.vector_store_id = None
        mock_response = make_mock_response()
        mcp_enabled_model.client.responses.create = Mock(return_value=mock_response)

        mcp_enabled_model._create_response("conv_123", "test query")

        call_kwargs = mcp_enabled_model.client.responses.create.call_args[1]
        tools = call_kwargs.get('tools', [])
        assert len(tools) > 0
        assert any(t.get('name') == 'search_data' for t in tools)

    def test_mcp_service_integration(self, mcp_enabled_model):
        """測試 MCP 服務整合"""
        assert hasattr(mcp_enabled_model, 'mcp_service')
        assert mcp_enabled_model.mcp_service is not None
        assert mcp_enabled_model.mcp_service.is_enabled is True


class TestBuildSystemPrompt:
    """測試 system prompt 建構"""

    def test_build_system_prompt_from_file(self):
        """測試從 prompts.yml 載入 system prompt"""
        mock_prompts = {"system_prompt": "Custom system prompt"}

        with patch('src.core.config.get_value', return_value=False), \
             patch('builtins.open', mock_open(read_data="")), \
             patch('yaml.safe_load', return_value=mock_prompts):
            model = OpenAIModel("test_key")

        assert model.system_prompt == "Custom system prompt"

    def test_build_system_prompt_file_not_found(self):
        """測試 prompts.yml 不存在時使用預設值"""
        with patch('src.core.config.get_value', return_value=False), \
             patch('builtins.open', side_effect=FileNotFoundError()):
            model = OpenAIModel("test_key")

        assert model.system_prompt == "You are a helpful assistant."

    def test_build_system_prompt_file_not_found_with_mcp(self):
        """測試 prompts.yml 不存在且 MCP 啟用時，從 config 讀取 mcp.system_prompt"""
        with patch('src.core.config.get_value') as mock_config:
            mock_config.side_effect = lambda key, default=None: {
                'features.enable_mcp': True,
                'mcp.enabled': True,
                'mcp.system_prompt': 'MCP fallback prompt',
            }.get(key, default)

            with patch('src.services.mcp_service.get_mcp_service') as mock_mcp:
                mock_service = Mock()
                mock_service.is_enabled = True
                mock_service.get_function_schemas_for_openai.return_value = []
                mock_mcp.return_value = mock_service

                with patch('builtins.open', side_effect=FileNotFoundError()):
                    model = OpenAIModel("test_key", enable_mcp=True)

        assert model.system_prompt == "MCP fallback prompt"

    def test_build_system_prompt_file_not_found_with_mcp_config_error(self):
        """測試 prompts.yml 不存在 + MCP 啟用但 config 也讀取失敗"""
        call_count = [0]

        def mock_get_value(key, default=None):
            call_count[0] += 1
            if key == 'mcp.system_prompt':
                raise Exception("Config error")
            return {
                'features.enable_mcp': True,
                'mcp.enabled': True,
            }.get(key, default)

        with patch('src.core.config.get_value', side_effect=mock_get_value):
            with patch('src.services.mcp_service.get_mcp_service') as mock_mcp:
                mock_service = Mock()
                mock_service.is_enabled = True
                mock_service.get_function_schemas_for_openai.return_value = []
                mock_mcp.return_value = mock_service

                with patch('builtins.open', side_effect=FileNotFoundError()):
                    model = OpenAIModel("test_key", enable_mcp=True)

        # Fallback to default when both prompts.yml and config fail
        assert model.system_prompt == "You are a helpful assistant."

    def test_build_system_prompt_general_exception(self):
        """測試 prompts.yml 載入時發生一般異常"""
        with patch('src.core.config.get_value', return_value=False), \
             patch('builtins.open', mock_open(read_data="")), \
             patch('yaml.safe_load', side_effect=Exception("YAML parse error")):
            model = OpenAIModel("test_key")

        assert model.system_prompt == "You are a helpful assistant."

    def test_build_system_prompt_with_mcp_guidelines(self):
        """測試 MCP 啟用時附加 guidelines"""
        mock_prompts = {
            "system_prompt": "Base prompt",
            "mcp_guidelines": "MCP guidelines here"
        }

        with patch('src.core.config.get_value') as mock_config:
            mock_config.side_effect = lambda key, default=None: {
                'features.enable_mcp': True,
                'mcp.enabled': True
            }.get(key, default)

            with patch('src.services.mcp_service.get_mcp_service') as mock_mcp:
                mock_service = Mock()
                mock_service.is_enabled = True
                mock_service.get_function_schemas_for_openai.return_value = []
                mock_mcp.return_value = mock_service

                with patch('builtins.open', mock_open(read_data="")), \
                     patch('yaml.safe_load', return_value=mock_prompts):
                    model = OpenAIModel("test_key", enable_mcp=True)

        assert "Base prompt" in model.system_prompt
        assert "MCP guidelines here" in model.system_prompt


if __name__ == "__main__":
    pytest.main([__file__])
