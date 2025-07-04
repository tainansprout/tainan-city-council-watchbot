"""
Gunicorn 配置文件 - Cloud Run 優化設置
"""

import os

# 伺服器綁定 - Cloud Run 使用 PORT 環境變數
bind = f"0.0.0.0:{os.getenv('PORT', '8080')}"

# Worker 配置
workers = 2
worker_class = "sync"

# 超時設置
timeout = 120
keepalive = 2

# 請求限制
max_requests = 1000
max_requests_jitter = 100

# 不使用預加載 - 避免 Cloud Run 啟動問題
preload_app = False

# 日誌配置
accesslog = "-"
errorlog = "-"
loglevel = "info"

# 進程名稱
proc_name = "chatgpt-line-bot"

# Cloud Run 安全設置
forwarded_allow_ips = "*"