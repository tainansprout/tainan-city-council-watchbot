"""
MCP 效能和分頁測試
"""

import pytest
import asyncio
import time
import json
import tempfile
import os
from unittest.mock import AsyncMock, Mock, patch
from concurrent.futures import ThreadPoolExecutor
from src.core.mcp_config import MCPConfigManager
from src.core.mcp_client import MCPClient
from src.services.mcp_service import MCPService

# Mock async context manager helper
class MockAsyncContextManager:
    def __init__(self, return_value):
        self.return_value = return_value
        
    async def __aenter__(self):
        return self.return_value
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


class TestMCPPerformance:
    """測試 MCP 效能"""
    
    def setup_method(self):
        """設定測試環境"""
        self.temp_dir = tempfile.mkdtemp()
        self.server_config = {
            "base_url": "http://localhost:3000/api/mcp",
            "timeout": 30,
            "retry_attempts": 3
        }
        
        # 創建測試配置
        self.test_config = {
            "mcp_server": self.server_config,
            "functions": [
                {
                    "name": f"function_{i}",
                    "description": f"測試函數 {i}",
                    "mcp_tool": f"tool_{i}",
                    "enabled": True,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"}
                        }
                    }
                }
                for i in range(50)  # 50 個函數
            ],
            "tools": {}
        }
        
        config_file = os.path.join(self.temp_dir, "perf_test.json")
        with open(config_file, 'w') as f:
            json.dump(self.test_config, f)
    
    def teardown_method(self):
        """清理測試環境"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_config_loading_performance(self):
        """測試配置載入效能"""
        config_manager = MCPConfigManager(self.temp_dir)
        
        # 測試初次載入時間
        start_time = time.time()
        config_manager.load_mcp_config("perf_test.json")
        first_load_time = time.time() - start_time
        
        # 測試快取載入時間
        start_time = time.time()
        config_manager.load_mcp_config("perf_test.json")
        cached_load_time = time.time() - start_time
        
        # 快取載入應該明顯更快
        assert cached_load_time < first_load_time * 0.5
        assert first_load_time < 2.0  # 初次載入應該在 2 秒內
        assert cached_load_time < 0.1  # 快取載入應該在 0.1 秒內
    
    def test_function_schema_generation_performance(self):
        """測試函數模式生成效能"""
        config_manager = MCPConfigManager(self.temp_dir)
        
        # 測試 OpenAI schema 生成效能
        start_time = time.time()
        openai_schemas = config_manager.get_function_schemas_for_openai("perf_test.json")
        openai_time = time.time() - start_time
        
        # 測試 Anthropic schema 生成效能
        start_time = time.time()
        anthropic_prompt = config_manager.get_function_schemas_for_anthropic("perf_test.json")
        anthropic_time = time.time() - start_time
        
        # 驗證結果
        assert len(openai_schemas) == 50
        assert len(anthropic_prompt) > 1000
        
        # 效能要求
        assert openai_time < 0.5  # OpenAI schema 生成應該在 0.5 秒內
        assert anthropic_time < 0.5  # Anthropic schema 生成應該在 0.5 秒內
    
    def test_concurrent_config_loading(self):
        """測試並發配置載入"""
        config_manager = MCPConfigManager(self.temp_dir)
        
        def load_config():
            return config_manager.load_mcp_config("perf_test.json")
        
        # 並發載入測試
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(load_config) for _ in range(20)]
            results = [future.result() for future in futures]
        
        concurrent_time = time.time() - start_time
        
        # 驗證結果
        assert all(result == self.test_config for result in results)
        assert concurrent_time < 2.0  # 並發載入應該在 2 秒內完成
    
    def test_parameter_validation_performance(self):
        """測試參數驗證效能"""
        config_manager = MCPConfigManager(self.temp_dir)
        
        # 測試大量參數驗證
        test_cases = [
            ("function_0", {"query": f"test_query_{i}"})
            for i in range(1000)
        ]
        
        start_time = time.time()
        for function_name, args in test_cases:
            valid, error = config_manager.validate_function_arguments(
                function_name, args, "perf_test.json"
            )
            assert valid is True
        
        validation_time = time.time() - start_time
        
        # 1000 次驗證應該在 1 秒內完成
        assert validation_time < 1.0
        
        # 平均每次驗證時間
        avg_time = validation_time / 1000
        assert avg_time < 0.001  # 平均每次驗證應該在 0.001 秒內
    
    @pytest.mark.asyncio
    async def test_concurrent_function_calls(self):
        """測試並發函數呼叫"""
        mock_client = Mock()
        mock_client.call_tool = AsyncMock(return_value={
            "success": True,
            "data": "test result",
            "content_type": "text",
            "metadata": {}
        })
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch('src.services.mcp_service.MCPClient', return_value=mock_client):
            service = MCPService(self.temp_dir, "perf_test.json")
            
            # 並發呼叫測試
            async def call_function(i):
                return await service.handle_function_call(
                    "function_0", {"query": f"test_{i}"}
                )
            
            start_time = time.time()
            tasks = [call_function(i) for i in range(100)]
            results = await asyncio.gather(*tasks)
            concurrent_time = time.time() - start_time
            
            # 驗證結果
            assert all(result["success"] for result in results)
            assert concurrent_time < 5.0  # 100 次並發呼叫應該在 5 秒內完成
    
    def test_memory_usage_optimization(self):
        """測試記憶體使用優化"""
        config_manager = MCPConfigManager(self.temp_dir)
        
        # 載入配置
        config_manager.load_mcp_config("perf_test.json")
        
        # 檢查快取大小
        cache_size = len(config_manager._config_cache)
        assert cache_size == 1
        
        # 多次載入不應該增加快取大小
        for _ in range(10):
            config_manager.load_mcp_config("perf_test.json")
        
        assert len(config_manager._config_cache) == cache_size
        
        # 清理快取
        config_manager.reload_config()
        assert len(config_manager._config_cache) == 0


class TestMCPPagination:
    """測試 MCP 分頁功能"""
    
    def setup_method(self):
        """設定測試環境"""
        self.server_config = {
            "base_url": "http://localhost:3000/api/mcp",
            "timeout": 30
        }
        self.client = MCPClient(self.server_config)
    
    @pytest.mark.asyncio
    async def test_pagination_basic_flow(self):
        """測試基本分頁流程"""
        # 模擬分頁回應
        page_responses = [
            # 第一頁
            {
                "jsonrpc": "2.0",
                "id": 123,
                "result": {
                    "tools": [
                        {"name": "tool1", "description": "Tool 1"},
                        {"name": "tool2", "description": "Tool 2"}
                    ],
                    "nextCursor": "cursor_page_2"
                }
            },
            # 第二頁
            {
                "jsonrpc": "2.0",
                "id": 124,
                "result": {
                    "tools": [
                        {"name": "tool3", "description": "Tool 3"},
                        {"name": "tool4", "description": "Tool 4"}
                    ],
                    "nextCursor": "cursor_page_3"
                }
            },
            # 最後一頁
            {
                "jsonrpc": "2.0",
                "id": 125,
                "result": {
                    "tools": [
                        {"name": "tool5", "description": "Tool 5"}
                    ]
                    # 沒有 nextCursor 表示最後一頁
                }
            }
        ]
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = Mock()
            mock_session.closed = False
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session
            
            # 設定分頁回應
            mock_posts = []
            for response in page_responses:
                mock_resp = Mock()
                mock_resp.status = 200
                mock_resp.text = AsyncMock(return_value=json.dumps(response))
                mock_posts.append(MockAsyncContextManager(mock_resp))
            
            mock_session.post = Mock(side_effect=mock_posts)
            
            # 測試第一頁
            success, tools, next_cursor, error = await self.client.list_tools()
            assert success is True
            assert len(tools) == 2
            assert tools[0]["name"] == "tool1"
            assert tools[1]["name"] == "tool2"
            assert next_cursor == "cursor_page_2"
            assert error is None
            
            # 測試第二頁
            success, tools, next_cursor, error = await self.client.list_tools("cursor_page_2")
            assert success is True
            assert len(tools) == 2
            assert tools[0]["name"] == "tool3"
            assert tools[1]["name"] == "tool4"
            assert next_cursor == "cursor_page_3"
            assert error is None
            
            # 測試最後一頁
            success, tools, next_cursor, error = await self.client.list_tools("cursor_page_3")
            assert success is True
            assert len(tools) == 1
            assert tools[0]["name"] == "tool5"
            assert next_cursor is None  # 最後一頁
            assert error is None
    
    @pytest.mark.asyncio
    async def test_pagination_large_dataset(self):
        """測試大數據集分頁"""
        # 模擬大數據集（1000 個工具，每頁 100 個）
        total_tools = 1000
        page_size = 100
        total_pages = total_tools // page_size
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = Mock()
            mock_session.closed = False
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session
            
            def create_page_response(page_num):
                start_idx = page_num * page_size
                end_idx = min(start_idx + page_size, total_tools)
                
                tools = [
                    {"name": f"tool_{i}", "description": f"Tool {i}"}
                    for i in range(start_idx, end_idx)
                ]
                
                result = {
                    "jsonrpc": "2.0",
                    "id": 123 + page_num,
                    "result": {
                        "tools": tools
                    }
                }
                
                # 如果不是最後一頁，添加 nextCursor
                if page_num < total_pages - 1:
                    result["result"]["nextCursor"] = f"cursor_page_{page_num + 1}"
                
                return result
            
            # 創建所有頁面的回應
            page_responses = [create_page_response(i) for i in range(total_pages)]
            mock_posts = []
            for response in page_responses:
                mock_resp = Mock()
                mock_resp.status = 200
                mock_resp.text = AsyncMock(return_value=json.dumps(response))
                mock_posts.append(MockAsyncContextManager(mock_resp))
            
            mock_session.post = Mock(side_effect=mock_posts)
            
            # 測試分頁遍歷
            all_tools = []
            cursor = None
            page_count = 0
            
            while True:
                success, tools, next_cursor, error = await self.client.list_tools(cursor)
                
                assert success is True
                assert error is None
                assert len(tools) <= page_size
                
                all_tools.extend(tools)
                page_count += 1
                
                if next_cursor is None:
                    break
                
                cursor = next_cursor
            
            # 驗證結果
            assert len(all_tools) == total_tools
            assert page_count == total_pages
            
            # 驗證工具順序
            for i, tool in enumerate(all_tools):
                assert tool["name"] == f"tool_{i}"
                assert tool["description"] == f"Tool {i}"
    
    @pytest.mark.asyncio
    async def test_pagination_error_handling(self):
        """測試分頁錯誤處理"""
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = Mock()
            mock_session.closed = False
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session
            
            # 測試無效 cursor 錯誤
            error_response = {
                "jsonrpc": "2.0",
                "id": 123,
                "error": {
                    "code": -32602,
                    "message": "Invalid cursor"
                }
            }
            
            mock_resp = Mock()
            mock_resp.status = 200
            mock_resp.text = AsyncMock(return_value=json.dumps(error_response))
            mock_session.post = Mock(return_value=MockAsyncContextManager(mock_resp))
            
            success, tools, next_cursor, error = await self.client.list_tools("invalid_cursor")
            
            assert success is False
            assert tools is None
            assert next_cursor is None
            assert error == "Invalid cursor"
    
    @pytest.mark.asyncio
    async def test_pagination_empty_results(self):
        """測試分頁空結果"""
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = Mock()
            mock_session.closed = False
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session
            
            # 空結果回應
            empty_response = {
                "jsonrpc": "2.0",
                "id": 123,
                "result": {
                    "tools": []
                }
            }
            
            mock_resp = Mock()
            mock_resp.status = 200
            mock_resp.text = AsyncMock(return_value=json.dumps(empty_response))
            mock_session.post = Mock(return_value=MockAsyncContextManager(mock_resp))
            
            success, tools, next_cursor, error = await self.client.list_tools()
            
            assert success is True
            assert tools == []
            assert next_cursor is None
            assert error is None
    
    @pytest.mark.asyncio
    async def test_pagination_cursor_consistency(self):
        """測試分頁 cursor 一致性"""
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = Mock()
            mock_session.closed = False
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session
            
            # 測試不同長度的 cursor
            cursors = [
                "short",
                "medium_length_cursor",
                "very_long_cursor_with_special_characters_!@#$%^&*()_+-=[]{}|;':\",./<>?",
                "cursor_with_unicode_字符_測試",
                "cursor_with_numbers_12345_and_symbols_!@#"
            ]
            
            for cursor in cursors:
                # 創建包含該 cursor 的回應
                response = {
                    "jsonrpc": "2.0",
                    "id": 123,
                    "result": {
                        "tools": [{"name": "test_tool"}],
                        "nextCursor": cursor
                    }
                }
                
                mock_resp = Mock()
                mock_resp.status = 200
                mock_resp.text = AsyncMock(return_value=json.dumps(response))
                # 創建 async context manager for post response
                mock_post = AsyncMock()
                mock_post.__aenter__ = AsyncMock(return_value=mock_resp)
                mock_post.__aexit__ = AsyncMock(return_value=None)
                mock_session.post = Mock(return_value=MockAsyncContextManager(mock_resp))
                
                success, tools, next_cursor, error = await self.client.list_tools()
                
                assert success is True
                assert next_cursor == cursor
                
                # 驗證 cursor 作為參數傳遞
                mock_session.post.assert_called()
                call_args = mock_session.post.call_args
                request_data = call_args[1]['json']
                
                # 重置 mock 以測試下一個 cursor
                mock_session.post.reset_mock()
                
                # 使用返回的 cursor 進行下一次請求
                mock_resp2 = Mock()
                mock_resp2.status = 200
                mock_resp2.text = AsyncMock(return_value=json.dumps({
                    "jsonrpc": "2.0",
                    "id": 124,
                    "result": {"tools": []}
                }))
                # 創建 async context manager for post response
                mock_post2 = AsyncMock()
                mock_post2.__aenter__ = AsyncMock(return_value=mock_resp2)
                mock_post2.__aexit__ = AsyncMock(return_value=None)
                mock_session.post.return_value = mock_post2
                
                success, tools, next_cursor, error = await self.client.list_tools(cursor)
                assert success is True
                
                # 驗證 cursor 正確傳遞
                call_args = mock_session.post.call_args
                request_data = call_args[1]['json']
                assert request_data['params']['cursor'] == cursor
    
    @pytest.mark.asyncio
    async def test_pagination_performance_large_pages(self):
        """測試大頁面分頁效能"""
        # 模擬大頁面（每頁 10000 個工具）
        page_size = 10000
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = Mock()
            mock_session.closed = False
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session
            
            # 創建大頁面回應
            large_tools = [
                {"name": f"tool_{i}", "description": f"Tool {i}"}
                for i in range(page_size)
            ]
            
            response = {
                "jsonrpc": "2.0",
                "id": 123,
                "result": {
                    "tools": large_tools
                }
            }
            
            mock_resp = Mock()
            mock_resp.status = 200
            mock_resp.text = AsyncMock(return_value=json.dumps(response))
            mock_session.post = Mock(return_value=MockAsyncContextManager(mock_resp))
            
            # 測試處理大頁面的效能
            start_time = time.time()
            success, tools, next_cursor, error = await self.client.list_tools()
            processing_time = time.time() - start_time
            
            assert success is True
            assert len(tools) == page_size
            assert processing_time < 1.0  # 處理 10000 個工具應該在 1 秒內
    
    @pytest.mark.asyncio
    async def test_pagination_concurrent_requests(self):
        """測試並發分頁請求"""
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = Mock()
            mock_session.closed = False
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session
            
            # 模擬不同的頁面回應
            def create_response(page_id):
                return {
                    "jsonrpc": "2.0",
                    "id": page_id,
                    "result": {
                        "tools": [
                            {"name": f"tool_{page_id}_{i}", "description": f"Tool {page_id} {i}"}
                            for i in range(5)
                        ]
                    }
                }
            
            # 創建多個客戶端實例
            clients = [MCPClient(self.server_config) for _ in range(5)]
            
            # 為每個客戶端設定不同的回應
            async def test_client_pagination(client, page_id):
                response = create_response(page_id)
                mock_resp = Mock()
                mock_resp.status = 200
                mock_resp.text = AsyncMock(return_value=json.dumps(response))
                
                # 暫時替換 session
                with patch.object(client, '_session', mock_session):
                    mock_session.post = Mock(return_value=MockAsyncContextManager(mock_resp))
                    return await client.list_tools(f"cursor_{page_id}")
            
            # 並發執行分頁請求
            start_time = time.time()
            tasks = [test_client_pagination(clients[i], i) for i in range(5)]
            results = await asyncio.gather(*tasks)
            concurrent_time = time.time() - start_time
            
            # 驗證結果
            for i, (success, tools, next_cursor, error) in enumerate(results):
                assert success is True
                assert len(tools) == 5
                assert tools[0]["name"] == f"tool_{i}_0"
                assert error is None
            
            # 並發請求應該在合理時間內完成
            assert concurrent_time < 2.0