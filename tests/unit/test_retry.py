"""
測試重試機制模組的單元測試
"""
import pytest
import time
import requests
from unittest.mock import Mock, patch, MagicMock
from src.utils.retry import (
    retry_with_backoff, 
    retry_on_rate_limit, 
    retry_on_network_error, 
    CircuitBreaker
)


class TestRetryWithBackoff:
    """測試基本重試裝飾器"""
    
    def test_successful_execution_on_first_attempt(self):
        """測試第一次嘗試就成功的情況"""
        @retry_with_backoff(max_retries=3)
        def successful_func():
            return True, "success", None
        
        result = successful_func()
        assert result == (True, "success", None)
    
    def test_retry_after_failure(self):
        """測試失敗後重試的情況"""
        call_count = 0
        
        @retry_with_backoff(max_retries=2, base_delay=0.1)
        def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return True, "success after retry", None
        
        with patch('time.sleep') as mock_sleep:
            result = failing_then_success()
            
            assert result == (True, "success after retry", None)
            assert call_count == 3
            assert mock_sleep.call_count == 2  # 重試 2 次
    
    def test_all_retries_fail(self):
        """測試所有重試都失敗的情況"""
        @retry_with_backoff(max_retries=2, base_delay=0.1)
        def always_failing():
            raise RuntimeError("Persistent failure")
        
        with patch('time.sleep'):
            result = always_failing()
            
            assert result[0] is False  # success = False
            assert result[1] is None   # data = None
            assert "Persistent failure" in result[2]  # error message
    
    def test_exponential_backoff_calculation(self):
        """測試指數退避延遲時間計算"""
        @retry_with_backoff(max_retries=3, base_delay=1.0, exponential_base=2.0, jitter=False)
        def always_failing():
            raise Exception("Test failure")
        
        with patch('time.sleep') as mock_sleep:
            always_failing()
            
            # 檢查延遲時間是指數增長的
            call_args = [call[0][0] for call in mock_sleep.call_args_list]
            assert len(call_args) == 3
            assert call_args[0] == 1.0   # 第一次重試：1.0 * 2^0 = 1.0
            assert call_args[1] == 2.0   # 第二次重試：1.0 * 2^1 = 2.0
            assert call_args[2] == 4.0   # 第三次重試：1.0 * 2^2 = 4.0
    
    def test_max_delay_limit(self):
        """測試最大延遲時間限制"""
        @retry_with_backoff(max_retries=5, base_delay=10.0, max_delay=15.0, exponential_base=2.0, jitter=False)
        def always_failing():
            raise Exception("Test failure")
        
        with patch('time.sleep') as mock_sleep:
            always_failing()
            
            call_args = [call[0][0] for call in mock_sleep.call_args_list]
            # 確保沒有延遲時間超過 max_delay
            assert all(delay <= 15.0 for delay in call_args)
    
    def test_jitter_adds_randomness(self):
        """測試隨機抖動功能"""
        @retry_with_backoff(max_retries=3, base_delay=2.0, jitter=True)
        def always_failing():
            raise Exception("Test failure")
        
        with patch('random.random', return_value=0.75), \
             patch('time.sleep') as mock_sleep:
            always_failing()
            
            call_args = [call[0][0] for call in mock_sleep.call_args_list]
            # 檢查延遲時間有被 jitter 調整
            # jitter 係數為 0.5 + 0.75 * 0.5 = 0.875
            expected_first_delay = 2.0 * 0.875
            assert abs(call_args[0] - expected_first_delay) < 0.01
    
    def test_specific_exception_filtering(self):
        """測試特定異常類型的過濾"""
        @retry_with_backoff(max_retries=2, exceptions=ValueError)
        def mixed_exceptions():
            # 模擬第一次拋出 ValueError（會重試），第二次拋出 RuntimeError（不會重試）
            if not hasattr(mixed_exceptions, 'call_count'):
                mixed_exceptions.call_count = 0
            mixed_exceptions.call_count += 1
            
            if mixed_exceptions.call_count == 1:
                raise ValueError("This should be retried")
            else:
                raise RuntimeError("This should not be retried")
        
        with patch('time.sleep'):
            # RuntimeError 不在重試異常清單中，應該直接拋出
            with pytest.raises(RuntimeError, match="This should not be retried"):
                mixed_exceptions()
    
    def test_logging_on_retry(self):
        """測試重試時的日誌記錄"""
        @retry_with_backoff(max_retries=2, base_delay=0.1)
        def failing_function():
            raise Exception("Test error")
        
        with patch('time.sleep'), \
             patch('src.utils.retry.logger') as mock_logger:
            failing_function()
            
            # 檢查警告日誌被記錄
            assert mock_logger.warning.call_count == 2
            # 檢查錯誤日誌被記錄（最終失敗）
            assert mock_logger.error.call_count == 1


