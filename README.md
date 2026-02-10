# 多平台聊天機器人 ChatGPT Line Bot

中文 | [English](README.en.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Test Coverage](https://img.shields.io/badge/coverage-86%25-brightgreen.svg)](htmlcov/index.html)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)](https://github.com/tnsprout/ChatGPT-Line-Bot/actions)

本專案是一個**多平台聊天機器人**，支援 LINE、Discord、Telegram、WhatsApp、Messenger 等多個平台，整合了多種 AI 模型提供商（OpenAI、Anthropic Claude、Google Gemini、Ollama）。機器人採用模組化架構設計，部署在 Google Cloud Run 上，並使用 Google Cloud SQL 進行對話歷史管理。

**🆕 v2.1 核心基礎設施整合升級**：高效能日誌系統與安全模組整合，優化效能並簡化維護。

> 本專案 Fork 自 [ExplainThis 的 ChatGPT-Line-Bot](https://github.com/TheExplainthis/ChatGPT-Line-Bot)

## 核心特色

🤖 **多 AI 模型支援**: 統一介面整合 OpenAI、Anthropic、Gemini、Ollama  
🌐 **多平台支援**: LINE、Discord、Telegram、WhatsApp、Messenger 等平台統一管理  
📚 **RAG 知識庫**: 所有模型支援文檔檢索與引用功能  
🔗 **統一引用處理**: 跨模型的一致引用格式化  
🛡️ **企業級安全**: 輸入驗證、速率限制、錯誤處理  
📊 **監控與日志**: 完整的系統監控和性能指標  
🔌 **MCP 整合**: 支援 Model Context Protocol 外部工具調用

## 快速開始

### 必要準備
- Python 3.8+ 開發環境
- Google Cloud Platform 帳號
- 至少一個 AI 模型提供商的 API 金鑰
- 至少一個聊天平台的配置

### 三步驟部署

```bash
# 1. 下載並安裝依賴
git clone https://github.com/tnsprout/ChatGPT-Line-Bot.git
cd ChatGPT-Line-Bot
pip install -r requirements.txt

# 2. 快速配置
cp config/config.yml.example config/config.yml
# 編輯 config.yml，填入您的 API 金鑰

# 3. 設定 Prompt
cp config/prompts.yml.default config/prompts.yml
# 編輯 prompts.yml，自訂 system prompt 內容

# 4. 本地開發
python main.py
```

## 配置設定

### 基本配置文件 (`config/config.yml`)

```yaml
# AI 模型配置
llm:
  provider: "openai"  # openai, anthropic, gemini, ollama

# OpenAI 配置
openai:
  api_key: "${OPENAI_API_KEY}"
  assistant_id: "${OPENAI_ASSISTANT_ID}"

# LINE 平台配置
platforms:
  line:
    enabled: true
    channel_access_token: "${LINE_CHANNEL_ACCESS_TOKEN}"
    channel_secret: "${LINE_CHANNEL_SECRET}"

# 資料庫配置
db:
  host: "${DB_HOST}"
  port: ${DB_PORT}
  db_name: "${DB_NAME}"
  user: "${DB_USER}"
  password: "${DB_PASSWORD}"

# MCP (Model Context Protocol) 配置
mcp:
  enabled: true
  config_dir: "config/mcp"
  system_prompt: |
    您是一個具備外部工具調用能力的 AI 助理...

# 功能開關
features:
  enable_mcp: true  # 啟用 MCP 功能
  audio_transcription: true
  rag_search: true
```

### 環境變數設定

```bash
# 核心設定
export FLASK_ENV=production
export LLM_PROVIDER=openai

# AI 模型 API 金鑰
export OPENAI_API_KEY=sk-proj-xxxxxxxx
export ANTHROPIC_API_KEY=sk-ant-xxxxxxxx
export GEMINI_API_KEY=AIza-xxxxxxxx

# LINE 平台
export LINE_CHANNEL_ACCESS_TOKEN=your_token
export LINE_CHANNEL_SECRET=your_secret

# 資料庫
export DB_HOST=your-db-host
export DB_NAME=your_db_name
export DB_USER=your_db_user
export DB_PASSWORD=your_db_password
```

## 系統架構

```
src/
├── core/              # 核心基礎設施
│   ├── config.py      # 配置管理
│   ├── logger.py      # 日誌系統
│   ├── security.py    # 安全模組
│   └── memory_monitor.py  # 記憶體監控
├── services/          # 業務邏輯層
│   ├── chat.py        # 聊天服務
│   ├── audio.py       # 音訊處理
│   ├── conversation.py # 對話管理
│   └── response.py    # 回應格式化
├── models/            # AI 模型整合
│   ├── openai_model.py    # OpenAI 整合
│   ├── anthropic_model.py # Anthropic 整合
│   ├── gemini_model.py    # Gemini 整合
│   └── ollama_model.py    # Ollama 整合
├── platforms/         # 平台支援
│   ├── base.py        # 平台抽象介面
│   ├── factory.py     # 平台工廠
│   └── line_handler.py # LINE 平台處理器
└── database/          # 資料庫層
    ├── connection.py  # 資料庫連接
    ├── models.py      # 資料模型
    └── operations.py  # 資料庫操作
```

## 部署

### Google Cloud Run 部署

```bash
# 構建並推送到 Google Container Registry
gcloud builds submit --tag gcr.io/{project-id}/{image-name}

# 部署到 Cloud Run
gcloud run deploy {service-name} \
  --image gcr.io/{project-id}/{image-name} \
  --platform managed \
  --port 8080 \
  --memory 2G \
  --region {region} \
  --set-env-vars FLASK_ENV=production

# 健康檢查
curl https://{service-url}/health
```

### 資料庫設定

```bash
# 自動設定資料庫（推薦）
python scripts/db_migration.py auto-setup

# 或使用傳統方式
python scripts/setup_database.py setup
```

## 開發與測試

### 本地開發

```bash
# 開發模式
python main.py  # 自動檢測開發環境

# 生產模式測試
FLASK_ENV=production python main.py
```

### 運行測試

```bash
# 執行所有測試
python -m pytest

# 執行測試並生成覆蓋率報告
python -m pytest --cov=src --cov-report=html

# 執行特定測試
python -m pytest tests/unit/
python -m pytest tests/integration/
```

## API 端點

### 核心端點
- `GET /`: 應用程式資訊
- `GET /health`: 系統健康檢查
- `GET /metrics`: 應用程式指標

### 平台 Webhook
- `POST /webhooks/line`: LINE 平台 webhook
- `POST /webhooks/discord`: Discord 平台 webhook
- `POST /webhooks/telegram`: Telegram 平台 webhook
- `POST /webhooks/instagram`: Instagram 平台 webhook
- `POST /webhooks/slack`: Slack 平台 webhook

### Web 介面
- `GET /login`: 登入頁面
- `GET /chat`: 聊天介面（需要認證）
- `POST /ask`: 聊天 API（需要認證）

## 🔌 MCP (Model Context Protocol) 整合

本專案支援 MCP 協議，讓 AI 模型能夠調用外部工具和服務，提供更豐富的功能。

### MCP 功能特色

- **統一工具調用**: 透過標準化協議調用外部 API 和服務
- **多模型支援**: OpenAI、Anthropic、Gemini 三大模型都支援 MCP
- **安全設計**: 遵循 MCP 安全最佳實踐，包含用戶同意機制
- **彈性配置**: 可選式啟用，不影響現有功能

### 快速設定 MCP

1. **啟用 MCP 功能**
```yaml
# config/config.yml
features:
  enable_mcp: true

mcp:
  enabled: true
  config_dir: "config/mcp"
```

2. **建立 MCP 設定檔案**
```bash
# 參考範例檔案
cp config/mcp/example.json.example config/mcp/my_tools.json
# 編輯 my_tools.json，設定您的 MCP Server 和工具
```

3. **MCP 設定檔案格式**
```json
{
  "mcp_server": {
    "base_url": "http://localhost:3000/api/mcp",
    "timeout": 30
  },
  "functions": [
    {
      "name": "search_data",
      "description": "搜尋資料",
      "mcp_tool": "search_tool",
      "enabled": true,
      "parameters": {
        "type": "object",
        "properties": {
          "query": {"type": "string", "description": "搜尋關鍵字"}
        }
      }
    }
  ]
}
```

### MCP 工作流程

1. **用戶輸入**: 用戶發送訊息給 AI 模型
2. **模型判斷**: AI 模型判斷是否需要調用外部工具
3. **工具調用**: 系統透過 MCP Client 向 MCP Server 請求工具執行
4. **結果整合**: 將工具執行結果回傳給 AI 模型
5. **最終回應**: AI 模型基於工具結果生成最終回應給用戶

### 支援的 MCP 模式

- **OpenAI Assistant API**: 透過 function calling 機制
- **Anthropic Messages API**: 透過 JSON 格式的 function call
- **Gemini API**: 透過 function_declarations 和 functionCall

## 📚 詳細文檔

更詳細的配置和部署指南，請參考：

### 設定與部署
- [📋 配置管理指南](docs/CONFIGURATION.md) - 完整的配置設定說明
- [🚀 運行指南](docs/RUNNING.md) - 本地開發與生產環境運行
- [☁️ 部署指南](docs/DEPLOYMENT.md) - Google Cloud Run 部署完整流程
- [🔒 安全性指南](docs/SECURITY.md) - 安全配置與最佳實踐

### 功能與架構
- [📖 RAG 實作說明](docs/RAG_IMPLEMENTATION.md) - 檢索增強生成功能詳解
- [🗄️ 資料庫管理](docs/ORM_GUIDE.md) - SQLAlchemy ORM 與遷移管理
- [👨‍💻 開發者指南](CLAUDE.md) - 專案架構與開發規範

## ❓ 常見問題

### Q: 部署後 Bot 沒有回應？
1. 檢查 Webhook URL 設定是否正確
2. 確認環境變數是否正確設定
3. 查看 Cloud Run 日誌排除問題

### Q: AI 模型回應錯誤？
1. 確認 API 金鑰是否有效
2. 檢查模型配置是否正確
3. 查看應用程式日誌瞭解詳細錯誤

### Q: 資料庫連接失敗？
1. 確認資料庫連接參數
2. 檢查 SSL 憑證配置
3. 驗證防火牆規則

## 🤝 貢獻指南

歡迎貢獻！請遵循以下步驟：

1. Fork 本專案並創建功能分支
2. 進行您的更改並編寫測試
3. 確保程式碼通過所有測試
4. 提交 Pull Request

## 📄 授權

本專案採用 MIT 授權條款 - 詳細資訊請參考 [LICENSE](LICENSE) 文件。

## 🆘 支援

如果您遇到問題或需要協助，請：

1. 查看上述 [詳細文檔](#-詳細文檔) 瞭解配置和部署
2. 在 [GitHub Issues](https://github.com/tnsprout/ChatGPT-Line-Bot/issues) 提交問題
3. 查看 [開發者指南](CLAUDE.md) 瞭解更多技術細節