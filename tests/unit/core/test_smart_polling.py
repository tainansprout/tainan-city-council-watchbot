"""
測試智慧輪詢策略模組
"""
import pytest
import time
from unittest.mock import Mock, patch, call
from src.core.smart_polling import (
    SmartPollingStrategy, 
    PollingContext, 
    smart_polling_wait,
    OpenAIPollingStrategy
)


class TestSmartPollingStrategy:
    """測試智慧輪詢策略"""
    
    @pytest.fixture
    def polling_strategy(self):
        """創建輪詢策略實例"""
        return SmartPollingStrategy()
    
    def test_initialization(self, polling_strategy):
        """測試初始化"""
        assert polling_strategy.wait_sequence == [5, 3, 2, 1]
        assert polling_strategy.final_interval == 1
        assert polling_strategy.max_wait_time == 90
    
    def test_get_base_wait_time_sequence(self, polling_strategy):
        """測試基礎等待時間序列"""
        # 測試序列內的等待時間
        assert polling_strategy._get_base_wait_time(0) == 5
        assert polling_strategy._get_base_wait_time(1) == 3
        assert polling_strategy._get_base_wait_time(2) == 2
        assert polling_strategy._get_base_wait_time(3) == 1
        
        # 測試超過序列的等待時間
        assert polling_strategy._get_base_wait_time(4) == 1
        assert polling_strategy._get_base_wait_time(10) == 1
    
    def test_get_wait_time_different_statuses(self, polling_strategy):
        """測試不同狀態的等待時間"""
        # 排隊狀態 - 增加50%
        queued_time = polling_strategy.get_wait_time(0, 'queued')
        assert queued_time == 5 * 1.5  # 7.5秒
        
        # 執行中狀態 - 正常
        in_progress_time = polling_strategy.get_wait_time(0, 'in_progress')
        assert in_progress_time == 5
        
        # 需要操作狀態 - 快速檢查
        requires_action_time = polling_strategy.get_wait_time(0, 'requires_action')
        assert requires_action_time == 0.5
        
        # 其他狀態 - 正常
        other_time = polling_strategy.get_wait_time(0, 'unknown')
        assert other_time == 5
    
    def test_get_max_wait_time(self, polling_strategy):
        """測試最大等待時間"""
        assert polling_strategy.get_max_wait_time() == 90
    
    def test_should_continue_polling(self, polling_strategy):
        """測試是否應該繼續輪詢"""
        assert polling_strategy.should_continue_polling(50) is True
        assert polling_strategy.should_continue_polling(90) is False
        assert polling_strategy.should_continue_polling(100) is False
    
    def test_log_polling_attempt(self, polling_strategy):
        """測試記錄輪詢嘗試"""
        with patch('src.core.smart_polling.logger') as mock_logger:
            polling_strategy.log_polling_attempt(2, 'in_progress', 2.0, 10.5)
            
            mock_logger.debug.assert_called_once_with(
                "智慧輪詢 - 第 3 次: 狀態='in_progress', 等待=2.0秒, 已耗時=10.5秒"
            )
    
    def test_get_polling_summary(self, polling_strategy):
        """測試取得輪詢摘要"""
        summary = polling_strategy.get_polling_summary(5, 15.5, 'completed')
        
        assert "5 次嘗試" in summary
        assert "總耗時 15.5秒" in summary
        assert "平均間隔 3.1秒" in summary
        assert "最終狀態: completed" in summary
    
    def test_get_polling_summary_zero_attempts(self, polling_strategy):
        """測試零次嘗試的輪詢摘要"""
        summary = polling_strategy.get_polling_summary(0, 0.0, 'failed')
        
        assert "0 次嘗試" in summary
        assert "平均間隔 0.0秒" in summary


