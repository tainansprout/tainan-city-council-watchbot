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

#### 平台配置

**LINE Bot 配置**
- `LINE_CHANNEL_ACCESS_TOKEN` → `platforms.line.channel_access_token`
- `LINE_CHANNEL_SECRET` → `platforms.line.channel_secret`

**Discord Bot 配置**
- `DISCORD_BOT_TOKEN` → `platforms.discord.bot_token`
- `DISCORD_GUILD_ID` → `platforms.discord.guild_id`
- `DISCORD_COMMAND_PREFIX` → `platforms.discord.command_prefix`

**Telegram Bot 配置**
- `TELEGRAM_BOT_TOKEN` → `platforms.telegram.bot_token`
- `TELEGRAM_WEBHOOK_SECRET` → `platforms.telegram.webhook_secret`

**WhatsApp Business API 配置**
- `WHATSAPP_ACCESS_TOKEN` → `platforms.whatsapp.access_token`
- `WHATSAPP_PHONE_NUMBER_ID` → `platforms.whatsapp.phone_number_id`
- `WHATSAPP_APP_SECRET` → `platforms.whatsapp.app_secret`
- `WHATSAPP_VERIFY_TOKEN` → `platforms.whatsapp.verify_token`

#### AI 模型配置

**OpenAI 配置**
- `OPENAI_API_KEY` → `openai.api_key`
- `OPENAI_ASSISTANT_ID` → `openai.assistant_id`
- `OPENAI_BASE_URL` → `openai.base_url`
- `OPENAI_MODEL` → `openai.model`
- `OPENAI_TEMPERATURE` → `openai.temperature`
- `OPENAI_MAX_TOKENS` → `openai.max_tokens`

**Anthropic Claude 配置**
- `ANTHROPIC_API_KEY` → `anthropic.api_key`
- `ANTHROPIC_MODEL` → `anthropic.model`
- `ANTHROPIC_TEMPERATURE` → `anthropic.temperature`
- `ANTHROPIC_MAX_TOKENS` → `anthropic.max_tokens`

**Google Gemini 配置**
- `GEMINI_API_KEY` → `gemini.api_key`
- `GEMINI_MODEL` → `gemini.model`
- `GEMINI_TEMPERATURE` → `gemini.temperature`
- `GEMINI_CORPUS_NAME` → `gemini.corpus_name`
- `GEMINI_BASE_URL` → `gemini.base_url`

**Hugging Face 配置**
- `HUGGINGFACE_API_KEY` → `huggingface.api_key`
- `HUGGINGFACE_MODEL_NAME` → `huggingface.model_name`
- `HUGGINGFACE_API_TYPE` → `huggingface.api_type`
- `HUGGINGFACE_BASE_URL` → `huggingface.base_url`
- `HUGGINGFACE_TEMPERATURE` → `huggingface.temperature`
- `HUGGINGFACE_MAX_TOKENS` → `huggingface.max_tokens`
- `HUGGINGFACE_TIMEOUT` → `huggingface.timeout`

**Ollama 配置**
- `OLLAMA_BASE_URL` → `ollama.base_url`
- `OLLAMA_MODEL` → `ollama.model`
- `OLLAMA_TEMPERATURE` → `ollama.temperature`

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

#### 平台配置（至少需要一個平台）

```yaml
platforms:
  line:                    # LINE Bot (主要平台)
    enabled: true
    channel_access_token: "必須設定"
    channel_secret: "必須設定"
  
  discord:                 # Discord Bot (可選)
    enabled: false
    bot_token: "設定時必須"
  
  telegram:                # Telegram Bot (可選)
    enabled: false
    bot_token: "設定時必須"
```

#### AI 模型配置（至少需要一個模型）

```yaml
# 根據 llm.provider 設定，對應的 API key 為必須
llm:
  provider: "openai"       # 主要模型提供商

openai:                    # 當 provider 為 openai 時必須
  api_key: "必須設定"

anthropic:                 # 當 provider 為 anthropic 時必須
  api_key: "必須設定"

gemini:                    # 當 provider 為 gemini 時必須
  api_key: "必須設定"

huggingface:               # 當 provider 為 huggingface 時必須
  api_key: "必須設定"

# ollama 為本地模型，不需要 API key
```

