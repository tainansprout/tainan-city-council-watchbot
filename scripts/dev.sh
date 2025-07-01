#!/bin/bash
# 開發環境啟動腳本

echo "🔧 啟動開發環境..."
echo "使用 Flask 開發服務器 (僅適用於開發)"

# 移動到腳本所在目錄，然後移動到項目根目錄
cd "$(dirname "${BASH_SOURCE[0]}")"
pushd .. > /dev/null
PROJECT_ROOT="$(pwd)"
popd > /dev/null

# 載入本地環境變量
if [ -f "$PROJECT_ROOT/.env.local" ]; then
    echo "載入本地環境變量..."
    set -o allexport
    source "$PROJECT_ROOT/.env.local"
    set +o allexport
else
    echo "⚠️  找不到 .env.local 檔案"
    echo "請複製 .env.local.example 為 .env.local 並填入實際的值"
    
    # 設置基本開發環境變量
    export FLASK_ENV=development
    export DEBUG=true
    export HOST=127.0.0.1
    export PORT=8080
fi

echo "環境: $FLASK_ENV"
echo "主機: $HOST"
echo "端口: $PORT"
echo ""

# 切換到項目根目錄並啟動 Flask 開發服務器
cd "$PROJECT_ROOT"
python main.py