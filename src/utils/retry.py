import time
import logging
import random
from functools import wraps
from typing import Callable, Any, Tuple, Type, Union

logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_retries: int = 3, 
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception
):
    """
    指數退避重試裝飾器
    
    Args:
        max_retries: 最大重試次數
        base_delay: 基礎延遲時間（秒）
        max_delay: 最大延遲時間（秒）
        exponential_base: 指數底數
        jitter: 是否加入隨機抖動以避免驚群效應
        exceptions: 要重試的異常類型
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Tuple[bool, Any, str]:
            last_exception = None
            
            for attempt in range(max_retries + 1):  # +1 因為第一次不算重試
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    # 最後一次嘗試失敗時不再重試
                    if attempt == max_retries:
                        logger.error(f"All {max_retries + 1} attempts failed: {e}")
                        break
                    
                    # 計算延遲時間
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    
                    # 加入隨機抖動
                    if jitter:
                        delay *= (0.5 + random.random() * 0.5)  # 0.5x 到 1.0x 的隨機係數
                    
                    logger.warning(
                        f"Attempt {attempt + 1} failed, retrying in {delay:.2f}s: {e}"
                    )
                    time.sleep(delay)
            
            # 如果所有重試都失敗，返回標準格式
            return False, None, str(last_exception)
        
        return wrapper
    return decorator


def retry_on_rate_limit(max_retries: int = 5, base_delay: float = 1.0):
    """
    專門針對 API 速率限制的重試裝飾器
    """
    return retry_with_backoff(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=120.0,  # 最多等待 2 分鐘
        exponential_base=2.0,
        jitter=True,
        exceptions=(Exception,)  # 可以根據具體 API 調整異常類型
    )


def retry_on_network_error(max_retries: int = 3, base_delay: float = 0.5):
    """
    專門針對網路錯誤的重試裝飾器
    """
    import requests
    
    network_exceptions = (
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        requests.exceptions.RequestException,
    )
    
    return retry_with_backoff(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=30.0,
        exponential_base=1.5,
        jitter=True,
        exceptions=network_exceptions
    )


class CircuitBreaker:
    """
    斷路器模式實作 - 防止對故障服務的持續請求
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: Type[Exception] = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if self.state == 'OPEN':
                if self._should_attempt_reset():
                    self.state = 'HALF_OPEN'
                else:
                    raise Exception("Circuit breaker is OPEN")
            
            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            except self.expected_exception as e:
                self._on_failure()
                raise e
        
        return wrapper
    
    def _should_attempt_reset(self) -> bool:
        """檢查是否應該嘗試重置斷路器"""
        return (
            self.last_failure_time and 
            time.time() - self.last_failure_time >= self.recovery_timeout
        )
    
    def _on_success(self):
        """成功時重置斷路器"""
        self.failure_count = 0
        self.state = 'CLOSED'
        logger.debug("Circuit breaker reset to CLOSED state")
    
    def _on_failure(self):
        """失敗時更新斷路器狀態"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'
            logger.warning(
                f"Circuit breaker opened after {self.failure_count} failures"
            )


# 使用範例
if __name__ == "__main__":
    # 重試裝飾器範例
    @retry_with_backoff(max_retries=3, base_delay=1.0)
    def unstable_api_call():
        import random
        if random.random() < 0.7:  # 70% 失敗率
            raise Exception("API temporarily unavailable")
        return True, "Success", None
    
    # 斷路器範例
    @CircuitBreaker(failure_threshold=3, recovery_timeout=10)
    def failing_service():
        raise Exception("Service is down")
    
    # 測試
    try:
        result = unstable_api_call()
        print(f"API call result: {result}")
    except Exception as e:
        print(f"API call failed: {e}")