#### 資料庫配置

```yaml
db:
  host: "必須設定"
  user: "必須設定"
  password: "必須設定"
  db_name: "必須設定"
```

---

## 🤖 AI 模型配置詳細說明

### Hugging Face 配置 (v2.1)

Hugging Face 提供了世界上最大的開源 AI 模型庫，支援多種先進的語言模型。本系統完全整合了 Hugging Face Inference API，支援聊天對話、RAG 檢索、語音轉文字和圖片生成功能。

#### 📋 完整配置範例

```yaml
huggingface:
  # 必需：Hugging Face API 金鑰
  # 從 https://huggingface.co/settings/tokens 獲取
  api_key: "${HUGGINGFACE_API_KEY}"
  
  # 主要聊天模型（2025年最佳性能模型）
  model_name: "meta-llama/Llama-4-Scout-17B-16E-Instruct"
  
  # API 類型選擇
  # - inference_api: 免費但有使用限制，適合測試
  # - serverless: 快速啟動，按使用付費
  # - dedicated: 專用端點，最快但成本較高
  api_type: "inference_api"
  
  # API 基礎 URL
  base_url: "https://api-inference.huggingface.co"
  
  # 備用模型列表（按性能排序 - 2025年更新）
  fallback_models:
    - "meta-llama/Llama-4-Maverick-17B-128E-Instruct"  # Llama 4 旗艦模型
    - "mistralai/Magistral-Small-2506"                  # Mistral 2025最新推理模型
    - "meta-llama/Llama-3.1-8B-Instruct"               # 穩定的2024旗艦
    - "mistralai/Mistral-Nemo-Instruct-2407"           # Mistral 12B 高性能
    - "mistralai/Mistral-7B-Instruct-v0.3"             # 輕量級備選
    - "meta-llama/Llama-3.2-3B-Instruct"               # 快速響應備選
  
  # 功能專用模型（2024年最佳）
  embedding_model: "sentence-transformers/all-MiniLM-L6-v2"  # 文本嵌入
  speech_model: "openai/whisper-large-v3"                     # 語音轉文字
  image_model: "stabilityai/stable-diffusion-xl-base-1.0"     # 圖片生成
  
  # 生成參數（針對 Llama 優化）
  temperature: 0.7        # 創造性控制 (0.0-1.0)
  max_tokens: 1024        # 最大回應長度
  timeout: 90             # 請求超時時間（秒）
```

#### 🌍 環境變數設定

```bash
# 基本配置
export HUGGINGFACE_API_KEY="hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export HUGGINGFACE_MODEL_NAME="meta-llama/Llama-4-Scout-17B-16E-Instruct"
export HUGGINGFACE_API_TYPE="inference_api"
export HUGGINGFACE_TEMPERATURE="0.7"
export HUGGINGFACE_MAX_TOKENS="1024"
export HUGGINGFACE_TIMEOUT="90"

# 進階配置
export HUGGINGFACE_BASE_URL="https://api-inference.huggingface.co"
```

#### 🎯 推薦模型配置

**2025年最佳聊天模型（非中國）：**

🚀 **meta-llama/Llama-4-Scout-17B-16E-Instruct** (主要推薦)
- Meta 2025年最新 Llama 4 系列，17B 活躍參數，16個專家
- 原生多模態支援，世界領先的10M上下文長度
- 在同級別中性能最優，超越 Gemma 3、Gemini 2.0 Flash-Lite
- 支援多語言，包括中文、英文、法文、德文、日文、韓文等

🎯 **meta-llama/Llama-4-Maverick-17B-128E-Instruct** (旗艦模型)
- Meta 2025年最強模型，17B 活躍參數，128個專家
- 性能超越 GPT-4o 和 Gemini 2.0 Flash
- 與 DeepSeek v3 相當但參數效率更高
- 適合需要最高性能的任務

🔬 **mistralai/Magistral-Small-2506** (Mistral 2025)
- Mistral 2025年最新推理模型，24B參數
- 可在單張 RTX 4090 或 32GB RAM MacBook 上運行
- 支援長推理鏈，多語言支援優秀
- Apache 2.0 開源授權

