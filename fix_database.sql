-- 資料庫遷移腳本：增加平台支援
-- 請在 Google Cloud SQL 中執行此腳本

-- 第一步：增加 platform 欄位
ALTER TABLE user_thread_table 
ADD COLUMN platform VARCHAR(50) DEFAULT 'line';

-- 第二步：更新現有資料的 platform 欄位
UPDATE user_thread_table 
SET platform = 'line' 
WHERE platform IS NULL;

-- 第三步：將 platform 設為 NOT NULL
ALTER TABLE user_thread_table 
ALTER COLUMN platform SET NOT NULL;

-- 第四步：刪除舊的主鍵約束
ALTER TABLE user_thread_table 
DROP CONSTRAINT user_thread_table_pkey;

-- 第五步：建立新的複合主鍵
ALTER TABLE user_thread_table 
ADD CONSTRAINT user_thread_table_pkey PRIMARY KEY (user_id, platform);

-- 第六步：建立效能索引
CREATE INDEX IF NOT EXISTS idx_thread_user_platform 
ON user_thread_table(user_id, platform);

CREATE INDEX IF NOT EXISTS idx_thread_created_at 
ON user_thread_table(created_at);

-- 第七步：建立新的對話歷史表（供其他 AI 模型使用）
CREATE TABLE IF NOT EXISTS simple_conversation_history (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    platform VARCHAR(50) NOT NULL DEFAULT 'line',
    model_provider VARCHAR(50) NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 建立對話歷史表的索引
CREATE INDEX IF NOT EXISTS idx_conversation_user_platform 
ON simple_conversation_history(user_id, platform);

CREATE INDEX IF NOT EXISTS idx_conversation_user_platform_provider 
ON simple_conversation_history(user_id, platform, model_provider);

CREATE INDEX IF NOT EXISTS idx_conversation_created_at 
ON simple_conversation_history(created_at);