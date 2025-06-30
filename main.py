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
from src.database import Database
from src.utils import check_token_valid
from src.services import ChatService, AudioService

app = Flask(__name__)
config = load_config()
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

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError as e:
        logger.error(traceback.format_exception(e))
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)
    return 'OK'



@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    """處理文字訊息"""
    user_id = event.source.user_id
    text = event.message.text.strip()
    msg = chat_service.handle_message(user_id, text)
    
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
        # 檢查資料庫連線
        try:
            with database.get_session() as session:
                session.execute('SELECT 1')
            health_status['checks']['database'] = {'status': 'healthy'}
        except Exception as e:
            health_status['checks']['database'] = {
                'status': 'unhealthy', 
                'error': str(e)
            }
            health_status['status'] = 'unhealthy'
        
        # 檢查 OpenAI API
        try:
            is_valid, error = model.check_connection()
            if is_valid:
                health_status['checks']['openai_api'] = {'status': 'healthy'}
            else:
                health_status['checks']['openai_api'] = {
                    'status': 'unhealthy', 
                    'error': error
                }
                health_status['status'] = 'unhealthy'
        except Exception as e:
            health_status['checks']['openai_api'] = {
                'status': 'unhealthy', 
                'error': str(e)
            }
            health_status['status'] = 'unhealthy'
        
        # 返回結果
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

@app.route('/chat')
def index():
    return render_template('chat.html')

@app.route('/ask', methods=['POST'])
def ask():
    user_message = request.json['message']
    response_message = ask_api(user_message)
    return jsonify({'message': response_message})

def ask_api(message):
    """Web API 處理"""
    text_content = chat_service.handle_message('test_user', message)
    return text_content.text


if __name__ == "__main__":
    check_token_valid(model)
    app.run(host='0.0.0.0', port=8080, debug=True)
