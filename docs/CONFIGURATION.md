# 🔧 配置管理指南

本文檔說明 ChatGPT Line Bot 的配置管理系統，包括應用程式配置和部署配置的設定方式與優先級。

## 📖 目錄

- [應用程式配置](#應用程式配置)
- [部署配置](#部署配置)
- [環境變數對照表](#環境變數對照表)
- [配置範例](#配置範例)
- [最佳實踐](#最佳實踐)

## 應用程式配置

### 🎯 配置優先級

應用程式使用以下優先級載入配置（高優先級會覆蓋低優先級）：

```
1. config/config.yml (基本配置文件)
2. 環境變數 (Environment Variables) ← 最高優先級
```

### 📁 配置文件位置

- **主配置文件**: `config/config.yml`
- **配置範例**: `config/config.yml.example`

### 🔄 配置載入流程

1. **載入 YAML 配置**: 讀取 `config/config.yml` 作為基本配置
2. **環境變數覆蓋**: 檢查對應的環境變數，如果存在則覆蓋 YAML 中的值
3. **配置驗證**: 檢查必要配置項是否存在

### 🌍 支援的環境變數

#### LINE Bot 配置
- `LINE_CHANNEL_ACCESS_TOKEN` → `line.channel_access_token`
- `LINE_CHANNEL_SECRET` → `line.channel_secret`

#### OpenAI 配置
- `OPENAI_API_KEY` → `openai.api_key`
- `OPENAI_ASSISTANT_ID` → `openai.assistant_id`
- `OPENAI_BASE_URL` → `openai.base_url`

#### 資料庫配置
- `DB_HOST` → `db.host`
- `DB_PORT` → `db.port`
- `DB_NAME` → `db.db_name`
- `DB_USER` → `db.user`
- `DB_PASSWORD` → `db.password`
- `DB_SSLMODE` → `db.sslmode`
- `DB_SSLROOTCERT` → `db.sslrootcert`
- `DB_SSLCERT` → `db.sslcert`
- `DB_SSLKEY` → `db.sslkey`

#### 認證配置
- `TEST_AUTH_METHOD` → `auth.method`
- `TEST_PASSWORD` → `auth.password`
- `TEST_USERNAME` → `auth.username`
- `TEST_API_TOKEN` → `auth.api_token`
- `TEST_SECRET_KEY` → `auth.secret_key`
- `TEST_TOKEN_EXPIRY` → `auth.token_expiry`

#### 其他配置
- `LOG_LEVEL` → `log_level`
- `LOG_FILE` → `logfile`
- `FLASK_ENV` → `flask_env`

### 📋 必要配置項

以下配置項為必須設定的項目：

```yaml
line:
  channel_access_token: "必須設定"
  channel_secret: "必須設定"

openai:
  api_key: "必須設定"

db:
  host: "必須設定"
  user: "必須設定"
  password: "必須設定"
```

---

## 部署配置

### 🎯 配置優先級

部署腳本 (`scripts/deploy/`) 使用以下優先級載入配置：

```
1. config/deploy/.env (部署配置文件)
2. 環境變數 (Environment Variables) ← 最高優先級
3. 互動式輸入 (Interactive Input，僅在非自動模式)
```

### 📁 配置文件位置

- **部署配置文件**: `config/deploy/.env`
- **配置範例**: `config/deploy/.env.example`

### 🔄 部署配置載入流程

1. **載入 .env 文件**: 讀取 `config/deploy/.env` 作為基本配置
2. **環境變數覆蓋**: 檢查對應的環境變數，如果存在則覆蓋 .env 中的值
3. **互動式輸入**: 在互動模式下，提示用戶輸入缺少的配置
4. **配置驗證**: 檢查必要的部署配置項

### 🌍 部署環境變數

#### Google Cloud 基本設定
```bash
PROJECT_ID=your-project-id
REGION=asia-east1
ZONE=asia-east1-a
```

#### Cloud Run 設定
```bash
SERVICE_NAME=chatgpt-line-bot
IMAGE_NAME=chatgpt-line-bot
MEMORY=2Gi
CPU=2
MAX_INSTANCES=100
MIN_INSTANCES=1
```

#### Secret Manager 設定
```bash
OPENAI_API_KEY_SECRET=openai-api-key
OPENAI_ASSISTANT_ID_SECRET=openai-assistant-id
LINE_CHANNEL_ACCESS_TOKEN_SECRET=line-channel-access-token
LINE_CHANNEL_SECRET_SECRET=line-channel-secret
DB_HOST_SECRET=db-host
DB_USER_SECRET=db-user
DB_PASSWORD_SECRET=db-password
DB_NAME_SECRET=db-name
```

#### 實際數值 (用於創建 Secrets)
```bash
OPENAI_API_KEY=sk-proj-xxxxxxxx
OPENAI_ASSISTANT_ID=asst_xxxxxxxx
LINE_CHANNEL_ACCESS_TOKEN=your_token
LINE_CHANNEL_SECRET=your_secret
DB_HOST=your.db.host
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_NAME=your_db_name
```

---

## 環境變數對照表

| 用途 | config.yml 路徑 | 環境變數 | 部署腳本變數 |
|------|----------------|----------|-------------|
| LINE Access Token | `line.channel_access_token` | `LINE_CHANNEL_ACCESS_TOKEN` | `LINE_CHANNEL_ACCESS_TOKEN` |
| LINE Secret | `line.channel_secret` | `LINE_CHANNEL_SECRET` | `LINE_CHANNEL_SECRET` |
| OpenAI API Key | `openai.api_key` | `OPENAI_API_KEY` | `OPENAI_API_KEY` |
| OpenAI Assistant ID | `openai.assistant_id` | `OPENAI_ASSISTANT_ID` | `OPENAI_ASSISTANT_ID` |
| 資料庫主機 | `db.host` | `DB_HOST` | `DB_HOST` |
| 資料庫用戶 | `db.user` | `DB_USER` | `DB_USER` |
| 資料庫密碼 | `db.password` | `DB_PASSWORD` | `DB_PASSWORD` |
| 資料庫名稱 | `db.db_name` | `DB_NAME` | `DB_NAME` |

---

## 配置範例

### 💻 本地開發配置

**方法 1: 使用 config.yml**
```yaml
# config/config.yml
line:
  channel_access_token: "your_line_token"
  channel_secret: "your_line_secret"

openai:
  api_key: "sk-proj-xxxxxxxx"
  assistant_id: "asst_xxxxxxxx"

db:
  host: "localhost"
  port: 5432
  user: "postgres"
  password: "your_password"
  db_name: "chatbot_dev"
```

**方法 2: 使用環境變數**
```bash
# .env.local (需手動載入)
export LINE_CHANNEL_ACCESS_TOKEN="your_line_token"
export LINE_CHANNEL_SECRET="your_line_secret"
export OPENAI_API_KEY="sk-proj-xxxxxxxx"
export OPENAI_ASSISTANT_ID="asst_xxxxxxxx"
export DB_HOST="localhost"
export DB_USER="postgres"
export DB_PASSWORD="your_password"
export DB_NAME="chatbot_dev"

# 載入環境變數
source .env.local
python main.py
```

### ☁️ 部署配置

**設定部署配置文件**
```bash
# 1. 複製範例文件
cp config/deploy/.env.example config/deploy/.env

# 2. 編輯配置
vim config/deploy/.env
```

**或使用環境變數覆蓋**
```bash
# 設定環境變數
export PROJECT_ID="your-gcp-project"
export OPENAI_API_KEY="sk-proj-xxxxxxxx"
export LINE_CHANNEL_ACCESS_TOKEN="your_token"

# 執行部署
./scripts/deploy/deploy-to-cloudrun.sh
```

### 🧪 測試不同配置

```bash
# 測試配置載入
python src/core/config.py

# 測試環境變數覆蓋
LOG_LEVEL=DEBUG TEST_AUTH_METHOD=token python src/core/config.py

# 測試部署配置
./scripts/deploy/deploy-to-cloudrun.sh --dry-run
```

---

## 最佳實踐

### 🔒 安全性

1. **敏感資訊處理**
   - 📁 本地開發：使用 `config/config.yml`，加入 `.gitignore`
   - ☁️ 生產環境：使用 Google Secret Manager
   - 🚫 **絕對不要**：將敏感資訊提交到版本控制

2. **配置文件權限**
   ```bash
   # 設定適當的檔案權限
   chmod 600 config/config.yml
   chmod 600 config/deploy/.env
   ```

### 🏗️ 開發工作流程

1. **本地開發**
   ```bash
   # 複製配置範例
   cp config/config.yml.example config/config.yml
   
   # 編輯配置
   vim config/config.yml
   
   # 運行應用
   python main.py
   ```

2. **部署準備**
   ```bash
   # 複製部署配置
   cp config/deploy/.env.example config/deploy/.env
   
   # 編輯部署配置
   vim config/deploy/.env
   
   # 測試部署配置
   ./scripts/deploy/deploy-to-cloudrun.sh --dry-run
   ```

3. **生產部署**
   ```bash
   # 執行部署
   ./scripts/deploy/deploy-to-cloudrun.sh
   ```

### 🔧 配置驗證

**檢查配置完整性**
```bash
# 檢查應用程式配置
python -c "
from src.core.config import load_config
config = load_config()
print('配置檢查完成')
"

# 檢查部署配置
./scripts/deploy/deploy-to-cloudrun.sh --dry-run
```

### 📝 配置文檔

- 在團隊中分享時，提供 `.example` 文件而非實際配置
- 在 README 中說明必要的配置步驟
- 使用註解說明每個配置項的用途

---

## 🆘 故障排除

### 常見問題

1. **配置文件不存在**
   ```
   ⚠️ 配置文件不存在: config/config.yml，使用環境變數配置
   ```
   **解決方法**: 複製 `config.yml.example` 為 `config.yml` 並填入值

2. **缺少必要配置**
   ```
   ⚠️ 缺少必要配置: line.channel_access_token, openai.api_key
   ```
   **解決方法**: 在 `config.yml` 或環境變數中設定缺少的值

3. **部署配置錯誤**
   ```
   警告: 找不到 config/deploy/.env 檔案
   ```
   **解決方法**: 複製 `config/deploy/.env.example` 為 `config/deploy/.env`

### 除錯指令

```bash
# 檢查配置載入結果
python src/core/config.py

# 檢查環境變數
env | grep -E "(LINE_|OPENAI_|DB_)"

# 檢查部署配置
cat config/deploy/.env

# 測試部署腳本
./scripts/deploy/deploy-to-cloudrun.sh --help
```

---

## 📚 相關文檔

- [運行指南](RUNNING.md)
- [部署指南](DEPLOYMENT.md)
- [安全政策](SECURITY.md)
- [CLAUDE.md](../CLAUDE.md) - 開發者指南