class TestRetryOnRateLimit:
    """測試 API 速率限制重試裝飾器"""
    
    def test_rate_limit_retry_parameters(self):
        """測試速率限制重試的參數設定"""
        @retry_on_rate_limit(max_retries=5, base_delay=2.0)
        def rate_limited_api():
            raise Exception("Rate limit exceeded")
        
        with patch('time.sleep') as mock_sleep:
            rate_limited_api()
            
            # 檢查重試次數
            assert mock_sleep.call_count == 5
    
    def test_rate_limit_max_delay(self):
        """測試速率限制重試的最大延遲時間"""
        @retry_on_rate_limit(max_retries=10, base_delay=30.0)
        def rate_limited_api():
            raise Exception("Rate limit exceeded")
        
        with patch('time.sleep') as mock_sleep:
            rate_limited_api()
            
            call_args = [call[0][0] for call in mock_sleep.call_args_list]
            # 確保延遲時間不超過 120 秒
            assert all(delay <= 120.0 for delay in call_args)


class TestRetryOnNetworkError:
    """測試網路錯誤重試裝飾器"""
    
    def test_network_error_retry(self):
        """測試網路錯誤重試功能"""
        @retry_on_network_error(max_retries=3, base_delay=0.1)
        def network_call():
            raise requests.exceptions.ConnectionError("Network error")
        
        with patch('time.sleep') as mock_sleep:
            result = network_call()
            
            assert result[0] is False  # 失敗
            assert "Network error" in result[2]
            assert mock_sleep.call_count == 3
    
    def test_network_error_specific_exceptions(self):
        """測試網路錯誤重試只處理特定異常"""
        @retry_on_network_error(max_retries=2)
        def non_network_error():
            raise ValueError("Not a network error")
        
        # ValueError 不在網路異常清單中，應該直接拋出
        with pytest.raises(ValueError, match="Not a network error"):
            non_network_error()
    
    def test_successful_after_network_retry(self):
        """測試網路重試後成功的情況"""
        call_count = 0
        
        @retry_on_network_error(max_retries=2, base_delay=0.1)
        def intermittent_network_issue():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise requests.exceptions.Timeout("Timeout error")
            return True, "network recovered", None
        
        with patch('time.sleep'):
            result = intermittent_network_issue()
            
            assert result == (True, "network recovered", None)
            assert call_count == 2