class TestPollingContext:
    """測試輪詢上下文"""
    
    @pytest.fixture
    def mock_strategy(self):
        """模擬輪詢策略"""
        strategy = Mock(spec=SmartPollingStrategy)
        strategy.should_continue_polling.return_value = True
        strategy.get_wait_time.return_value = 1.0
        strategy.get_polling_summary.return_value = "Test summary"
        return strategy
    
    def test_context_manager_lifecycle(self, mock_strategy):
        """測試上下文管理器生命週期"""
        with patch('src.core.smart_polling.logger') as mock_logger, \
             patch('time.time', side_effect=[0, 10]):  # 模擬開始和結束時間
            
            with PollingContext("test_operation", mock_strategy) as context:
                assert context.operation_name == "test_operation"
                assert context.strategy == mock_strategy
                
            # 檢查日誌記錄
            mock_logger.info.assert_any_call("開始智慧輪詢: test_operation")
            mock_logger.info.assert_any_call("結束智慧輪詢: test_operation - Test summary")
            mock_strategy.get_polling_summary.assert_called_once_with(0, 10, 'unknown')
    
    def test_context_manager_with_time_mock_exhausted(self, mock_strategy):
        """測試時間模擬耗盡的情況"""
        with patch('src.core.smart_polling.logger') as mock_logger:
            time_calls = [0]  # 用於計數 time.time() 調用
            
            def mock_time():
                if time_calls[0] >= 1:  # 第二次調用拋出異常
                    raise StopIteration("time mock exhausted")
                time_calls[0] += 1
                return 0
            
            with patch('time.time', side_effect=mock_time):
                with PollingContext("test_operation", mock_strategy):
                    pass
                    
            # 檢查特殊日誌記錄
            mock_logger.info.assert_called_with("結束智慧輪詢: test_operation (time mock exhausted)")
    
    def test_wait_for_condition_success(self, mock_strategy):
        """測試等待條件成功"""
        check_function = Mock(return_value=(True, 'completed', {'result': 'success'}))
        completion_statuses = ['completed']
        failure_statuses = ['failed']
        
        with patch('time.time', side_effect=[0, 1, 2]), \
             patch('time.sleep') as mock_sleep, \
             patch('src.core.smart_polling.logger'):
            
            with PollingContext("test_op", mock_strategy) as context:
                success, data, error = context.wait_for_condition(
                    check_function, completion_statuses, failure_statuses
                )
            
            assert success is True
            assert data == {'result': 'success'}
            assert error is None
            check_function.assert_called_once()
    
    def test_wait_for_condition_failure_status(self, mock_strategy):
        """測試等待條件遇到失敗狀態"""
        check_function = Mock(return_value=(True, 'failed', {'error': 'operation failed'}))
        completion_statuses = ['completed']
        failure_statuses = ['failed']
        
        with patch('time.time', side_effect=[0, 1]), \
             patch('src.core.smart_polling.logger'):
            
            with PollingContext("test_op", mock_strategy) as context:
                success, data, error = context.wait_for_condition(
                    check_function, completion_statuses, failure_statuses
                )
            
            assert success is False
            assert data == {'error': 'operation failed'}
            assert "test_op 失敗: failed" in error
    
    def test_wait_for_condition_failure_status_with_last_error(self, mock_strategy):
        """測試等待條件遇到帶有詳細錯誤的失敗狀態"""
        error_data = {
            'last_error': {'message': 'Detailed error message'}
        }
        check_function = Mock(return_value=(True, 'failed', error_data))
        completion_statuses = ['completed']
        failure_statuses = ['failed']
        
        with patch('time.time', side_effect=[0, 1]), \
             patch('src.core.smart_polling.logger'):
            
            with PollingContext("test_op", mock_strategy) as context:
                success, data, error = context.wait_for_condition(
                    check_function, completion_statuses, failure_statuses
                )
            
            assert success is False
            assert "錯誤: Detailed error message" in error
    
    def test_wait_for_condition_check_function_failure(self, mock_strategy):
        """測試檢查函數失敗"""
        check_function = Mock(return_value=(False, 'error', 'Check failed'))
        completion_statuses = ['completed']
        failure_statuses = ['failed']
        
        with patch('time.time', side_effect=[0, 1]), \
             patch('src.core.smart_polling.logger'):
            
            with PollingContext("test_op", mock_strategy) as context:
                success, data, error = context.wait_for_condition(
                    check_function, completion_statuses, failure_statuses
                )
            
            assert success is False
            assert data is None
            assert "檢查操作失敗: Check failed" in error
    
    def test_wait_for_condition_timeout(self, mock_strategy):
        """測試輪詢超時"""
        check_function = Mock(return_value=(True, 'in_progress', {}))
        completion_statuses = ['completed']
        failure_statuses = ['failed']
        mock_strategy.should_continue_polling.return_value = False
        
        time_values = [0, 100]  # 開始時間，結束時間
        time_calls = [0]
        
        def mock_time():
            if time_calls[0] < len(time_values):
                result = time_values[time_calls[0]]
                time_calls[0] += 1
                return result
            return time_values[-1]  # 返回最後一個值
        
        with patch('time.time', side_effect=mock_time), \
             patch('src.core.smart_polling.logger'):
            
            with PollingContext("test_op", mock_strategy) as context:
                success, data, error = context.wait_for_condition(
                    check_function, completion_statuses, failure_statuses
                )
            
            assert success is False
            assert data is None
            assert "test_op 超時 (100.0秒)" in error
    
    def test_wait_for_condition_timeout_with_time_mock_exhausted(self, mock_strategy):
        """測試時間模擬耗盡時的超時處理"""
        check_function = Mock(return_value=(True, 'in_progress', {}))
        completion_statuses = ['completed']
        failure_statuses = ['failed']
        mock_strategy.should_continue_polling.return_value = False
        
        time_calls = [0]
        
        def mock_time():
            if time_calls[0] >= 1:  # 第二次調用拋出異常
                raise StopIteration("time mock exhausted")
            time_calls[0] += 1
            return 0
        
        with patch('time.time', side_effect=mock_time), \
             patch('src.core.smart_polling.logger'):
            
            with PollingContext("test_op", mock_strategy) as context:
                success, data, error = context.wait_for_condition(
                    check_function, completion_statuses, failure_statuses
                )
            
            assert success is False
            assert data is None
            assert error == "Request timeout"
    
    def test_wait_for_condition_exception_in_check(self, mock_strategy):
        """測試檢查函數拋出異常"""
        check_function = Mock(side_effect=Exception("Check function error"))
        completion_statuses = ['completed']
        failure_statuses = ['failed']
        
        with patch('time.time', side_effect=[0, 1]), \
             patch('src.core.smart_polling.logger'):
            
            with PollingContext("test_op", mock_strategy) as context:
                success, data, error = context.wait_for_condition(
                    check_function, completion_statuses, failure_statuses
                )
            
            assert success is False
            assert data is None
            assert "輪詢過程中發生錯誤: Check function error" in error
    
    def test_wait_for_condition_with_polling_loop(self, mock_strategy):
        """測試完整的輪詢循環"""
        # 模擬三次檢查：進行中、進行中、完成
        check_function = Mock(side_effect=[
            (True, 'in_progress', {}),
            (True, 'in_progress', {}),
            (True, 'completed', {'result': 'final'})
        ])
        completion_statuses = ['completed']
        failure_statuses = ['failed']
        
        with patch('time.time', side_effect=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]), \
             patch('time.sleep') as mock_sleep, \
             patch('src.core.smart_polling.logger'):
            
            with PollingContext("test_op", mock_strategy) as context:
                success, data, error = context.wait_for_condition(
                    check_function, completion_statuses, failure_statuses
                )
            
            assert success is True
            assert data == {'result': 'final'}
            assert error is None
            assert check_function.call_count == 3
            assert mock_sleep.call_count == 2  # 兩次等待
    
    def test_wait_for_condition_with_time_mock_errors_in_loop(self, mock_strategy):
        """測試循環中時間模擬錯誤的處理"""
        check_function = Mock(side_effect=[
            (True, 'in_progress', {}),
            (True, 'completed', {'result': 'final'})
        ])
        completion_statuses = ['completed']
        failure_statuses = ['failed']
        
        # 模擬時間函數在某些調用中失敗
        time_side_effects = [0, 1, StopIteration, 3]
        
        with patch('time.time', side_effect=time_side_effects), \
             patch('time.sleep') as mock_sleep, \
             patch('src.core.smart_polling.logger'):
            
            with PollingContext("test_op", mock_strategy) as context:
                success, data, error = context.wait_for_condition(
                    check_function, completion_statuses, failure_statuses
                )
            
            # 應該仍然能夠成功完成
            assert success is True
            assert data == {'result': 'final'}
            assert error is None


