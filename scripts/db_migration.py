#!/usr/bin/env python3
"""
資料庫遷移管理腳本
提供完整的 Alembic 遷移管理功能
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path

# 添加專案根目錄到 Python 路徑
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import load_config
from src.core.logger import get_logger

logger = get_logger(__name__)

class DatabaseMigrationManager:
    """資料庫遷移管理器"""
    
    def __init__(self):
        self.project_root = PROJECT_ROOT
        self.alembic_ini = self.project_root / "alembic.ini"
        
    def run_alembic_command(self, command: list, capture_output: bool = False):
        """執行 Alembic 命令"""
        try:
            # 切換到專案根目錄
            os.chdir(self.project_root)
            
            # 構建完整命令
            full_command = ["alembic"] + command
            
            logger.info(f"執行命令: {' '.join(full_command)}")
            
            if capture_output:
                result = subprocess.run(
                    full_command,
                    capture_output=True,
                    text=True,
                    check=True
                )
                return result.stdout.strip()
            else:
                subprocess.run(full_command, check=True)
                return None
                
        except subprocess.CalledProcessError as e:
            logger.error(f"命令執行失敗: {e}")
            if hasattr(e, 'stderr') and e.stderr:
                logger.error(f"錯誤輸出: {e.stderr}")
            raise
        except Exception as e:
            logger.error(f"執行 Alembic 命令時發生錯誤: {e}")
            raise
    
    def init_migrations(self):
        """初始化遷移環境"""
        logger.info("初始化 Alembic 遷移環境...")
        
        if self.alembic_ini.exists():
            logger.warning("Alembic 已經初始化，跳過初始化步驟")
            return
        
        # 初始化 Alembic
        self.run_alembic_command(["init", "alembic"])
        logger.info("Alembic 初始化完成")
    
    def create_migration(self, message: str, auto: bool = True):
        """創建新的遷移檔案"""
        logger.info(f"創建遷移: {message}")
        
        if auto:
            # 自動偵測變更
            self.run_alembic_command(["revision", "--autogenerate", "-m", message])
        else:
            # 手動創建空白遷移
            self.run_alembic_command(["revision", "-m", message])
        
        logger.info("遷移檔案創建完成")
    
    def upgrade_database(self, revision: str = "head"):
        """升級資料庫到指定版本"""
        logger.info(f"升級資料庫到版本: {revision}")
        self.run_alembic_command(["upgrade", revision])
        logger.info("資料庫升級完成")
    
    def downgrade_database(self, revision: str):
        """降級資料庫到指定版本"""
        logger.info(f"降級資料庫到版本: {revision}")
        self.run_alembic_command(["downgrade", revision])
        logger.info("資料庫降級完成")
    
    def show_current_revision(self):
        """顯示當前資料庫版本"""
        try:
            current = self.run_alembic_command(["current"], capture_output=True)
            logger.info(f"當前資料庫版本: {current}")
            return current
        except Exception as e:
            logger.error(f"無法獲取當前版本: {e}")
            return None
    
    def show_migration_history(self):
        """顯示遷移歷史"""
        logger.info("遷移歷史:")
        self.run_alembic_command(["history", "--verbose"])
    
    def show_heads(self):
        """顯示所有 head 版本"""
        try:
            heads = self.run_alembic_command(["heads"], capture_output=True)
            logger.info(f"Head 版本: {heads}")
            return heads
        except Exception as e:
            logger.error(f"無法獲取 head 版本: {e}")
            return None
    
    def validate_migrations(self):
        """驗證遷移檔案完整性"""
        logger.info("驗證遷移檔案...")
        
        # 檢查是否有分支
        try:
            self.run_alembic_command(["check"])
            logger.info("遷移檔案驗證通過")
            return True
        except subprocess.CalledProcessError:
            logger.error("遷移檔案驗證失敗 - 可能存在分支或其他問題")
            return False
    
    def stamp_database(self, revision: str):
        """標記資料庫版本（不執行 SQL）"""
        logger.info(f"標記資料庫版本為: {revision}")
        self.run_alembic_command(["stamp", revision])
        logger.info("資料庫版本標記完成")
    
    def show_sql(self, revision_range: str = "head"):
        """顯示 SQL 而不執行"""
        logger.info(f"顯示 SQL（版本範圍: {revision_range}）:")
        self.run_alembic_command(["upgrade", revision_range, "--sql"])
    
    def auto_setup(self):
        """自動設置遷移環境"""
        logger.info("開始自動設置遷移環境...")
        
        # 1. 檢查配置
        try:
            config = load_config()
            db_config = config.get('db', {})
            if not db_config:
                raise ValueError("找不到資料庫配置")
            logger.info("配置檢查通過")
        except Exception as e:
            logger.error(f"配置檢查失敗: {e}")
            return False
        
        # 2. 初始化遷移環境（如果需要）
        if not self.alembic_ini.exists():
            self.init_migrations()
        
        # 3. 驗證遷移檔案
        if not self.validate_migrations():
            logger.error("遷移檔案驗證失敗")
            return False
        
        # 4. 顯示當前狀態
        self.show_current_revision()
        self.show_heads()
        
        logger.info("自動設置完成")
        return True

def main():
    """主函數"""
    parser = argparse.ArgumentParser(description="資料庫遷移管理工具")
    parser.add_argument("command", choices=[
        "init", "create", "upgrade", "downgrade", "current", 
        "history", "heads", "validate", "stamp", "sql", "auto-setup"
    ], help="要執行的命令")
    
    parser.add_argument("-m", "--message", help="遷移訊息（用於 create）")
    parser.add_argument("-r", "--revision", help="目標版本（用於 upgrade/downgrade/stamp）")
    parser.add_argument("--manual", action="store_true", help="手動創建遷移（不自動偵測）")
    parser.add_argument("--sql-only", action="store_true", help="只顯示 SQL，不執行")
    
    args = parser.parse_args()
    
    manager = DatabaseMigrationManager()
    
    try:
        if args.command == "init":
            manager.init_migrations()
            
        elif args.command == "create":
            if not args.message:
                logger.error("創建遷移需要提供訊息（-m 或 --message）")
                return 1
            manager.create_migration(args.message, auto=not args.manual)
            
        elif args.command == "upgrade":
            revision = args.revision or "head"
            if args.sql_only:
                manager.show_sql(revision)
            else:
                manager.upgrade_database(revision)
                
        elif args.command == "downgrade":
            if not args.revision:
                logger.error("降級需要指定目標版本（-r 或 --revision）")
                return 1
            manager.downgrade_database(args.revision)
            
        elif args.command == "current":
            manager.show_current_revision()
            
        elif args.command == "history":
            manager.show_migration_history()
            
        elif args.command == "heads":
            manager.show_heads()
            
        elif args.command == "validate":
            if manager.validate_migrations():
                logger.info("所有遷移檔案都有效")
                return 0
            else:
                logger.error("遷移檔案驗證失敗")
                return 1
                
        elif args.command == "stamp":
            if not args.revision:
                logger.error("標記版本需要指定目標版本（-r 或 --revision）")
                return 1
            manager.stamp_database(args.revision)
            
        elif args.command == "sql":
            revision_range = args.revision or "head"
            manager.show_sql(revision_range)
            
        elif args.command == "auto-setup":
            if manager.auto_setup():
                logger.info("自動設置成功")
                return 0
            else:
                logger.error("自動設置失敗")
                return 1
        
        return 0
        
    except Exception as e:
        logger.error(f"命令執行失敗: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())