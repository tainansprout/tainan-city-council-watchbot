import pytest
from unittest.mock import Mock, patch, MagicMock
import re

from src.models.openai_model import OpenAIModel
from src.models.base import FileInfo, RAGResponse, ChatMessage


class TestOpenAIModelEnhanced:
    """OpenAI 模型增強測試 - 包含重構後的功能"""
    
    @pytest.fixture
    def openai_model(self):
        return OpenAIModel(
            api_key='test_key',
            assistant_id='test_assistant',
            base_url='https://api.openai.com/v1'
        )
    
    def test_get_file_references_success(self, openai_model):
        """測試檔案引用字典獲取成功"""
        # 模擬檔案列表回應
        mock_files = [
            FileInfo(file_id='file-123', filename='document1.txt'),
            FileInfo(file_id='file-456', filename='report.json'),
            FileInfo(file_id='file-789', filename='data.csv')
        ]
        
        with patch.object(openai_model, 'list_files', return_value=(True, mock_files, None)):
            result = openai_model.get_file_references()
            
            expected = {
                'file-123': 'document1',
                'file-456': 'report',
                'file-789': 'data.csv'  # CSV 不會被移除（只移除 txt 和 json）
            }
            assert result == expected
    
    def test_get_file_references_failure(self, openai_model):
        """測試檔案引用字典獲取失敗"""
        with patch.object(openai_model, 'list_files', return_value=(False, None, 'API Error')):
            result = openai_model.get_file_references()
            assert result == {}
    
    def test_get_file_references_exception(self, openai_model):
        """測試檔案引用字典獲取異常"""
        with patch.object(openai_model, 'list_files', side_effect=Exception('Connection error')):
            result = openai_model.get_file_references()
            assert result == {}
    
    def test_get_response_data_success(self, openai_model):
        """測試從回應中提取助理數據成功"""
        mock_response = {
            'data': [
                {
                    'role': 'user',
                    'content': [{'type': 'text', 'text': {'value': 'User message'}}]
                },
                {
                    'role': 'assistant',
                    'content': [{'type': 'text', 'text': {'value': 'Assistant response'}}]
                }
            ]
        }
        
        result = openai_model._get_response_data(mock_response)
        
        assert result is not None
        assert result['role'] == 'assistant'
        assert result['content'][0]['text']['value'] == 'Assistant response'
    
    def test_get_response_data_no_assistant(self, openai_model):
        """測試從回應中提取助理數據失敗（無助理回應）"""
        mock_response = {
            'data': [
                {
                    'role': 'user',
                    'content': [{'type': 'text', 'text': {'value': 'User message'}}]
                }
            ]
        }
        
        result = openai_model._get_response_data(mock_response)
        assert result is None
    
    def test_get_response_data_malformed(self, openai_model):
        """測試處理格式不正確的回應"""
        mock_response = {'invalid': 'format'}
        
        result = openai_model._get_response_data(mock_response)
        assert result is None
    
    def test_process_openai_response_with_citations(self, openai_model):
        """測試處理帶有引用的 OpenAI 回應"""
        # 模擬包含引用的 thread_messages
        mock_thread_messages = {
            'data': [
                {
                    'role': 'assistant',
                    'content': [
                        {
                            'type': 'text',
                            'text': {
                                'value': '根據文件 【0†source】，今天天氣很好。',
                                'annotations': [
                                    {
                                        'text': '【0†source】',
                                        'file_citation': {
                                            'file_id': 'file-123',
                                            'quote': '今天天氣晴朗'
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }
        
        # 模擬檔案字典
        with patch.object(openai_model, 'get_file_references', return_value={'file-123': 'weather_report'}):
            content, sources = openai_model._process_openai_response(mock_thread_messages)
            
            # 驗證內容處理
            assert '[1]' in content
            assert '【0†source】' not in content  # 原始引用應被替換
            assert '[1]: weather_report' in content
            
            # 驗證來源資訊
            assert len(sources) == 1
            assert sources[0]['file_id'] == 'file-123'
            assert sources[0]['filename'] == 'weather_report'
            assert sources[0]['quote'] == '今天天氣晴朗'
    
    def test_process_openai_response_without_citations(self, openai_model):
        """測試處理無引用的 OpenAI 回應"""
        mock_thread_messages = {
            'data': [
                {
                    'role': 'assistant',
                    'content': [
                        {
                            'type': 'text',
                            'text': {
                                'value': '這是一個普通的回應，沒有引用。',
                                'annotations': []
                            }
                        }
                    ]
                }
            ]
        }
        
        content, sources = openai_model._process_openai_response(mock_thread_messages)
        
        assert content == '這是一個普通的回應，沒有引用。'
        assert sources == []
    
    def test_process_openai_response_multiple_citations(self, openai_model):
        """測試處理多個引用的 OpenAI 回應"""
        mock_thread_messages = {
            'data': [
                {
                    'role': 'assistant',
                    'content': [
                        {
                            'type': 'text',
                            'text': {
                                'value': '根據 【0†source】 和 【1†source】，結論是...',
                                'annotations': [
                                    {
                                        'text': '【0†source】',
                                        'file_citation': {
                                            'file_id': 'file-123',
                                            'quote': '第一個引用'
                                        }
                                    },
                                    {
                                        'text': '【1†source】',
                                        'file_citation': {
                                            'file_id': 'file-456',
                                            'quote': '第二個引用'
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }
        
        with patch.object(openai_model, 'get_file_references', return_value={
            'file-123': 'doc1',
            'file-456': 'doc2'
        }):
            content, sources = openai_model._process_openai_response(mock_thread_messages)
            
            # 驗證多個引用的處理
            assert '[1]' in content and '[2]' in content
            assert '[1]: doc1' in content
            assert '[2]: doc2' in content
            assert len(sources) == 2
    
    def test_process_openai_response_empty_data(self, openai_model):
        """測試處理空數據的 OpenAI 回應"""
        mock_thread_messages = {'data': []}
        
        content, sources = openai_model._process_openai_response(mock_thread_messages)
        
        assert content == ''
        assert sources == []
    
    def test_process_openai_response_error_handling(self, openai_model):
        """測試 OpenAI 回應處理的錯誤處理"""
        # 測試格式不正確的數據
        malformed_data = {'invalid': 'format'}
        
        content, sources = openai_model._process_openai_response(malformed_data)
        
        assert content == ''
        assert sources == []
    
    @patch('src.models.openai_model.s2t_converter', create=True)
    def test_process_openai_response_chinese_conversion(self, mock_converter, openai_model):
        """測試 OpenAI 回應的中文轉換"""
        mock_converter.convert.side_effect = lambda x: x.replace('简', '簡')
        
        mock_thread_messages = {
            'data': [
                {
                    'role': 'assistant',
                    'content': [
                        {
                            'type': 'text',
                            'text': {
                                'value': '这是简体中文回应',
                                'annotations': []
                            }
                        }
                    ]
                }
            ]
        }
        
        content, sources = openai_model._process_openai_response(mock_thread_messages)
        
        # 驗證轉換器被調用並且內容被處理
        mock_converter.convert.assert_called()
        # 驗證轉換結果（簡體變繁體）
        assert '這是簡體中文回應' in content
    
    def test_query_with_rag_integration(self, openai_model):
        """測試 query_with_rag 與引用處理的整合"""
        # 模擬完整的 RAG 流程
        with patch.object(openai_model, 'create_thread') as mock_create_thread, \
             patch.object(openai_model, 'add_message_to_thread') as mock_add_message, \
             patch.object(openai_model, 'run_assistant') as mock_run_assistant, \
             patch.object(openai_model, '_process_openai_response') as mock_process:
            
            # 設定模擬
            mock_create_thread.return_value = (True, Mock(thread_id='new_thread'), None)
            mock_add_message.return_value = (True, None)
            mock_run_assistant.return_value = (True, Mock(
                content='原始回應',
                metadata={'thread_messages': {'data': []}}
            ), None)
            mock_process.return_value = ('處理後的回應 [1]\n\n[1]: 檔案', [{'file_id': 'file-123'}])
            
            # 執行測試
            is_successful, rag_response, error = openai_model.query_with_rag('測試查詢')
            
            # 驗證結果
            assert is_successful
            assert rag_response.answer == '處理後的回應 [1]\n\n[1]: 檔案'
            assert len(rag_response.sources) == 1
            assert rag_response.metadata['model'] == 'openai-assistant'
            
            # 驗證調用順序
            mock_create_thread.assert_called_once()
            mock_add_message.assert_called_once()
            mock_run_assistant.assert_called_once()
            mock_process.assert_called_once()
    
    def test_complex_citation_pattern_detection(self, openai_model):
        """測試複雜引用格式的偵測"""
        mock_thread_messages = {
            'data': [
                {
                    'role': 'assistant',
                    'content': [
                        {
                            'type': 'text',
                            'text': {
                                'value': '根據【複雜引用格式】的文件，結論是...',
                                'annotations': []
                            }
                        }
                    ]
                }
            ]
        }
        
        with patch('src.models.openai_model.logger') as mock_logger:
            content, sources = openai_model._process_openai_response(mock_thread_messages)
            
            # 驗證日誌記錄了複雜引用格式的偵測
            mock_logger.debug.assert_called()
            # 檢查是否有記錄複雜引用格式
            debug_calls = [call[0][0] for call in mock_logger.debug.call_args_list]
            assert any('複雜引用格式' in call for call in debug_calls)
    
    def test_file_references_caching_behavior(self, openai_model):
        """測試檔案引用的快取行為（多次調用）"""
        mock_files = [FileInfo(file_id='file-123', filename='test.txt')]
        
        with patch.object(openai_model, 'list_files', return_value=(True, mock_files, None)) as mock_list:
            # 第一次調用
            result1 = openai_model.get_file_references()
            # 第二次調用  
            result2 = openai_model.get_file_references()
            
            # 驗證每次都會調用 list_files（沒有快取）
            assert mock_list.call_count == 2
            assert result1 == result2 == {'file-123': 'test'}