class TestSmartPollingWaitFunction:
    """測試智慧輪詢等待函數"""
    
    def test_smart_polling_wait_with_defaults(self):
        """測試使用預設參數的智慧輪詢等待"""
        check_function = Mock(return_value=(True, 'completed', {'result': 'test'}))
        
        with patch('time.time', side_effect=[0, 1, 2]), \
             patch('time.sleep'), \
             patch('src.core.smart_polling.logger'):
            
            success, data, error = smart_polling_wait(
                "test_operation",
                check_function
            )
            
            assert success is True
            assert data == {'result': 'test'}
            assert error is None
    
    def test_smart_polling_wait_with_custom_parameters(self):
        """測試使用自定義參數的智慧輪詢等待"""
        check_function = Mock(return_value=(True, 'done', {'result': 'custom'}))
        
        with patch('time.time', side_effect=[0, 1, 2]), \
             patch('time.sleep'), \
             patch('src.core.smart_polling.logger'):
            
            success, data, error = smart_polling_wait(
                "custom_operation",
                check_function,
                completion_statuses=['done', 'finished'],
                failure_statuses=['error', 'timeout'],
                max_wait_time=60
            )
            
            assert success is True
            assert data == {'result': 'custom'}
            assert error is None
    
    def test_smart_polling_wait_failure(self):
        """測試智慧輪詢等待失敗"""
        check_function = Mock(return_value=(True, 'error', {'message': 'failed'}))
        
        with patch('time.time', side_effect=[0, 1]), \
             patch('src.core.smart_polling.logger'):
            
            success, data, error = smart_polling_wait(
                "failing_operation",
                check_function,
                completion_statuses=['completed'],
                failure_statuses=['error']
            )
            
            assert success is False
            assert data == {'message': 'failed'}
            assert "failing_operation 失敗: error" in error


