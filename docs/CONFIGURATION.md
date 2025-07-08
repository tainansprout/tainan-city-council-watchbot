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

### ⚙️ ConfigManager Singleton (v2.0)

新版本使用 ConfigManager 單例模式來管理配置：

**特色**：
- **執行緒安全**: 使用雙重檢查鎖定模式確保執行緒安全
- **效能優化**: 配置僅載入一次，避免重複 I/O 操作
- **記憶體高效**: 單一實例在所有請求間共享
- **懶載入**: 只有在需要時才載入配置

**使用方式**：
```python
from src.core.config import ConfigManager

# 取得配置管理器實例
config_manager = ConfigManager()

# 取得完整配置
config = config_manager.get_config()

# 取得特定配置值
line_token = config_manager.get_value('platforms.line.channel_access_token')
db_host = config_manager.get_value('db.host')

# 強制重新載入配置（開發時使用）
config_manager.force_reload()
```

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

#### 認證配置 (v2.0)
- `TEST_AUTH_METHOD` → `auth.method` (認證方式: simple_password, basic_auth, token)
- `TEST_PASSWORD` → `auth.password` (簡單密碼認證的密碼)
- `TEST_USERNAME` → `auth.username` (Basic Auth 用戶名)
- `TEST_API_TOKEN` → `auth.api_token` (API Token 認證用)
- `TEST_SECRET_KEY` → `auth.secret_key` (Session 密鑰)
- `TEST_TOKEN_EXPIRY` → `auth.token_expiry` (Token 有效期，秒為單位)

#### 安全配置 (v2.1 - 2024 年最佳實踐)

##### 安全標頭配置
- `ENABLE_SECURITY_HEADERS` → `security.headers.enabled` (啟用安全標頭)
- `FORCE_HTTPS` → `security.headers.force_https` (強制 HTTPS 重定向)
- `ENABLE_HSTS` → `security.headers.enable_hsts` (啟用 HTTP Strict Transport Security)
- `DEBUG_SECURITY_HEADERS` → `security.headers.debug_headers` (記錄詳細安全標頭日誌)

##### CORS 跨域配置
- `ENABLE_CORS` → `security.cors.enabled` (啟用 CORS 支援)
- `CORS_ALLOWED_ORIGINS` → `security.cors.allowed_origins` (允許的來源域名，逗號分隔)

##### 速率限制配置
- `GENERAL_RATE_LIMIT` → `security.rate_limiting.general_rate_limit` (一般端點每分鐘請求數)
- `WEBHOOK_RATE_LIMIT` → `security.rate_limiting.webhook_rate_limit` (Webhook 端點每分鐘請求數)
- `TEST_ENDPOINT_RATE_LIMIT` → `security.rate_limiting.test_endpoint_rate_limit` (測試端點每分鐘請求數)

##### 內容安全配置
- `MAX_MESSAGE_LENGTH` → `security.content.max_message_length` (一般訊息最大長度)
- `MAX_TEST_MESSAGE_LENGTH` → `security.content.max_test_message_length` (測試訊息最大長度)

##### 監控和日誌配置
- `LOG_SECURITY_EVENTS` → `security.monitoring.log_security_events` (記錄安全事件)
- `ENABLE_REQUEST_LOGGING` → `security.monitoring.enable_request_logging` (啟用請求日誌)
- `ENABLE_SECURITY_REPORT` → `security.monitoring.enable_security_report` (開發環境安全報告端點)

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

## 🔒 安全配置詳細說明 (v2.1)

### 安全配置架構

新版本採用 2024 年安全最佳實踐，提供完整的安全標頭保護、CORS 支援、速率限制和內容安全檢查。

### 📋 完整配置範例

```yaml
security:
  # 安全標頭配置
  headers:
    enabled: true              # 啟用安全標頭
    force_https: false         # 不強制 HTTPS（支援測試環境）
    enable_hsts: false         # 不啟用 HSTS（測試友善）
    debug_headers: false       # 是否記錄詳細的安全標頭日誌
    
  # CORS 跨域配置
  cors:
    enabled: false             # 啟用 CORS 支援
    allowed_origins: []        # 允許的來源，空陣列表示不限制
    # 範例: ["https://example.com", "https://app.example.com"]
    allowed_methods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allowed_headers: ["Content-Type", "Authorization", "X-Requested-With", "X-CSRF-Token"]
    allow_credentials: true
    max_age: 86400             # 預檢請求快取時間（秒）
    
  # 速率限制配置
  rate_limiting:
    enabled: true
    general_rate_limit: 60     # 一般端點每分鐘請求數
    webhook_rate_limit: 300    # Webhook 端點每分鐘請求數
    test_endpoint_rate_limit: 10  # 測試端點每分鐘請求數
    
  # 內容安全配置
  content:
    max_message_length: 5000   # 一般訊息最大長度
    max_test_message_length: 1000  # 測試訊息最大長度
    enable_input_sanitization: true  # 啟用輸入清理
    
  # 監控和日誌
  monitoring:
    log_security_events: true  # 記錄安全事件
    enable_request_logging: true  # 啟用請求日誌
    enable_security_report: true  # 開發環境啟用安全報告端點
```

