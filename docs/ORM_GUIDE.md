# ORM 系統指南

## 概述

本專案已整合 SQLAlchemy 2.0 + Alembic 作為 ORM 和資料庫遷移解決方案，提供類似 `npm run` 的腳本系統來管理資料庫操作。

## 快速開始

### 1. 首次設置

```bash
# 安裝 ORM 相關依賴
pip install -r requirements-orm.txt

# 首次資料庫設置（包含遷移初始化）
./scripts/db.sh setup
```

### 2. 日常使用命令

```bash
# 檢查資料庫連線和狀態
./scripts/db.sh check

# 查看遷移狀態
./scripts/db.sh status

# 創建新的遷移（當模型改變時）
./scripts/db.sh migrate -m "Add new feature"

# 應用遷移到資料庫
./scripts/db.sh upgrade

# 回滾上一個遷移
./scripts/db.sh rollback
```

## 資料庫架構

### 現有表格

1. **user_thread_table** - OpenAI Assistant API 的 thread 管理
   - `user_id` (主鍵) - Line 用戶 ID
   - `thread_id` - OpenAI thread ID
   - `created_at` - 創建時間

2. **simple_conversation_history** - 非 OpenAI 模型的對話歷史
   - `id` (主鍵) - 自增 ID
   - `user_id` - Line 用戶 ID
   - `model_provider` - 模型提供商 (anthropic, gemini, ollama)
   - `role` - 角色 (user, assistant)
   - `content` - 對話內容
   - `created_at` - 創建時間

## 高可用性配置

### 連線池設置

```python
# 連線池配置 (src/models/database.py)
pool_size=20,          # 基本連線數
max_overflow=30,       # 最大溢出連線
pool_timeout=30,       # 連線等待超時
pool_recycle=3600,     # 連線回收時間（1小時）
pool_pre_ping=True,    # 連線前測試
```

### SSL 和 Keepalive

```python
connect_args={
    "sslmode": "require",
    "connect_timeout": 10,
    "keepalives_idle": 600,    # TCP keepalive
    "keepalives_interval": 30,
    "keepalives_count": 3,
}
```

## 使用 ORM 模型

### 基本查詢

```python
from src.models.database import get_db_session, SimpleConversationHistory

# 使用 session
with get_db_session() as session:
    # 查詢用戶對話
    conversations = session.query(SimpleConversationHistory).filter(
        SimpleConversationHistory.user_id == "user123"
    ).all()
    
    # 新增對話
    new_conv = SimpleConversationHistory(
        user_id="user123",
        model_provider="anthropic",
        role="user",
        content="Hello"
    )
    session.add(new_conv)
    session.commit()
```

### 使用對話管理器

```python
from src.services.conversation_manager_orm import get_conversation_manager

manager = get_conversation_manager()

# 新增訊息
manager.add_message("user123", "anthropic", "user", "Hello")

# 取得歷史
history = manager.get_recent_conversations("user123", "anthropic", limit=10)

# 清除歷史
manager.clear_user_history("user123", "anthropic")
```

## 遷移管理

### 創建遷移

```bash
# 自動檢測模型變更並創建遷移
./scripts/db.sh migrate -m "描述變更內容"

# 或直接使用 alembic
alembic revision --autogenerate -m "描述變更內容"
```

### 應用遷移

```bash
# 升級到最新版本
./scripts/db.sh upgrade

# 或指定版本
alembic upgrade head
alembic upgrade +1  # 升級一個版本
```

### 回滾遷移

```bash
# 回滾上一個版本
./scripts/db.sh rollback

# 或指定版本
alembic downgrade -1
alembic downgrade base  # 回滾到初始狀態
```

## 生產環境注意事項

### 環境變數配置

```bash
# 資料庫連線（優先使用環境變數）
export DATABASE_URL="postgresql://user:pass@host:port/db"

# 或個別設置
export DB_HOST="your-host"
export DB_PORT="5432"
export DB_NAME="your-db"
export DB_USER="your-user"
export DB_PASSWORD="your-password"
```

### 遷移最佳實踐

1. **備份優先**: 生產環境遷移前務必備份資料庫
2. **測試遷移**: 在測試環境先執行遷移
3. **漸進式遷移**: 大型變更分成多個小遷移
4. **回滾計畫**: 準備回滾方案以防萬一

### 監控和維護

```python
# 定期清理舊對話記錄
from src.services.conversation_manager_orm import get_conversation_manager

manager = get_conversation_manager()
deleted_count = manager.cleanup_old_conversations(days_to_keep=30)
print(f"Cleaned up {deleted_count} old records")
```

## 故障排除

### 常見問題

1. **連線失敗**: 檢查資料庫連線字串和網路
2. **遷移衝突**: 使用 `alembic heads` 檢查分支，合併衝突
3. **SSL 錯誤**: 確保 SSL 憑證配置正確

### 診斷命令

```bash
# 檢查資料庫狀態
./scripts/db.sh check

# 查看遷移歷史
./scripts/db.sh status

# 重置資料庫（開發環境）
./scripts/db.sh reset  # ⚠️ 會刪除所有資料
```

## 遷移到 ORM

現有專案遷移步驟：

1. 安裝依賴: `pip install -r requirements-orm.txt`
2. 備份現有資料庫
3. 執行設置: `./scripts/db.sh setup`
4. 測試新功能
5. 逐步將原有 SQL 查詢改為 ORM 操作