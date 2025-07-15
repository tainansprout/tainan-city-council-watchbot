"""
多平台聊天機器人主應用程式
使用新的平台架構和設計模式
"""
import atexit
from flask import Flask, request, abort, jsonify, render_template
from typing import Dict, Any

# 核心模組
from .core.config import load_config
from .core.logger import get_logger
logger = get_logger(__name__)
from .core.security import init_security, InputValidator, require_json_input
from .core.auth import init_test_auth_with_config, get_auth_status_info, require_test_auth, init_test_auth
from .core.error_handler import ErrorHandler

# 模型和服務
from .models.factory import ModelFactory
from .database.connection import Database
from .services.chat import ChatService
from .services.audio import AudioService

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
        self.chat_service = None
        
        # 平台管理
        self.platform_factory = get_platform_factory()
        self.platform_manager = get_platform_manager()
        self.config_validator = get_config_validator()
        
        # Flask 應用程式 - 設定模板和靜態文件路徑
        import os
        src_root = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(src_root)
        template_folder = os.path.join(src_root, 'templates')  # src/templates/
        static_folder = os.path.join(project_root, 'static') if os.path.exists(os.path.join(project_root, 'static')) else None
        
        self.app = Flask(__name__, 
                        template_folder=template_folder,
                        static_folder=static_folder)
        
        # 設置 Flask 配置 - 確保 JSON 正確編碼中文
        self.app.config['JSON_AS_ASCII'] = False
        self.app.config['JSONIFY_MIMETYPE'] = 'application/json; charset=utf-8'
        
        # 初始化應用程式
        self._initialize_app()
    
    
    def _initialize_app(self):
        """初始化應用程式組件"""
        try:
            # 1. 驗證配置
            self._validate_config()
            
            # 2. 初始化安全性
            init_security(self.app, self.config)
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
            
            # 8. 初始化記憶體監控
            self._initialize_memory_monitoring()
            
            # 9. 註冊清理函數
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
        
        # 初始化回應格式化器
        from .services.response import ResponseFormatter
        self.response_formatter = ResponseFormatter(self.config)
        
        # 初始化核心聊天服務
        self.chat_service = ChatService(
            model=self.model,
            database=self.database,
            config=self.config
        )
        
        # 初始化音訊服務
        self.audio_service = AudioService(
            model=self.model
        )
        
        logger.info("Core chat service and audio service initialized successfully")
    
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
    
    def _initialize_memory_monitoring(self):
        """初始化記憶體監控和智慧垃圾回收"""
        logger.info("Initializing memory monitoring...")
        
        try:
            from .core.memory_monitor import setup_memory_monitoring
            
            # 設置 Flask 應用的記憶體監控
            self.memory_monitor, self.smart_gc = setup_memory_monitoring(self.app)
            
            logger.info("Memory monitoring initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize memory monitoring: {e}")
            # 不拋出異常，允許應用程式繼續運行
    
    def _register_routes(self):
        """註冊 Flask 路由"""
        
        # 健康檢查端點
        @self.app.route("/health")
        def health_check():
            return self._health_check()
        
        # 通用 webhook 端點 - 使用平台路由
        @self.app.route("/webhooks/<platform_name>", methods=['POST', 'GET'])
        def webhook_handler(platform_name):
            if request.method == 'GET':
                return self._handle_webhook_verification(platform_name)
            else:
                return self._handle_webhook(platform_name)
        
        # 根路徑
        @self.app.route("/")
        def home():
            # 獲取當前使用的模型信息
            model_info = {
                'provider': self.config.get('llm', {}).get('provider', 'unknown'),
                'available_providers': []
            }
            
            # 檢查可用的模型提供商
            for provider in ['openai', 'anthropic', 'gemini', 'ollama']:
                if self.config.get(provider, {}).get('api_key') or provider == 'ollama':
                    model_info['available_providers'].append(provider)
            
            response_data = {
                'name': self.config.get('app', {}).get('name', 'Multi-Platform Chat Bot'),
                'version': self.config.get('app', {}).get('version', '2.0.0'),
                'platforms': [p.value for p in self.platform_manager.get_enabled_platforms()],
                'models': model_info,
                'status': 'running'
            }
            
            # 使用 ResponseFormatter 的 JSON 回應處理
            return self.response_formatter.json_response(response_data)
        
        # 指標端點
        @self.app.route("/metrics")
        def metrics():
            return self._get_metrics()
        
        # 記憶體統計端點
        @self.app.route("/memory-stats")
        def memory_stats():
            """記憶體統計端點"""
            try:
                # 檢查 memory_monitor 是否已初始化
                if not hasattr(self, 'memory_monitor') or self.memory_monitor is None:
                    raise RuntimeError("Memory monitor not initialized")
                stats = self.memory_monitor.get_detailed_report()
                return self.response_formatter.json_response(stats)
            except Exception as e:
                logger.error(f"Error getting memory stats: {e}")
                return self.response_formatter.json_response({
                    'error': 'Failed to get memory stats',
                    'message': str(e)
                }, 500)
        
        # 聊天介面 - 僅支援 JSON
        @self.app.route('/chat', methods=['GET', 'POST'])
        def chat_interface():
            """聊天介面 - GET 顯示頁面，POST 處理 JSON 登入"""
            app_name = self.config.get('app', {}).get('name', '聊天機器人')
            app_description = self.config.get('app', {}).get('description', '智慧對話系統')
            
            if request.method == 'GET':
                # GET 請求檢查是否已登入
                if 'test_authenticated' in __import__('flask').session and __import__('flask').session['test_authenticated']:
                    return render_template('chat.html', app_name=app_name, app_description=app_description)
                else:
                    # 未登入時重定向到 /login，而不是直接顯示登入頁面
                    from flask import redirect, url_for
                    return redirect(url_for('login_api'))
            
            elif request.method == 'POST':
                # POST 請求僅接受 JSON 格式登入
                if not request.is_json:
                    return self.response_formatter.json_response({'success': False, 'error': '請使用 JSON 格式提交'}, 400)
                
                try:
                    data = request.get_json()
                except Exception:
                    return self.response_formatter.json_response({'success': False, 'error': '無效的 JSON 格式'}, 400)
                
                if not data or 'password' not in data:
                    return self.response_formatter.json_response({'success': False, 'error': '缺少密碼欄位'}, 400)
                
                password = data.get('password', '')
                
                # 驗證密碼
                from .core.auth import test_auth
                if test_auth and test_auth.verify_password(password):
                    __import__('flask').session['test_authenticated'] = True
                    __import__('flask').session.permanent = True
                    return self.response_formatter.json_response({'success': True, 'message': '登入成功'})
                else:
                    return self.response_formatter.json_response({'success': False, 'error': '密碼錯誤'}, 401)
        
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
                    return self.response_formatter.json_response({'success': False, 'error': '請使用 JSON 格式提交'}, 400)
                
                try:
                    data = request.get_json()
                except Exception:
                    return self.response_formatter.json_response({'success': False, 'error': '無效的 JSON 格式'}, 400)
                
                if not data or 'password' not in data:
                    return self.response_formatter.json_response({'success': False, 'error': '缺少密碼欄位'}, 400)
                
                password = data.get('password', '')
                
                from .core.auth import test_auth
                if test_auth and test_auth.verify_password(password):
                    __import__('flask').session['test_authenticated'] = True
                    __import__('flask').session.permanent = True
                    return self.response_formatter.json_response({'success': True, 'message': '登入成功'})
                else:
                    return self.response_formatter.json_response({'success': False, 'error': '密碼錯誤'}, 401)
        
        # 登出端點
        @self.app.route('/logout', methods=['POST'])
        def logout():
            """登出功能 - 清除 session"""
            __import__('flask').session.pop('test_authenticated', None)
            __import__('flask').session.clear()
            return self.response_formatter.json_response({'success': True, 'message': '已成功登出'})
        
        # 測試用聊天端點 - 僅用於開發測試
        @self.app.route('/ask', methods=['POST'])
        @require_json_input(['message'])
        def ask_endpoint():
            """測試用聊天端點 - 僅用於開發測試"""
            # 檢查認證
            if 'test_authenticated' not in __import__('flask').session or not __import__('flask').session['test_authenticated']:
                return self.response_formatter.json_response({'error': '需要先登入'}, 401)
            
            # 初始化變數在 try 區塊外
            test_user_id = "U" + "0" * 32  # 固定的測試用戶 ID
            user_message = ""
            
            try:
                # 獲取清理後的輸入
                user_message = request.validated_json['message']
                
                # 長度檢查 - 在生產環境中限制更嚴格以防止濫用
                # 動態導入 security_config
                from .core.security import security_config
                
                # 安全 fallback：如果 security_config 為 None，使用預設值
                if security_config is not None:
                    max_length = security_config.get_max_message_length(is_test=True)
                else:
                    # 從配置中直接獲取，或使用預設值
                    max_length = self.config.get('security', {}).get('content', {}).get('max_message_length', 5000)
                    logger.warning("security_config is None, using fallback max_length: %d", max_length)
                
                if len(user_message) > max_length:
                    return self.response_formatter.json_response({'error': f'測試訊息長度不能超過 {max_length} 字符'}, 400)
                
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
                response = self.chat_service.handle_message(test_message)
                
                # 清理回應內容以防止 XSS
                if hasattr(response, 'content'):
                    clean_response = InputValidator.sanitize_text(response.content)
                else:
                    clean_response = InputValidator.sanitize_text(str(response))
                
                # 🔥 準備回應，包含 MCP 互動資訊（如果存在）
                response_data = {'message': clean_response}
                
                # 提取 MCP 互動資訊
                if hasattr(response, 'metadata') and response.metadata:
                    mcp_interactions = response.metadata.get('mcp_interactions')
                    if mcp_interactions:
                        response_data['mcp_interactions'] = mcp_interactions
                
                return jsonify(response_data)
                
            except Exception as e:
                # 記錄詳細的錯誤 log
                logger.error(f"Error in ask endpoint: {type(e).__name__}: {e}")
                logger.error(f"Error details - User: {test_user_id}, Message: {user_message[:100]}...")
                
                # 使用錯誤處理器取得詳細的錯誤訊息（用於測試介面）
                detailed_error = self.error_handler.get_error_message(e, use_detailed=True)
                
                # 根據錯誤類型決定 HTTP 狀態碼
                status_code = self._get_error_status_code(e, detailed_error)
                
                return jsonify({
                    'error': detailed_error,
                    'error_type': self.error_handler._classify_error(str(e)),
                    'timestamp': __import__('time').time()
                }), status_code
        
        logger.info("Routes registered successfully")
    
    def _get_error_status_code(self, error: Exception, error_message: str) -> int:
        """根據錯誤類型決定適當的 HTTP 狀態碼"""
        error_str = str(error).lower()
        
        # 速率限制 - 429 Too Many Requests
        if 'rate limit' in error_str or 'api 速率限制' in error_str:
            return 429
        
        # 認證錯誤 - 401 Unauthorized  
        if 'api key' in error_str or 'unauthorized' in error_str:
            return 401
        
        # 配額錯誤 - 402 Payment Required
        if 'quota exceeded' in error_str or 'billing' in error_str:
            return 402
        
        # 服務不可用 - 503 Service Unavailable
        if 'overloaded' in error_str or 'timeout' in error_str or 'connection' in error_str:
            return 503
        
        # MCP 相關錯誤 - 502 Bad Gateway (外部服務問題)
        if 'mcp' in error_str:
            return 502
        
        # 預設為 500 Internal Server Error
        return 500
    
    def _handle_webhook_verification(self, platform_name: str):
        """處理 webhook 驗證請求（主要用於 WhatsApp、Messenger 和 Instagram）"""
        try:
            logger.info(f"[WEBHOOK_VERIFY] Received verification request for {platform_name}")
            
            # 解析平台類型
            try:
                platform_type = PlatformType(platform_name.lower())
            except ValueError:
                logger.error(f"[WEBHOOK_VERIFY] Unknown platform: {platform_name}")
                abort(404)
            
            # WhatsApp、Messenger 和 Instagram 需要 webhook 驗證
            if platform_type in [PlatformType.WHATSAPP, PlatformType.MESSENGER, PlatformType.INSTAGRAM]:
                # 取得平台處理器
                handler = self.platform_manager.get_handler(platform_type)
                if not handler:
                    logger.error(f"[WEBHOOK_VERIFY] No handler found for {platform_name}")
                    abort(404)
                
                # 取得驗證參數
                hub_mode = request.args.get('hub.mode')
                hub_verify_token = request.args.get('hub.verify_token')
                hub_challenge = request.args.get('hub.challenge')
                
                logger.debug(f"[WEBHOOK_VERIFY] Mode: {hub_mode}, Token: {hub_verify_token}, Challenge: {hub_challenge}")
                
                # 驗證 webhook
                if hub_mode == 'subscribe':
                    challenge = handler.verify_webhook(hub_verify_token, hub_challenge)
                    if challenge:
                        logger.info(f"[WEBHOOK_VERIFY] {platform_name} webhook verification successful")
                        return challenge
                    else:
                        logger.error(f"[WEBHOOK_VERIFY] {platform_name} webhook verification failed")
                        abort(403)
                else:
                    logger.error(f"[WEBHOOK_VERIFY] Invalid hub mode: {hub_mode}")
                    abort(400)
            else:
                # 其他平台不需要 GET 驗證
                logger.warning(f"[WEBHOOK_VERIFY] Platform {platform_name} does not support GET verification")
                abort(405)
                
        except Exception as e:
            logger.error(f"[WEBHOOK_VERIFY] Error handling verification for {platform_name}: {e}")
            abort(500)
    
    def _handle_webhook(self, platform_name: str):
        """統一的 webhook 處理器"""
        try:
            # 記錄請求基本資訊
            logger.info(f"[WEBHOOK] Received {platform_name} webhook request")
            logger.debug(f"[WEBHOOK] Request method: {request.method}")
            logger.debug(f"[WEBHOOK] Content-Type: {request.headers.get('Content-Type', 'None')}")
            
            # 解析平台類型
            try:
                platform_type = PlatformType(platform_name.lower())
                logger.debug(f"[WEBHOOK] Platform type resolved: {platform_type.value}")
            except ValueError:
                logger.error(f"[WEBHOOK] Unknown platform: {platform_name}")
                abort(404)
            
            # 取得請求資料
            body = request.get_data(as_text=True)
            headers = dict(request.headers)
            
            logger.debug(f"[WEBHOOK] Request body size: {len(body)} bytes")
            logger.debug(f"[WEBHOOK] Request headers: {headers}")
            logger.debug(f"[WEBHOOK] Request body preview: {body[:500]}..." if len(body) > 500 else f"[WEBHOOK] Request body: {body}")
            
            # 檢查平台管理器狀態
            logger.debug(f"[WEBHOOK] Platform manager status - enabled platforms: {[p.value for p in self.platform_manager.get_enabled_platforms()]}")
            
            # 使用平台管理器處理 webhook
            logger.debug(f"[WEBHOOK] Starting webhook processing with platform manager")
            messages = self.platform_manager.handle_platform_webhook(
                platform_type, body, headers
            )
            
            logger.debug(f"[WEBHOOK] Platform manager returned {len(messages) if messages else 0} messages")
            
            if not messages:
                logger.warning(f"[WEBHOOK] No valid messages from {platform_name} webhook - returning OK")
                return 'OK'
            
            # 處理每個訊息
            logger.debug(f"[WEBHOOK] Processing {len(messages)} messages")
            for i, message in enumerate(messages):
                try:
                    logger.info(f"[WEBHOOK] Received - User: {getattr(message.user, 'user_id', 'unknown')}, Content: {str(message.content)[:100]}{'...' if len(str(message.content)) > 100 else ''}")
                    logger.debug(f"[WEBHOOK] Processing message {i+1}/{len(messages)} - ID: {getattr(message, 'message_id', 'unknown')}, Type: {getattr(message, 'message_type', 'unknown')}")
                    
                    # 根據訊息類型選擇合適的服務處理
                    if message.message_type == "audio":
                        logger.debug(f"[WEBHOOK] Processing audio message with audio service")
                        
                        # 步驟 1: 使用音訊服務進行轉錄
                        audio_result = self.audio_service.handle_message(
                            user_id=message.user.user_id,
                            audio_content=message.raw_data,
                            platform=message.user.platform.value
                        )
                        
                        if not audio_result['success']:
                            # 轉錄失敗，返回錯誤訊息
                            error_response = self.error_handler.get_error_message(
                                Exception(audio_result['error_message']), 
                                use_detailed=False
                            )
                            from .platforms.base import PlatformResponse
                            response = PlatformResponse(
                                content=error_response,
                                response_type='text'
                            )
                            logger.error(f"[WEBHOOK] Audio transcription failed for user {message.user.user_id}")
                        else:
                            # 步驟 2: 轉錄成功，創建文字訊息並交給 ChatService 處理
                            logger.debug(f"[WEBHOOK] Audio transcription successful, processing with chat service")
                            transcribed_text = audio_result['transcribed_text']
                            
                            # 創建文字訊息
                            from .platforms.base import PlatformMessage
                            text_message = PlatformMessage(
                                message_id=f"audio_transcribed_{message.user.user_id}",
                                user=message.user,
                                content=transcribed_text,
                                message_type="text",
                                reply_token=getattr(message, 'reply_token', None)
                            )
                            
                            # 使用 ChatService 處理轉錄文字
                            response = self.chat_service.handle_message(text_message)
                            logger.info(f"[WEBHOOK] Audio processing completed successfully")
                            
                    else:
                        # 使用核心聊天服務處理文字訊息
                        logger.debug(f"[WEBHOOK] Processing text message with chat service")
                        response = self.chat_service.handle_message(message)
                    
                    logger.info(f"[WEBHOOK] Sending - Content: {str(getattr(response, 'content', 'No content'))[:100]}{'...' if hasattr(response, 'content') and len(str(response.content)) > 100 else ''}")
                    logger.debug(f"[WEBHOOK] Response type: {getattr(response, 'response_type', 'unknown')}")
                    
                    # 發送回應
                    logger.debug(f"[WEBHOOK] Getting platform handler for response")
                    handler = self.platform_manager.get_handler(platform_type)
                    if handler:
                        logger.debug(f"[WEBHOOK] Platform handler found, sending response")
                        success = handler.send_response(response, message)
                        if success:
                            logger.info(f"[WEBHOOK] Response sent successfully to user: {getattr(message.user, 'user_id', 'unknown')}")
                        else:
                            logger.error(f"[WEBHOOK] Failed to send response via {platform_name}")
                    else:
                        logger.error(f"[WEBHOOK] No platform handler found for {platform_name}")
                    
                except Exception as e:
                    # 記錄詳細的錯誤 log
                    logger.error(f"[WEBHOOK] Error processing message from {platform_name}: {type(e).__name__}: {e}")
                    logger.error(f"[WEBHOOK] Error details - Platform: {platform_name}, Message ID: {getattr(message, 'message_id', 'unknown')}")
                    logger.error(f"[WEBHOOK] Exception traceback:", exc_info=True)
                    continue
            
            logger.debug(f"[WEBHOOK] Webhook processing completed successfully for {platform_name}")
            return 'OK'
            
        except Exception as e:
            # 記錄詳細的錯誤 log
            logger.error(f"[WEBHOOK] Error handling {platform_name} webhook: {type(e).__name__}: {e}")
            logger.error(f"[WEBHOOK] Webhook error details - Platform: {platform_name}, Request size: {len(request.get_data())}")
            logger.error(f"[WEBHOOK] Exception traceback:", exc_info=True)
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
            return jsonify(health_status), status_code
            
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
            # Logger 不應該拋出 ValueError，如果出現請檢查 logging 配置
            print("Shutting down application...")
            try:
                if self.database:
                    self.database.close_engine()
            except Exception as e:
                # 只捕獲資料庫關閉的錯誤，不影響 logging
                print(f"Error during database cleanup: {e}")
            print("Application shutdown complete")
        
        atexit.register(cleanup)
    
    def run(self, host='0.0.0.0', port=8080, debug=False):
        """運行應用程式"""
        logger.info(f"Starting multi-platform chat bot on {host}:{port}")
        self.app.run(host=host, port=port, debug=debug)
    
    def get_flask_app(self):
        """取得 Flask 應用程式實例 (用於部署)"""
        return self.app