🥇 **meta-llama/Llama-3.1-8B-Instruct** (穩定首選)
- Meta 2024年旗艦 8B 模型，性能卓越穩定
- 在 LMSYS 排行榜排名第5位
- 支援128K上下文，多語言支援優秀
- 在指令跟隨、推理、程式碼生成方面表現優異

#### 💡 使用情境配置

**開發環境配置**
```yaml
huggingface:
  api_key: "${HUGGINGFACE_API_KEY}"
  model_name: "meta-llama/Llama-3.1-8B-Instruct"  # 較小模型，快速響應
  api_type: "inference_api"  # 免費 API
  temperature: 0.7
  max_tokens: 512
  timeout: 60
```

**生產環境配置**
```yaml
huggingface:
  api_key: "${HUGGINGFACE_API_KEY}"
  model_name: "meta-llama/Llama-4-Scout-17B-16E-Instruct"  # 最佳性能
  api_type: "serverless"  # 付費 API，更穩定
  temperature: 0.7
  max_tokens: 1024
  timeout: 90
  fallback_models:
    - "meta-llama/Llama-4-Maverick-17B-128E-Instruct"
    - "meta-llama/Llama-3.1-8B-Instruct"
```

**高性能配置**
```yaml
huggingface:
  api_key: "${HUGGINGFACE_API_KEY}"
  model_name: "meta-llama/Llama-4-Maverick-17B-128E-Instruct"  # 最強模型
  api_type: "dedicated"  # 專用端點，最快
  temperature: 0.8  # 稍高創造性
  max_tokens: 2048  # 較長回應
  timeout: 120
```

#### ⚠️ 注意事項

1. **免費 Inference API** 有速率限制，推薦用於測試
2. **生產環境**建議使用 Serverless 或 Dedicated 端點
3. **某些模型**可能需要較長時間載入（冷啟動）
4. **大型模型**可能需要更高的 timeout 設定
5. **語音和圖片功能**需要對應的模型支援
6. **備用模型**會在主模型不可用時自動切換

#### 🔧 故障排除

**常見問題**：

1. **模型載入中**
   ```
   HTTP 503: Model is loading
   ```
   **解決方法**: 等待幾分鐘或切換到已預熱的模型

2. **API 配額耗盡**
   ```
   HTTP 429: Rate limit exceeded
   ```
   **解決方法**: 升級到付費 API 或等待配額重置

3. **模型不存在**
   ```
   HTTP 404: Model not found
   ```
   **解決方法**: 檢查模型名稱拼寫或選擇其他模型

**測試配置**：
```bash
# 測試 HuggingFace 連接
python -c "
from src.models.huggingface_model import HuggingFaceModel
from src.models.base import ChatMessage

model = HuggingFaceModel(api_key='your_api_key')
success, error = model.check_connection()
print(f'連接狀態: {\"成功\" if success else \"失敗\"}, 錯誤: {error}')
"
```

### OpenAI 配置

OpenAI 提供 GPT 系列模型，包括最新的 GPT-4 和 GPT-3.5-turbo，具備優秀的聊天能力和 Assistant API 功能。

#### 📋 完整配置範例

```yaml
openai:
  # 必需：OpenAI API 金鑰
  api_key: "${OPENAI_API_KEY}"
  
  # 可選：Assistant ID（使用 Assistant API 時）
  assistant_id: "${OPENAI_ASSISTANT_ID}"
  
  # 可選設定
  base_url: "https://api.openai.com/v1"  # API 基礎 URL
  model: "gpt-4"                         # 預設模型
  temperature: 0.1                       # 生成溫度
  max_tokens: 4000                       # 最大 token 數
```

#### 🌍 環境變數設定

```bash
export OPENAI_API_KEY="sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export OPENAI_ASSISTANT_ID="asst_xxxxxxxxxxxxxxxxxxxxxxxx"
export OPENAI_BASE_URL="https://api.openai.com/v1"
export OPENAI_MODEL="gpt-4"
export OPENAI_TEMPERATURE="0.1"
export OPENAI_MAX_TOKENS="4000"
```

