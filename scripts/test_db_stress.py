#!/usr/bin/env python3
"""
資料庫連線池壓力測試
測試統一連線池在併發壓力下的行為

用法：
    python scripts/test_db_stress.py
    python scripts/test_db_stress.py --threads 30 --hold 2.0
"""
import sys
import os
import time
import threading
import argparse
from pathlib import Path

# 加入專案根目錄
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def get_database():
    """建立 Database instance"""
    from src.database.connection import Database
    from src.core.config import load_config
    config = load_config()
    return Database(config['db'])


def print_pool_status(db, label=""):
    """印出連線池狀態"""
    info = db.get_connection_info()
    print(f"  [{label}] pool_size={info['pool_size']} "
          f"checked_in={info['checked_in']} "
          f"checked_out={info['checked_out']} "
          f"overflow={info['overflow']}")


def worker(db, worker_id, hold_seconds, results):
    """模擬一個併發連線"""
    start = time.time()
    try:
        with db.get_session() as session:
            from sqlalchemy import text
            session.execute(text("SELECT 1"))
            elapsed_acquire = time.time() - start

            # 持有連線一段時間，模擬實際操作
            time.sleep(hold_seconds)

            elapsed_total = time.time() - start
            results[worker_id] = {
                'status': 'ok',
                'acquire_time': elapsed_acquire,
                'total_time': elapsed_total
            }
    except Exception as e:
        elapsed_total = time.time() - start
        results[worker_id] = {
            'status': 'error',
            'error': str(e),
            'total_time': elapsed_total
        }


def run_test(num_threads, hold_seconds):
    """執行壓力測試"""
    print(f"\n{'='*60}")
    print(f"資料庫連線池壓力測試")
    print(f"{'='*60}")

    db = get_database()

    # 先確認連線正常
    if not db.check_connection():
        print("ERROR: 無法連線到資料庫")
        return

    pool = db.engine.pool
    print(f"\n連線池設定:")
    print(f"  pool_size = {pool.size()}")
    print(f"  max_overflow = {pool._max_overflow}")
    print(f"  pool_timeout = {pool._timeout}")
    max_connections = pool.size() + pool._max_overflow
    print(f"  最大連線數 = {max_connections}")

    print(f"\n測試參數:")
    print(f"  併發 threads = {num_threads}")
    print(f"  每個連線持有時間 = {hold_seconds}s")

    # --- Test 1: 逐步增加併發 ---
    for batch_size in [1, 5, 10, 15, max_connections, num_threads]:
        if batch_size > num_threads:
            continue

        print(f"\n--- 測試: {batch_size} 個併發連線 ---")
        print_pool_status(db, "開始前")

        results = {}
        threads = []

        start = time.time()
        for i in range(batch_size):
            t = threading.Thread(target=worker, args=(db, i, hold_seconds, results))
            threads.append(t)
            t.start()

        # 等所有 thread 開始後印出狀態
        time.sleep(0.3)
        print_pool_status(db, "執行中")

        for t in threads:
            t.join(timeout=30)

        elapsed = time.time() - start
        print_pool_status(db, "結束後")

        # 統計結果
        ok_count = sum(1 for r in results.values() if r['status'] == 'ok')
        err_count = sum(1 for r in results.values() if r['status'] == 'error')
        acquire_times = [r['acquire_time'] for r in results.values() if r['status'] == 'ok']

        print(f"  結果: {ok_count} 成功, {err_count} 失敗, 耗時 {elapsed:.2f}s")
        if acquire_times:
            print(f"  取得連線時間: min={min(acquire_times):.3f}s "
                  f"max={max(acquire_times):.3f}s "
                  f"avg={sum(acquire_times)/len(acquire_times):.3f}s")
        if err_count > 0:
            for wid, r in results.items():
                if r['status'] == 'error':
                    print(f"  Worker {wid} 錯誤: {r['error'][:100]}")

    # --- Test 2: 超過上限 ---
    over_limit = max_connections + 5
    if over_limit > num_threads:
        over_limit = num_threads

    if over_limit > max_connections:
        print(f"\n--- 測試: 超過上限 ({over_limit} > {max_connections}) ---")
        print(f"  預期: 部分連線需等待，pool_timeout={pool._timeout}s 後可能 timeout")
        print_pool_status(db, "開始前")

        results = {}
        threads = []

        start = time.time()
        for i in range(over_limit):
            t = threading.Thread(target=worker, args=(db, i, hold_seconds, results))
            threads.append(t)
            t.start()

        time.sleep(0.3)
        print_pool_status(db, "執行中")

        for t in threads:
            t.join(timeout=60)

        elapsed = time.time() - start
        print_pool_status(db, "結束後")

        ok_count = sum(1 for r in results.values() if r['status'] == 'ok')
        err_count = sum(1 for r in results.values() if r['status'] == 'error')
        print(f"  結果: {ok_count} 成功, {err_count} 失敗, 耗時 {elapsed:.2f}s")

    # 清理
    db.close_engine()
    print(f"\n{'='*60}")
    print(f"測試完成")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="資料庫連線池壓力測試")
    parser.add_argument("--threads", type=int, default=20, help="最大併發 thread 數（預設 20）")
    parser.add_argument("--hold", type=float, default=1.0, help="每個連線持有秒數（預設 1.0）")
    args = parser.parse_args()

    run_test(args.threads, args.hold)