### 🛡️ 安全標頭說明

#### 自動應用的安全標頭

**Content Security Policy (CSP)**
- **作用**: 防止 XSS 攻擊和資料注入
- **開發環境**: 較寬鬆設定，支援 WebSocket 和必要的 CDN
- **生產環境**: 嚴格設定，僅允許必要的資源

**X-Frame-Options**
- **作用**: 防止 Clickjacking 攻擊
- **設定**: `DENY` - 完全禁止頁面被嵌入框架

**X-Content-Type-Options**
- **作用**: 防止 MIME sniffing 攻擊
- **設定**: `nosniff` - 強制瀏覽器遵循 Content-Type

**Permissions Policy**
- **作用**: 控制瀏覽器 API 的使用權限
- **設定**: 禁用不必要的 API（攝影機、麥克風、定位等）

**Cross-Origin 政策**
- **COEP**: `credentialless` - 彈性的跨域嵌入政策
- **COOP**: `same-origin` - 限制跨域開啟者政策
- **CORP**: `same-site` - 限制跨域資源政策

#### HTTPS 和 HSTS 配置

**設計原則**: 支援測試環境的 HTTP，同時允許生產環境啟用 HTTPS

```yaml
# 測試環境友善配置（預設）
security:
  headers:
    force_https: false  # 不強制 HTTPS
    enable_hsts: false  # 不啟用 HSTS

# 生產環境 HTTPS 配置
security:
  headers:
    force_https: true   # 強制 HTTPS
    enable_hsts: true   # 啟用 HSTS
```

**環境變數覆蓋**:
```bash
# 生產環境啟用 HTTPS
export FORCE_HTTPS=true
export ENABLE_HSTS=true
```

### 🌐 CORS 配置說明

#### 基本 CORS 設定

```yaml
security:
  cors:
    enabled: true
    allowed_origins: 
      - "https://example.com"
      - "https://app.example.com"
    allowed_methods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allowed_headers: ["Content-Type", "Authorization", "X-Requested-With"]
    allow_credentials: true
    max_age: 86400  # 24小時
```

#### CORS 使用情境

**情境 1: 公開 API**
```yaml
cors:
  enabled: true
  allowed_origins: ["*"]  # 允許所有來源（不建議生產環境）
  allow_credentials: false
```

**情境 2: 特定前端應用**
```yaml
cors:
  enabled: true
  allowed_origins: ["https://myapp.com", "https://admin.myapp.com"]
  allow_credentials: true
```

**情境 3: 開發環境**
```yaml
cors:
  enabled: true
  allowed_origins: ["http://localhost:3000", "http://localhost:8080"]
  allow_credentials: true
```

### ⚡ 速率限制說明

#### 端點類型分類

**一般端點** (`general_rate_limit: 60`)
- 首頁、健康檢查、指標端點
- 每分鐘 60 次請求

**Webhook 端點** (`webhook_rate_limit: 300`)
- LINE、Discord、Telegram webhook
- 每分鐘 300 次請求（支援高頻率訊息）

**測試端點** (`test_endpoint_rate_limit: 10`)
- `/ask`、`/security-report` 等測試用端點
- 每分鐘 10 次請求（防止濫用）

#### 速率限制算法

使用 **滑動窗口演算法**，提供 O(1) 複雜度的高效檢查：

```python
# 範例配置
security:
  rate_limiting:
    enabled: true
    general_rate_limit: 60    # 每分鐘 60 次
    webhook_rate_limit: 300   # 每分鐘 300 次
    test_endpoint_rate_limit: 10  # 每分鐘 10 次
```

### 🔍 內容安全檢查

#### 輸入清理和驗證

**`enable_input_sanitization` 設定說明**

這個設定控制是否啟用自動輸入安全檢查和惡意程式碼過濾功能，是系統安全防護的重要組成部分。

⚠️ **重要說明**: 此功能**僅過濾惡意程式碼**，不會清空或大幅修改正常的聊天內容。一般用戶的正常對話內容（包括中文、英文、數字、標點符號等）都會被保留。

**啟用時 (`true`) 的防護功能**:

1. **HTML/XSS 攻擊防護**
   - 過濾惡意的 `<script>` 標籤和危險內容
   - 移除 `javascript:` 協議鏈接
   - 清理 `on*` 事件處理器 (onclick, onload 等)
   - 對特殊字符進行 HTML 安全編碼

2. **代碼注入攻擊防護**
   - 檢測和移除惡意的 `<iframe>`、`<object>`、`<embed>` 標籤
   - 過濾危險的 CSS `expression()` 函數
   - 移除可能有害的 `@import` CSS 指令
   - 防護 `eval()` 和 `exec()` 等危險函數調用

3. **路徑遍歷攻擊防護**
   - 檢測和移除 `../` 等路徑遍歷攻擊模式
   - 過濾 Python 魔法方法等系統級調用

4. **惡意內容過濾**
   - 移除不可見的控制字符（但保留正常的換行和製表符）
   - 對 HTML 特殊字符進行安全轉義
   - 檢查內容長度限制

**效能優化特性**:
- **預編譯正則表達式**: 避免重複編譯，提升安全檢查速度
- **智慧快取**: 常見文本的安全檢查結果快取，減少重複處理
- **批次處理**: 支援批次安全檢查多個文本

**正常內容處理範例**:
```
輸入: "你好！今天天氣很好，我想問一下關於 Python 程式設計的問題。"
輸出: "你好！今天天氣很好，我想問一下關於 Python 程式設計的問題。" ✅ 完全保留

輸入: "<script>alert('惡意程式碼')</script>這是正常對話"
輸出: "這是正常對話" ✅ 移除惡意程式碼，保留正常內容
```

**配置範例**:

```yaml
security:
  content:
    # 啟用惡意程式碼過濾（建議在生產環境啟用）
    enable_input_sanitization: true
    
    # 長度限制（防止過長內容攻擊）
    max_message_length: 5000      # 一般訊息最大 5000 字元
    max_test_message_length: 1000 # 測試訊息最大 1000 字元
```

**使用情境建議**:

**生產環境** (`enable_input_sanitization: true`)
```yaml
security:
  content:
    enable_input_sanitization: true  # 必須啟用惡意程式碼防護
    max_message_length: 5000         # 嚴格限制
```

**開發環境** (`enable_input_sanitization: true`)
```yaml
security:
  content:
    enable_input_sanitization: true  # 建議啟用以測試安全過濾效果
    max_message_length: 10000        # 可放寬限制用於測試
```

**特殊測試環境** (`enable_input_sanitization: false`)
```yaml
security:
  content:
    enable_input_sanitization: false # 僅在需要測試原始輸入時禁用
    max_message_length: 1000         # 仍保持長度限制防護
```

**安全影響**:

✅ **啟用時的好處**:
- 有效防護 XSS 攻擊，保護用戶安全
- 阻止代碼注入嘗試，維護系統安全
- 過濾惡意程式碼，保留正常對話內容
- 符合安全最佳實踐和合規要求

⚠️ **禁用時的風險**:
- 暴露於 XSS 攻擊風險
- 可能受到代碼注入攻擊
- 惡意程式碼可能影響其他用戶
- 不符合安全合規要求

**對正常使用的影響**:
- ✅ **不影響**: 中文、英文、數字、標點符號等正常內容
- ✅ **不影響**: 正常的程式碼討論（如 "Python 的 for 迴圈怎麼寫？"）
- ✅ **不影響**: HTML 實體字符（會被安全編碼而非刪除）
- ⚠️ **會過濾**: 可執行的 JavaScript 程式碼、惡意 HTML 標籤

**除錯和監控**:

```bash
# 檢查輸入清理統計
python -c "
from src.core.security import InputValidator
stats = InputValidator.get_cache_stats()
print(f'快取使用率: {stats[\"cache_usage_percent\"]}%')
print(f'快取大小: {stats[\"cache_size\"]}/{stats[\"max_cache_size\"]}')
"

# 測試輸入清理效果
python -c "
from src.core.security import InputValidator
test_input = '<script>alert(\"test\")</script>Hello World'
cleaned = InputValidator.sanitize_text(test_input)
print(f'原始: {test_input}')
print(f'清理後: {cleaned}')
"
```

**效能考量**:
- 輸入清理會增加少量處理時間（通常 < 1ms）
- 快取機制能顯著提升重複內容的處理速度
- 預編譯正則表達式確保檢查效率
- 對於高頻率請求建議監控清理效能

### 📊 監控和報告

#### 安全事件日誌

```yaml
security:
  monitoring:
    log_security_events: true      # 記錄速率限制、輸入驗證失敗等
    enable_request_logging: true   # 記錄所有 HTTP 請求
    enable_security_report: true   # 開發環境提供 /security-report 端點
```

