-- 資料庫初始化 SQL 腳本
-- 用於 Docker Compose 的 PostgreSQL 自動初始化

-- 確保資料庫和用戶存在
CREATE DATABASE IF NOT EXISTS chatgpt_line_bot;
CREATE USER IF NOT EXISTS chatgpt_user WITH PASSWORD 'your_password_here';

-- 授予權限
GRANT ALL PRIVILEGES ON DATABASE chatgpt_line_bot TO chatgpt_user;

-- 連接到應用資料庫
\c chatgpt_line_bot;

-- 授予 schema 權限
GRANT ALL ON SCHEMA public TO chatgpt_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO chatgpt_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO chatgpt_user;

-- 設置預設權限
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO chatgpt_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO chatgpt_user;