import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from src.utils import (
    preprocess_text, postprocess_text, get_date_string,
    detect_none_references, get_content_and_reference,
    check_token_valid, get_file_dict
)


class TestTextProcessing:
    """文字處理工具測試"""
    
    def test_get_date_string_today(self):
        with patch('src.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 15, 10, 30, 0)
            
            result = get_date_string("today")
            assert result == "2024/01/15"
    
    def test_get_date_string_tomorrow(self):
        with patch('src.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 15, 10, 30, 0)
            mock_datetime.timedelta = timedelta  # 確保 timedelta 可用
            
            result = get_date_string("tomorrow")
            assert result == "2024/01/16"
    
    def test_get_date_string_yesterday(self):
        with patch('src.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 15, 10, 30, 0)
            mock_datetime.timedelta = timedelta
            
            result = get_date_string("yesterday")
            assert result == "2024/01/14"
    
    def test_get_date_string_invalid(self):
        with pytest.raises(ValueError, match="day 參數必須是"):
            get_date_string("invalid_day")
    
    def test_preprocess_text_with_date_replacement(self):
        config = {
            'text_processing': {
                'preprocessors': [
                    {'type': 'replace_date_string'}
                ]
            }
        }
        
        with patch('src.utils.get_date_string') as mock_get_date:
            mock_get_date.side_effect = lambda day: {
                'today': '2024/01/15',
                'tomorrow': '2024/01/16',
                'yesterday': '2024/01/14'
            }[day]
            
            text = "今天的天氣如何？明天會下雨嗎？昨天發生了什麼？"
            result = preprocess_text(text, config)
            
            assert "2024/01/15" in result
            assert "2024/01/16" in result
            assert "2024/01/14" in result
    
    def test_preprocess_text_without_preprocessors(self):
        config = {'text_processing': {}}
        text = "今天的天氣如何？"
        
        result = preprocess_text(text, config)
        assert result == text  # 應該不變
    
    def test_postprocess_text_with_replacements(self):
        config = {
            'text_processing': {
                'post-replacements': [
                    {'pattern': r'OpenAI', 'replacement': 'AI助理'},
                    {'pattern': r'GPT', 'replacement': '語言模型'}
                ]
            }
        }
        
        text = "OpenAI 的 GPT 模型很強大"
        result = postprocess_text(text, config)
        
        assert "AI助理" in result
        assert "語言模型" in result
        assert "OpenAI" not in result
        assert "GPT" not in result
    
    def test_postprocess_text_without_replacements(self):
        config = {'text_processing': {}}
        text = "測試文字"
        
        result = postprocess_text(text, config)
        assert result == text


class TestReferenceDetection:
    """引用檢測測試"""
    
    def test_detect_none_references_with_none(self):
        text = "這裡是回應 [1]: None 的內容"
        assert detect_none_references(text) is True
    
    def test_detect_none_references_without_none(self):
        text = "這裡是回應 [1]: 有效引用 的內容"
        assert detect_none_references(text) is False
    
    def test_detect_none_references_multiple_references(self):
        text = "回應 [1]: 有效引用 [2]: None [3]: 另一個引用"
        assert detect_none_references(text) is True
    
    def test_detect_none_references_empty_text(self):
        assert detect_none_references("") is False


class TestContentAndReference:
    """內容和引用處理測試"""
    
    def test_get_content_and_reference_with_annotations(self):
        response = {
            'data': [
                {
                    'role': 'assistant',
                    'content': [
                        {
                            'type': 'text',
                            'text': {
                                'value': '根據文件【0†source】的內容...',
                                'annotations': [
                                    {
                                        'text': '【0†source】',
                                        'file_citation': {
                                            'file_id': 'file_123'
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }
        
        file_dict = {'file_123': 'document'}
        
        with patch('src.utils.s2t_converter') as mock_converter:
            mock_converter.convert.return_value = '根據文件[1]的內容...'
            
            result = get_content_and_reference(response, file_dict)
            
            assert '[1]' in result
            assert '[1]: document' in result
    
    def test_get_content_and_reference_no_assistant_response(self):
        response = {
            'data': [
                {
                    'role': 'user',
                    'content': [{'type': 'text', 'text': {'value': 'User message'}}]
                }
            ]
        }
        
        result = get_content_and_reference(response, {})
        assert result == ''
    
    def test_get_content_and_reference_no_annotations(self):
        response = {
            'data': [
                {
                    'role': 'assistant',
                    'content': [
                        {
                            'type': 'text',
                            'text': {
                                'value': '這是沒有引用的回應',
                                'annotations': []
                            }
                        }
                    ]
                }
            ]
        }
        
        with patch('src.utils.s2t_converter') as mock_converter:
            mock_converter.convert.return_value = '這是沒有引用的回應'
            
            result = get_content_and_reference(response, {})
            assert result == '這是沒有引用的回應'


class TestModelValidation:
    """模型驗證測試"""
    
    def test_check_token_valid_success(self):
        mock_model = Mock()
        mock_model.check_token_valid.return_value = (True, None, None)
        
        result = check_token_valid(mock_model)
        assert result is True
    
    def test_check_token_valid_failure(self):
        mock_model = Mock()
        mock_model.check_token_valid.return_value = (False, None, 'Invalid token')
        
        with pytest.raises(ValueError, match='Invalid API token'):
            check_token_valid(mock_model)
    
    def test_get_file_dict_success(self):
        mock_model = Mock()
        mock_model.list_files.return_value = (
            True,
            {
                'data': [
                    {'id': 'file_1', 'filename': 'document1.txt'},
                    {'id': 'file_2', 'filename': 'document2.json'},
                    {'id': 'file_3', 'filename': 'data.txt'}
                ]
            },
            None
        )
        
        result = get_file_dict(mock_model)
        
        expected = {
            'file_1': 'document1',
            'file_2': 'document2',
            'file_3': 'data'
        }
        assert result == expected
    
    def test_get_file_dict_failure(self):
        mock_model = Mock()
        mock_model.list_files.return_value = (False, None, 'API error')
        
        with pytest.raises(Exception, match='API error'):
            get_file_dict(mock_model)


class TestUtilsIntegration:
    """工具函數整合測試"""
    
    def test_full_text_processing_pipeline(self):
        """測試完整的文字處理流程"""
        config = {
            'text_processing': {
                'preprocessors': [
                    {'type': 'replace_date_string'}
                ],
                'post-replacements': [
                    {'pattern': r'AI', 'replacement': '人工智慧'}
                ]
            }
        }
        
        with patch('src.utils.get_date_string') as mock_get_date:
            mock_get_date.return_value = '2024/01/15'
            
            # 預處理
            input_text = "今天的 AI 發展如何？"
            preprocessed = preprocess_text(input_text, config)
            assert "2024/01/15" in preprocessed
            
            # 假設經過模型處理後的回應
            model_response = "2024/01/15的 AI 發展很快速"
            
            # 後處理
            postprocessed = postprocess_text(model_response, config)
            assert "人工智慧" in postprocessed
            assert "AI" not in postprocessed
    
    @patch('src.utils.s2t_converter')
    def test_chinese_conversion_in_response(self, mock_converter):
        """測試中文轉換功能"""
        mock_converter.convert.return_value = "繁體中文回應"
        
        response = {
            'data': [
                {
                    'role': 'assistant',
                    'content': [
                        {
                            'type': 'text',
                            'text': {
                                'value': '简体中文回应',
                                'annotations': []
                            }
                        }
                    ]
                }
            ]
        }
        
        result = get_content_and_reference(response, {})
        
        mock_converter.convert.assert_called_once_with('简体中文回应')
        assert result == "繁體中文回應"