# 部署腳本使用指南

本資料夾包含 ChatGPT Line Bot 的所有部署相關腳本和配置檔案。

## 📁 檔案結構

```
deploy/
├── .env.example           # 環境變數配置模板
├── README.md             # 本說明文件
├── Dockerfile.cloudrun   # Cloud Run 專用 Dockerfile
├── cloudrun-service.yaml # Cloud Run 服務配置
├── deploy-to-cloudrun.sh # 主要部署腳本
├── monitoring-setup.sh   # 監控設定腳本
├── setup-loadbalancer.sh # 負載平衡器設定腳本
└── setup-monitoring.sh   # 監控和警報設定腳本
```

## 🚀 快速開始

### 1. 配置環境變數

```bash
# 複製環境變數模板
cp deploy/.env.example deploy/.env

# 編輯配置檔案，填入實際的值
vim deploy/.env
```

### 2. 部署到 Cloud Run

```bash
# 基本部署（互動模式）
./deploy/deploy-to-cloudrun.sh

# 自動部署（不詢問確認）
./deploy/deploy-to-cloudrun.sh --auto

# 檢查配置（乾運行）
./deploy/deploy-to-cloudrun.sh --dry-run

# 從特定步驟開始（錯誤修復）
./deploy/deploy-to-cloudrun.sh --start-from build-image
```

## 🔧 部署腳本功能

### 互動模式特點

1. **步驟確認**：每個步驟執行前都會詢問用戶確認
2. **錯誤處理**：出錯時提供重新開始的指令
3. **跳過功能**：可以跳過不需要的步驟
4. **安全退出**：隨時可以安全退出腳本

### 執行模式

| 模式 | 說明 | 使用場景 |
|------|------|----------|
| 互動模式 | 預設模式，每步詢問確認 | 首次部署、學習過程 |
| 自動模式 | `--auto` 跳過所有確認 | CI/CD、熟悉流程後 |
| 乾運行 | `--dry-run` 只顯示指令不執行 | 檢查配置、學習指令 |
| 部分執行 | `--start-from STEP` 從指定步驟開始 | 錯誤修復、重新部署 |

### 可用步驟

| 步驟代碼 | 說明 | 包含操作 |
|----------|------|----------|
| `setup-project` | 設定專案 | 設定 project ID、啟用 API |
| `setup-secrets` | 配置密鑰 | 建立 Secret Manager 密鑰 |
| `build-image` | 建立映像 | Docker 建置和推送 |
| `deploy-service` | 部署服務 | 部署到 Cloud Run |
| `setup-permissions` | 設定權限 | IAM 權限配置 |

## 📊 監控設定

```bash
# 設定監控和警報
./deploy/monitoring-setup.sh --dry-run

# 自動設定監控
./deploy/monitoring-setup.sh --auto
```

## 🌐 負載平衡器設定

```bash
# 設定全球負載平衡器
./deploy/setup-loadbalancer.sh --dry-run

# 自動設定負載平衡器
./deploy/setup-loadbalancer.sh --auto
```

## 🔐 安全性配置

### 環境變數

所有敏感資訊都應該通過環境變數傳遞：

```bash
export OPENAI_API_KEY="your_openai_api_key"
export LINE_CHANNEL_ACCESS_TOKEN="your_line_token"
export LINE_CHANNEL_SECRET="your_line_secret"
export DB_HOST="your_db_host"
export DB_USER="your_db_user"
export DB_PASSWORD="your_db_password"
export DB_NAME="your_db_name"
```

### Secret Manager

腳本會自動將敏感資訊存儲到 Google Secret Manager：

- `openai-api-key`
- `line-channel-access-token`
- `line-channel-secret`
- `db-host`、`db-user`、`db-password`、`db-name`

## 🐛 故障排除

### 常見錯誤和解決方案

1. **環境變數未設定**
   ```bash
   # 錯誤: 環境變數 PROJECT_ID 未設定
   # 解決: 檢查 deploy/.env 檔案
   ```

2. **權限不足**
   ```bash
   # 確保已登入並有適當權限
   gcloud auth login
   gcloud auth application-default login
   ```

3. **API 未啟用**
   ```bash
   # 腳本會自動啟用，但可能需要等待
   # 手動啟用：gcloud services enable [API_NAME]
   ```

4. **Docker 建置失敗**
   ```bash
   # 從建置步驟重新開始
   ./deploy/deploy-to-cloudrun.sh --start-from build-image
   ```

### 重新開始部署

如果部署過程中出錯：

```bash
# 查看錯誤訊息中的建議指令
# 通常格式為：
./deploy/deploy-to-cloudrun.sh --start-from [FAILED_STEP]
```

## 💡 最佳實踐

1. **首次部署**：使用互動模式了解每個步驟
2. **生產部署**：使用自動模式結合 CI/CD
3. **測試配置**：使用乾運行模式檢查設定
4. **錯誤修復**：使用部分執行模式節省時間
5. **安全管理**：定期輪替 Secret Manager 中的密鑰

## 📚 相關文檔

- [部署指南](../docs/DEPLOYMENT.md)
- [安全政策](../docs/SECURITY.md)
- [架構說明](../docs/RAG_IMPLEMENTATION.md)