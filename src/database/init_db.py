"""
資料庫初始化腳本
執行此腳本可以建立完整的資料庫結構
"""
import os
import sys
import logging
from src.core.logger import get_logger
from pathlib import Path

# 添加專案根目錄到 Python 路徑
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from alembic.config import Config
from alembic import command
from src.core.config import ConfigManager

logger = get_logger(__name__)


def init_database():
    """初始化資料庫結構"""
    try:
        # 獲取配置
        config_manager = ConfigManager()
        config = config_manager.get_config()
        
        # 設定 Alembic 配置
        alembic_cfg = Config(str(project_root / "alembic.ini"))
        
        # 檢查資料庫連接
        logger.info("檢查資料庫連接...")
        
        # 執行 migration 到最新版本
        logger.info("執行資料庫 migration...")
        command.upgrade(alembic_cfg, "head")
        
        logger.info("資料庫初始化完成！")
        return True
        
    except Exception as e:
        logger.error(f"資料庫初始化失敗: {e}")
        return False


def check_database_status():
    """檢查資料庫狀態"""
    try:
        alembic_cfg = Config(str(project_root / "alembic.ini"))
        
        # 檢查當前版本
        logger.info("檢查資料庫版本...")
        command.current(alembic_cfg)
        
        # 檢查是否有待執行的 migration
        logger.info("檢查待執行的 migration...")
        command.heads(alembic_cfg)
        
        return True
        
    except Exception as e:
        logger.error(f"檢查資料庫狀態失敗: {e}")
        return False


if __name__ == "__main__":
    # 使用統一的 logger 系統
    logger.info("Starting database initialization script...")
    
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        check_database_status()
    else:
        init_database()