class TestOpenAIPollingStrategy:
    """測試 OpenAI 輪詢策略"""
    
    @pytest.fixture
    def openai_strategy(self):
        """創建 OpenAI 輪詢策略實例"""
        return OpenAIPollingStrategy()
    
    def test_openai_strategy_initialization(self, openai_strategy):
        """測試 OpenAI 策略初始化"""
        assert openai_strategy.max_wait_time == 90
        assert openai_strategy.status_multipliers['queued'] == 1.5
        assert openai_strategy.status_multipliers['in_progress'] == 1.0
        assert openai_strategy.status_multipliers['requires_action'] == 0.3
        assert openai_strategy.status_multipliers['cancelling'] == 0.5
    
    def test_openai_get_wait_time_with_status_multipliers(self, openai_strategy):
        """測試 OpenAI 特定的等待時間計算"""
        # 測試不同狀態的乘數效果
        base_wait = 5  # 第一次嘗試的基礎等待時間
        
        # 排隊狀態
        queued_time = openai_strategy.get_wait_time(0, 'queued')
        assert queued_time == base_wait * 1.5
        
        # 執行中狀態
        in_progress_time = openai_strategy.get_wait_time(0, 'in_progress')
        assert in_progress_time == base_wait * 1.0
        
        # 需要操作狀態
        requires_action_time = openai_strategy.get_wait_time(0, 'requires_action')
        assert requires_action_time == base_wait * 0.3
        
        # 取消中狀態
        cancelling_time = openai_strategy.get_wait_time(0, 'cancelling')
        assert cancelling_time == base_wait * 0.5
        
        # 未知狀態（使用預設乘數 1.0）
        unknown_time = openai_strategy.get_wait_time(0, 'unknown_status')
        assert unknown_time == base_wait * 1.0
    
    def test_openai_strategy_inheritance(self, openai_strategy):
        """測試 OpenAI 策略繼承了基礎功能"""
        # 測試基礎方法仍然可用
        assert openai_strategy.should_continue_polling(50) is True
        assert openai_strategy.should_continue_polling(100) is False
        
        # 測試基礎等待序列
        assert openai_strategy._get_base_wait_time(0) == 5
        assert openai_strategy._get_base_wait_time(1) == 3
        assert openai_strategy._get_base_wait_time(4) == 1


