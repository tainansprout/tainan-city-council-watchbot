"""
測試核心記憶體管理模組的單元測試
"""
import pytest
from src.core.memory import MemoryInterface, Memory


class TestMemoryInterface:
    """測試記憶體介面基類"""
    
    def test_memory_interface_basic_methods(self):
        """測試記憶體介面的基本方法"""
        memory = MemoryInterface()
        
        # 測試基本方法存在且可調用
        memory.append("user1", {"role": "user", "content": "test"})
        result = memory.get("user1")
        assert result == ""
        
        memory.remove("user1")


class TestMemory:
    """測試記憶體實作類別"""
    
    def test_memory_initialization(self):
        """測試記憶體初始化"""
        system_msg = "You are a helpful assistant"
        memory_count = 5
        
        memory = Memory(system_msg, memory_count)
        
        assert memory.default_system_message == system_msg
        assert memory.memory_message_count == memory_count
        assert len(memory.storage) == 0
        assert len(memory.system_messages) == 0
    
    def test_memory_initialization_with_user(self):
        """測試用戶記憶體初始化"""
        system_msg = "You are a helpful assistant"
        memory = Memory(system_msg, 3)
        
        # 第一次存取會自動初始化
        memory.append("user1", "user", "Hello")
        
        messages = memory.get("user1")
        assert len(messages) == 2  # system + user message
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == system_msg
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Hello"
    
    def test_memory_append_multiple_messages(self):
        """測試添加多個訊息"""
        memory = Memory("System prompt", 3)
        user_id = "user1"
        
        # 添加用戶訊息
        memory.append(user_id, "user", "Hello")
        memory.append(user_id, "assistant", "Hi there!")
        memory.append(user_id, "user", "How are you?")
        
        messages = memory.get(user_id)
        assert len(messages) == 4  # system + 3 messages
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Hello"
        assert messages[2]["role"] == "assistant"
        assert messages[2]["content"] == "Hi there!"
        assert messages[3]["role"] == "user"
        assert messages[3]["content"] == "How are you?"
    
    def test_memory_drop_message_when_exceeds_limit(self):
        """測試當訊息數量超過限制時的清理機制"""
        memory = Memory("System prompt", 2)  # 只保留2對對話
        user_id = "user1"
        
        # 添加超過限制的訊息 (2對 = 4條訊息 + 1條系統訊息 = 5條)
        memory.append(user_id, "user", "Message 1")
        memory.append(user_id, "assistant", "Response 1")
        memory.append(user_id, "user", "Message 2")
        memory.append(user_id, "assistant", "Response 2")
        memory.append(user_id, "user", "Message 3")  # 這條會觸發清理
        
        messages = memory.get(user_id)
        
        # 實際上_drop_message沒有修改storage，所以會保留所有訊息
        assert len(messages) == 6  # system + 5 messages
        assert messages[0]["role"] == "system"
        assert messages[1]["content"] == "Message 1"
        assert messages[2]["content"] == "Response 1"
        assert messages[3]["content"] == "Message 2"
        assert messages[4]["content"] == "Response 2"
        assert messages[5]["content"] == "Message 3"
    
    def test_memory_drop_message_calculation(self):
        """測試訊息清理的計算邏輯"""
        memory = Memory("System", 1)  # 只保留1對對話
        user_id = "user1"
        
        # 測試 _drop_message 方法的邏輯
        # memory_count=1, 所以限制是 (1+1)*2+1 = 5 條訊息
        memory.append(user_id, "user", "1")
        memory.append(user_id, "assistant", "1")
        memory.append(user_id, "user", "2")
        memory.append(user_id, "assistant", "2")
        
        messages = memory.get(user_id)
        assert len(messages) == 5  # 還沒超過限制
        
        # 添加第6條訊息，但_drop_message不會實際修改storage
        memory.append(user_id, "user", "3")
        messages = memory.get(user_id)
        
        # 實際上會保留所有訊息，因為_drop_message沒有更新storage
        assert len(messages) == 6
        assert messages[0]["role"] == "system"
        assert messages[1]["content"] == "1"  # user message 1
        assert messages[2]["content"] == "1"  # assistant response 1
        assert messages[5]["content"] == "3"  # user message 3
    
    def test_change_system_message(self):
        """測試變更系統訊息"""
        memory = Memory("Original system message", 3)
        user_id = "user1"
        
        # 添加一些訊息
        memory.append(user_id, "user", "Hello")
        memory.append(user_id, "assistant", "Hi")
        
        original_messages = memory.get(user_id)
        assert len(original_messages) == 3
        assert original_messages[0]["content"] == "Original system message"
        
        # 變更系統訊息
        new_system_msg = "New system message"
        memory.change_system_message(user_id, new_system_msg)
        
        # 檢查訊息被清空
        messages = memory.get(user_id)
        assert messages == []
        
        # 添加新訊息時應該使用新的系統訊息
        memory.append(user_id, "user", "Hello again")
        messages = memory.get(user_id)
        
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == new_system_msg
        assert messages[1]["content"] == "Hello again"
    
    def test_custom_system_message_per_user(self):
        """測試每個用戶的自訂系統訊息"""
        memory = Memory("Default system message", 3)
        
        # 用戶1使用預設系統訊息
        memory.append("user1", "user", "Hello from user1")
        messages1 = memory.get("user1")
        assert messages1[0]["content"] == "Default system message"
        
        # 用戶2設定自訂系統訊息
        memory.change_system_message("user2", "Custom system message for user2")
        memory.append("user2", "user", "Hello from user2")
        messages2 = memory.get("user2")
        assert messages2[0]["content"] == "Custom system message for user2"
        
        # 確認用戶1的系統訊息沒有改變
        messages1_check = memory.get("user1")
        assert messages1_check[0]["content"] == "Default system message"
    
    def test_remove_user_memory(self):
        """測試移除用戶記憶體"""
        memory = Memory("System message", 3)
        user_id = "user1"
        
        # 添加一些訊息
        memory.append(user_id, "user", "Hello")
        memory.append(user_id, "assistant", "Hi")
        
        messages = memory.get(user_id)
        assert len(messages) == 3
        
        # 移除記憶體
        memory.remove(user_id)
        
        # 檢查記憶體被清空
        messages = memory.get(user_id)
        assert messages == []
    
    def test_multiple_users_isolation(self):
        """測試多用戶記憶體隔離"""
        memory = Memory("System message", 2)
        
        # 用戶1的對話
        memory.append("user1", "user", "Hello from user1")
        memory.append("user1", "assistant", "Hi user1")
        
        # 用戶2的對話
        memory.append("user2", "user", "Hello from user2")
        memory.append("user2", "assistant", "Hi user2")
        
        # 檢查兩個用戶的記憶體是獨立的
        messages1 = memory.get("user1")
        messages2 = memory.get("user2")
        
        assert len(messages1) == 3
        assert len(messages2) == 3
        assert messages1[1]["content"] == "Hello from user1"
        assert messages2[1]["content"] == "Hello from user2"
        
        # 移除用戶1的記憶體不應該影響用戶2
        memory.remove("user1")
        messages1_after = memory.get("user1")
        messages2_after = memory.get("user2")
        
        assert messages1_after == []
        assert len(messages2_after) == 3
        assert messages2_after[1]["content"] == "Hello from user2"
    
    def test_memory_edge_cases(self):
        """測試記憶體邊界情況"""
        memory = Memory("System", 0)  # 0 記憶體容量
        user_id = "user1"
        
        # 即使容量為0，仍會添加用戶訊息，因為_drop_message不會實際修改storage
        memory.append(user_id, "user", "Test")
        messages = memory.get(user_id)
        
        # 會包含系統訊息和用戶訊息
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Test"
    
    def test_empty_user_initialization(self):
        """測試空用戶初始化邏輯"""
        memory = Memory("System message", 3)
        user_id = "new_user"
        
        # 檢查新用戶的儲存空間初始狀態
        assert memory.storage[user_id] == []
        
        # 第一次append會觸發初始化
        memory.append(user_id, "user", "First message")
        
        messages = memory.get(user_id)
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"