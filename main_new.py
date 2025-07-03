#!/usr/bin/env python3
"""
多平台聊天機器人主入口點
使用新的平台架構

使用方式:
  python main_new.py                    # 開發模式
  python main_new.py --config custom.yml  # 指定配置檔案
  python main_new.py --port 8080         # 指定埠號
"""

import argparse
import sys
import os
from pathlib import Path

# 添加 src 到 Python 路徑
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.app import MultiPlatformChatBot, create_app
from src.core.logger import logger


def parse_arguments():
    """解析命令列參數"""
    parser = argparse.ArgumentParser(
        description='Multi-Platform Chat Bot',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main_new.py                        # 開發模式
  python main_new.py --config config.yml   # 指定配置檔案
  python main_new.py --port 8080 --host 0.0.0.0  # 指定主機和埠號
  python main_new.py --production           # 生產模式
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        default=None,
        help='配置檔案路徑 (預設: config/config.yml)'
    )
    
    parser.add_argument(
        '--host',
        type=str,
        default='0.0.0.0',
        help='伺服器主機 (預設: 0.0.0.0)'
    )
    
    parser.add_argument(
        '--port', '-p',
        type=int,
        default=8080,
        help='伺服器埠號 (預設: 8080)'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='啟用除錯模式'
    )
    
    parser.add_argument(
        '--production',
        action='store_true',
        help='生產模式 (關閉除錯)'
    )
    
    parser.add_argument(
        '--validate-config',
        action='store_true',
        help='只驗證配置檔案而不啟動伺服器'
    )
    
    parser.add_argument(
        '--show-platforms',
        action='store_true',
        help='顯示支援的平台列表'
    )
    
    return parser.parse_args()


def validate_config_only(config_path: str = None):
    """只驗證配置檔案"""
    try:
        from src.platforms.factory import get_config_validator
        from src.core.config import load_config
        
        logger.info("驗證配置檔案...")
        
        # 載入配置
        config = load_config(config_path)
        
        # 驗證平台配置
        validator = get_config_validator()
        is_valid, platform_errors = validator.validate_all_platforms(config)
        
        if is_valid:
            logger.info("✅ 配置檔案驗證通過")
            return True
        else:
            logger.error("❌ 配置檔案驗證失敗:")
            for platform, errors in platform_errors.items():
                for error in errors:
                    logger.error(f"  {platform}: {error}")
            return False
            
    except Exception as e:
        logger.error(f"配置檔案驗證時發生錯誤: {e}")
        return False


def show_supported_platforms():
    """顯示支援的平台列表"""
    try:
        from src.platforms.factory import get_platform_registry
        
        registry = get_platform_registry()
        platforms = registry.get_available_platforms()
        
        print("支援的平台:")
        for platform in platforms:
            print(f"  - {platform.value}")
        
        return True
        
    except Exception as e:
        logger.error(f"取得平台列表時發生錯誤: {e}")
        return False


def main():
    """主函數"""
    args = parse_arguments()
    
    # 顯示平台列表
    if args.show_platforms:
        show_supported_platforms()
        return
    
    # 只驗證配置
    if args.validate_config:
        success = validate_config_only(args.config)
        sys.exit(0 if success else 1)
    
    # 設定除錯模式
    debug_mode = args.debug and not args.production
    
    try:
        logger.info("正在啟動多平台聊天機器人...")
        logger.info(f"配置檔案: {args.config or '預設'}")
        logger.info(f"主機: {args.host}")
        logger.info(f"埠號: {args.port}")
        logger.info(f"除錯模式: {debug_mode}")
        
        # 創建並運行機器人
        bot = MultiPlatformChatBot(config_path=args.config)
        bot.run(host=args.host, port=args.port, debug=debug_mode)
        
    except KeyboardInterrupt:
        logger.info("收到中斷信號，正在關閉...")
    except Exception as e:
        logger.error(f"啟動失敗: {e}")
        if debug_mode:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()