#### 安全報告端點

**開發環境專用**: `GET /security-report`

提供詳細的安全配置報告，包括：
- 當前安全標頭配置
- 安全等級評估（A-D 評級）
- 配置建議和警告
- 速率限制統計

### 🎛️ 環境特定配置

#### 開發環境最佳實踐

```yaml
security:
  headers:
    enabled: true
    force_https: false    # 允許 HTTP 測試
    enable_hsts: false    # 不啟用 HSTS
    debug_headers: true   # 啟用詳細日誌
  cors:
    enabled: true
    allowed_origins: ["http://localhost:3000"]
  monitoring:
    enable_security_report: true  # 啟用安全報告
```

#### 生產環境最佳實踐

```yaml
security:
  headers:
    enabled: true
    force_https: true     # 強制 HTTPS
    enable_hsts: true     # 啟用 HSTS
    debug_headers: false  # 關閉詳細日誌
  cors:
    enabled: false        # 僅在需要時啟用
  rate_limiting:
    enabled: true
    general_rate_limit: 60
  monitoring:
    log_security_events: true
    enable_security_report: false  # 生產環境隱藏
```

#### 測試環境配置

```bash
# 環境變數覆蓋
export ENABLE_SECURITY_HEADERS=true
export FORCE_HTTPS=false          # 支援 HTTP 測試
export ENABLE_HSTS=false           # 不啟用 HSTS
export ENABLE_CORS=true
export CORS_ALLOWED_ORIGINS="http://localhost:3000,https://test.example.com"
export DEBUG_SECURITY_HEADERS=true
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

# 安全配置 (開發環境)
security:
  headers:
    enabled: true
    force_https: false    # 允許 HTTP 測試
    debug_headers: true   # 啟用詳細日誌
  cors:
    enabled: true
    allowed_origins: ["http://localhost:3000"]
  rate_limiting:
    enabled: true
    test_endpoint_rate_limit: 20  # 開發環境可提高測試限制
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

# 安全配置環境變數
export ENABLE_SECURITY_HEADERS=true
export FORCE_HTTPS=false           # 測試環境允許 HTTP
export ENABLE_CORS=true
export CORS_ALLOWED_ORIGINS="http://localhost:3000"
export DEBUG_SECURITY_HEADERS=true

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

# 測試安全配置
ENABLE_SECURITY_HEADERS=true FORCE_HTTPS=false python -c "
from src.core.config import load_config
from src.core.security import SecurityConfig, SecurityHeaders
config = load_config()
security_config = SecurityConfig(config)
headers = SecurityHeaders.get_security_headers(sec_config=security_config)
print(f'生成了 {len(headers)} 個安全標頭')
"

# 測試安全報告（開發環境）
python -c "
from src.core.security import SecurityHeaders
report = SecurityHeaders.get_security_report()
print(f'安全等級: {SecurityHeaders.validate_security_configuration()[\"grade\"]}')
"

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

4. **安全標頭配置問題**
   ```
   ⚠️ CSP 政策過於嚴格，前端資源載入失敗
   ```
   **解決方法**: 在開發環境設定 `security.headers.debug_headers: true` 檢查詳細日誌

5. **CORS 跨域問題**
   ```
   ❌ Access to fetch at 'http://localhost:8080/api' blocked by CORS policy
   ```
   **解決方法**: 
   ```yaml
   security:
     cors:
       enabled: true
       allowed_origins: ["http://localhost:3000"]
   ```

6. **速率限制觸發**
   ```
   ⚠️ Rate limit exceeded for client
   ```
   **解決方法**: 調整對應端點的速率限制或檢查是否有異常請求

### 除錯指令

```bash
# 檢查配置載入結果
python src/core/config.py

# 檢查環境變數
env | grep -E "(LINE_|OPENAI_|DB_)"

# 檢查部署配置
cat config/deploy/.env

# 檢查安全配置
python -c "
from src.core.config import load_config
from src.core.security import SecurityConfig
config = load_config()
security_config = SecurityConfig(config)
print('安全配置已載入:', security_config.config.keys())
"

# 測試安全標頭生成
python -c "
from src.core.security import SecurityHeaders
validation = SecurityHeaders.validate_security_configuration()
print(f'安全等級: {validation[\"grade\"]}, 分數: {validation[\"score\"]}')
"

# 測試部署腳本
./scripts/deploy/deploy-to-cloudrun.sh --help
```

---

## 📚 相關文檔

- [運行指南](RUNNING.md)
- [部署指南](DEPLOYMENT.md)
- [安全政策](SECURITY.md)
- [CLAUDE.md](../CLAUDE.md) - 開發者指南