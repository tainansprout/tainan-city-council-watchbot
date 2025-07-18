import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from src.utils.main import (
    get_response_data, get_role_and_content, dedup_citation_blocks,
    check_token_valid, get_date_string, load_text_processing_config,
    preprocess_text, replace_text, postprocess_text, add_disclaimer
)


class TestResponseParsing:
    """回應解析功能測試"""
    
    def test_get_response_data_with_assistant_response(self):
        """測試從回應中提取助理的數據"""
        response = {
            'data': [
                {
                    'role': 'user',
                    'content': [{'type': 'text', 'text': {'value': 'User message'}}]
                },
                {
                    'role': 'assistant',
                    'content': [
                        {
                            'type': 'text',
                            'text': {'value': 'Assistant response'}
                        }
                    ]
                }
            ]
        }
        
        result = get_response_data(response)
        assert result is not None
        assert result['role'] == 'assistant'
        assert result['content'][0]['text']['value'] == 'Assistant response'
    
    def test_get_response_data_no_assistant_response(self):
        """測試沒有助理回應的情況"""
        response = {
            'data': [
                {
                    'role': 'user',
                    'content': [{'type': 'text', 'text': {'value': 'User message'}}]
                }
            ]
        }
        
        result = get_response_data(response)
        assert result is None
    
    def test_get_response_data_empty_content(self):
        """測試空內容的情況"""
        response = {
            'data': [
                {
                    'role': 'assistant',
                    'content': []
                }
            ]
        }
        
        result = get_response_data(response)
        assert result is None


class TestRoleAndContent:
    """角色和內容提取測試"""
    
    def test_get_role_and_content_openai_assistant_format(self):
        """測試 OpenAI Assistant API 格式"""
        response = {
            'data': [
                {
                    'role': 'assistant',
                    'content': [
                        {
                            'type': 'text',
                            'text': {'value': 'Hello from assistant'}
                        }
                    ]
                }
            ]
        }
        
        role, content = get_role_and_content(response)
        assert role == 'assistant'
        assert content == 'Hello from assistant'
    
    def test_get_role_and_content_standard_chat_format(self):
        """測試標準聊天格式"""
        response = {
            'choices': [
                {
                    'message': {
                        'role': 'assistant',
                        'content': 'Standard chat response'
                    }
                }
            ]
        }
        
        role, content = get_role_and_content(response)
        assert role == 'assistant'
        assert content == 'Standard chat response'
    
    def test_get_role_and_content_simple_message_format(self):
        """測試簡單訊息格式"""
        response = {
            'role': 'assistant',
            'content': 'Simple message'
        }
        
        role, content = get_role_and_content(response)
        assert role == 'assistant'
        assert content == 'Simple message'
    
    def test_get_role_and_content_chat_response_object(self):
        """測試 ChatResponse 物件"""
        mock_response = Mock()
        mock_response.content = 'Response from object'
        
        role, content = get_role_and_content(mock_response)
        assert role == 'assistant'
        assert content == 'Response from object'
    
    def test_get_role_and_content_fallback(self):
        """測試預設回傳"""
        response = "Plain string response"
        
        role, content = get_role_and_content(response)
        assert role == 'assistant'
        assert content == "Plain string response"


class TestCitationDeduplication:
    """引用去重功能測試"""
    
    def test_dedup_citation_blocks_simple_duplicate(self):
        """測試簡單重複引用"""
        text = "這是內容 [1][1][1] 繼續內容"
        result = dedup_citation_blocks(text)
        assert result == "這是內容  [1]  繼續內容"
    
    def test_dedup_citation_blocks_multiple_citations(self):
        """測試多個引用去重"""
        text = "內容 [1][2][1][3][2] 更多內容"
        result = dedup_citation_blocks(text)
        assert result == "內容  [1][2][3]  更多內容"
    
    def test_dedup_citation_blocks_no_duplicates(self):
        """測試沒有重複的引用"""
        text = "內容 [1] 和 [2] 分開的引用"
        result = dedup_citation_blocks(text)
        assert result == "內容 [1] 和 [2] 分開的引用"
    
    def test_dedup_citation_blocks_single_citation(self):
        """測試單個引用（不去重）"""
        text = "內容 [1] 單個引用"
        result = dedup_citation_blocks(text)
        assert result == "內容 [1] 單個引用"
    
    def test_dedup_citation_blocks_multiple_blocks(self):
        """測試多個引用區塊"""
        text = "第一個 [1][1] 區塊和第二個 [2][3][2] 區塊"
        result = dedup_citation_blocks(text)
        assert result == "第一個  [1]  區塊和第二個  [2][3]  區塊"
    
    def test_dedup_citation_blocks_empty_text(self):
        """測試空文字"""
        result = dedup_citation_blocks("")
        assert result == ""
    
    def test_dedup_citation_blocks_no_citations(self):
        """測試沒有引用的文字"""
        text = "這是沒有引用的普通文字"
        result = dedup_citation_blocks(text)
        assert result == "這是沒有引用的普通文字"


