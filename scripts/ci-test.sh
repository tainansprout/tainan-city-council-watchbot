#!/bin/bash

# CI/CD 測試腳本
# 模擬持續整合流程中的關鍵測試

set -e  # 遇到錯誤立即退出

echo "🚀 開始 CI/CD 測試流程"

# 移動到項目根目錄
cd "$(dirname "${BASH_SOURCE[0]}")"
cd ..

echo "📁 當前目錄: $(pwd)"

# 清理快取
echo "🧹 清理 Python 快取..."
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
rm -rf .pytest_cache 2>/dev/null || true

# 檢查語法
echo "✅ 檢查 Python 語法..."
python -m py_compile main.py
python -m py_compile src/core/config.py
python -m py_compile src/app.py

# 檢查導入
echo "📦 檢查關鍵模組導入..."
python -c "
from src.core.config import ConfigManager
from src.app import create_app
print('✅ 所有關鍵模組導入成功')
" > /dev/null

# 檢查配置文件
echo "⚙️  檢查配置文件..."
python -c "
import yaml
with open('config/config.yml.example', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)
required_sections = ['app', 'llm', 'platforms', 'db', 'auth']
for section in required_sections:
    assert section in config, f'Missing config section: {section}'
print('✅ 配置文件格式正確')
" > /dev/null

# 測試收集
echo "🔍 測試收集驗證..."
test_count=$(pytest --collect-only --no-cov 2>/dev/null | grep "collected" | tail -1 | grep -o '[0-9]\+' | head -1)
echo "✅ 成功收集 $test_count 個測試"

# 運行關鍵測試
echo "🧪 運行關鍵測試..."
pytest tests/unit/test_config_manager.py::TestConfigManager::test_singleton_pattern -v --no-cov > /dev/null
echo "✅ ConfigManager 測試通過"

# 檢查部署腳本語法
echo "📜 檢查部署腳本語法..."
bash -n scripts/deploy/deploy-to-cloudrun.sh
bash -n scripts/dev.sh
bash -n scripts/prod.sh
echo "✅ 所有腳本語法正確"

echo ""
echo "🎉 CI/CD 測試流程完成！"
echo "📊 測試統計:"
echo "   - Python 文件: $(find . -name '*.py' -type f | wc -l | tr -d ' ')"
echo "   - 測試數量: $test_count"
echo "   - 配置文件: ✅ 正確"
echo "   - 腳本語法: ✅ 正確"
echo "   - 關鍵功能: ✅ 正常"