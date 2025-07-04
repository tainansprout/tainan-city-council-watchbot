"""
Gunicorn 配置文件 - 生產環境設置
"""

import os
import multiprocessing

# 伺服器綁定
bind = f"0.0.0.0:{os.getenv('PORT', '8080')}"

# Worker 配置
workers = int(os.getenv('GUNICORN_WORKERS', '2'))
worker_class = "gevent"
worker_connections = 1000

# 超時設置
timeout = 120
keepalive = 2

# 請求限制
max_requests = 1000
max_requests_jitter = 100

# 預加載應用
preload_app = True

# 日誌配置
accesslog = "-"
errorlog = "-"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# 進程名稱
proc_name = "chatgpt-line-bot"

# 安全設置
forwarded_allow_ips = "*"
secure_scheme_headers = {
    'X-FORWARDED-PROTOCOL': 'ssl',
    'X-FORWARDED-PROTO': 'https',
    'X-FORWARDED-SSL': 'on'
}

# 性能調優
max_worker_connections = 1000

# Worker 臨時目錄設定 - 跨平台兼容
import os
import platform

if platform.system() == "Linux" and os.path.exists("/dev/shm"):
    # Linux 系統使用共享記憶體以提升性能
    worker_tmp_dir = "/dev/shm"
else:
    # macOS 和其他系統使用系統臨時目錄
    worker_tmp_dir = os.environ.get('TMPDIR', '/tmp')

# 重啟設置
max_worker_lifetime = 3600  # 1 hour
max_worker_memory_usage = 0  # 禁用記憶體限制

def when_ready(server):
    """當服務器準備好接受連接時調用"""
    server.log.info("Server is ready. Spawning workers")

def worker_int(worker):
    """Worker 收到 SIGINT 信號時調用"""
    worker.log.info("worker received INT or QUIT signal")

def pre_fork(server, worker):
    """Fork worker 之前調用"""
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_fork(server, worker):
    """Fork worker 之後調用"""
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_worker_init(worker):
    """Worker 初始化完成後調用"""
    worker.log.info("Worker initialized (pid: %s)", worker.pid)

def worker_exit(server, worker):
    """Worker 退出時調用"""
    server.log.info("Worker exited (pid: %s)", worker.pid)