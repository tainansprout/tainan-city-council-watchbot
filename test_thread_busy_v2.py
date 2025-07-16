#!/usr/bin/env python3
"""
更準確的測試：模擬同一個 LINE 用戶在同一個 thread 中快速發送多個訊息
"""

import sys
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加專案路徑
sys.path.append('.')

from src.core.config import load_config
from src.models.factory import ModelFactory
from src.platforms.base import PlatformMessage, PlatformUser, PlatformType
from src.services.chat import ChatService
from src.database.connection import Database

def test_same_user_concurrent_messages():
    """測試同一個用戶快速連續發送訊息"""
    print("🧪 測試同一個用戶快速連續發送訊息...")
    
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
    
    # 使用固定的用戶 ID（模擬真實 LINE 用戶）
    test_user = PlatformUser(
        user_id='line_user_fixed_123',  # 固定的用戶 ID
        display_name='Fixed LINE User',
        platform=PlatformType.LINE
    )
    
    # 首先發送一個訊息來建立 thread
    print("📝 建立初始 thread...")
    initial_message = PlatformMessage(
        message_id='init_msg',
        user=test_user,
        content='初始訊息，建立 thread',
        message_type='text',
        reply_token='init_reply'
    )
    
    try:
        initial_response = chat_service.handle_message(initial_message)
        print(f"✅ 初始 thread 建立成功")
        time.sleep(1)  # 等待初始響應完成
    except Exception as e:
        print(f"❌ 初始 thread 建立失敗: {e}")
        return
    
    # 現在快速發送多個訊息到同一個用戶（應該使用同一個 thread）
    results = []
    
    def send_concurrent_message(message_num):
        """發送併發訊息到同一個用戶"""
        message = PlatformMessage(
            message_id=f'concurrent_msg_{message_num}',
            user=test_user,  # 相同的用戶
            content=f'併發訊息 {message_num}：請快速回應',
            message_type='text',
            reply_token=f'concurrent_reply_{message_num}'
        )
        
        try:
            print(f"📤 發送併發訊息 {message_num} (用戶: {test_user.user_id})")
            start_time = time.time()
            response = chat_service.handle_message(message)
            end_time = time.time()
            
            result = {
                'message_num': message_num,
                'success': True,
                'time_taken': end_time - start_time,
                'response_preview': response.content[:50] + '...' if len(response.content) > 50 else response.content
            }
            results.append(result)
            print(f"✅ 併發訊息 {message_num} 成功")
            
        except Exception as e:
            result = {
                'message_num': message_num,
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }
            results.append(result)
            print(f"❌ 併發訊息 {message_num} 失敗: {e}")
    
    # 同時發送多個訊息（模擬用戶快速點擊）
    print("\n🚀 同時發送多個訊息到同一個用戶...")
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        # 幾乎同時提交多個任務
        futures = []
        for i in range(1, 6):  # 發送 5 個併發訊息
            future = executor.submit(send_concurrent_message, i)
            futures.append(future)
        
        # 等待所有任務完成
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"❌ 執行任務時發生異常: {e}")
    
    # 顯示結果
    print("\n📊 併發測試結果:")
    for result in sorted(results, key=lambda x: x['message_num']):
        if result['success']:
            print(f"✅ 訊息 {result['message_num']}: 成功 ({result['time_taken']:.2f}s)")
        else:
            print(f"❌ 訊息 {result['message_num']}: 失敗")
            print(f"   錯誤類型: {result['error_type']}")
            print(f"   錯誤訊息: {result['error']}")
    
    return results

def test_direct_openai_thread_collision():
    """直接測試 OpenAI Thread 的併發衝突"""
    print("\n🧪 直接測試 OpenAI Thread 的併發衝突...")
    
    # 載入配置
    config = load_config('config/config.yml')
    
    # 創建 OpenAI 模型
    llm_config = config.get('llm', {})
    provider = llm_config.get('provider', 'openai')
    model_config = config.get(provider, {})
    model_config['provider'] = provider
    model = ModelFactory.create_from_config(model_config)
    
    # 創建一個 thread
    print("📁 創建測試 thread...")
    is_successful, thread_info, error = model.create_thread()
    if not is_successful:
        print(f"❌ 無法創建 thread: {error}")
        return
    
    thread_id = thread_info.thread_id
    print(f"✅ Thread 創建成功: {thread_id}")
    
    # 定義併發執行函數
    def run_assistant_concurrent(run_num):
        """併發執行 Assistant"""
        from src.models.base import ChatMessage
        
        try:
            # 添加訊息
            message = ChatMessage(role='user', content=f'併發執行測試 {run_num}')
            is_successful, error = model.add_message_to_thread(thread_id, message)
            
            if not is_successful:
                print(f"❌ 添加訊息失敗 (run {run_num}): {error}")
                return {'run_num': run_num, 'success': False, 'stage': 'add_message', 'error': error}
            
            # 立即執行 Assistant（這裡可能會衝突）
            print(f"🏃 執行 Assistant (run {run_num})")
            is_successful, response, error = model.run_assistant(thread_id)
            
            if not is_successful:
                print(f"❌ 執行 Assistant 失敗 (run {run_num}): {error}")
                return {'run_num': run_num, 'success': False, 'stage': 'run_assistant', 'error': error}
            
            print(f"✅ Assistant 執行成功 (run {run_num})")
            return {'run_num': run_num, 'success': True}
            
        except Exception as e:
            print(f"❌ 執行過程中發生異常 (run {run_num}): {e}")
            return {'run_num': run_num, 'success': False, 'stage': 'exception', 'error': str(e), 'error_type': type(e).__name__}
    
    # 併發執行多個 Assistant runs
    print(f"\n🚀 同時執行多個 Assistant runs (thread: {thread_id})")
    
    run_results = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = []
        for i in range(1, 4):  # 同時執行 3 個 Assistant runs
            future = executor.submit(run_assistant_concurrent, i)
            futures.append(future)
        
        for future in as_completed(futures):
            try:
                result = future.result()
                run_results.append(result)
            except Exception as e:
                print(f"❌ 執行任務時發生異常: {e}")
    
    # 顯示結果
    print("\n📊 直接 OpenAI 併發測試結果:")
    for result in sorted(run_results, key=lambda x: x['run_num']):
        if result['success']:
            print(f"✅ Run {result['run_num']}: 成功")
        else:
            print(f"❌ Run {result['run_num']}: 失敗 (階段: {result['stage']})")
            print(f"   錯誤: {result['error']}")
            if 'error_type' in result:
                print(f"   錯誤類型: {result['error_type']}")
    
    # 清理
    try:
        model.delete_thread(thread_id)
        print(f"🗑️ 已刪除測試 thread: {thread_id}")
    except:
        pass
    
    return run_results

if __name__ == "__main__":
    print("🧪 OpenAI Thread 併發衝突測試 v2")
    print("=" * 50)
    
    # 測試 1: 同一個用戶快速發送多個訊息
    print("\n【測試 1】同一個用戶快速發送多個訊息")
    results1 = test_same_user_concurrent_messages()
    
    # 測試 2: 直接測試 OpenAI Thread 併發衝突
    print("\n【測試 2】直接測試 OpenAI Thread 併發衝突")
    results2 = test_direct_openai_thread_collision()
    
    print("\n🔍 分析結果:")
    print("根據上述錯誤訊息，我們將更新 error_handler.py 來處理特定的 OpenAI 錯誤")