"""
多平台聊天機器人主應用程式
使用新的平台架構和設計模式
"""
import atexit
import logging
from flask import Flask, request, abort, jsonify, render_template
from typing import Dict, Any

# 核心模組
from .core.config import load_config
from .core.logger import logger
from .core.security import init_security, InputValidator, require_json_input
from .core.security_config import security_config
from .core.auth import init_test_auth_with_config, get_auth_status_info, require_test_auth, init_test_auth
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
        self.config = load_config(config_path or "config/config.yml")
        
        # 初始化核心組件
        self.error_handler = ErrorHandler()
        self.database = None
        self.model = None
        self.core_chat_service = None
        
        # 平台管理
        self.platform_factory = get_platform_factory()
        self.platform_manager = get_platform_manager()
        self.config_validator = get_config_validator()
        
        # Flask 應用程式 - 設定模板和靜態文件路徑
        import os
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        template_folder = os.path.join(project_root, 'templates')
        static_folder = os.path.join(project_root, 'static') if os.path.exists(os.path.join(project_root, 'static')) else None
        
        self.app = Flask(__name__, 
                        template_folder=template_folder,
                        static_folder=static_folder)
        
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
            init_test_auth(self.app)
            
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
        
        # 聊天介面 - 僅支援 JSON
        @self.app.route('/chat', methods=['GET', 'POST'])
        def chat_interface():
            """聊天介面 - GET 顯示頁面，POST 處理 JSON 登入"""
            app_name = self.config.get('app', {}).get('name', '聊天機器人')
            
            if request.method == 'GET':
                # GET 請求檢查是否已登入
                if 'test_authenticated' in __import__('flask').session and __import__('flask').session['test_authenticated']:
                    return render_template('chat.html', app_name=app_name)
                else:
                    # 未登入時重定向到 /login，而不是直接顯示登入頁面
                    from flask import redirect, url_for
                    return redirect(url_for('login_api'))
            
            elif request.method == 'POST':
                # POST 請求僅接受 JSON 格式登入
                if not request.is_json:
                    return jsonify({'success': False, 'error': '請使用 JSON 格式提交'}), 400
                
                data = request.get_json()
                if not data or 'password' not in data:
                    return jsonify({'success': False, 'error': '缺少密碼欄位'}), 400
                
                password = data.get('password', '')
                
                # 驗證密碼
                from .core.auth import test_auth
                if test_auth and test_auth.verify_password(password):
                    __import__('flask').session['test_authenticated'] = True
                    __import__('flask').session.permanent = True
                    return jsonify({'success': True, 'message': '登入成功'})
                else:
                    return jsonify({'success': False, 'error': '密碼錯誤'}), 401
        
        # JSON 登入端點
        @self.app.route('/login', methods=['GET', 'POST'])
        def login_api():
            """JSON 登入 API - GET 顯示登入頁面，POST 處理登入"""
            app_name = self.config.get('app', {}).get('name', '聊天機器人')
            
            if request.method == 'GET':
                # GET 請求顯示登入頁面
                return render_template('login.html', app_name=app_name)
            
            elif request.method == 'POST':
                # POST 請求處理 JSON 登入
                if not request.is_json:
                    return jsonify({'success': False, 'error': '請使用 JSON 格式提交'}), 400
                
                data = request.get_json()
                if not data or 'password' not in data:
                    return jsonify({'success': False, 'error': '缺少密碼欄位'}), 400
                
                password = data.get('password', '')
                
                from .core.auth import test_auth
                if test_auth and test_auth.verify_password(password):
                    __import__('flask').session['test_authenticated'] = True
                    __import__('flask').session.permanent = True
                    return jsonify({'success': True, 'message': '登入成功'})
                else:
                    return jsonify({'success': False, 'error': '密碼錯誤'}), 401
        
        # 登出端點
        @self.app.route('/logout', methods=['POST'])
        def logout():
            """登出功能 - 清除 session"""
            __import__('flask').session.pop('test_authenticated', None)
            __import__('flask').session.clear()
            return jsonify({'success': True, 'message': '已成功登出'})
        
        # 測試用聊天端點 - 僅用於開發測試
        @self.app.route('/ask', methods=['POST'])
        @require_json_input(['message'])
        def ask_endpoint():
            """測試用聊天端點 - 僅用於開發測試"""
            # 檢查認證
            if 'test_authenticated' not in __import__('flask').session or not __import__('flask').session['test_authenticated']:
                return jsonify({'error': '需要先登入'}), 401
            
            try:
                # 獲取清理後的輸入
                user_message = request.validated_json['message']
                
                # 長度檢查 - 在生產環境中限制更嚴格以防止濫用
                max_length = security_config.get_max_message_length(is_test=True)
                if len(user_message) > max_length:
                    return jsonify({'error': f'測試訊息長度不能超過 {max_length} 字符'}), 400
                
                # 使用固定的測試用戶 ID
                test_user_id = "U" + "0" * 32  # 固定的測試用戶 ID
                
                # 創建測試訊息對象
                from .platforms.base import PlatformMessage, PlatformUser, PlatformType
                
                test_user = PlatformUser(
                    user_id=test_user_id,
                    display_name="測試用戶",
                    platform=PlatformType.LINE
                )
                
                test_message = PlatformMessage(
                    message_id="test_msg_" + str(int(__import__('time').time())),
                    user=test_user,
                    content=user_message,
                    message_type="text",
                    reply_token="test_reply_token"
                )
                
                # 使用核心聊天服務處理訊息
                response = self.core_chat_service.process_message(test_message)
                
                # 清理回應內容以防止 XSS
                if hasattr(response, 'content'):
                    clean_response = InputValidator.sanitize_text(response.content)
                else:
                    clean_response = InputValidator.sanitize_text(str(response))
                
                return jsonify({'message': clean_response})
                
            except Exception as e:
                logger.error(f"Error in ask endpoint: {e}")
                return jsonify({'error': '處理訊息時發生錯誤，請稍後再試'}), 500
        
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
                from sqlalchemy import text
                with self.database.get_session() as session:
                    session.execute(text('SELECT 1'))
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
    bot = MultiPlatformChatBot(config_path or "config/config.yml")
    return bot.get_flask_app()


# 為了向後兼容，保留原有的全域變數和函數
if __name__ == "__main__":
    # 開發模式運行
    bot = MultiPlatformChatBot()
    bot.run(debug=True)