#!/usr/bin/env python3
"""
一鍵建立資料庫腳本
執行此腳本可以完整建立專案所需的資料庫結構
"""
import os
import sys
import logging
from pathlib import Path

# 添加專案根目錄到 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.init_db import init_database, check_database_status
from src.database.operations import get_database_operations

logger = logging.getLogger(__name__)


def setup_complete_database():
    """完整的資料庫設置流程"""
    print("=" * 60)
    print("🚀 開始設置資料庫...")
    print("=" * 60)
    
    # 步驟 1: 初始化資料庫結構
    print("\n📋 步驟 1: 初始化資料庫結構")
    if init_database():
        print("✅ 資料庫結構初始化成功")
    else:
        print("❌ 資料庫結構初始化失敗")
        return False
    
    # 步驟 2: 檢查資料庫狀態
    print("\n📋 步驟 2: 檢查資料庫狀態")
    if check_database_status():
        print("✅ 資料庫狀態檢查通過")
    else:
        print("❌ 資料庫狀態檢查失敗")
        return False
    
    # 步驟 3: 執行健康檢查
    print("\n📋 步驟 3: 執行健康檢查")
    db_ops = get_database_operations()
    health_result = db_ops.health_check()
    
    if health_result["status"] == "healthy":
        print("✅ 資料庫健康檢查通過")
        print(f"   - 連接狀態: {'正常' if health_result['connection'] else '異常'}")
        print(f"   - 表結構: {health_result['tables']}")
        print(f"   - 統計資訊: {health_result.get('stats', {})}")
    else:
        print("❌ 資料庫健康檢查失敗")
        print(f"   - 錯誤: {health_result.get('error', '未知錯誤')}")
        return False
    
    print("\n" + "=" * 60)
    print("🎉 資料庫設置完成！")
    print("=" * 60)
    print("\n📝 後續步驟:")
    print("1. 確認配置文件 (config/config.yml) 中的資料庫連接設定")
    print("2. 啟動應用程式: python main.py")
    print("3. 如需清理舊資料: python -c \"from src.database.operations import get_database_operations; get_database_operations().cleanup_old_data()\"")
    
    return True


def show_help():
    """顯示使用說明"""
    print("""
資料庫設置腳本使用說明

用法:
    python scripts/setup_database.py [選項]

選項:
    setup       執行完整的資料庫設置 (預設)
    status      只檢查資料庫狀態
    health      執行健康檢查
    help        顯示此說明

範例:
    python scripts/setup_database.py setup
    python scripts/setup_database.py status
    python scripts/setup_database.py health
    """)


def main():
    """主函數"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 檢查命令行參數
    action = "setup"
    if len(sys.argv) > 1:
        action = sys.argv[1].lower()
    
    if action == "help":
        show_help()
    elif action == "status":
        print("檢查資料庫狀態...")
        check_database_status()
    elif action == "health":
        print("執行資料庫健康檢查...")
        db_ops = get_database_operations()
        result = db_ops.health_check()
        print(f"健康檢查結果: {result}")
    elif action == "setup":
        success = setup_complete_database()
        sys.exit(0 if success else 1)
    else:
        print(f"未知的選項: {action}")
        print("使用 'help' 查看可用選項")
        sys.exit(1)


if __name__ == "__main__":
    main()