https://onlinelibrary.wiley.com/doi/10.1002/poi3.263
中文 | [English](README.en.md)

本專案是使用 Line 作為前端，連接 OpenAI Assistant API 的聊天機器人。機器人將部署在 Google Cloud Run 上，並使用 Google Cloud SQL 來存取聊天線程 ID。

## 目錄

- [前置準備](#前置準備)
- [取得 OpenAI 的 API Token](#取得-openai-的-api-token)
- [設定 OpenAI Assistant API](#設定-openai-assistant-api)
- [設定 Line Bot](#設定-line-bot)
- [設定環境變數](#設定環境變數)
- [設定 Google Cloud SQL](#設定-google-cloud-sql)
- [完成設定檔](#完成設定檔)
- [部署到 Google Cloud Run](#部署到-google-cloud-run)
- [測試程式運作](#測試程式運作)

## 前置準備

- 一個已啟用計費的 Google Cloud Platform 帳號
- OpenAI API 使用權限
- Line Developers 帳號

## 取得 OpenAI 的 API Token

1. [OpenAI Platform](https://platform.openai.com/) 平台中註冊/登入帳號

2. 左上方有一個頭像，在那邊建立一個 Project。

3. 進入 Project 後，於左邊尋找 Project → API Key

4. 點選右上角的 `+ Create` ，即可生成 OpenAI 的 API Token。

## 設定 OpenAI Assistant API

1. **建立Assistant**

   - 進入專案後，請在上方點選「Playground」，之後在介面左邊點選「Assistants」，進入OpenAI Assistant API的介面，接著建立一個Assistant。

2. **上傳您需要作為資料庫之檔案**

   - 請在 Assistant 介面上設定名稱與System instructions，作為機器人預設的system prompt。Model建議選取`gpt-4o`，Temperature建議設定為`0.01`。
   - 接著，在 Tools → File Search中，點選 `+ FIles` 上傳你要作為資料庫的檔案。

3. **在 Playground 測試可用性**

   - 前往 [OpenAI Playground](https://platform.openai.com/playground)
   - 測試您的 Assistant 是否能正常運作。

4. **記錄 assistant_id**

   - 在 Assistant 名字下方有一串文字，即為 `assistant_id`，請記錄下來，稍後會用到。

## 設定 Line Bot

1. **建立 Line Bot**

   - 登入 [Line Developers Console](https://developers.line.biz/console/)
   - 建立新的 Provider 和 Channel（Messaging API）

2. **取得 Channel 資訊**

   - 在 Channel 設定中，取得 `Channel Access Token` 和 `Channel Secret`
   - 在 `Basic Settings` 下方，有一個 `Channel Secret` →  按下 `Issue`，生成後即為 `channel_secret`。
   - 在 `Messaging API` 下方，有一個 `Channel access token` →  按下 `Issue`，生成後即為 `channel_access_token`。

3. **設定 Webhook URL**

   - 將 Webhook URL 設定為稍後部署的 Google Cloud Run 地址（可在部署完成後更新）
   - 啟用 Webhook，將「使用 Webhook」開關切換為開啟

## 設定 Google Cloud SQL

1. **建立 Cloud SQL 個體**

   - 前往 [Cloud SQL Instances](https://console.cloud.google.com/sql/instances)
   - 點選 **建立執行個體**，選擇您需要的資料庫（例如 PostgreSQL）

2. **配置執行個體**

   - 設定執行個體名稱、密碼等資訊
   - 建立連線操作用之帳戶，並記錄使用者名稱與密碼
   - 建立資料庫
   - 使用Cloud SQL Studio於資料庫中執行以下SQL指令以建立Table
    ```sql
    CREATE TABLE user_thread_table (
        user_id VARCHAR(255) PRIMARY KEY,
        thread_id VARCHAR(255),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    ```

3. **取得連線資訊**

   - 在執行個體建立後，記下以下資訊：

     - 執行個體連線名稱（Instance Connection Name）
     - 主機（Host）
     - 埠號（Port）
     - 資料庫名稱（Database Name）
     - 使用者名稱（User）
     - 密碼（Password）

4. **取得 SSL 憑證**

   - 進入執行個體詳情頁面
   - 在 **連線** 標籤下，啟用 SSL 連線
   - 下載：

     - 服務器 CA 憑證（Server CA Certificate）
     - 用戶端憑證（Client Certificate）
     - 用戶端金鑰（Client Key）
   - 執行以下指令轉換以上憑證與金鑰

    ```bash
    openssl x509 -in client-cert.pem -out ssl-cert.crt # Server CA Certificate
    openssl x509 -in server-ca.pem -out ca-cert.crt # Client Certificate
    openssl rsa -in client-key.pem -out ssl-key.key # Client Key
    ```
   - 把 `ssl-cert.crt`、`ca-cert.crt`、`ssl-key.key` 這三個檔案複製到 `config/ssl/`下面

## 配置管理

本專案支援靈活的配置管理，適應不同的部署環境需求。

### 🎯 配置優先級

**應用程式配置優先級**（高優先級覆蓋低優先級）：
1. `config/config.yml` - 基本配置文件
2. **環境變數** - 最高優先級（適合生產環境）

**部署腳本配置優先級**：
1. `config/deploy/.env` - 部署配置文件  
2. **環境變數** - 最高優先級
3. 互動式輸入 - 當缺少配置時提示

### 📁 配置文件位置

```
config/
├── config.yml.example          # 應用程式配置範例
├── config.yml                  # 應用程式配置 (需自行建立)
└── deploy/
    ├── .env.example            # 部署配置範例  
    ├── .env                    # 部署配置 (需自行建立)
    ├── Dockerfile.cloudrun     # Cloud Run Dockerfile
    └── cloudrun-service.yaml   # Cloud Run 服務配置
```

### 💻 本地開發配置

請準備以下資訊：
- `channel_access_token` - Line Channel Access Token
- `channel_secret` - Line Channel Secret  
- `openai_api_key` - OpenAI API Key
- `assistant_id` - OpenAI Assistant ID
- 資料庫連線資訊

**方法 1: 使用配置文件（推薦）**

```bash
# 複製配置範例
cp config/config.yml.example config/config.yml

# 編輯配置文件
vim config/config.yml
```

```yaml
line:
  channel_access_token: YOUR_CHANNEL_ACCESS_TOKEN
  channel_secret: YOUR_CHANNEL_SECRET

openai:
  api_key: YOUR_OPENAI_API_KEY
  assistant_id: YOUR_ASSISTANT_ID

db:
  host: YOUR_DB_HOST
  port: 5432
  db_name: YOUR_DB_NAME
  user: YOUR_DB_USER
  password: YOUR_DB_PASSWORD
  sslmode: verify-ca
  sslrootcert: config/ssl/ca-cert.crt
  sslcert: config/ssl/client.crt
  sslkey: config/ssl/client.key
```

**方法 2: 使用環境變數**

```bash
# 設定環境變數
export LINE_CHANNEL_ACCESS_TOKEN="your_token"
export LINE_CHANNEL_SECRET="your_secret"
export OPENAI_API_KEY="sk-proj-xxxxxxxx"
export OPENAI_ASSISTANT_ID="asst_xxxxxxxx"
export DB_HOST="your_db_host"
export DB_USER="your_db_user"
export DB_PASSWORD="your_db_password"
export DB_NAME="your_db_name"

# 運行應用
python main.py
```

### ☁️ 生產環境配置

生產環境使用 Google Secret Manager 管理敏感資訊，通過環境變數注入到容器中。

**支援的環境變數對照**：

| 配置項目 | config.yml 路徑 | 環境變數 |
|----------|----------------|----------|
| Line Access Token | `line.channel_access_token` | `LINE_CHANNEL_ACCESS_TOKEN` |
| Line Secret | `line.channel_secret` | `LINE_CHANNEL_SECRET` |
| OpenAI API Key | `openai.api_key` | `OPENAI_API_KEY` |
| OpenAI Assistant ID | `openai.assistant_id` | `OPENAI_ASSISTANT_ID` |
| 資料庫主機 | `db.host` | `DB_HOST` |
| 資料庫用戶 | `db.user` | `DB_USER` |
| 資料庫密碼 | `db.password` | `DB_PASSWORD` |
| 資料庫名稱 | `db.db_name` | `DB_NAME` |
| 認證方式 | `auth.method` | `TEST_AUTH_METHOD` |
| 日誌級別 | `log_level` | `LOG_LEVEL` |

### 🔍 配置驗證

```bash
# 檢查應用程式配置
python src/core/config.py

# 檢查部署配置  
./scripts/deploy/deploy-to-cloudrun.sh --dry-run
```

詳細的配置說明請參考：[配置管理指南](docs/CONFIGURATION.md)

## 部署到 Google Cloud Run

### 🚀 快速部署（推薦）

使用我們提供的自動化部署腳本：

```bash
# 1. 設定部署配置
cp config/deploy/.env.example config/deploy/.env
# 編輯 config/deploy/.env 檔案，填入你的專案設定

# 2. 執行自動部署腳本
./scripts/deploy/deploy-to-cloudrun.sh

# 3. 檢查配置（可選）
./scripts/deploy/deploy-to-cloudrun.sh --dry-run
```

### 📖 詳細部署指南

如需完整的部署流程、監控設定、負載平衡器配置等，請參考：
- [完整部署指南](docs/DEPLOYMENT.md)  
- [配置管理指南](docs/CONFIGURATION.md)
- [運行指南](docs/RUNNING.md)

### 🔧 手動部署（進階用戶）

如果你想要手動控制每個步驟：

1. **設定Google Cloud Console**

   ```bash
   gcloud auth login
   gcloud config set project {your-project-id}
   ```

2. **建立容器映像**

   ```bash
   gcloud builds submit --tag gcr.io/{your-project-id}/{your-image-name} -f config/deploy/Dockerfile.cloudrun .
   ```

3. **部署到 Cloud Run**

   ```bash
   gcloud run services replace config/deploy/cloudrun-service.yaml --region {your-region}
   ```

   - 請將以上指令中的佔位符替換為您的實際資訊。

4. **測試部署結果**

   - 部署後，會回傳一個Service URL，如 https://chatgpt-line-bot-****.run.app ，請記錄下來。

5. **設定 Webhook URL**

   - 進入Line Bot設定介面，將 Webhook URL 設定 Service URL 地址。
   - 啟用 Webhook，將「使用 Webhook」開關切換為開啟。
   - 點選 Verify，看是否回傳成功。

## 測試程式運作

1. **訪問 Chat 端點**

   - 前往 Service URL，如 `https://{your-cloud-run-url}/chat`，確認應用程式是否運行正常。

2. **透過 Line 測試**

   - 向您的 Line Bot 發送訊息，測試完整功能。

3. **檢查 Log**

   - 如果出現問題，使用 `gcloud` 或 Google Cloud Console 來檢查Log

## 開發與測試

### 本地開發設定

1. **安裝依賴套件**
   ```bash
   pip install -r requirements.txt
   ```

2. **設定本地環境變數**
   ```bash
   # 複製環境變數模板
   cp .env.local.example .env.local
   
   # 編輯 .env.local 填入您的配置
   vim .env.local
   ```

3. **運行開發服務器**
   
   **🔧 開發環境（推薦）：**
   ```bash
   # 使用開發腳本啟動
   ./scripts/dev.sh
   ```
   
   **🧪 本地生產測試：**
   ```bash
   # 測試生產配置
   ./scripts/test-prod.sh
   ```
   
   **⚡ 直接運行：**
   ```bash
   # 開發模式（會顯示警告，這是正常現象）
   python main.py
   
   # 生產模式（使用 Gunicorn）
   python wsgi.py
   ```

### 安裝測試依賴

```bash
pip install -r requirements-test.txt
```

### 執行測試

本專案使用 pytest 作為測試框架，包含單元測試、整合測試和 API 測試。

**執行所有測試：**
```bash
pytest
```

**執行特定測試類型：**
```bash
# 單元測試
pytest tests/unit/

# 整合測試
pytest tests/integration/

# API 測試
pytest tests/api/

# 外部服務模擬測試
pytest tests/mocks/
```

**測試覆蓋率報告：**
```bash
pytest --cov=src --cov-report=html
```

**詳細測試輸出：**
```bash
pytest -v
```

**指定測試檔案：**
```bash
pytest tests/unit/test_models.py
pytest tests/integration/test_chat_flow.py
```

### 程式碼品質檢查

```bash
# 檢查程式碼風格
flake8 src/ tests/

# 型別檢查
mypy src/
```

### 測試架構

- **單元測試** (`tests/unit/`): 測試個別模組和函數
- **整合測試** (`tests/integration/`): 測試服務間的整合
- **API 測試** (`tests/api/`): 測試 Flask 端點
- **模擬測試** (`tests/mocks/`): 測試外部服務的模擬

### 配置檔案

測試配置檔案位於 `pytest.ini`，包含以下設定：
- 測試路徑
- 覆蓋率設定
- 測試標記
- 輸出格式

## 注意事項

- 確保所有敏感資訊只放在 `config/ssl/` 當中及 `config/config.yml`。
- 如有需要，使用 Google Secret Manager 來管理密碼。
- 遵循安全和合規的最佳實踐。

## 捐款支持

本專案由台南新芽進行，若您希望能支持本專案，請[捐款贊助台南新芽](https://bit.ly/3RBvPyZ)。

## 特別感謝

本專案 Fork 自 [ExplainThis 的 ChatGPT-Line-Bot](https://github.com/TheExplainthis/ChatGPT-Line-Bot) 。特此致謝。

## 授權

[MIT](LICENSE)
