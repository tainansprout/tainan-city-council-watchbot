"""
回應服務測試
測試 src/services/response.py 中的 ResponseFormatter
"""
import pytest
from unittest.mock import Mock, patch

from src.services.response import ResponseFormatter
from src.models.base import RAGResponse


class TestResponseFormatter:
    """ResponseFormatter 單元測試"""
    
    @pytest.fixture
    def formatter(self):
        config = {'text_processing': {}}
        return ResponseFormatter(config)
    
    def test_initialization(self, formatter):
        """測試 ResponseFormatter 初始化"""
        assert formatter.config is not None
        assert hasattr(formatter, 'format_rag_response')
        assert hasattr(formatter, '_format_sources')
    
    def test_format_rag_response_with_sources(self, formatter):
        """測試帶有來源的 RAG 回應格式化"""
        rag_response = RAGResponse(
            answer='這是一個測試回應',
            sources=[
                {'filename': 'document1.txt', 'type': 'file_citation'},
                {'filename': 'document2.json', 'type': 'file_citation'}
            ],
            metadata={}
        )
        
        result = formatter.format_rag_response(rag_response)
        
        assert '這是一個測試回應' in result
        assert '[1]: document1' in result
        assert '[2]: document2' in result
    
    def test_format_rag_response_without_sources(self, formatter):
        """測試無來源的 RAG 回應格式化"""
        rag_response = RAGResponse(
            answer='這是一個無來源的回應',
            sources=[],
            metadata={}
        )
        
        result = formatter.format_rag_response(rag_response)
        
        assert result == '這是一個無來源的回應'
        assert '[1]:' not in result
    
    def test_format_sources_openai_format(self, formatter):
        """測試 OpenAI 格式來源"""
        sources = [
            {'file_id': 'file-123', 'filename': 'doc1.txt', 'type': 'file_citation'},
            {'file_id': 'file-456', 'filename': 'doc2.json', 'type': 'file_citation'}
        ]
        
        result = formatter._format_sources(sources)
        
        assert '[1]: doc1' in result
        assert '[2]: doc2' in result
    
    def test_format_sources_gemini_format(self, formatter):
        """測試 Gemini 格式來源"""
        sources = [
            {'document_id': 'doc-123', 'title': 'Gemini Document 1', 'type': 'document'},
            {'document_id': 'doc-456', 'filename': 'gemini_doc2.txt', 'type': 'document'}
        ]
        
        result = formatter._format_sources(sources)
        
        assert '[1]: Gemini Document 1' in result
        assert '[2]: gemini_doc2' in result  # 副檔名被移除
    
    def test_format_sources_anthropic_format(self, formatter):
        """測試 Anthropic 格式來源"""
        sources = [
            {'reference_id': 'ref-123', 'filename': 'anthropic_doc.txt', 'type': 'reference'},
            {'reference_id': 'ref-456', 'title': 'Anthropic Reference', 'type': 'reference'}
        ]
        
        result = formatter._format_sources(sources)
        
        assert '[1]: anthropic_doc' in result
        assert '[2]: Anthropic Reference' in result
    
    def test_format_sources_generic_format(self, formatter):
        """測試通用格式來源"""
        sources = [
            {'filename': 'generic_file.pdf', 'id': 'gen-123'},
            {'filename': 'another_file.docx'}
        ]
        
        result = formatter._format_sources(sources)
        
        assert '[1]: generic_file' in result  # PDF 副檔名被移除
        assert '[2]: another_file' in result  # DOCX 副檔名被移除
    
    def test_format_sources_malformed_data(self, formatter):
        """測試格式不正確的來源資料"""
        sources = [
            {'invalid': 'format'},  # 無效格式
            None,  # None 值
            {'filename': None, 'type': 'unknown'},  # 檔名為 None
            {}  # 空字典
        ]
        
        result = formatter._format_sources(sources)
        
        # 應該能處理而不崩潰，但可能返回空字串（因為 None 值被跳過）
        assert isinstance(result, str)
        # 至少應該有一個有效的來源（第一個有效的字典）
        assert '[1]: Source-1' in result or len(result) == 0
    
    def test_format_sources_empty_list(self, formatter):
        """測試空來源列表"""
        result = formatter._format_sources([])
        assert result == ""
    
    def test_format_sources_duplicate_removal(self, formatter):
        """測試重複來源移除"""
        sources = [
            {'file_id': 'file-123', 'filename': 'doc.txt', 'type': 'file_citation'},
            {'file_id': 'file-123', 'filename': 'doc.txt', 'type': 'file_citation'},  # 重複
            {'file_id': 'file-456', 'filename': 'other.txt', 'type': 'file_citation'}
        ]
        
        result = formatter._format_sources(sources)
        
        # 只應該有 2 個來源（重複的被移除）
        lines = [line for line in result.split('\n') if line.strip()]
        assert len(lines) == 2
        assert any('doc' in line for line in lines)
        assert any('other' in line for line in lines)
    
    def test_extract_source_info_with_fallback(self, formatter):
        """測試來源資訊提取的降級處理"""
        # 測試當沒有明確檔名時的處理
        source = {'file_id': 'very-long-file-id-123456789'}
        
        info = formatter._extract_source_info(source, 1)
        
        assert info['filename'] == 'File-very-lon'  # 截取前8字符
        assert info['key'] == 'very-long-file-id-123456789'
    
    def test_format_simple_response(self, formatter):
        """測試簡單回應格式化"""
        content = '这是简体中文回应'
        
        result = formatter.format_simple_response(content)
        
        # 應該轉換為繁體中文（或保持原狀如果 OpenCC 不可用）
        assert isinstance(result, str)
        assert len(result) > 0  # 至少應該有內容
    
    def test_error_handling_in_format_rag_response(self, formatter):
        """測試 format_rag_response 的錯誤處理"""
        # 測試 None 回應
        rag_response = RAGResponse(answer=None, sources=[], metadata={})
        result = formatter.format_rag_response(rag_response)
        assert '回應處理失敗' in result
        
        # 測試空回應
        rag_response = RAGResponse(answer='', sources=[], metadata={})
        result = formatter.format_rag_response(rag_response)
        assert result == ''
    
    @patch('src.services.response.s2t_converter')
    def test_chinese_conversion_error_handling(self, mock_converter, formatter):
        """測試中文轉換錯誤處理"""
        mock_converter.convert.side_effect = Exception("Conversion error")
        
        rag_response = RAGResponse(answer='測試回應', sources=[], metadata={})
        result = formatter.format_rag_response(rag_response)
        
        # 即使轉換失敗，也應該返回原始內容
        assert '測試回應' in result or '回應處理失敗' in result
    
    @patch('src.services.response.s2t_converter')
    def test_chinese_conversion_simple_to_traditional(self, mock_converter, formatter):
        """測試簡體轉繁體中文轉換（來自 OpenAI 模型測試）"""
        # 模擬簡體轉繁體的轉換
        mock_converter.convert.side_effect = lambda x: x.replace('这是简体中文回应', '這是簡體中文回應')
        
        rag_response = RAGResponse(answer='这是简体中文回应', sources=[], metadata={})
        result = formatter.format_rag_response(rag_response)
        
        # 驗證轉換器被調用
        mock_converter.convert.assert_called()
        # 驗證轉換結果（簡體變繁體）
        assert '這是簡體中文回應' in result


