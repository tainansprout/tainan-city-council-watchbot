"""
測試智慧超時配置模組的單元測試
"""
import pytest
import time
from unittest.mock import patch, Mock

from src.core.api_timeouts import SmartTimeoutConfig, TimeoutContext


class TestSmartTimeoutConfig:
    """測試智慧超時配置"""

    def test_get_timeout_known_operation(self):
        """測試已知操作的超時時間"""
        assert SmartTimeoutConfig.get_timeout('chat_completion') == 45
        assert SmartTimeoutConfig.get_timeout('health_check') == 3

    def test_get_timeout_unknown_operation(self):
        """測試未知操作的預設超時時間"""
        assert SmartTimeoutConfig.get_timeout('unknown_op') == 45
        assert SmartTimeoutConfig.get_timeout('unknown_op', default=30) == 30

    @pytest.mark.parametrize("provider, factor", [
        ('openai', 1.0),
        ('anthropic', 1.1),
        ('gemini', 0.9),
        ('ollama', 2.0),
        ('unknown_provider', 1.0)
    ])
    def test_get_timeout_for_model(self, provider, factor):
        """測試不同模型提供商的超時時間調整"""
        base_timeout = SmartTimeoutConfig.TIMEOUT_MAPPING['chat_completion']
        expected_timeout = int(base_timeout * factor)
        assert SmartTimeoutConfig.get_timeout_for_model('chat_completion', provider) == max(expected_timeout, 5)

    def test_get_timeout_for_model_minimum_value(self):
        """測試超時時間的最小值"""
        # 假設 gemini 的調整因子會使超時低於 5 秒
        with patch.dict(SmartTimeoutConfig.TIMEOUT_MAPPING, {'health_check': 3}):
            assert SmartTimeoutConfig.get_timeout_for_model('health_check', 'gemini') == 5

    def test_get_operation_info_known_operation(self):
        """測試已知操作的詳細資訊"""
        info = SmartTimeoutConfig.get_operation_info('rag_query')
        assert info['timeout'] == 60
        assert info['description'] == 'RAG 知識庫查詢'
        assert info['category'] == 'user_core'

    def test_get_operation_info_unknown_operation(self):
        """測試未知操作的詳細資訊"""
        info = SmartTimeoutConfig.get_operation_info('unknown_op')
        assert info['timeout'] == 45  # 預設值
        assert info['description'] == '未知操作'
        assert info['category'] == 'unknown'

    @pytest.mark.parametrize("operation, category", [
        ('health_check', 'system'),
        ('chat_completion', 'user_core'),
        ('file_upload', 'file_operation'),
        ('something_else', 'unknown')
    ])
    def test_get_operation_category(self, operation, category):
        """測試操作分類的正確性"""
        assert SmartTimeoutConfig._get_operation_category(operation) == category


class TestTimeoutContext:
    """測試超時上下文管理器"""

    def test_context_enter(self):
        """測試進入上下文時返回正確的超時時間"""
        context = TimeoutContext('chat_completion', 'openai')
        with context as timeout:
            assert timeout == 45

    @patch('src.core.api_timeouts.get_logger')
    def test_context_exit_with_timeout_exception(self, mock_get_logger):
        """測試發生超時異常時記錄日誌"""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        context = TimeoutContext('rag_query', 'anthropic')
        
        try:
            with context:
                # The string representation of the exception must contain "timeout"
                raise TimeoutError("The operation has hit a timeout")
        except TimeoutError:
            # The check happens after the exception is caught
            pass

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args[0][0]
        assert "操作超時: rag_query" in call_args
        assert "提供商: anthropic" in call_args
        assert f"設定超時: {int(60 * 1.1)}秒" in call_args
        assert "實際耗時:" in call_args

    @patch('src.core.api_timeouts.get_logger')
    def test_context_exit_with_other_exception(self, mock_get_logger):
        """測試發生非超時異常時不記錄日誌"""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        context = TimeoutContext('file_upload')
        
        try:
            with context:
                raise ValueError("Some other error")
        except ValueError:
            pass
        
        mock_logger.warning.assert_not_called()

    @patch('src.core.api_timeouts.get_logger')
    def test_context_exit_without_exception(self, mock_get_logger):
        """測試無異常退出時不記錄日誌"""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        with TimeoutContext('model_list'):
            pass
        
        mock_logger.warning.assert_not_called()
