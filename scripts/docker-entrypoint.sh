#!/bin/bash
set -e

# Docker Entrypoint Script
# 遵循 2024 年 Docker 最佳實踐：將遷移與應用啟動解耦

echo "🐳 Docker Entrypoint - ChatGPT Line Bot"
echo "Environment: ${FLASK_ENV:-development}"

# 函數：等待資料庫就緒
wait_for_database() {
    echo "⏳ 等待資料庫連線..."
    
    # 使用 Python 腳本檢查資料庫連線
    python3 -c "
import os
import time
import psycopg2
from urllib.parse import urlparse

def wait_for_db():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print('⚠️  DATABASE_URL 未設定，跳過資料庫檢查')
        return True
    
    parsed = urlparse(database_url)
    
    max_retries = 30
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            conn = psycopg2.connect(
                host=parsed.hostname,
                port=parsed.port or 5432,
                user=parsed.username,
                password=parsed.password,
                database=parsed.path[1:] if parsed.path else 'postgres'
            )
            conn.close()
            print('✅ 資料庫連線成功')
            return True
        except Exception as e:
            retry_count += 1
            print(f'❌ 資料庫連線失敗 (嘗試 {retry_count}/{max_retries}): {e}')
            if retry_count < max_retries:
                time.sleep(2)
    
    print('💥 資料庫連線超時')
    return False

if not wait_for_db():
    exit(1)
"
    
    if [ $? -ne 0 ]; then
        echo "💥 資料庫連線失敗，退出"
        exit 1
    fi
}

# 函數：運行資料庫遷移
run_migrations() {
    echo "🔄 執行資料庫遷移..."
    
    # 使用新的遷移工具
    python scripts/migrate.py setup
    
    if [ $? -ne 0 ]; then
        echo "💥 資料庫遷移失敗"
        exit 1
    fi
    
    echo "✅ 資料庫遷移完成"
}

# 函數：啟動應用程式
start_application() {
    echo "🚀 啟動應用程式..."
    
    if [ "${FLASK_ENV}" = "production" ]; then
        echo "🏭 生產模式 - 使用 Gunicorn"
        exec gunicorn -c gunicorn.conf.py main:application
    else
        echo "🛠️  開發模式 - 使用 Flask 開發服務器"
        exec python main.py
    fi
}

# 主要邏輯
case "${1}" in
    "migrate-only")
        echo "📋 僅執行資料庫遷移模式"
        wait_for_database
        run_migrations
        echo "✅ 遷移完成，容器退出"
        ;;
    
    "app-only")
        echo "🏃 僅啟動應用程式模式（跳過遷移）"
        wait_for_database
        start_application
        ;;
    
    "full" | "")
        echo "🔄 完整模式：遷移 + 啟動應用程式"
        wait_for_database
        
        # 檢查是否應該運行遷移
        if [ "${SKIP_MIGRATIONS}" = "true" ]; then
            echo "⏭️  跳過資料庫遷移 (SKIP_MIGRATIONS=true)"
        else
            run_migrations
        fi
        
        start_application
        ;;
    
    "bash")
        echo "🔧 進入 bash shell"
        exec bash
        ;;
    
    *)
        echo "🎯 直接執行指定命令: $@"
        exec "$@"
        ;;
esac