class TestResponseFormatterDisclaimer:
    """ResponseFormatter 免責聲明整合測試"""
    
    def test_format_rag_response_with_disclaimer(self):
        """測試 RAG 回應包含免責聲明"""
        config = {
            'text_processing': {
                'disclaimer': '本回應僅供參考，請以官方資訊為準。'
            }
        }
        formatter = ResponseFormatter(config)
        
        rag_response = RAGResponse(
            answer='這是測試回應內容',
            sources=[],
            metadata={}
        )
        
        result = formatter.format_rag_response(rag_response)
        
        # 驗證回應內容和免責聲明都存在
        assert '這是測試回應內容' in result
        assert '本回應僅供參考，請以官方資訊為準。' in result
        # 驗證格式正確（有兩個換行分隔）
        assert '這是測試回應內容\n\n本回應僅供參考，請以官方資訊為準。' in result
    
    def test_format_rag_response_with_disclaimer_and_sources(self):
        """測試包含免責聲明和來源的 RAG 回應"""
        config = {
            'text_processing': {
                'disclaimer': '測試免責聲明'
            }
        }
        formatter = ResponseFormatter(config)
        
        rag_response = RAGResponse(
            answer='回應內容',
            sources=[
                {'filename': 'document1.txt', 'type': 'file_citation'},
                {'filename': 'document2.pdf', 'type': 'file_citation'}
            ],
            metadata={}
        )
        
        result = formatter.format_rag_response(rag_response)
        
        # 驗證順序：內容 + 免責聲明 + 來源
        assert '回應內容' in result
        assert '測試免責聲明' in result
        assert '[1]: document1' in result
        assert '[2]: document2' in result
        
        # 驗證結構：回應內容 -> 免責聲明 -> 來源
        lines = result.split('\n')
        content_line = None
        disclaimer_line = None
        source_lines = []
        
        for i, line in enumerate(lines):
            if '回應內容' in line:
                content_line = i
            elif '測試免責聲明' in line:
                disclaimer_line = i
            elif '[1]:' in line or '[2]:' in line:
                source_lines.append(i)
        
        assert content_line is not None
        assert disclaimer_line is not None
        assert len(source_lines) == 2
        # 免責聲明應該在內容後、來源前
        assert content_line < disclaimer_line < source_lines[0]
    
    def test_format_rag_response_without_disclaimer_config(self):
        """測試沒有免責聲明配置的情況"""
        config = {'text_processing': {}}
        formatter = ResponseFormatter(config)
        
        rag_response = RAGResponse(
            answer='測試回應內容',
            sources=[],
            metadata={}
        )
        
        result = formatter.format_rag_response(rag_response)
        
        # 應該只有回應內容，沒有免責聲明
        assert result == '測試回應內容'
    
    def test_format_rag_response_empty_disclaimer(self):
        """測試空免責聲明配置"""
        config = {
            'text_processing': {
                'disclaimer': ''
            }
        }
        formatter = ResponseFormatter(config)
        
        rag_response = RAGResponse(
            answer='測試回應內容',
            sources=[],
            metadata={}
        )
        
        result = formatter.format_rag_response(rag_response)
        
        # 空免責聲明應該不添加任何內容
        assert result == '測試回應內容'
    
    def test_format_rag_response_disclaimer_in_text_processing_only(self):
        """測試只支援 text_processing 中的免責聲明配置"""
        config = {
            'disclaimer': '根層級免責聲明',  # 這個不會被使用
            'text_processing': {
                'disclaimer': '正確的免責聲明配置'
            }
        }
        formatter = ResponseFormatter(config)
        
        rag_response = RAGResponse(
            answer='測試回應',
            sources=[],
            metadata={}
        )
        
        result = formatter.format_rag_response(rag_response)
        
        assert '測試回應' in result
        assert '正確的免責聲明配置' in result
        assert '根層級免責聲明' not in result  # 根層級的不應該被使用
    
    @patch('src.services.response.add_disclaimer')
    def test_format_rag_response_disclaimer_function_called(self, mock_add_disclaimer):
        """測試 add_disclaimer 函數被正確調用"""
        config = {
            'text_processing': {
                'disclaimer': '測試免責聲明'
            }
        }
        formatter = ResponseFormatter(config)
        
        # 模擬 add_disclaimer 返回值
        mock_add_disclaimer.return_value = '處理後的內容與免責聲明'
        
        rag_response = RAGResponse(
            answer='原始回應',
            sources=[],
            metadata={}
        )
        
        result = formatter.format_rag_response(rag_response)
        
        # 驗證 add_disclaimer 被調用且傳入正確參數
        mock_add_disclaimer.assert_called_once()
        call_args = mock_add_disclaimer.call_args
        assert '原始回應' in call_args[0][0]  # 第一個參數是轉換後的文本
        assert call_args[0][1] == config  # 第二個參數是配置
        
        # 驗證返回值來自 add_disclaimer
        assert '處理後的內容與免責聲明' in result
    
    def test_format_rag_response_disclaimer_with_chinese_conversion(self):
        """測試免責聲明與中文轉換的整合"""
        config = {
            'text_processing': {
                'disclaimer': '本回答僅供參考'
            }
        }
        formatter = ResponseFormatter(config)
        
        # 使用簡體中文作為輸入（會被轉換為繁體）
        rag_response = RAGResponse(
            answer='这是简体中文回应',
            sources=[],
            metadata={}
        )
        
        result = formatter.format_rag_response(rag_response)
        
        # 驗證中文轉換和免責聲明都正確處理
        assert '這是簡體中文回應' in result  # 轉換為繁體
        assert '本回答僅供參考' in result
        # 驗證順序正確
        assert '這是簡體中文回應\n\n本回答僅供參考' in result
    
    def test_format_rag_response_disclaimer_error_handling(self):
        """測試免責聲明處理的錯誤處理"""
        config = {
            'text_processing': {
                'disclaimer': '測試免責聲明'
            }
        }
        formatter = ResponseFormatter(config)
        
        # 測試 None 回應
        rag_response = RAGResponse(answer=None, sources=[], metadata={})
        result = formatter.format_rag_response(rag_response)
        
        # 即使回應內容為 None，也應該能正確處理（返回錯誤訊息）
        assert '回應處理失敗' in result
    
    def test_format_rag_response_disclaimer_multiline(self):
        """測試多行免責聲明"""
        config = {
            'text_processing': {
                'disclaimer': '第一行免責聲明\n第二行免責聲明'
            }
        }
        formatter = ResponseFormatter(config)
        
        rag_response = RAGResponse(
            answer='測試回應',
            sources=[],
            metadata={}
        )
        
        result = formatter.format_rag_response(rag_response)
        
        # 驗證多行免責聲明正確添加
        assert '測試回應' in result
        assert '第一行免責聲明' in result
        assert '第二行免責聲明' in result
        # 驗證格式：回應 + 兩個換行 + 多行免責聲明
        expected = '測試回應\n\n第一行免責聲明\n第二行免責聲明'
        assert expected in result
    
    def test_format_simple_response_with_disclaimer(self):
        """測試簡單回應包含免責聲明"""
        config = {
            'text_processing': {
                'disclaimer': '測試免責聲明'
            }
        }
        formatter = ResponseFormatter(config)
        
        # format_simple_response 現在也應該添加免責聲明
        result = formatter.format_simple_response('簡單回應內容')
        
        # 應該包含原始內容和免責聲明
        assert '簡單回應內容' in result
        assert '測試免責聲明' in result
        assert '簡單回應內容\n\n測試免責聲明' in result


