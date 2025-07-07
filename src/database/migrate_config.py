"""
Flask-Migrate 配置模組
遵循 2024 年資料庫遷移最佳實踐
"""

import os
from flask import Flask
from flask_migrate import Migrate
from .models import db


def init_migrate(app: Flask) -> Migrate:
    """
    初始化 Flask-Migrate
    
    遵循最佳實踐:
    - 自動啟用 compare_type (檢測欄位類型變更)
    - 自動啟用 render_as_batch (支援 SQLite)
    - 配置適當的比較選項
    """
    
    # Flask-Migrate 4.0+ 自動啟用這些選項
    migrate = Migrate(
        app, 
        db,
        # 自動啟用的選項 (Flask-Migrate 4.0+):
        # compare_type=True,      # 檢測欄位類型變更
        # render_as_batch=True,   # SQLite 兼容模式
        directory='migrations'   # 遷移檔案目錄
    )
    
    return migrate


def configure_migration_logging():
    """配置遷移過程的日誌"""
    import logging
    
    # 設置 Alembic 日誌等級
    logging.getLogger('alembic').setLevel(logging.INFO)
    
    # 如果是生產環境，降低日誌等級
    if os.getenv('FLASK_ENV') == 'production':
        logging.getLogger('alembic.runtime.migration').setLevel(logging.WARNING)


def get_migration_config():
    """
    取得遷移相關配置
    
    Returns:
        dict: 遷移配置字典
    """
    return {
        'directory': 'migrations',
        'multidb': False,  # 單一資料庫
        'compare_type': True,  # 檢測類型變更
        'compare_server_default': True,  # 檢測預設值變更
        'render_as_batch': True,  # SQLite 支援
    }


def is_migration_mode() -> bool:
    """檢查是否為遷移模式"""
    return os.getenv('MIGRATION_MODE', '').lower() == 'true'


def validate_migration_environment():
    """
    驗證遷移環境
    
    檢查:
    - 資料庫連線
    - 必要的環境變數
    - 遷移目錄結構
    """
    errors = []
    
    # 檢查資料庫 URL
    database_url = os.getenv('DATABASE_URL') or os.getenv('SQLALCHEMY_DATABASE_URI')
    if not database_url:
        errors.append("缺少資料庫連線設定 (DATABASE_URL 或 SQLALCHEMY_DATABASE_URI)")
    
    # 檢查遷移目錄
    import pathlib
    project_root = pathlib.Path(__file__).parent.parent.parent
    migrations_dir = project_root / 'migrations'
    
    if migrations_dir.exists():
        # 檢查 Alembic 配置
        alembic_ini = migrations_dir / 'alembic.ini'
        env_py = migrations_dir / 'env.py'
        
        if not env_py.exists():
            errors.append("遷移環境不完整，請運行 init 命令")
    
    return errors