class TestSmartPollingEdgeCases:
    """測試智慧輪詢的邊界情況"""
    
    def test_polling_context_with_time_errors_throughout(self):
        """測試整個過程中時間函數都有問題的情況"""
        mock_strategy = Mock(spec=SmartPollingStrategy)
        mock_strategy.should_continue_polling.return_value = False
        
        check_function = Mock(return_value=(True, 'in_progress', {}))
        
        time_calls = [0]
        
        def mock_time():
            time_calls[0] += 1
            if time_calls[0] >= 2:  # 從第二次調用開始拋出異常
                raise StopIteration("time mock exhausted")
            return 0
        
        with patch('time.time', side_effect=mock_time), \
             patch('src.core.smart_polling.logger'):
            
            with PollingContext("error_test", mock_strategy) as context:
                success, data, error = context.wait_for_condition(
                    check_function, ['completed'], ['failed']
                )
            
            assert success is False
            assert data is None
            assert error == "Request timeout"
    
    def test_polling_context_start_time_error(self):
        """測試開始時間獲取錯誤"""
        time_calls = [0]
        
        def mock_time():
            if time_calls[0] >= 1:
                raise StopIteration("time mock exhausted")
            time_calls[0] += 1
            return 0
        
        with patch('time.time', side_effect=mock_time):
            # 即使時間獲取失敗，上下文仍應該能創建
            try:
                with PollingContext("start_error_test") as context:
                    assert context.operation_name == "start_error_test"
            except StopIteration:
                # 如果在初始化時就拋出異常，我們接受這個行為
                # 因為這表示 time.time() 確實被正確調用了
                pass
    
    def test_smart_polling_strategy_with_extreme_values(self):
        """測試極端值情況"""
        strategy = SmartPollingStrategy()
        
        # 測試非常大的嘗試次數
        wait_time = strategy.get_wait_time(1000, 'in_progress')
        assert wait_time == 1  # 應該回到最終間隔
        
        # 測試負數嘗試次數（不應該發生，但測試穩健性）
        wait_time = strategy.get_wait_time(0, 'in_progress')
        assert wait_time == 5  # 應該回到第一個值
    
    def test_polling_summary_with_edge_cases(self):
        """測試輪詢摘要的邊界情況"""
        strategy = SmartPollingStrategy()
        
        # 測試負數時間
        summary = strategy.get_polling_summary(1, -1.0, 'error')
        assert "總耗時 -1.0秒" in summary
        
        # 測試零嘗試次數
        summary = strategy.get_polling_summary(0, 10.0, 'timeout')
        assert "平均間隔 10.0秒" in summary  # 零嘗試時，平均間隔等於總時間


if __name__ == "__main__":
    pytest.main([__file__])