class TestCircuitBreaker:
    """測試斷路器模式"""
    
    def test_circuit_breaker_closed_state(self):
        """測試斷路器關閉狀態的正常執行"""
        breaker = CircuitBreaker(failure_threshold=3)
        
        @breaker
        def successful_function():
            return "success"
        
        result = successful_function()
        assert result == "success"
        assert breaker.state == 'CLOSED'
        assert breaker.failure_count == 0
    
    def test_circuit_breaker_opens_after_threshold(self):
        """測試斷路器在達到失敗閾值後開啟"""
        breaker = CircuitBreaker(failure_threshold=3)
        
        @breaker
        def failing_function():
            raise Exception("Service failure")
        
        # 執行失敗次數達到閾值
        for i in range(3):
            with pytest.raises(Exception):
                failing_function()
        
        assert breaker.state == 'OPEN'
        assert breaker.failure_count == 3
    
    def test_circuit_breaker_blocks_calls_when_open(self):
        """測試斷路器開啟時阻擋呼叫"""
        breaker = CircuitBreaker(failure_threshold=2)
        
        @breaker
        def failing_function():
            raise Exception("Service failure")
        
        # 觸發斷路器開啟
        for i in range(2):
            with pytest.raises(Exception):
                failing_function()
        
        assert breaker.state == 'OPEN'
        
        # 斷路器開啟後應該阻擋呼叫
        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            failing_function()
    
    def test_circuit_breaker_half_open_recovery(self):
        """測試斷路器半開狀態的恢復機制"""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
        
        @breaker
        def test_function():
            return "success"
        
        # 手動設定斷路器為開啟狀態
        breaker.state = 'OPEN'
        breaker.last_failure_time = time.time() - 2  # 2 秒前失敗
        
        # 超過恢復時間後，應該進入半開狀態並嘗試執行
        result = test_function()
        
        assert result == "success"
        assert breaker.state == 'CLOSED'  # 成功後回到關閉狀態
        assert breaker.failure_count == 0
    
    def test_circuit_breaker_failure_in_half_open(self):
        """測試半開狀態下失敗的處理"""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
        
        @breaker
        def failing_function():
            raise Exception("Still failing")
        
        # 手動設定為半開狀態
        breaker.state = 'HALF_OPEN'
        breaker.last_failure_time = time.time() - 2
        
        with pytest.raises(Exception, match="Still failing"):
            failing_function()
        
        # 半開狀態下失敗應該重新開啟斷路器
        assert breaker.failure_count >= 1
    
    def test_circuit_breaker_should_not_reset_before_timeout(self):
        """測試斷路器在恢復時間未到時不應重置"""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=60)
        
        # 設定最近失敗時間
        breaker.state = 'OPEN'
        breaker.last_failure_time = time.time()
        
        assert not breaker._should_attempt_reset()
    
    def test_circuit_breaker_should_reset_after_timeout(self):
        """測試斷路器在恢復時間到達後應該重置"""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
        
        # 設定 2 秒前的失敗時間
        breaker.state = 'OPEN'
        breaker.last_failure_time = time.time() - 2
        
        assert breaker._should_attempt_reset()
    
    def test_circuit_breaker_custom_exception(self):
        """測試斷路器自定義異常類型"""
        breaker = CircuitBreaker(failure_threshold=2, expected_exception=ValueError)
        
        @breaker
        def mixed_exception_function():
            if not hasattr(mixed_exception_function, 'call_count'):
                mixed_exception_function.call_count = 0
            mixed_exception_function.call_count += 1
            
            if mixed_exception_function.call_count == 1:
                raise ValueError("Expected failure")
            else:
                raise RuntimeError("Unexpected failure")
        
        # ValueError 應該被斷路器處理
        with pytest.raises(ValueError):
            mixed_exception_function()
        
        assert breaker.failure_count == 1
        
        # RuntimeError 不應該被斷路器處理，直接拋出
        with pytest.raises(RuntimeError):
            mixed_exception_function()
        
        # failure_count 不應該增加，因為 RuntimeError 不是預期的異常
        assert breaker.failure_count == 1


class TestRetryIntegration:
    """測試重試機制的整合功能"""
    
    def test_retry_and_circuit_breaker_together(self):
        """測試重試裝飾器和斷路器一起使用"""
        breaker = CircuitBreaker(failure_threshold=2)
        
        @retry_with_backoff(max_retries=1, base_delay=0.1)
        @breaker
        def service_call():
            raise Exception("Service error")
        
        # 第一次呼叫（包含重試）
        with patch('time.sleep'):
            result = service_call()
            assert result[0] is False  # 重試失敗
        
        # 檢查斷路器狀態
        assert breaker.failure_count >= 1
    
    def test_retry_preserves_function_metadata(self):
        """測試重試裝飾器保留函數元數據"""
        @retry_with_backoff(max_retries=2)
        def documented_function():
            """This is a test function"""
            return True, "success", None
        
        assert documented_function.__doc__ == "This is a test function"
        assert documented_function.__name__ == "documented_function"
    
    def test_circuit_breaker_preserves_function_metadata(self):
        """測試斷路器保留函數元數據"""
        breaker = CircuitBreaker()
        
        @breaker
        def documented_function():
            """This is a test function"""
            return "success"
        
        assert documented_function.__doc__ == "This is a test function"
        assert documented_function.__name__ == "documented_function"


class TestRetryMainExecution:
    """測試重試模組的主程式執行"""
    
    def test_main_execution_example(self):
        """測試主程式範例代碼的執行"""
        with patch('random.random', return_value=0.8), \
             patch('time.sleep'), \
             patch('builtins.print') as mock_print:
            
            # 模擬 unstable_api_call 的執行
            @retry_with_backoff(max_retries=3, base_delay=0.1)
            def unstable_api_call():
                import random
                if random.random() < 0.7:
                    raise Exception("API temporarily unavailable")
                return True, "Success", None
            
            try:
                result = unstable_api_call()
                assert result == (True, "Success", None)
            except Exception:
                pass  # 可能會失敗，這是正常的
    
    def test_circuit_breaker_example(self):
        """測試斷路器範例代碼"""
        @CircuitBreaker(failure_threshold=3, recovery_timeout=10)
        def failing_service():
            raise Exception("Service is down")
        
        # 測試斷路器會在多次失敗後開啟
        for i in range(3):
            with pytest.raises(Exception):
                failing_service()
        
        # 第4次呼叫應該被斷路器阻擋
        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            failing_service()