class TestResponseFormatterReferenceMarkers:
    """ResponseFormatter 引用標記過濾測試"""
    
    def test_format_rag_response_with_reference_markers(self):
        """測試 RAG 回應中引用標記的過濾"""
        config = {'text_processing': {}}
        formatter = ResponseFormatter(config)
        
        rag_response = RAGResponse(
            answer='這是測試回應【4:0】【5:5】【6:6】，後面還有更多內容。',
            sources=[],
            metadata={}
        )
        
        result = formatter.format_rag_response(rag_response)
        
        # 驗證引用標記被移除
        assert '這是測試回應，後面還有更多內容。' in result
        assert '【4:0】' not in result
        assert '【5:5】' not in result
        assert '【6:6】' not in result
    
    def test_format_rag_response_with_markers_and_disclaimer(self):
        """測試同時有引用標記和免責聲明的 RAG 回應"""
        config = {
            'text_processing': {
                'disclaimer': '測試免責聲明'
            }
        }
        formatter = ResponseFormatter(config)
        
        rag_response = RAGResponse(
            answer='測試內容【1:2】【3:4】更多內容【5:6】。',
            sources=[],
            metadata={}
        )
        
        result = formatter.format_rag_response(rag_response)
        
        # 驗證引用標記被移除且免責聲明被添加
        assert '測試內容更多內容。' in result
        assert '測試免責聲明' in result
        assert '【1:2】' not in result
        assert '【3:4】' not in result
        assert '【5:6】' not in result
    
    def test_format_rag_response_markers_and_sources(self):
        """測試引用標記過濾與來源顯示的整合"""
        config = {
            'text_processing': {
                'disclaimer': '免責聲明'
            }
        }
        formatter = ResponseFormatter(config)
        
        rag_response = RAGResponse(
            answer='回應內容【1:2】【3:4】結尾。',
            sources=[
                {'filename': 'test.txt', 'type': 'file_citation'}
            ],
            metadata={}
        )
        
        result = formatter.format_rag_response(rag_response)
        
        # 驗證順序：過濾後的內容 + 免責聲明 + 來源
        assert '回應內容結尾。' in result
        assert '免責聲明' in result
        assert '[1]: test' in result
        assert '【1:2】' not in result
        assert '【3:4】' not in result
    
    def test_format_simple_response_with_reference_markers(self):
        """測試簡單回應中引用標記的過濾"""
        config = {'text_processing': {}}
        formatter = ResponseFormatter(config)
        
        content = '簡單回應【7:8】【9:10】內容。'
        result = formatter.format_simple_response(content)
        
        # 驗證引用標記被移除
        assert result == '簡單回應內容。'
        assert '【7:8】' not in result
        assert '【9:10】' not in result
    
    def test_format_simple_response_with_markers_and_disclaimer(self):
        """測試簡單回應中引用標記過濾和免責聲明"""
        config = {
            'text_processing': {
                'disclaimer': '簡單回應免責聲明'
            }
        }
        formatter = ResponseFormatter(config)
        
        content = '測試內容【11:12】【13:14】結尾。'
        result = formatter.format_simple_response(content)
        
        # 驗證引用標記被移除且免責聲明被添加
        assert '測試內容結尾。' in result
        assert '簡單回應免責聲明' in result
        assert '【11:12】' not in result
        assert '【13:14】' not in result
    
    def test_format_responses_no_markers(self):
        """測試沒有引用標記的回應"""
        config = {
            'text_processing': {
                'disclaimer': '免責聲明'
            }
        }
        formatter = ResponseFormatter(config)
        
        # 測試 RAG 回應
        rag_response = RAGResponse(
            answer='沒有引用標記的內容。',
            sources=[],
            metadata={}
        )
        
        rag_result = formatter.format_rag_response(rag_response)
        assert '沒有引用標記的內容。' in rag_result
        assert '免責聲明' in rag_result
        
        # 測試簡單回應
        simple_result = formatter.format_simple_response('沒有引用標記的簡單內容。')
        assert '沒有引用標記的簡單內容。' in simple_result
        assert '免責聲明' in simple_result
    
    def test_format_responses_only_markers(self):
        """測試只有引用標記的回應"""
        config = {
            'text_processing': {
                'disclaimer': '免責聲明'
            }
        }
        formatter = ResponseFormatter(config)
        
        # 測試 RAG 回應
        rag_response = RAGResponse(
            answer='【1:2】【3:4】【5:6】',
            sources=[],
            metadata={}
        )
        
        rag_result = formatter.format_rag_response(rag_response)
        assert '免責聲明' in rag_result
        assert '【1:2】' not in rag_result
        
        # 測試簡單回應
        simple_result = formatter.format_simple_response('【7:8】【9:10】')
        assert '免責聲明' in simple_result
        assert '【7:8】' not in simple_result


