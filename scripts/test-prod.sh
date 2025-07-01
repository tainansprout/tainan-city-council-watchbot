#!/bin/bash
# 本地生產環境測試腳本
# 在本地測試生產配置，但使用較少的 worker

echo "🧪 本地生產環境測試..."
echo "使用輕量級生產配置進行本地測試"

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

# 覆蓋為生產環境設定
export FLASK_ENV=production
export DEBUG=false
export PORT=${PORT:-8080}

# 檢查 Gunicorn 是否安裝
if ! command -v gunicorn &> /dev/null; then
    echo "❌ 錯誤: 未安裝 gunicorn"
    echo "請運行: pip install gunicorn"
    exit 1
fi

# 使用較輕量的配置進行本地測試
echo "🔧 使用本地測試配置"
echo "📱 應用: wsgi:application"
echo "🌐 URL: http://localhost:$PORT"
echo "環境: $FLASK_ENV"
echo ""

# 切換到項目根目錄並啟動 Gunicorn
cd "$PROJECT_ROOT"
gunicorn \
    --bind 127.0.0.1:$PORT \
    --workers ${GUNICORN_WORKERS:-1} \
    --worker-class gevent \
    --timeout ${GUNICORN_TIMEOUT:-60} \
    --keep-alive 2 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    wsgi:application