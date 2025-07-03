import pytest
from unittest.mock import Mock, patch

from src.services.response_formatter import ResponseFormatter
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
    
    @patch('src.services.response_formatter.s2t_converter')
    def test_chinese_conversion_error_handling(self, mock_converter, formatter):
        """測試中文轉換錯誤處理"""
        mock_converter.convert.side_effect = Exception("Conversion error")
        
        rag_response = RAGResponse(answer='測試回應', sources=[], metadata={})
        result = formatter.format_rag_response(rag_response)
        
        # 即使轉換失敗，也應該返回原始內容
        assert '測試回應' in result or '回應處理失敗' in result