def create_app(config_path: str = None, migration_mode: bool = False) -> Flask:
    """
    工廠函數 - 創建 Flask 應用程式實例
    用於生產部署 (如 Gunicorn) 和資料庫遷移
    
    Args:
        config_path: 配置檔案路徑
        migration_mode: 是否為遷移模式（只初始化資料庫相關組件）
    """
    import os
    
    # 檢查是否為遷移模式
    migration_mode = migration_mode or os.getenv('MIGRATION_MODE', '').lower() == 'true'
    
    if migration_mode:
        # 遷移模式：只創建最小 Flask 應用程式和資料庫配置
        from flask import Flask
        from .core.config import load_config
        from .database.models import db
        from .database.migrate_config import init_migrate
        
        # 創建最小 Flask 應用程式
        app = Flask(__name__)
        
        # 載入配置
        config = load_config(config_path or "config/config.yml")
        
        # 設定資料庫 URI
        db_config = config.get('db', {})
        database_url = os.getenv('DATABASE_URL')
        
        if not database_url:
            # 從配置建構 URL
            host = db_config.get('host', 'localhost')
            port = db_config.get('port', 5432)
            database = db_config.get('db_name', 'chatbot')
            username = db_config.get('user', 'postgres')
            password = db_config.get('password', 'password')
            
            # SSL 配置
            ssl_params = ""
            if 'sslmode' in db_config:
                ssl_params = f"?sslmode={db_config['sslmode']}"
                if 'sslrootcert' in db_config:
                    ssl_params += f"&sslrootcert={db_config['sslrootcert']}"
            
            database_url = f"postgresql://{username}:{password}@{host}:{port}/{database}{ssl_params}"
        
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        # 初始化資料庫和遷移
        db.init_app(app)
        init_migrate(app)
        
        return app
    else:
        # 正常模式：創建完整應用程式
        bot = MultiPlatformChatBot(config_path or "config/config.yml")
        return bot.get_flask_app()


# 為了向後兼容，保留原有的全域變數和函數
if __name__ == "__main__":
    # 開發模式運行
    bot = MultiPlatformChatBot()
    bot.run(debug=True)