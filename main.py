#!/usr/bin/env python3
"""
統一的主應用程式
整合新的多平台架構與現有 LINE 功能
支援開發和生產環境的自動切換
"""

# 在生產環境中提前進行 gevent monkey patching 以避免 SSL 警告
import os
if os.getenv('FLASK_ENV') == 'production':
    try:
        import gevent.monkey
        gevent.monkey.patch_all()
    except ImportError:
        pass

import sys
import atexit
from flask import Flask

from src.app import MultiPlatformChatBot
from src.core.config import load_config
from src.core.logger import logger
from src.utils import check_token_valid

def create_app(config_path: str = None) -> Flask:
    """
    應用工廠函數 - 使用新架構創建應用程式
    保持與舊版本的兼容性
    """
    try:
        # 創建多平台聊天機器人實例
        bot = MultiPlatformChatBot(config_path)
        
        # 驗證 API token (保持向後兼容)
        if hasattr(bot, 'model') and bot.model:
            try:
                check_token_valid(bot.model)
            except ValueError as e:
                logger.warning(f"API token validation skipped: {e}")
        
        return bot.get_flask_app()
        
    except Exception as e:
        logger.error(f"Failed to create application: {e}")
        raise

def start_production_server():
    """啟動生產服務器 (使用 Gunicorn)"""
    import subprocess
    
    print("🚀 啟動生產服務器...")
    
    # 檢查是否安裝了 gunicorn
    try:
        import gunicorn
        print("✅ Gunicorn 已安裝")
    except ImportError:
        print("❌ 錯誤: 未安裝 gunicorn")
        print("請運行: pip install gunicorn")
        sys.exit(1)
    
    # 檢查 gunicorn 配置文件
    gunicorn_config = "gunicorn.conf.py"
    if not os.path.exists(gunicorn_config):
        print(f"⚠️  警告: 找不到 {gunicorn_config}，使用默認配置")
        gunicorn_config = None
    
    # 構建 Gunicorn 命令
    cmd = [sys.executable, "-m", "gunicorn"]
    
    if gunicorn_config:
        cmd.extend(["-c", gunicorn_config])
    else:
        # 默認配置
        cmd.extend([
            "--bind", f"{os.getenv('HOST', '0.0.0.0')}:{os.getenv('PORT', '8080')}",
            "--workers", "2",
            "--timeout", "120",
            "--worker-class", "sync"
        ])
    
    cmd.append("main:application")
    
    print(f"執行指令: {' '.join(cmd)}")
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n🛑 服務器已停止")
    except Exception as e:
        logger.error(f"Failed to start production server: {e}")
        sys.exit(1)


def main():
    """主函數 - 根據環境自動選擇運行模式"""
    try:
        # 根據環境變量決定運行模式
        env = os.getenv('FLASK_ENV', 'development')
        
        if env == 'production':
            print("🏭 生產環境模式")
            start_production_server()
        else:
            print("🔧 開發模式 - 使用新的多平台架構")
            print("✨ 支援平台: LINE (向後兼容), Discord, Telegram")
            print("⚠️  注意：此服務器僅適用於開發環境")
            
            # 載入配置
            config = load_config()
            
            # 創建應用程式
            app = create_app()
            
            app.run(
                host=os.getenv('HOST', '0.0.0.0'),
                port=int(os.getenv('PORT', '8080')),
                debug=os.getenv('DEBUG', 'True').lower() == 'true',
                use_reloader=False  # 減少重複載入
            )
            
    except Exception as e:
        logger.error(f"Application startup failed: {e}")
        raise

# 為 WSGI 服務器創建應用實例 (生產環境使用)
# 只在非直接執行時創建 WSGI 應用實例，避免重複初始化
application = None

def get_wsgi_application():
    """獲取 WSGI 應用實例，延遲創建避免重複初始化"""
    global application
    if application is None:
        try:
            # 創建應用實例 (不修改環境變數，保持原始設定)
            application = create_app()
            
            # 記錄當前環境
            current_env = os.getenv('FLASK_ENV', 'development')
            logger.info(f"WSGI application created for environment: {current_env}")
            
            # 在生產環境中進行額外的初始化
            if current_env == 'production':
                with application.app_context():
                    # 這裡可以添加額外的生產環境初始化邏輯
                    logger.info("Production application instance initialized successfully")
                    
        except Exception as e:
            logger.error(f"Failed to create WSGI application: {e}")
            # 在生產環境中，我們仍然需要一個有效的 application 對象
            # 創建一個基本的錯誤應用
            from flask import Flask
            application = Flask(__name__)
            
            @application.route('/health')
            def error_health():
                return {'status': 'error', 'message': str(e)}, 503
    
    return application

# 為了兼容性，提供 application 變數
# 但只在被 import 為模組且非直接執行時創建
if __name__ != "__main__":
    application = get_wsgi_application()


if __name__ == "__main__":
    main()