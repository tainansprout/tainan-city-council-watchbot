# 🚀 ChatGPT Line Bot 運行指南

本指南介紹如何在不同環境中運行 ChatGPT Line Bot，確保使用正確的服務器配置。

## 📁 項目結構

```
ChatGPT-Line-Bot/
├── main.py                 # Flask 應用主文件
├── wsgi.py                 # WSGI 入口點（生產環境）
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

**直接運行:**
```bash
export FLASK_ENV=development
python main.py
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

**直接運行:**
```bash
export FLASK_ENV=production
gunicorn -c gunicorn.conf.py wsgi:application
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

**直接運行:**
```bash
export FLASK_ENV=production
gunicorn -c gunicorn.conf.py wsgi:application
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