class TestDateHandling:
    """日期處理測試"""
    
    def test_get_date_string_today(self):
        with patch('src.utils.main.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 15, 10, 30, 0)
            
            result = get_date_string("today")
            assert result == "2024/01/15"
    
    def test_get_date_string_tomorrow(self):
        with patch('src.utils.main.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 15, 10, 30, 0)
            mock_datetime.timedelta = timedelta  # 確保 timedelta 可用
            
            result = get_date_string("tomorrow")
            assert result == "2024/01/16"
    
    def test_get_date_string_yesterday(self):
        with patch('src.utils.main.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 15, 10, 30, 0)
            mock_datetime.timedelta = timedelta
            
            result = get_date_string("yesterday")
            assert result == "2024/01/14"
    
    def test_get_date_string_invalid(self):
        with pytest.raises(ValueError, match="day 參數必須是"):
            get_date_string("invalid_day")
    
    def test_get_date_string_default(self):
        """測試預設值（今天）"""
        with patch('src.utils.main.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 15, 10, 30, 0)
            
            result = get_date_string()  # 不傳參數，應該預設為 today
            assert result == "2024/01/15"


class TestTextProcessing:
    """文字處理功能測試"""
    
    def test_load_text_processing_config_with_config(self):
        """測試載入文字處理配置"""
        config = {
            'text_processing': {
                'preprocessors': [{'type': 'replace_date_string'}],
                'post-replacements': [{'pattern': 'AI', 'replacement': '人工智慧'}]
            }
        }
        
        result = load_text_processing_config(config)
        assert 'preprocessors' in result
        assert 'post-replacements' in result
    
    def test_load_text_processing_config_empty(self):
        """測試空配置"""
        config = {}
        
        result = load_text_processing_config(config)
        assert result == {}
    
    def test_preprocess_text_with_date_replacement(self):
        config = {
            'text_processing': {
                'preprocessors': [
                    {'type': 'replace_date_string'}
                ]
            }
        }
        
        with patch('src.utils.main.get_date_string') as mock_get_date:
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
    
    def test_preprocess_text_english_dates(self):
        """測試英文日期替換"""
        config = {
            'text_processing': {
                'preprocessors': [
                    {'type': 'replace_date_string'}
                ]
            }
        }
        
        with patch('src.utils.main.get_date_string') as mock_get_date:
            mock_get_date.side_effect = lambda day: {
                'today': '2024/01/15',
                'tomorrow': '2024/01/16',
                'yesterday': '2024/01/14'
            }[day]
            
            text = "What happened today? Tomorrow will be better. Yesterday was good."
            result = preprocess_text(text, config)
            
            assert "2024/01/15" in result
            assert "2024/01/16" in result
            assert "2024/01/14" in result
    
    def test_preprocess_text_without_preprocessors(self):
        config = {'text_processing': {}}
        text = "今天的天氣如何？"
        
        result = preprocess_text(text, config)
        assert result == text  # 應該不變
    
    def test_replace_text_with_replacements(self):
        """測試文字替換功能"""
        text = "OpenAI 的 GPT 模型很強大"
        replacements = [
            {'pattern': r'OpenAI', 'replacement': 'AI助理'},
            {'pattern': r'GPT', 'replacement': '語言模型'}
        ]
        
        result = replace_text(text, replacements)
        
        assert "AI助理" in result
        assert "語言模型" in result
        assert "OpenAI" not in result
        assert "GPT" not in result
    
    def test_replace_text_empty_replacements(self):
        """測試空替換列表"""
        text = "測試文字"
        result = replace_text(text, [])
        assert result == text
    
    def test_replace_text_none_replacements(self):
        """測試 None 替換列表"""
        text = "測試文字"
        result = replace_text(text, None)
        assert result == text
    
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
        
        with patch('src.utils.main.get_date_string') as mock_get_date:
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
    
    def test_citation_processing_workflow(self):
        """測試引用處理工作流程"""
        # 模擬從 API 回應中提取內容
        response = {
            'data': [
                {
                    'role': 'assistant',
                    'content': [
                        {
                            'type': 'text',
                            'text': {'value': '根據資料 [1][1][2][1] 顯示結果'}
                        }
                    ]
                }
            ]
        }
        
        # 提取角色和內容
        role, content = get_role_and_content(response)
        assert role == 'assistant'
        assert content == '根據資料 [1][1][2][1] 顯示結果'
        
        # 去重引用
        deduplicated = dedup_citation_blocks(content)
        assert deduplicated == '根據資料  [1][2]  顯示結果'
    
    def test_error_handling_in_pipeline(self):
        """測試處理流程中的錯誤處理"""
        # 測試無效的回應格式
        invalid_response = {"invalid": "format"}
        role, content = get_role_and_content(invalid_response)
        
        # 應該回傳預設值
        assert role == 'assistant'
        assert content == str(invalid_response)
        
        # 測試空字串的引用處理
        empty_result = dedup_citation_blocks("")
        assert empty_result == ""


class TestDisclaimer:
    """免責聲明功能測試"""
    
    def test_add_disclaimer_with_config(self):
        """測試帶有配置的免責聲明添加"""
        config = {
            'text_processing': {
                'disclaimer': '本回應僅供參考，請以官方資訊為準。'
            }
        }
        
        text = '這是一個測試回應。'
        result = add_disclaimer(text, config)
        
        expected = '這是一個測試回應。\n\n本回應僅供參考，請以官方資訊為準。'
        assert result == expected
    
    def test_add_disclaimer_with_empty_disclaimer(self):
        """測試空免責聲明配置"""
        config = {
            'text_processing': {
                'disclaimer': ''
            }
        }
        
        text = '這是一個測試回應。'
        result = add_disclaimer(text, config)
        
        # 空免責聲明應該不添加任何內容
        assert result == text
    
    def test_add_disclaimer_with_whitespace_only_disclaimer(self):
        """測試只有空白字符的免責聲明"""
        config = {
            'text_processing': {
                'disclaimer': '   \n\t   '
            }
        }
        
        text = '這是一個測試回應。'
        result = add_disclaimer(text, config)
        
        # 只有空白字符的免責聲明應該不添加任何內容
        assert result == text
    
    def test_add_disclaimer_missing_text_processing(self):
        """測試缺少 text_processing 配置"""
        config = {}  # 完全空的配置
        
        text = '測試回應'
        result = add_disclaimer(text, config)
        
        # 沒有 text_processing 配置應該返回原文
        assert result == text
    
    def test_add_disclaimer_no_disclaimer_config(self):
        """測試沒有免責聲明配置"""
        config = {
            'text_processing': {},
            'other_config': 'some_value'
        }
        
        text = '測試回應'
        result = add_disclaimer(text, config)
        
        # text_processing 存在但沒有 disclaimer 配置應該返回原文
        assert result == text
    
    def test_add_disclaimer_empty_text(self):
        """測試空字串文本"""
        config = {
            'text_processing': {
                'disclaimer': '免責聲明'
            }
        }
        
        text = ''
        result = add_disclaimer(text, config)
        
        expected = '\n\n免責聲明'
        assert result == expected
    
    def test_add_disclaimer_multiline_text(self):
        """測試多行文本"""
        config = {
            'text_processing': {
                'disclaimer': '免責聲明'
            }
        }
        
        text = '第一行\n第二行\n第三行'
        result = add_disclaimer(text, config)
        
        expected = '第一行\n第二行\n第三行\n\n免責聲明'
        assert result == expected
    
    def test_add_disclaimer_with_disclaimer_containing_newlines(self):
        """測試包含換行的免責聲明"""
        config = {
            'text_processing': {
                'disclaimer': '免責聲明第一行\n免責聲明第二行'
            }
        }
        
        text = '原始內容'
        result = add_disclaimer(text, config)
        
        expected = '原始內容\n\n免責聲明第一行\n免責聲明第二行'
        assert result == expected
    
    def test_add_disclaimer_strips_disclaimer(self):
        """測試免責聲明會被去除前後空白"""
        config = {
            'text_processing': {
                'disclaimer': '   免責聲明內容   '
            }
        }
        
        text = '測試內容'
        result = add_disclaimer(text, config)
        
        expected = '測試內容\n\n免責聲明內容'
        assert result == expected