### Anthropic Claude 配置

Anthropic Claude 提供高品質的對話體驗，特別擅長安全和有用的回應。

#### 📋 完整配置範例

```yaml
anthropic:
  # 必需：Anthropic API 金鑰
  api_key: "${ANTHROPIC_API_KEY}"
  
  # 模型選擇
  model: "claude-3-5-sonnet-20240620"    # 推薦使用最新版本
  
  # 生成參數
  max_tokens: 4000                       # 最大回應長度
  temperature: 0.1                       # 生成溫度
```

#### 🌍 環境變數設定

```bash
export ANTHROPIC_API_KEY="sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export ANTHROPIC_MODEL="claude-3-5-sonnet-20240620"
export ANTHROPIC_TEMPERATURE="0.1"
export ANTHROPIC_MAX_TOKENS="4000"
```

### Google Gemini 配置

Google Gemini 提供強大的多模態能力和 Semantic Retrieval API，支援長上下文和檔案上傳。

#### 📋 完整配置範例

```yaml
gemini:
  # 必需：Google Gemini API 金鑰
  api_key: "${GEMINI_API_KEY}"
  
  # 模型選擇
  model: "gemini-1.5-pro-latest"         # 最新 Gemini 模型
  
  # 生成參數
  temperature: 0.1                       # 生成溫度
  
  # Semantic Retrieval 設定
  corpus_name: "chatbot-knowledge"       # 知識庫名稱
  
  # API 設定
  base_url: "https://generativelanguage.googleapis.com"
```

#### 🌍 環境變數設定

```bash
export GEMINI_API_KEY="AIzaSyxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export GEMINI_MODEL="gemini-1.5-pro-latest"
export GEMINI_TEMPERATURE="0.1"
export GEMINI_CORPUS_NAME="chatbot-knowledge"
export GEMINI_BASE_URL="https://generativelanguage.googleapis.com"
```

### Ollama 本地模型配置

Ollama 提供完全本地運行的開源模型，無需 API 金鑰，適合隱私要求高的環境。

#### 📋 完整配置範例

```yaml
ollama:
  # Ollama 服務地址
  base_url: "http://localhost:11434"     # 本地 Ollama 服務
  
  # 模型選擇
  model: "llama3.1:8b"                   # 推薦使用 Llama 3.1
  
  # 生成參數
  temperature: 0.1                       # 生成溫度
```

#### 🌍 環境變數設定

```bash
export OLLAMA_BASE_URL="http://localhost:11434"
export OLLAMA_MODEL="llama3.1:8b"
export OLLAMA_TEMPERATURE="0.1"
```

#### 🔧 Ollama 安裝和設定

1. **安裝 Ollama**：
   ```bash
   # macOS
   brew install ollama
   
   # Linux
   curl -fsSL https://ollama.ai/install.sh | sh
   
   # Windows
   # 下載並安裝：https://ollama.ai/download/windows
   ```

2. **下載和運行模型**：
   ```bash
   # 下載 Llama 3.1 8B 模型
   ollama pull llama3.1:8b
   
   # 啟動 Ollama 服務
   ollama serve
   
   # 測試模型
   ollama run llama3.1:8b "Hello, how are you?"
   ```

---

## 🖥️ 平台配置詳細說明

### LINE Bot 配置

LINE Bot 是主要支援的平台，提供完整的聊天機器人功能。

#### 📋 完整配置範例

```yaml
platforms:
  line:
    enabled: true                        # 啟用 LINE 平台
    channel_access_token: "${LINE_CHANNEL_ACCESS_TOKEN}"
    channel_secret: "${LINE_CHANNEL_SECRET}"
```

#### 🌍 環境變數設定

```bash
export LINE_CHANNEL_ACCESS_TOKEN="your_line_channel_access_token"
export LINE_CHANNEL_SECRET="your_line_channel_secret"
```

#### 🔧 LINE Bot 設定步驟

