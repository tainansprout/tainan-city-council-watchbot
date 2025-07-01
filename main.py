#!/usr/bin/env python3

from flask import Flask, request, abort,render_template, jsonify
from linebot import (
    LineBotApi
)
from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)

from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    ReplyMessageRequest,
    TextMessage
)

from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    AudioMessageContent
)


import atexit
import traceback

from src.models import ModelFactory
from src.core.config import load_config
from src.core.logger import logger
from src.core.security import InputValidator, require_json_input, verify_line_signature, init_security
from src.core.security_config import security_config
from src.core.auth import require_test_auth, init_test_auth, get_auth_status_info, init_test_auth_with_config
from src.database import Database
from src.utils import check_token_valid
from src.services import ChatService, AudioService

app = Flask(__name__)
config = load_config()

# 初始化安全性配置
init_security(app)

# 初始化測試認證 - 使用配置文件
init_test_auth_with_config(config)
init_test_auth(app)

configuration = Configuration(access_token=config['line']['channel_access_token'])
handler = WebhookHandler(config['line']['channel_secret'])

# 初始化服務
database = Database(config['db'])
model = ModelFactory.create_from_config({
    'provider': 'openai',
    'api_key': config['openai']['api_key'],
    'assistant_id': config['openai']['assistant_id']
})
chat_service = ChatService(model, database, config)
audio_service = AudioService(model, chat_service)

atexit.register(database.close_engine)

@app.route("/webhooks/line", methods=['POST', 'GET'])
def webhooks_line():
    if request.method == 'GET':
        return jsonify({
            'error': 'GET method not supported',
            'message': 'This endpoint only accepts POST requests from LINE webhook',
            'endpoint': '/webhooks/line'
        }), 405
    return _handle_line_webhook()

@app.route("/callback", methods=['POST', 'GET'])
def callback():
    """向後兼容的端點"""
    if request.method == 'GET':
        return jsonify({
            'error': 'GET method not supported', 
            'message': 'This endpoint only accepts POST requests from LINE webhook',
            'endpoint': '/callback',
            'note': 'This endpoint is deprecated, please use /webhooks/line'
        }), 405
    return _handle_line_webhook()

def _handle_line_webhook():
    # 獲取請求簽名和內容
    signature = request.headers.get('X-Line-Signature')
    if not signature:
        logger.warning("Missing Line signature")
        abort(400)
    
    body = request.get_data(as_text=True)
    
    # 記錄請求
    logger.info("LINE webhook received")
    
    try:
        # 使用官方 handler 處理，它會自動驗證簽名
        handler.handle(body, signature)
    except InvalidSignatureError as e:
        logger.warning(f"Invalid Line signature: {e}")
        abort(400)
    except Exception as e:
        logger.error(f"Webhook handling failed: {e}")
        abort(500)
    
    return 'OK'



@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    """處理文字訊息"""
    user_id = event.source.user_id
    
    # 驗證用戶 ID 格式
    if not InputValidator.validate_user_id(user_id):
        logger.warning(f"Invalid user ID format: {user_id}")
        return
    
    # 驗證和清理訊息內容
    text = event.message.text.strip() if event.message.text else ""
    validation_result = InputValidator.validate_message_content(text)
    
    if not validation_result['is_valid']:
        logger.warning(f"Invalid message from {user_id}: {validation_result['errors']}")
        # 發送友善的錯誤訊息給用戶
        error_msg = TextMessage(text="抱歉，您的訊息格式不正確，請重新輸入。")
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[error_msg]
                )
            )
        return
    
    # 使用清理後的內容
    clean_text = validation_result['cleaned_content']
    msg = chat_service.handle_message(user_id, clean_text)
    
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[msg]
            )
        )

@handler.add(MessageEvent, message=AudioMessageContent)
def handle_audio_message(event):
    """處理音訊訊息"""
    user_id = event.source.user_id
    
    with ApiClient(configuration) as api_client:
        line_bot_blob_api = MessagingApiBlob(api_client)
        audio_content = line_bot_blob_api.get_message_content(message_id=event.message.id)
        
        msg = audio_service.handle_audio_message(user_id, audio_content)
        
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[msg]
            )
        )


@app.route("/", methods=['GET'])
def home():
    return 'Hello World'

