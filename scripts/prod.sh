#!/bin/bash
# 生產環境啟動腳本

echo "🚀 啟動生產環境..."
echo "使用 Gunicorn WSGI 服務器"

# 移動到腳本所在目錄，然後移動到項目根目錄
cd "$(dirname "${BASH_SOURCE[0]}")"
pushd .. > /dev/null
PROJECT_ROOT="$(pwd)"
popd > /dev/null

# 載入本地環境變量（如果存在）
if [ -f "$PROJECT_ROOT/.env.local" ]; then
    echo "載入本地環境變量..."
    set -o allexport
    source "$PROJECT_ROOT/.env.local"
    set +o allexport
fi

# 設置生產環境變量
export FLASK_ENV=production
export DEBUG=false

# 檢查 Gunicorn 是否安裝
if ! command -v gunicorn &> /dev/null; then
    echo "❌ 錯誤: 未安裝 gunicorn"
    echo "請運行: pip install gunicorn"
    exit 1
fi

# 使用 Gunicorn 配置文件啟動
echo "🔧 配置: gunicorn.conf.py"
echo "📱 應用: main:application"

# 切換到項目根目錄並啟動 Gunicorn
cd "$PROJECT_ROOT"
gunicorn -c gunicorn.conf.py main:application