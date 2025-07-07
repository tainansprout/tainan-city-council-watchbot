"""
Gunicorn 配置文件 - Cloud Run 和 Docker 優化設置
"""

import os
import multiprocessing

# 伺服器綁定 - Cloud Run 使用 PORT 環境變數
bind = f"0.0.0.0:{os.getenv('PORT', '8080')}"

# Worker 配置 - 動態計算 worker 數量
def get_workers():
    # Cloud Run 限制記憶體，使用較保守的 worker 數量
    if os.getenv('K_SERVICE') or os.getenv('CLOUD_RUN_SERVICE'):  # K_SERVICE 是 Cloud Run 的標準環境變數
        return 2  # Cloud Run 建議使用 1 個 worker 以節省記憶體
    # 本地開發或容器環境
    return min(3, max(1, multiprocessing.cpu_count() // 2))  # 較保守的設定

workers = get_workers()
worker_class = "sync"  # 使用 sync 避免額外依賴
worker_connections = 1000

# 超時設置 - Cloud Run 優化
timeout = 240  # Cloud Run 建議較長的超時時間
keepalive = 5  # 更長的 keepalive
graceful_timeout = 60  # 更長的優雅關閉時間

# 請求限制
max_requests = 1000
max_requests_jitter = 100

# 預加載設置 - Cloud Run 優化
# Cloud Run 建議使用 preload_app=True 以減少啟動時間
preload_app = True

# 日誌配置
accesslog = "-"
errorlog = "-"
loglevel = "info"
access_log_format = '%({x-forwarded-for}i)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# 進程名稱
proc_name = "chatgpt-line-bot"

# 安全設置
forwarded_allow_ips = "*"
proxy_protocol = True
proxy_allow_ips = "*"

# 效能調優 - Cloud Run 特化
max_requests_jitter = 50
# worker_tmp_dir 在 Cloud Run 中不需要設定，Cloud Run 會自動管理臨時檔案

# 啟動和關閉鉤子
def on_starting(server):
    server.log.info("Starting Gunicorn with %d workers", workers)

def on_exit(server):
    server.log.info("Gunicorn shutting down")

def worker_int(worker):
    worker.log.info("Worker received INT or QUIT signal")

# 監控設置
def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def pre_fork(server, worker):
    server.log.info("Worker about to fork (pid: %s)", worker.pid)

def worker_abort(worker):
    worker.log.info("Worker aborted (pid: %s)", worker.pid)