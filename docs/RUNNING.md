# 🚀 ChatGPT Line Bot 運行指南

本指南介紹如何在不同環境中運行 ChatGPT Line Bot，確保使用正確的服務器配置。

## 🌟 支援的平台和 AI 模型

### 📱 支援的聊天平台
- **LINE Bot** - 主要支援平台，完整功能
- **Discord Bot** - 群組聊天和指令功能
- **Telegram Bot** - 豐富互動和檔案傳輸
- **Slack Bot** - 企業級聊天機器人
- **WhatsApp Bot** - 企業級客服，支援媒體訊息

### 🤖 支援的 AI 模型
- **OpenAI GPT** - GPT-4 系列，Assistant API
- **Anthropic Claude** - Claude 3.5 Sonnet，安全對話
- **Google Gemini** - Gemini 1.5 Pro，多模態能力
- **Hugging Face** - 開源模型，包含 Llama 4、Mistral 等
- **Ollama** - 本地部署，完全私有

詳細配置請參考：[配置指南](CONFIGURATION.md)

## 🌟 WhatsApp 平台功能

### 📱 WhatsApp Business Cloud API
WhatsApp 平台使用 Meta 官方的 WhatsApp Business Cloud API，提供企業級的即時通訊服務。

#### 支援功能
- ✅ **文字訊息**: 完整的文字內容接收和發送
- ✅ **音訊訊息**: 自動下載和轉錄為文字
- ✅ **圖片訊息**: 自動下載圖片檔案
- ✅ **文件訊息**: 支援 PDF、DOC、XLSX 等格式
- ✅ **位置訊息**: 經緯度座標和地址資訊
- ✅ **聯絡人訊息**: 聯絡人卡片資訊
- ✅ **簽名驗證**: HMAC-SHA256 webhook 安全驗證

#### 技術特色
- **官方 API**: 使用 Meta 官方 WhatsApp Business Cloud API
- **統一介面**: 與其他平台使用相同的聊天服務
- **媒體處理**: 自動媒體檔案下載和處理
- **安全性**: 完整的簽名驗證和錯誤處理

#### 申請要求
- Meta Business Account 驗證
- WhatsApp Business API 審核（1-4週）
- 商業證明文件
- 電話號碼驗證

#### 限制說明
- **24小時窗口**: 只能回覆用戶主動發送的訊息
- **模板訊息**: 營銷訊息需要使用預先審核的模板
- **費用計算**: 依據訊息量和地區計費
- **群組限制**: 不支援群組訊息發送

### 🔧 WhatsApp 設定
```yaml
platforms:
  whatsapp:
    enabled: true
    access_token: "${WHATSAPP_ACCESS_TOKEN}"
    phone_number_id: "${WHATSAPP_PHONE_NUMBER_ID}"
    app_secret: "${WHATSAPP_APP_SECRET}"
    verify_token: "${WHATSAPP_VERIFY_TOKEN}"
    api_version: "v13.0"
```

### 📞 Webhook 設定
- **Webhook URL**: `https://your-domain.com/webhooks/whatsapp`
- **驗證方式**: GET 請求與 verify_token 驗證
- **接收方式**: POST 請求包含訊息資料
- **簽名驗證**: 使用 App Secret 進行 HMAC-SHA256 驗證

### 🧪 測試命令
```bash
# 執行 WhatsApp 測試
python -m pytest tests/unit/platforms/test_whatsapp_handler.py -v

# 檢查平台狀態
curl http://your-domain.com/health | jq '.checks.platforms'

# 測試 webhook 驗證
curl -X GET "https://your-domain.com/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=your_verify_token&hub.challenge=test"
```

## 📁 項目結構

```
ChatGPT-Line-Bot/
├── main.py                 # 統一入口點（v2.0）- 自動環境偵測
├── gunicorn.conf.py        # Gunicorn 配置文件
├── .env.local.example      # 本地開發環境變量模板
├── scripts/                # 啟動腳本
│   ├── dev.sh             # 開發環境啟動腳本
│   ├── prod.sh            # 生產環境啟動腳本
│   ├── test-prod.sh       # 本地生產測試腳本
│   └── deploy/            # 雲端部署腳本
│       ├── deploy-to-cloudrun.sh
│       ├── monitoring-setup.sh
│       └── setup-loadbalancer.sh
├── config/                 # 配置文件
│   ├── config.yml.example # 應用配置模板
│   └── deploy/            # 雲端部署配置
│       ├── .env.example   # 雲端部署環境變量模板
│       ├── Dockerfile.cloudrun
│       └── cloudrun-service.yaml
└── docs/                   # 文檔
    ├── RUNNING.md         # 運行指南（本文件）
    ├── DEPLOYMENT.md      # 部署指南
    └── ...
```

## 🔧 環境配置

### 本地開發環境

```bash
# 1. 複製環境變量模板
cp .env.local.example .env.local

# 2. 編輯配置文件
vim .env.local
```

### 雲端部署環境