class TestJSONResponse:
    """測試 JSON 回應處理"""
    
    @pytest.fixture
    def formatter(self):
        config = {'text_processing': {}}
        return ResponseFormatter(config)
    
    def test_json_response_basic(self, formatter):
        """測試基本 JSON 回應"""
        data = {'message': 'Hello', 'status': 'success'}
        response = formatter.json_response(data)
        
        # 檢查回應類型和狀態碼
        assert response.status_code == 200
        assert response.content_type == 'application/json; charset=utf-8'
        
        # 檢查內容
        import json
        content = json.loads(response.get_data(as_text=True))
        assert content['message'] == 'Hello'
        assert content['status'] == 'success'
    
    def test_json_response_chinese_text(self, formatter):
        """測試中文內容的 JSON 回應"""
        data = {
            'name': '台南議會觀測機器人',
            'message': '測試中文回應',
            'error': '需要先登入'
        }
        response = formatter.json_response(data)
        
        # 檢查狀態和編碼
        assert response.status_code == 200
        assert 'charset=utf-8' in response.content_type
        
        # 檢查中文內容正確輸出（不是 Unicode 編碼）
        content_text = response.get_data(as_text=True)
        assert '台南議會觀測機器人' in content_text
        assert '測試中文回應' in content_text
        assert '需要先登入' in content_text
        
        # 確保不是 Unicode 轉義格式
        assert '\\u' not in content_text
    
    def test_json_response_custom_status_code(self, formatter):
        """測試自定義狀態碼"""
        data = {'error': '密碼錯誤', 'success': False}
        response = formatter.json_response(data, status_code=401)
        
        assert response.status_code == 401
        assert response.content_type == 'application/json; charset=utf-8'
        
        import json
        content = json.loads(response.get_data(as_text=True))
        assert content['error'] == '密碼錯誤'
        assert content['success'] is False
    
    def test_json_response_complex_data(self, formatter):
        """測試複雜資料結構"""
        data = {
            'platforms': ['line', 'discord'],
            'models': {
                'provider': 'openai',
                'available_providers': ['openai', 'ollama']
            },
            'config': {
                'enabled': True,
                'max_length': 1000
            }
        }
        response = formatter.json_response(data)
        
        assert response.status_code == 200
        
        import json
        content = json.loads(response.get_data(as_text=True))
        assert content['platforms'] == ['line', 'discord']
        assert content['models']['provider'] == 'openai'
        assert content['config']['enabled'] is True
    
    def test_json_response_error_handling(self, formatter):
        """測試錯誤處理"""
        # 創建一個無法序列化的物件
        import datetime
        
        class UnserializableObject:
            def __init__(self):
                self.created = datetime.datetime.now()
        
        data = {
            'message': 'test',
            'unserializable': UnserializableObject()  # 這會導致 JSON 序列化失敗
        }
        
        response = formatter.json_response(data)
        
        # 應該返回錯誤回應
        assert response.status_code == 500
        assert response.content_type == 'application/json; charset=utf-8'
        
        import json
        content = json.loads(response.get_data(as_text=True))
        assert content['error'] == '回應處理失敗'
    
    def test_json_response_empty_data(self, formatter):
        """測試空資料"""
        data = {}
        response = formatter.json_response(data)
        
        assert response.status_code == 200
        assert response.content_type == 'application/json; charset=utf-8'
        
        import json
        content = json.loads(response.get_data(as_text=True))
        assert content == {}
    
    def test_json_response_none_values(self, formatter):
        """測試包含 None 值的資料"""
        data = {
            'message': None,
            'user': 'test_user',
            'data': None,
            'success': True
        }
        response = formatter.json_response(data)
        
        assert response.status_code == 200
        
        import json
        content = json.loads(response.get_data(as_text=True))
        assert content['message'] is None
        assert content['user'] == 'test_user'
        assert content['data'] is None
        assert content['success'] is True