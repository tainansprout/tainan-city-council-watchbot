#!/usr/bin/env python3
"""
WSGI 入口點 - 用於生產環境
"""

import os
import sys

# 確保應用目錄在 Python 路徑中
sys.path.insert(0, os.path.dirname(__file__))

# 設置生產環境變量
os.environ.setdefault('FLASK_ENV', 'production')

try:
    from main import app, check_token_valid, model
    
    # 在生產環境中檢查 token 有效性
    check_token_valid(model)
    
    # WSGI 應用對象
    application = app
    
except Exception as e:
    import logging
    logging.error(f"Failed to initialize application: {e}")
    raise

if __name__ == "__main__":
    # 直接運行此文件時使用 Gunicorn
    import subprocess
    import sys
    
    print("🚀 啟動生產服務器...")
    
    # 檢查是否安裝了 gunicorn
    try:
        import gunicorn
    except ImportError:
        print("❌ 錯誤: 未安裝 gunicorn")
        print("請運行: pip install gunicorn")
        sys.exit(1)
    
    # 使用 Gunicorn 啟動
    cmd = [
        sys.executable, "-m", "gunicorn",
        "-c", "gunicorn.conf.py",
        "wsgi:application"
    ]
    
    print(f"執行指令: {' '.join(cmd)}")
    subprocess.run(cmd)