```bash
# 1. 複製部署環境變量模板
cp config/deploy/.env.example config/deploy/.env

# 2. 編輯部署配置文件
vim config/deploy/.env
```

## 🎯 運行方式

### 1. 開發環境（Flask 開發服務器）

**使用腳本（推薦）:**
```bash
./scripts/dev.sh
```

**統一啟動方式 (v2.0):**
```bash
# 自動偵測為開發環境
python main.py

# 或明確指定開發環境
FLASK_ENV=development python main.py
```

**特點:**
- ✅ 自動重載代碼變更
- ✅ 詳細錯誤訊息
- ✅ 調試模式
- ⚠️ 僅適用於開發環境
- ❌ 不適合生產環境

### 2. 本地生產測試

**使用腳本（推薦）:**
```bash
./scripts/test-prod.sh
```

**統一啟動方式 (v2.0):**
```bash
# 自動啟動 Gunicorn 輕量級配置
FLASK_ENV=production python main.py

# 向後兼容方式
gunicorn -c gunicorn.conf.py main:application
```

**特點:**
- ✅ 使用 Gunicorn WSGI 服務器
- ✅ 生產級配置但較輕量
- ✅ 適合本地測試生產配置
- ✅ 單個 worker 節省資源

### 3. 生產環境

**使用腳本:**
```bash
./scripts/prod.sh
```

**統一啟動方式 (v2.0):**
```bash
# 自動啟動 Gunicorn 完整配置
FLASK_ENV=production python main.py

# 向後兼容方式
gunicorn -c gunicorn.conf.py main:application
```

**Docker 運行:**
```bash
docker build -t chatgpt-line-bot .
docker run -p 8080:8080 chatgpt-line-bot
```

**特點:**
- ✅ 高性能 Gunicorn + Gevent
- ✅ 多 worker 並發處理
- ✅ 生產級安全配置
- ✅ 完整日誌記錄
- ✅ 自動重啟機制

### 4. 雲端部署（Google Cloud Run）

```bash
# 自動部署到 Cloud Run
./scripts/deploy/deploy-to-cloudrun.sh

# 檢查配置（乾運行）
./scripts/deploy/deploy-to-cloudrun.sh --dry-run

# 自動模式部署
./scripts/deploy/deploy-to-cloudrun.sh --auto
```

**特點:**
- ✅ 完全管理的服務
- ✅ 自動擴縮容
- ✅ SSL 終止
- ✅ 全球負載平衡
- ✅ 監控和日誌

## ⚠️ 重要提醒

### Flask 開發服務器警告

當您看到以下警告時：

```
WARNING: This is a development server. Do not use it in a production deployment. 
Use a production WSGI server instead.
```

**原因:** 您正在使用 Flask 內建的開發服務器

**解決方案:**
- **開發環境:** 這是正常的，可以忽略
- **生產環境:** 使用 `./scripts/prod.sh` 或 `gunicorn` 命令

### 環境分離最佳實踐

| 環境 | 啟動方式 | 配置文件 | 適用場景 |
|------|----------|----------|----------|
| 開發 | `./scripts/dev.sh` | `.env.local` | 日常開發、調試 |
| 本地測試 | `./scripts/test-prod.sh` | `.env.local` | 測試生產配置 |
| 生產 | `./scripts/prod.sh` | 環境變量 | 本地生產部署 |
| 雲端 | `./scripts/deploy/deploy-to-cloudrun.sh` | `config/deploy/.env` | Google Cloud Run |

## 🔍 故障排除

### 1. 端口被佔用

```bash
# 查找佔用端口的進程
lsof -i :8080

# 終止進程
kill -9 [PID]
```

### 2. 環境變量未載入

```bash
# 檢查是否有 .env.local 文件
ls -la .env.local

# 手動載入環境變量
source .env.local
```

### 3. Gunicorn 未安裝

```bash
# 安裝 Gunicorn
pip install gunicorn gevent

# 或使用 requirements.txt
pip install -r requirements.txt
```

### 4. 權限問題

```bash
# 確保腳本可執行
chmod +x scripts/*.sh

# 檢查文件權限
ls -la scripts/
```

## 🔒 安全配置

### 生產環境必須設置

- `LINE_CHANNEL_ACCESS_TOKEN`
- `LINE_CHANNEL_SECRET`
- `OPENAI_API_KEY`
- `DB_PASSWORD`
- `TEST_SECRET_KEY`

### 開發環境注意事項

- 不要在開發環境使用生產密鑰
- `.env.local` 文件已加入 `.gitignore`
- 定期輪替開發環境的測試密鑰

## 📚 相關文檔

- [部署指南](docs/DEPLOYMENT.md)
- [安全政策](docs/SECURITY.md)
- [架構說明](docs/RAG_IMPLEMENTATION.md)
- [Cloud Run 部署](docs/DEPLOYMENT.md)

## 🆘 獲取幫助

如果遇到問題：

1. 檢查日誌文件 `logs/app.log`
2. 確認環境變量設置
3. 驗證網路連接和 API 密鑰
4. 查看相關文檔
5. 提交 Issue 到項目倉庫