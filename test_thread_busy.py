#!/usr/bin/env python3
"""
測試 OpenAI Assistant API Thread 重複發送訊息的錯誤處理
模擬 LINE 用戶重複發送訊息的情況
"""

import sys
import os
import asyncio
import time
from threading import Thread
from concurrent.futures import ThreadPoolExecutor

# 添加專案路徑
sys.path.append('.')

from src.core.config import load_config
from src.models.factory import ModelFactory
from src.platforms.base import PlatformMessage, PlatformUser, PlatformType
from src.services.chat import ChatService
from src.database.connection import Database

def test_concurrent_messages():
    """測試重複發送訊息到同一個 thread"""
    print("🧪 開始測試重複發送訊息到 OpenAI Assistant Thread...")
    
    # 載入配置
    config = load_config('config/config.yml')
    
    # 創建模型和服務
    llm_config = config.get('llm', {})
    provider = llm_config.get('provider', 'openai')
    model_config = config.get(provider, {})
    model_config['provider'] = provider
    model = ModelFactory.create_from_config(model_config)
    
    database = Database(config['db'])
    chat_service = ChatService(model=model, database=database, config=config)
    
    # 創建測試用戶
    test_user = PlatformUser(
        user_id='test_concurrent_user_123',
        display_name='Test Concurrent User',
        platform=PlatformType.LINE
    )
    
    # 創建測試訊息
    def create_test_message(message_num):
        return PlatformMessage(
            message_id=f'test_msg_{message_num}',
            user=test_user,
            content=f'測試訊息 {message_num}：請幫我查詢一些資訊',
            message_type='text',
            reply_token=f'test_reply_{message_num}'
        )
    
    # 儲存結果
    results = []
    
    def send_message(message_num):
        """發送單個訊息"""
        print(f"📤 發送訊息 {message_num}")
        message = create_test_message(message_num)
        
        try:
            start_time = time.time()
            response = chat_service.handle_message(message)
            end_time = time.time()
            
            result = {
                'message_num': message_num,
                'success': True,
                'response': response.content[:100] + '...' if len(response.content) > 100 else response.content,
                'time_taken': end_time - start_time
            }
            results.append(result)
            print(f"✅ 訊息 {message_num} 成功，耗時 {result['time_taken']:.2f}s")
            
        except Exception as e:
            result = {
                'message_num': message_num,
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }
            results.append(result)
            print(f"❌ 訊息 {message_num} 失敗: {e}")
    
    print("\n🚀 開始併發發送訊息...")
    
    # 使用 ThreadPoolExecutor 來模擬併發請求
    with ThreadPoolExecutor(max_workers=3) as executor:
        # 幾乎同時發送 3 個訊息
        futures = []
        for i in range(1, 4):
            future = executor.submit(send_message, i)
            futures.append(future)
            time.sleep(0.1)  # 短暫延遲，模擬快速連續點擊
        
        # 等待所有請求完成
        for future in futures:
            future.result()
    
    print("\n📊 測試結果:")
    for result in sorted(results, key=lambda x: x['message_num']):
        if result['success']:
            print(f"✅ 訊息 {result['message_num']}: 成功 ({result['time_taken']:.2f}s)")
        else:
            print(f"❌ 訊息 {result['message_num']}: 失敗")
            print(f"   錯誤類型: {result['error_type']}")
            print(f"   錯誤訊息: {result['error']}")
    
    return results

def test_sequential_fast_messages():
    """測試快速連續發送訊息"""
    print("\n🧪 開始測試快速連續發送訊息...")
    
    # 載入配置
    config = load_config('config/config.yml')
    
    # 直接使用 OpenAI model 進行更底層的測試
    llm_config = config.get('llm', {})
    provider = llm_config.get('provider', 'openai')
    model_config = config.get(provider, {})
    model_config['provider'] = provider
    model = ModelFactory.create_from_config(model_config)
    
    # 創建一個 thread
    print("📁 創建新的 OpenAI Assistant Thread...")
    is_successful, thread_info, error = model.create_thread()
    if not is_successful:
        print(f"❌ 無法創建 thread: {error}")
        return
    
    thread_id = thread_info.thread_id
    print(f"✅ Thread 創建成功: {thread_id}")
    
    # 快速發送多個訊息
    from src.models.base import ChatMessage
    
    for i in range(1, 4):
        print(f"\n📤 發送訊息 {i} 到 thread {thread_id}")
        message = ChatMessage(role='user', content=f'快速測試訊息 {i}')
        
        try:
            # 添加訊息到 thread
            is_successful, error = model.add_message_to_thread(thread_id, message)
            if not is_successful:
                print(f"❌ 添加訊息 {i} 失敗: {error}")
                continue
            
            print(f"✅ 訊息 {i} 已添加到 thread")
            
            # 立即執行 Assistant（這裡可能會衝突）
            try:
                is_successful, response, error = model.run_assistant(thread_id)
                if not is_successful:
                    print(f"❌ 執行 Assistant 失敗 (訊息 {i}): {error}")
                    print(f"   錯誤類型: {type(error).__name__}")
                else:
                    print(f"✅ Assistant 執行成功 (訊息 {i})")
                    
            except Exception as e:
                print(f"❌ Assistant 執行異常 (訊息 {i}): {e}")
                print(f"   異常類型: {type(e).__name__}")
                
        except Exception as e:
            print(f"❌ 處理訊息 {i} 時發生異常: {e}")
            print(f"   異常類型: {type(e).__name__}")
        
        # 很短的延遲，模擬快速點擊
        time.sleep(0.5)
    
    # 清理：刪除測試 thread
    try:
        model.delete_thread(thread_id)
        print(f"🗑️ 已刪除測試 thread: {thread_id}")
    except:
        pass

if __name__ == "__main__":
    print("🧪 OpenAI Assistant Thread 重複訊息測試")
    print("=" * 50)
    
    # 測試 1: 透過 ChatService 併發發送
    print("\n【測試 1】透過 ChatService 併發發送訊息")
    results1 = test_concurrent_messages()
    
    # 測試 2: 直接對 OpenAI API 快速連續發送
    print("\n【測試 2】直接對 OpenAI API 快速連續發送訊息")
    test_sequential_fast_messages()
    
    print("\n🔍 分析結果:")
    print("請檢查上述錯誤訊息，我們將根據具體的錯誤內容更新 error_handler.py")