
import pytest
import json
from unittest.mock import MagicMock, AsyncMock, Mock, patch

from src.models.gemini_model import GeminiModel
from src.models.ollama_model import OllamaModel
from src.models.huggingface_model import HuggingFaceModel
from src.models.base import ChatMessage, ChatResponse, RAGResponse
from src.services.mcp_service import MCPService

@pytest.fixture
def mock_mcp_service():
    """Mock a MCPService instance for testing."""
    service = MagicMock(spec=MCPService)
    service.is_enabled = True
    
    # Mock function schemas for prompt building
    service.get_function_schemas_for_anthropic.return_value = '''<tools>
<tool_description>
<tool_name>search_data</tool_name>
<description>搜尋資料</description>
<parameters>
<parameter>
<name>query</name>
<type>string</type>
<description>搜尋關鍵字</description>
</parameter>
</parameters>
</tool_description>
</tools>'''
    
    # Mock function schemas for Gemini
    service.get_function_schemas_for_gemini.return_value = [{
        "name": "search_data",
        "description": "搜尋資料",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜尋關鍵字"}
            },
            "required": ["query"]
        }
    }]
    
    # Mock the actual tool call handling
    def mock_handle_call(tool_name, arguments):
        if tool_name == 'search_data':
            return {
                "success": True,
                "data": f"這是關於 {arguments.get('query')} 的搜尋結果。",
                "metadata": {
                    "sources": [{"filename": "test_source.txt"}]
                }
            }
        return {"success": False, "error": "Tool not found"}

    async def mock_handle_call_async(tool_name, arguments):
        return mock_handle_call(tool_name, arguments)

    # Create a simple mock service that directly returns the result
    service.handle_function_call = AsyncMock(side_effect=mock_handle_call_async)
    service.handle_function_call_sync = Mock(side_effect=mock_handle_call)
    service.handle_function_call_async = AsyncMock(side_effect=mock_handle_call_async)
    
    # Make sure the service is properly configured
    service.config_manager = MagicMock()
    service.mcp_client = MagicMock()
    
    return service

# --- Gemini MCP Test ---

@pytest.mark.asyncio
async def test_gemini_model_mcp_flow(mocker, mock_mcp_service):
    """Test the full MCP tool-calling flow for GeminiModel."""
    # 1. Setup
    gemini = GeminiModel(api_key="fake_key", enable_mcp=True)
    gemini.mcp_service = mock_mcp_service

    # Mock the internal _request method to simulate Gemini API responses
    mock_request = mocker.patch.object(gemini, '_request')

    # First call: Model returns a tool call request
    # Second call: Model returns the final response 
    mock_request.side_effect = [
        (True, {
            "candidates": [{
                "content": {
                    "parts": [{
                        "functionCall": {
                            "name": "search_data",
                            "args": {"query": "天氣"}
                        }
                    }]
                }
            }]
        }, None),
        (True, {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": "這是關於天氣的搜尋結果。"
                    }]
                }
            }]
        }, None)
    ]

    # 2. Execute
    messages = [ChatMessage(role="user", content="今天天氣如何？")]
    is_success, response, error = await gemini.chat_completion_with_mcp(messages)

    # 3. Assert
    assert is_success
    assert response is not None
    assert "搜尋結果" in response.content
    assert "test_source.txt" in [src['filename'] for src in response.metadata.get('sources', [])]
    
    # Verify that mcp_service.handle_function_call_sync was called
    mock_mcp_service.handle_function_call_sync.assert_called_once_with("search_data", {"query": "天氣"})

# --- Ollama MCP Test ---

@pytest.mark.asyncio
async def test_ollama_model_mcp_flow(mocker, mock_mcp_service):
    """Test the full prompt-based MCP tool-calling flow for OllamaModel."""
    # 1. Setup - Create the model first, then replace the mcp_service with our mock
    ollama = OllamaModel(enable_mcp=True)
    # Force the service to be our mock
    ollama.mcp_service = mock_mcp_service
    
    # Ensure the service is set to the mock
    assert ollama.mcp_service is mock_mcp_service

    # IMPORTANT: chat_completion is synchronous, not async!
    # So we need to use regular Mock, not AsyncMock
    mock_chat = mocker.patch.object(ollama, 'chat_completion')
    
    # First call: Model returns a JSON for tool call
    mock_chat.side_effect = [
        (True, ChatResponse(content=json.dumps({
            "tool_name": "search_data",
            "arguments": {"query": "今日新聞"}
        })), None),
        # Second call: Model returns the final answer
        (True, ChatResponse(content="根據搜尋結果，今日的頭條新聞是...", metadata={}), None)
    ]

    # 2. Execute
    messages = [ChatMessage(role="user", content="幫我找一下今天的新聞")]
    is_success, rag_response, error = await ollama.chat_completion_with_mcp(messages)

    # 3. Assert
    if not is_success:
        print(f"DEBUG: Test failed with error: {error}")
        # If it failed, let's check if the mock was called
        if mock_mcp_service.handle_function_call_sync.called:
            print("DEBUG: Mock was called, but test still failed")
        else:
            print("DEBUG: Mock was NOT called")
        
    assert is_success, f"Test failed with error: {error}"
    assert rag_response is not None
    assert "頭條新聞" in rag_response.answer
    assert "test_source.txt" in [src['filename'] for src in rag_response.sources]
    
    # Verify that mcp_service.handle_function_call_sync was called (not async version)
    mock_mcp_service.handle_function_call_sync.assert_called_once_with("search_data", {"query": "今日新聞"})
    assert mock_chat.call_count == 2

# --- HuggingFace MCP Test ---

@pytest.mark.asyncio
async def test_huggingface_model_mcp_flow(mocker, mock_mcp_service):
    """Test the full prompt-based MCP tool-calling flow for HuggingFaceModel."""
    # 1. Setup - Create the model first, then replace the mcp_service with our mock
    huggingface = HuggingFaceModel(api_key="fake_key", enable_mcp=True)
    # Force the service to be our mock
    huggingface.mcp_service = mock_mcp_service

    # IMPORTANT: chat_completion is synchronous, not async!
    # So we need to use regular Mock, not AsyncMock
    mock_chat = mocker.patch.object(huggingface, 'chat_completion')

    # First call: Model returns a JSON for tool call
    mock_chat.side_effect = [
        (True, ChatResponse(content=json.dumps({
            "tool_name": "search_data",
            "arguments": {"query": "推薦餐廳"}
        })), None),
        # Second call: Model returns the final answer
        (True, ChatResponse(content="為您推薦以下餐廳...", metadata={}), None)
    ]

    # 2. Execute
    messages = [ChatMessage(role="user", content="附近有什麼好吃的？")]
    is_success, rag_response, error = await huggingface.chat_completion_with_mcp(messages)

    # 3. Assert
    assert is_success
    assert rag_response is not None
    assert "為您推薦" in rag_response.answer
    assert "test_source.txt" in [src['filename'] for src in rag_response.sources]
    
    # Verify that mcp_service.handle_function_call_sync was called (not async version)
    mock_mcp_service.handle_function_call_sync.assert_called_once_with("search_data", {"query": "推薦餐廳"})
    assert mock_chat.call_count == 2
