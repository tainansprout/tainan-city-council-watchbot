"""
多平台聊天機器人主應用程式
使用新的平台架構和設計模式
"""
import atexit
import logging
from flask import Flask, request, abort, jsonify
from typing import Dict, Any

# 核心模組
from .core.config import load_config
from .core.logger import logger
from .core.security import init_security
from .core.auth import init_test_auth_with_config, get_auth_status_info
from .core.error_handler import ErrorHandler

# 模型和服務
from .models.factory import ModelFactory
from .database.db import Database
from .services.core_chat_service import CoreChatService

# 平台架構
from .platforms.factory import get_platform_factory, get_config_validator
from .platforms.base import get_platform_manager, PlatformType


class MultiPlatformChatBot:
    """
    多平台聊天機器人應用程式
    
    使用以下設計模式：
    - Factory Pattern: 創建模型和平台處理器
    - Strategy Pattern: 不同平台的處理策略
    - Singleton Pattern: 全域配置和管理器
    - Observer Pattern: 事件通知 (未來擴展)
    """
    
    def __init__(self, config_path: str = None):
        # 載入配置
        self.config = load_config(config_path)
        
        # 初始化核心組件
        self.error_handler = ErrorHandler()
        self.database = None
        self.model = None
        self.core_chat_service = None
        
        # 平台管理
        self.platform_factory = get_platform_factory()
        self.platform_manager = get_platform_manager()
        self.config_validator = get_config_validator()
        
        # Flask 應用程式
        self.app = Flask(__name__)
        
        # 初始化應用程式
        self._initialize_app()
    
    def _initialize_app(self):
        """初始化應用程式組件"""
        try:
            # 1. 驗證配置
            self._validate_config()
            
            # 2. 初始化安全性
            init_security(self.app)
            init_test_auth_with_config(self.config)
            
            # 3. 初始化資料庫
            self._initialize_database()
            
            # 4. 初始化模型
            self._initialize_model()
            
            # 5. 初始化核心聊天服務
            self._initialize_core_service()
            
            # 6. 初始化平台處理器
            self._initialize_platforms()
            
            # 7. 註冊路由
            self._register_routes()
            
            # 8. 註冊清理函數
            self._register_cleanup()
            
            logger.info("Multi-platform chat bot initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize application: {e}")
            raise
    
    def _validate_config(self):
        """驗證配置"""
        logger.info("Validating configuration...")
        
        # 驗證平台配置
        is_valid, platform_errors = self.config_validator.validate_all_platforms(self.config)
        
        if not is_valid:
            logger.error("Platform configuration validation failed:")
            for platform, errors in platform_errors.items():
                for error in errors:
                    logger.error(f"  {platform}: {error}")
            # 不拋出異常，允許部分平台運行
        
        logger.info("Configuration validation completed")
    
    def _initialize_database(self):
        """初始化資料庫"""
        logger.info("Initializing database...")
        self.database = Database(self.config['db'])
        logger.info("Database initialized successfully")
    
    def _initialize_model(self):
        """初始化 AI 模型"""
        logger.info("Initializing AI model...")
        
        # 取得模型配置
        llm_config = self.config.get('llm', {})
        provider = llm_config.get('provider', 'openai')
        
        # 根據提供商取得特定配置
        model_config = self.config.get(provider, {})
        model_config['provider'] = provider
        
        # 創建模型
        self.model = ModelFactory.create_from_config(model_config)
        logger.info(f"AI model initialized: {provider}")
    
    def _initialize_core_service(self):
        """初始化核心聊天服務"""
        logger.info("Initializing core chat service...")
        self.core_chat_service = CoreChatService(
            model=self.model,
            database=self.database,
            config=self.config
        )
        logger.info("Core chat service initialized successfully")
    
    def _initialize_platforms(self):
        """初始化平台處理器"""
        logger.info("Initializing platform handlers...")
        
        # 創建所有啟用的平台處理器
        handlers = self.platform_factory.create_enabled_handlers(self.config)
        
        # 註冊到平台管理器
        for platform_type, handler in handlers.items():
            success = self.platform_manager.register_handler(handler)
            if success:
                logger.info(f"Registered {platform_type.value} platform handler")
            else:
                logger.error(f"Failed to register {platform_type.value} platform handler")
        
        enabled_platforms = self.platform_manager.get_enabled_platforms()
        logger.info(f"Initialized {len(enabled_platforms)} platform handlers: {[p.value for p in enabled_platforms]}")
    
    def _register_routes(self):
        """註冊 Flask 路由"""
        
        # 健康檢查端點
        @self.app.route("/health")
        def health_check():
            return self._health_check()
        
        # 通用 webhook 端點 - 使用平台路由
        @self.app.route("/webhooks/<platform_name>", methods=['POST'])
        def webhook_handler(platform_name):
            return self._handle_webhook(platform_name)
        
        # 向後兼容的 LINE callback 端點
        @self.app.route("/callback", methods=['POST'])
        def line_callback():
            return self._handle_webhook('line')
        
        # 根路徑
        @self.app.route("/")
        def home():
            return jsonify({
                'name': self.config.get('app', {}).get('name', 'Multi-Platform Chat Bot'),
                'version': self.config.get('app', {}).get('version', '2.0.0'),
                'platforms': [p.value for p in self.platform_manager.get_enabled_platforms()],
                'status': 'running'
            })
        
        # 指標端點
        @self.app.route("/metrics")
        def metrics():
            return self._get_metrics()
        
        logger.info("Routes registered successfully")
    
    def _handle_webhook(self, platform_name: str):
        """統一的 webhook 處理器"""
        try:
            # 解析平台類型
            try:
                platform_type = PlatformType(platform_name.lower())
            except ValueError:
                logger.error(f"Unknown platform: {platform_name}")
                abort(404)
            
            # 取得請求資料
            signature = request.headers.get('X-Line-Signature') or request.headers.get('X-Hub-Signature-256', '')
            body = request.get_data(as_text=True)
            
            logger.info(f"Received {platform_name} webhook")
            
            # 使用平台管理器處理 webhook
            messages = self.platform_manager.handle_platform_webhook(
                platform_type, body, signature
            )
            
            if not messages:
                logger.warning(f"No valid messages from {platform_name} webhook")
                return 'OK'
            
            # 處理每個訊息
            for message in messages:
                try:
                    # 使用核心聊天服務處理訊息
                    response = self.core_chat_service.process_message(message)
                    
                    # 發送回應
                    handler = self.platform_manager.get_handler(platform_type)
                    if handler:
                        success = handler.send_response(response, message)
                        if not success:
                            logger.error(f"Failed to send response via {platform_name}")
                    
                except Exception as e:
                    logger.error(f"Error processing message from {platform_name}: {e}")
                    continue
            
            return 'OK'
            
        except Exception as e:
            logger.error(f"Error handling {platform_name} webhook: {e}")
            abort(500)
    
    def _health_check(self):
        """健康檢查"""
        from datetime import datetime
        
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': self.config.get('app', {}).get('version', '2.0.0'),
            'checks': {}
        }
        
        try:
            # 檢查資料庫連線
            try:
                with self.database.get_session() as session:
                    session.execute('SELECT 1')
                health_status['checks']['database'] = {'status': 'healthy'}
            except Exception as e:
                health_status['checks']['database'] = {
                    'status': 'unhealthy', 
                    'error': str(e)
                }
                health_status['status'] = 'unhealthy'
            
            # 檢查模型連線
            try:
                is_valid, error = self.model.check_connection()
                if is_valid:
                    health_status['checks']['model'] = {'status': 'healthy'}
                else:
                    health_status['checks']['model'] = {
                        'status': 'unhealthy', 
                        'error': error
                    }
                    health_status['status'] = 'unhealthy'
            except Exception as e:
                health_status['checks']['model'] = {
                    'status': 'unhealthy', 
                    'error': str(e)
                }
                health_status['status'] = 'unhealthy'
            
            # 檢查平台狀態
            enabled_platforms = self.platform_manager.get_enabled_platforms()
            health_status['checks']['platforms'] = {
                'enabled_count': len(enabled_platforms),
                'platforms': [p.value for p in enabled_platforms],
                'status': 'healthy' if enabled_platforms else 'no_platforms'
            }
            
            # 添加認證狀態資訊
            health_status['checks']['auth'] = get_auth_status_info()
            
            status_code = 200 if health_status['status'] == 'healthy' else 503
            return health_status, status_code
            
        except Exception as e:
            return {
                'status': 'unhealthy', 
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e)
            }, 503
    
    def _get_metrics(self):
        """取得系統指標"""
        try:
            metrics_data = {
                'timestamp': __import__('datetime').datetime.utcnow().isoformat(),
                'platforms': {
                    'enabled': [p.value for p in self.platform_manager.get_enabled_platforms()],
                    'count': len(self.platform_manager.get_enabled_platforms())
                },
                'model': {
                    'provider': self.model.get_provider().value if self.model else 'none'
                }
            }
            
            # 資料庫連線池資訊
            if self.database:
                try:
                    db_info = self.database.get_connection_info()
                    metrics_data['database'] = db_info
                except:
                    metrics_data['database'] = {'status': 'unavailable'}
            
            return jsonify(metrics_data)
            
        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return jsonify({'error': str(e)}), 500
    
    def _register_cleanup(self):
        """註冊清理函數"""
        def cleanup():
            logger.info("Shutting down application...")
            if self.database:
                self.database.close_engine()
            logger.info("Application shutdown complete")
        
        atexit.register(cleanup)
    
    def run(self, host='0.0.0.0', port=8080, debug=False):
        """運行應用程式"""
        logger.info(f"Starting multi-platform chat bot on {host}:{port}")
        self.app.run(host=host, port=port, debug=debug)
    
    def get_flask_app(self):
        """取得 Flask 應用程式實例 (用於部署)"""
        return self.app


def create_app(config_path: str = None) -> Flask:
    """
    工廠函數 - 創建 Flask 應用程式實例
    用於生產部署 (如 Gunicorn)
    """
    bot = MultiPlatformChatBot(config_path)
    return bot.get_flask_app()


# 為了向後兼容，保留原有的全域變數和函數
if __name__ == "__main__":
    # 開發模式運行
    bot = MultiPlatformChatBot()
    bot.run(debug=True)