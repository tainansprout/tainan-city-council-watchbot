-- 簡單對話歷史表（僅用於非 OpenAI 模型）
-- Migration: 001_add_simple_conversation_history.sql

CREATE TABLE IF NOT EXISTS simple_conversation_history (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    model_provider VARCHAR(50) NOT NULL,  -- 'anthropic', 'gemini', 'ollama'
    role VARCHAR(20) NOT NULL,             -- 'user', 'assistant'
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 創建索引以優化查詢性能
CREATE INDEX IF NOT EXISTS idx_user_model_recent 
ON simple_conversation_history (user_id, model_provider, created_at DESC);

-- 創建複合索引
CREATE INDEX IF NOT EXISTS idx_user_model 
ON simple_conversation_history (user_id, model_provider);

-- 添加註釋
COMMENT ON TABLE simple_conversation_history IS '非 OpenAI 模型的簡單對話歷史管理';
COMMENT ON COLUMN simple_conversation_history.user_id IS 'Line 用戶 ID';
COMMENT ON COLUMN simple_conversation_history.model_provider IS '模型提供商: anthropic, gemini, ollama';
COMMENT ON COLUMN simple_conversation_history.role IS '角色: user 或 assistant';
COMMENT ON COLUMN simple_conversation_history.content IS '對話內容';