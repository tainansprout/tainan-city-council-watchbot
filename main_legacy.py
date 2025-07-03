#!/usr/bin/env python3
"""
向後兼容的 main.py
保持原有的 LINE bot 功能，但使用新的平台架構
"""

from flask import Flask, request, abort, jsonify
import atexit
import logging

# 使用新的架構
from src.app import create_app
from src.core.logger import logger

# 創建應用程式實例
app = create_app()

# 為了向後兼容，保留一些原有的端點
@app.route("/callback", methods=['POST'])  
def callback():
    """向後兼容的 LINE callback 端點"""
    # 這個路由已經在新架構中處理了
    # 這裡只是為了確保舊的端點仍然可用
    return "This endpoint is handled by the new platform architecture", 200

@app.route("/", methods=['GET'])
def home():
    """根路徑 - 顯示基本資訊"""
    return jsonify({
        'message': 'ChatGPT Line Bot - Multi-Platform Edition',
        'status': 'running',
        'version': '2.0.0',
        'note': 'This is the legacy compatibility layer. Use /health for detailed status.'
    })

if __name__ == "__main__":
    logger.info("Starting ChatGPT Line Bot (Legacy Mode)")
    app.run(host='0.0.0.0', port=8080, debug=True)