@app.route('/health')
def health_check():
    """健康檢查端點"""
    from datetime import datetime
    
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0.0',
        'checks': {}
    }
    
    try:
        # 檢查資料庫連線 - 維持測試兼容格式
        try:
            with database.get_session() as session:
                session.execute('SELECT 1')
            health_status['database'] = {'status': 'connected'}
            health_status['checks']['database'] = {'status': 'healthy'}
        except Exception as e:
            health_status['database'] = {'status': 'error', 'error': str(e)}
            health_status['checks']['database'] = {
                'status': 'unhealthy', 
                'error': str(e)
            }
            health_status['status'] = 'unhealthy'
        
        # 檢查模型連線 - 維持測試兼容格式
        try:
            is_valid, error = model.check_connection()
            if is_valid:
                health_status['model'] = {'status': 'connected'}
                health_status['checks']['model'] = {'status': 'healthy'}
            else:
                health_status['model'] = {'status': 'error', 'error': error}
                health_status['checks']['model'] = {
                    'status': 'unhealthy', 
                    'error': error
                }
                health_status['status'] = 'unhealthy'
        except Exception as e:
            health_status['model'] = {'status': 'error', 'error': str(e)}
            health_status['checks']['model'] = {
                'status': 'unhealthy', 
                'error': str(e)
            }
            health_status['status'] = 'unhealthy'
        
        # 返回結果
        # 添加認證狀態資訊（僅顯示基本資訊）
        health_status['checks']['auth'] = get_auth_status_info()
        
        status_code = 200 if health_status['status'] == 'healthy' else 503
        return health_status, status_code
        
    except Exception as e:
        return {
            'status': 'unhealthy', 
            'timestamp': datetime.utcnow().isoformat(),
            'error': str(e)
        }, 503

@app.route('/metrics')
def metrics():
    """基本指標端點"""
    try:
        db_info = database.get_connection_info()
        
        metrics_data = {
            'database': {
                'pool_size': db_info['pool_size'],
                'checked_in': db_info['checked_in'],
                'checked_out': db_info['checked_out'],
                'overflow': db_info['overflow'],
                'invalid': db_info['invalid']
            },
            'model': {
                'provider': model.get_provider().value
            }
        }
        
        return metrics_data
        
    except Exception as e:
        return {'error': str(e)}, 500

@app.route('/chat', methods=['GET', 'POST'])
@require_test_auth
def index():
    """測試聊天介面 - 用於確認部署狀態"""
    app_name = config.get('app', {}).get('name', '聊天機器人')
    return render_template('chat.html', app_name=app_name)

@app.route('/ask', methods=['POST'])
@require_test_auth
@require_json_input(['message'])
def ask():
    """測試用聊天端點 - 僅用於開發測試"""
    try:
        # 獲取清理後的輸入
        user_message = request.validated_json['message']
        
        # 長度檢查 - 在生產環境中限制更嚴格以防止濫用
        max_length = security_config.get_max_message_length(is_test=True)
        if len(user_message) > max_length:
            return jsonify({'error': f'測試訊息長度不能超過 {max_length} 字符'}), 400
        
        # 使用固定的測試用戶 ID
        test_user_id = "U" + "0" * 32  # 固定的測試用戶 ID
        response_message = chat_service.handle_message(test_user_id, user_message)
        
        # 清理回應內容以防止 XSS
        if hasattr(response_message, 'text'):
            clean_response = InputValidator.sanitize_text(response_message.text)
        else:
            clean_response = InputValidator.sanitize_text(str(response_message))
        
        return jsonify({'message': clean_response})
        
    except Exception as e:
        logger.error(f"Test chat endpoint error: {e}")
        return jsonify({'error': '處理請求時發生錯誤'}), 500


@app.route('/auth-info')
def auth_info():
    """顯示認證資訊"""
    from src.core.auth import test_auth
    
    auth_info = test_auth.get_auth_info()
    
    return jsonify({
        'message': '測試介面需要認證',
        'auth_method': auth_info['method'],
        'description': auth_info['description'],
        'example': auth_info['example'] if os.getenv('FLASK_ENV') == 'development' else '請查看環境變數配置',
        'test_endpoints': [
            '/chat - 測試聊天介面',
            '/ask - 測試 API 端點'
        ]
    })


def create_app():
    """應用工廠函數 - 用於測試和生產環境"""
    return app

if __name__ == "__main__":
    import os
    
    # 檢查 API token 有效性
    check_token_valid(model)
    
    # 根據環境變量決定運行模式
    env = os.getenv('FLASK_ENV', 'development')
    
    if env == 'production':
        print("⚠️  生產環境應使用 WSGI 服務器 (如 Gunicorn)")
        print("建議使用: gunicorn -c gunicorn.conf.py main:app")
        print("或使用: python wsgi.py")
    else:
        print("🔧 開發模式 - 使用 Flask 開發服務器")
        print("⚠️  注意：此服務器僅適用於開發環境")
        app.run(
            host=os.getenv('HOST', '0.0.0.0'),
            port=int(os.getenv('PORT', '8080')),
            debug=os.getenv('DEBUG', 'True').lower() == 'true'
        )