1. **建立 LINE Bot**：
   - 前往 [LINE Developers Console](https://developers.line.biz/)
   - 建立新的 Provider 和 Channel
   - 選擇 "Messaging API" 類型

2. **取得憑證**：
   - **Channel Access Token**：在 "Messaging API" 頁面產生長期存取權杖
   - **Channel Secret**：在 "Basic settings" 頁面找到

3. **設定 Webhook**：
   - 在 "Messaging API" 頁面設定 Webhook URL
   - 格式：`https://your-domain.com/webhooks/line`
   - 啟用 "Use webhook" 選項

### Discord Bot 配置

Discord Bot 支援群組聊天和指令功能。

#### 📋 完整配置範例

```yaml
platforms:
  discord:
    enabled: true                        # 啟用 Discord 平台
    bot_token: "${DISCORD_BOT_TOKEN}"    # Bot 權杖
    guild_id: "${DISCORD_GUILD_ID}"      # 可選：特定伺服器 ID
    command_prefix: "!"                  # 可選：指令前綴
```

#### 🌍 環境變數設定

```bash
export DISCORD_BOT_TOKEN="your_discord_bot_token"
export DISCORD_GUILD_ID="your_discord_guild_id"  # 可選
export DISCORD_COMMAND_PREFIX="!"                # 可選
```

#### 🔧 Discord Bot 設定步驟

1. **建立 Discord 應用程式**：
   - 前往 [Discord Developer Portal](https://discord.com/developers/applications)
   - 點擊 "New Application" 建立新應用程式
   - 在 "Bot" 頁面建立 Bot

2. **取得 Bot Token**：
   - 在 "Bot" 頁面點擊 "Reset Token" 產生新權杖
   - 複製權杖作為 `DISCORD_BOT_TOKEN`

3. **設定權限**：
   - 在 "Bot" 頁面啟用必要的 Privileged Gateway Intents
   - 在 "OAuth2" > "URL Generator" 選擇適當的權限
   - 使用產生的 URL 邀請 Bot 到伺服器

4. **取得 Guild ID**（可選）：
   - 在 Discord 中啟用開發者模式
   - 右鍵點擊伺服器名稱，選擇 "Copy Server ID"

### Telegram Bot 配置

Telegram Bot 提供豐富的互動功能和檔案傳輸支援。

#### 📋 完整配置範例

```yaml
platforms:
  telegram:
    enabled: true                        # 啟用 Telegram 平台
    bot_token: "${TELEGRAM_BOT_TOKEN}"   # Bot 權杖
    webhook_secret: "${TELEGRAM_WEBHOOK_SECRET}"  # 可選：Webhook 驗證密鑰
```

#### 🌍 環境變數設定

```bash
export TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
export TELEGRAM_WEBHOOK_SECRET="your_webhook_secret"  # 可選
```

#### 🔧 Telegram Bot 設定步驟

1. **建立 Telegram Bot**：
   - 在 Telegram 中找到 [@BotFather](https://t.me/botfather)
   - 發送 `/newbot` 指令
   - 按照指示設定 Bot 名稱和用戶名

2. **取得 Bot Token**：
   - BotFather 會提供 Bot Token
   - 格式類似：`123456789:ABCdefGHIjklMNOpqrsTUVwxyz`

3. **設定 Webhook**（可選）：
   - 如果需要 Webhook 驗證，設定 `webhook_secret`
   - 系統會自動設定 Webhook URL

4. **測試 Bot**：
   - 在 Telegram 中搜尋你的 Bot
   - 發送 `/start` 測試連接

### Slack Bot 配置

Slack Bot 提供企業級聊天機器人功能。

#### 📋 完整配置範例

```yaml
platforms:
  slack:
    enabled: true                        # 啟用 Slack 平台
    bot_token: "${SLACK_BOT_TOKEN}"      # Bot 權杖
    signing_secret: "${SLACK_SIGNING_SECRET}"  # 簽名密鑰
    app_token: "${SLACK_APP_TOKEN}"      # 可選：Socket Mode 應用程式權杖
```

#### 🌍 環境變數設定

```bash
export SLACK_BOT_TOKEN="xoxb-your-slack-bot-token"
export SLACK_SIGNING_SECRET="your_slack_signing_secret"
export SLACK_APP_TOKEN="xapp-your-slack-app-token"  # 可選
```

#### 🔧 Slack Bot 設定步驟

1. **建立 Slack 應用程式**：
   - 前往 [Slack API](https://api.slack.com/apps)
   - 點擊 "Create New App"
   - 選擇 "From scratch" 並設定應用程式名稱和工作區

2. **設定 Bot Token**：
   - 在 "OAuth & Permissions" 頁面新增 Bot Token Scopes
   - 安裝應用程式到工作區
   - 複製 "Bot User OAuth Token"

3. **取得 Signing Secret**：
   - 在 "Basic Information" 頁面找到 "Signing Secret"

4. **設定事件訂閱**：
   - 在 "Event Subscriptions" 頁面啟用事件
   - 設定 Request URL：`https://your-domain.com/webhooks/slack`

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

### 平台配置

| 用途 | config.yml 路徑 | 環境變數 | 部署腳本變數 |
|------|----------------|----------|-------------|
| LINE Access Token | `platforms.line.channel_access_token` | `LINE_CHANNEL_ACCESS_TOKEN` | `LINE_CHANNEL_ACCESS_TOKEN` |
| LINE Secret | `platforms.line.channel_secret` | `LINE_CHANNEL_SECRET` | `LINE_CHANNEL_SECRET` |
| Discord Bot Token | `platforms.discord.bot_token` | `DISCORD_BOT_TOKEN` | `DISCORD_BOT_TOKEN` |
| Discord Guild ID | `platforms.discord.guild_id` | `DISCORD_GUILD_ID` | `DISCORD_GUILD_ID` |
| Discord Command Prefix | `platforms.discord.command_prefix` | `DISCORD_COMMAND_PREFIX` | `DISCORD_COMMAND_PREFIX` |
| Telegram Bot Token | `platforms.telegram.bot_token` | `TELEGRAM_BOT_TOKEN` | `TELEGRAM_BOT_TOKEN` |
| Telegram Webhook Secret | `platforms.telegram.webhook_secret` | `TELEGRAM_WEBHOOK_SECRET` | `TELEGRAM_WEBHOOK_SECRET` |
| Slack Bot Token | `platforms.slack.bot_token` | `SLACK_BOT_TOKEN` | `SLACK_BOT_TOKEN` |
| Slack Signing Secret | `platforms.slack.signing_secret` | `SLACK_SIGNING_SECRET` | `SLACK_SIGNING_SECRET` |
| Slack App Token | `platforms.slack.app_token` | `SLACK_APP_TOKEN` | `SLACK_APP_TOKEN` |

### AI 模型配置

| 用途 | config.yml 路徑 | 環境變數 | 部署腳本變數 |
|------|----------------|----------|-------------|
| OpenAI API Key | `openai.api_key` | `OPENAI_API_KEY` | `OPENAI_API_KEY` |
| OpenAI Assistant ID | `openai.assistant_id` | `OPENAI_ASSISTANT_ID` | `OPENAI_ASSISTANT_ID` |
| OpenAI Model | `openai.model` | `OPENAI_MODEL` | `OPENAI_MODEL` |
| OpenAI Base URL | `openai.base_url` | `OPENAI_BASE_URL` | `OPENAI_BASE_URL` |
| OpenAI Temperature | `openai.temperature` | `OPENAI_TEMPERATURE` | `OPENAI_TEMPERATURE` |
| OpenAI Max Tokens | `openai.max_tokens` | `OPENAI_MAX_TOKENS` | `OPENAI_MAX_TOKENS` |
| Anthropic API Key | `anthropic.api_key` | `ANTHROPIC_API_KEY` | `ANTHROPIC_API_KEY` |
| Anthropic Model | `anthropic.model` | `ANTHROPIC_MODEL` | `ANTHROPIC_MODEL` |
| Anthropic Temperature | `anthropic.temperature` | `ANTHROPIC_TEMPERATURE` | `ANTHROPIC_TEMPERATURE` |
| Anthropic Max Tokens | `anthropic.max_tokens` | `ANTHROPIC_MAX_TOKENS` | `ANTHROPIC_MAX_TOKENS` |
| Gemini API Key | `gemini.api_key` | `GEMINI_API_KEY` | `GEMINI_API_KEY` |
| Gemini Model | `gemini.model` | `GEMINI_MODEL` | `GEMINI_MODEL` |
| Gemini Temperature | `gemini.temperature` | `GEMINI_TEMPERATURE` | `GEMINI_TEMPERATURE` |
| Gemini Corpus Name | `gemini.corpus_name` | `GEMINI_CORPUS_NAME` | `GEMINI_CORPUS_NAME` |
| Gemini Base URL | `gemini.base_url` | `GEMINI_BASE_URL` | `GEMINI_BASE_URL` |
| HuggingFace API Key | `huggingface.api_key` | `HUGGINGFACE_API_KEY` | `HUGGINGFACE_API_KEY` |
| HuggingFace Model Name | `huggingface.model_name` | `HUGGINGFACE_MODEL_NAME` | `HUGGINGFACE_MODEL_NAME` |
| HuggingFace API Type | `huggingface.api_type` | `HUGGINGFACE_API_TYPE` | `HUGGINGFACE_API_TYPE` |
| HuggingFace Base URL | `huggingface.base_url` | `HUGGINGFACE_BASE_URL` | `HUGGINGFACE_BASE_URL` |
| HuggingFace Temperature | `huggingface.temperature` | `HUGGINGFACE_TEMPERATURE` | `HUGGINGFACE_TEMPERATURE` |
| HuggingFace Max Tokens | `huggingface.max_tokens` | `HUGGINGFACE_MAX_TOKENS` | `HUGGINGFACE_MAX_TOKENS` |
| HuggingFace Timeout | `huggingface.timeout` | `HUGGINGFACE_TIMEOUT` | `HUGGINGFACE_TIMEOUT` |
| Ollama Base URL | `ollama.base_url` | `OLLAMA_BASE_URL` | `OLLAMA_BASE_URL` |
| Ollama Model | `ollama.model` | `OLLAMA_MODEL` | `OLLAMA_MODEL` |
| Ollama Temperature | `ollama.temperature` | `OLLAMA_TEMPERATURE` | `OLLAMA_TEMPERATURE` |

### 資料庫配置

| 用途 | config.yml 路徑 | 環境變數 | 部署腳本變數 |
|------|----------------|----------|-------------|
| 資料庫主機 | `db.host` | `DB_HOST` | `DB_HOST` |
| 資料庫埠號 | `db.port` | `DB_PORT` | `DB_PORT` |
| 資料庫用戶 | `db.user` | `DB_USER` | `DB_USER` |
| 資料庫密碼 | `db.password` | `DB_PASSWORD` | `DB_PASSWORD` |
| 資料庫名稱 | `db.db_name` | `DB_NAME` | `DB_NAME` |
| SSL 模式 | `db.sslmode` | `DB_SSLMODE` | `DB_SSLMODE` |
| SSL 根憑證 | `db.sslrootcert` | `DB_SSLROOTCERT` | `DB_SSLROOTCERT` |
| SSL 用戶端憑證 | `db.sslcert` | `DB_SSLCERT` | `DB_SSLCERT` |
| SSL 私鑰 | `db.sslkey` | `DB_SSLKEY` | `DB_SSLKEY` |

---

## 配置範例

### 💻 本地開發配置

**方法 1: 使用 config.yml**
```yaml
# config/config.yml
platforms:
  line:
    enabled: true
    channel_access_token: "your_line_token"
    channel_secret: "your_line_secret"
  
  whatsapp:
    enabled: true
    access_token: "your_whatsapp_token"
    phone_number_id: "your_phone_number_id"
    app_secret: "your_app_secret"
    verify_token: "your_verify_token"
    api_version: "v13.0"

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
export WHATSAPP_ACCESS_TOKEN="your_whatsapp_token"
export WHATSAPP_PHONE_NUMBER_ID="your_phone_number_id"
export WHATSAPP_APP_SECRET="your_app_secret"
export WHATSAPP_VERIFY_TOKEN="your_verify_token"
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