# 🚀 ChatGPT Line Bot 部署指南

本指南提供完整的 Google Cloud Run 部署流程，包含高可用性、負載平衡、監控和 CI/CD 配置。

## 📋 部署前檢查清單

### 必要準備
- [ ] Google Cloud 專案已建立
- [ ] 帳單已啟用
- [ ] 必要的 API 已啟用
- [ ] 服務帳號金鑰已下載
- [ ] 網域名稱已準備（可選，用於 Load Balancer）

### 環境需求
- [ ] Docker 已安裝
- [ ] gcloud CLI 已安裝並認證
- [ ] Python 3.9+ 已安裝
- [ ] PostgreSQL 資料庫已準備

## 🔧 快速部署

### 1. 基本部署
```bash
# 1. 克隆專案
git clone <repository-url>
cd ChatGPT-Line-Bot

# 2. 設定環境變數
cp config/deploy/.env.example config/deploy/.env
# 編輯 config/deploy/.env 檔案，填入實際的 API 金鑰和配置

# 3. 執行部署腳本
chmod +x scripts/deploy/deploy-to-cloudrun.sh
./scripts/deploy/deploy-to-cloudrun.sh
```

### 2. 高可用性部署（包含 Load Balancer）
```bash
# 1. 基本部署完成後
chmod +x scripts/deploy/setup-loadbalancer.sh
./scripts/deploy/setup-loadbalancer.sh

# 2. 設定監控
chmod +x scripts/deploy/setup-monitoring.sh
./scripts/deploy/setup-monitoring.sh
```

## 🏗️ 詳細部署步驟

### 步驟 1: Google Cloud 專案設定

```bash
# 登入 Google Cloud
gcloud auth login

# 設定專案 ID
export PROJECT_ID="your-project-id"
gcloud config set project $PROJECT_ID

# 啟用必要的 API
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    secretmanager.googleapis.com \
    sql-component.googleapis.com \
    sqladmin.googleapis.com \
    compute.googleapis.com \
    monitoring.googleapis.com \
    logging.googleapis.com
```

### 步驟 2: 資料庫設定

#### 選項 A: Cloud SQL (推薦)
```bash
# 建立 Cloud SQL 實例
gcloud sql instances create chatgpt-line-bot-db \
    --database-version=POSTGRES_13 \
    --tier=db-f1-micro \
    --region=asia-east1

# 建立資料庫
gcloud sql databases create chatgpt_line_bot \
    --instance=chatgpt-line-bot-db

# 建立使用者
gcloud sql users create chatgpt_user \
    --instance=chatgpt-line-bot-db \
    --password=your_secure_password
```

#### 選項 B: 外部資料庫
確保你的 PostgreSQL 資料庫可以從 Google Cloud 存取，並且已經建立了必要的資料庫和使用者。

#### 資料庫結構初始化
無論使用哪種資料庫選項，都需要初始化資料庫結構：

```bash
# 方法 1: 使用新的遷移管理器（推薦）
python scripts/db_migration.py auto-setup

# 方法 2: 使用傳統設置腳本（向後相容）
python scripts/setup_database.py setup

# 方法 3: 直接使用 Alembic（進階用戶）
alembic upgrade head
```

### 步驟 3: 敏感資訊管理

```bash
# 載入環境變數
source config/deploy/.env

# 建立 Secret Manager 密鑰（從 .env 文件讀取）
echo -n "$OPENAI_API_KEY_SECRET" | gcloud secrets create openai-api-key --data-file=-
echo -n "$OPENAI_ASSISTANT_ID_SECRET" | gcloud secrets create openai-assistant-id --data-file=-
echo -n "$LINE_CHANNEL_ACCESS_TOKEN_SECRET" | gcloud secrets create line-channel-access-token --data-file=-
echo -n "$LINE_CHANNEL_SECRET_SECRET" | gcloud secrets create line-channel-secret --data-file=-

# WhatsApp Business API 密鑰
echo -n "$WHATSAPP_ACCESS_TOKEN_SECRET" | gcloud secrets create whatsapp-access-token --data-file=-
echo -n "$WHATSAPP_PHONE_NUMBER_ID_SECRET" | gcloud secrets create whatsapp-phone-number-id --data-file=-
echo -n "$WHATSAPP_APP_SECRET_SECRET" | gcloud secrets create whatsapp-app-secret --data-file=-
echo -n "$WHATSAPP_VERIFY_TOKEN_SECRET" | gcloud secrets create whatsapp-verify-token --data-file=-

echo -n "$DB_HOST_SECRET" | gcloud secrets create db-host --data-file=-
echo -n "$DB_USER_SECRET" | gcloud secrets create db-user --data-file=-
echo -n "$DB_PASSWORD_SECRET" | gcloud secrets create db-password --data-file=-
echo -n "$DB_NAME_SECRET" | gcloud secrets create db-name --data-file=-
echo -n "$TEST_PASSWORD" | gcloud secrets create test-password --data-file=-
```

### 步驟 4: 部署應用程式

```bash
# 載入環境變數
source config/deploy/.env

echo "PROJECT_ID: $PROJECT_ID"

# 設定project
gcloud config set project $PROJECT_ID

# 建立 Docker 映像
gcloud builds submit --tag asia.gcr.io/$PROJECT_ID/$SERVICE_NAME

# 部署到 Cloud Run
gcloud run deploy $SERVICE_NAME --image asia.gcr.io/$PROJECT_ID/$SERVICE_NAME --platform managed --port 8080 --memory 4G --timeout=3m
```

### 步驟 5: 設定 Load Balancer（可選但推薦）

```bash
# 執行 Load Balancer 設定腳本
./scripts/deploy/setup-loadbalancer.sh
```

這會建立：
- Network Endpoint Group (NEG)
- 後端服務
- URL 映射
- SSL 憑證
- HTTPS 代理
- 全球轉發規則
- 健康檢查
- Cloud CDN（可選）

### 步驟 6: 設定監控和警報

```bash
# 執行監控設定腳本
./scripts/deploy/setup-monitoring.sh
```

這會建立：
- 監控 Dashboard
- 警報政策（錯誤率、延遲、服務下線）
- 日誌聚合到 BigQuery
- 自訂指標
- 通知頻道

## 🔒 安全性配置

### 1. 服務帳號權限
```bash
# 建立服務帳號
gcloud iam service-accounts create chatgpt-line-bot-sa \
    --description="ChatGPT Line Bot Service Account" \
    --display-name="ChatGPT Line Bot"

# 授予最小權限
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:chatgpt-line-bot-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

### 2. 網路安全
```bash
# 限制 Cloud Run 存取（如果需要）
gcloud run services update chatgpt-line-bot \
    --ingress=internal \
    --region=asia-east1
```

### 3. 憑證輪替
定期輪替 API 金鑰和密碼：
```bash
# 更新 Secret Manager 中的值
echo -n "new_api_key" | gcloud secrets versions add openai-api-key --data-file=-
```

## 🚀 新架構特色 (v2.0)

### 統一啟動方式
新版本支援環境自動偵測：

```bash
# 開發環境（自動偵測）
python main.py

# 生產環境（自動啟動 Gunicorn）
FLASK_ENV=production python main.py

# 向後兼容 WSGI
gunicorn -c gunicorn.conf.py main:application
```

### 🔐 Web 測試介面

部署完成後，您可以通過以下方式測試：

1. **訪問 Web 測試介面**
   ```bash
   # 訪問登入頁面
   https://your-service-url/login
   
   # 使用設定的測試密碼登入
   # 登入成功後自動跳轉到聊天介面
   ```

2. **配置測試認證**
   ```bash
   # 在 Secret Manager 中設定測試密碼
   echo -n "your_secure_test_password" | gcloud secrets create test-password --data-file=-
   
   # 在 Cloud Run 環境變數中配置
   gcloud run services update chatgpt-line-bot \
       --region=asia-east1 \
       --set-env-vars TEST_PASSWORD="your_secure_test_password"
   ```

3. **安全最佳實踐**
   - 生產環境請使用強密碼
   - 定期更新測試密碼
   - 可考慮使用 IP 白名單限制測試介面存取

### ⚙️ ConfigManager 優化

新版本包含 ConfigManager singleton 模式：
- **效能優化**: 配置僅載入一次，避免重複 I/O
- **執行緒安全**: 支援多執行緒環境
- **記憶體高效**: 單一實例在所有請求間共享

## 🔄 CI/CD 設定

### GitHub Actions 設定

1. 在 GitHub 專案設定中添加以下 Secrets：
   - `GCP_PROJECT_ID`: 你的 Google Cloud 專案 ID
   - `GCP_SA_KEY`: 服務帳號金鑰 (JSON 格式)
   - `SLACK_WEBHOOK`: Slack 通知 Webhook (可選)

2. 推送到 main 分支會自動觸發部署

### 手動部署
```bash
# 建立新版本
docker build -f Dockerfile.cloudrun -t gcr.io/$PROJECT_ID/chatgpt-line-bot:v1.1.0 .
docker push gcr.io/$PROJECT_ID/chatgpt-line-bot:v1.1.0

# 更新 Cloud Run 服務
gcloud run deploy chatgpt-line-bot \
    --image gcr.io/$PROJECT_ID/chatgpt-line-bot:v1.1.0 \
    --region=asia-east1
```

## 📊 監控和維護

### 監控儀表板
- **Request Count**: 請求數量趨勢
- **Response Latency**: 回應延遲分佈
- **Error Rate**: 錯誤率監控
- **Instance Count**: 實例數量變化

### 重要指標
- **可用性**: 目標 99.9%
- **回應時間**: P95 < 5 秒
- **錯誤率**: < 1%

### 日誌分析
```bash
# 查看最近的錯誤日誌
gcloud logging read "resource.type=cloud_run_revision AND severity>=ERROR" --limit=50 --format=json

# 查看特定時間範圍的日誌
gcloud logging read "resource.type=cloud_run_revision AND timestamp>=\"2024-01-01T00:00:00Z\"" --limit=100
```

## 🚨 故障排除

### 常見問題

#### 1. 部署失敗
```bash
# 檢查建置日誌
gcloud builds log $(gcloud builds list --limit=1 --format="value(id)")

# 檢查 Cloud Run 日誌
gcloud logs read "resource.type=cloud_run_revision" --limit=50
```

#### 2. 健康檢查失敗
```bash
# 檢查健康檢查端點
curl https://your-service-url/health

# 檢查服務狀態
gcloud run services describe chatgpt-line-bot --region=asia-east1
```

#### 3. 記憶體或 CPU 不足
```bash
# 增加資源配置
gcloud run services update chatgpt-line-bot \
    --region=asia-east1 \
    --memory=4Gi \
    --cpu=4
```

#### 4. 資料庫連線問題
```bash
# 檢查 Secret Manager 中的資料庫配置
gcloud secrets versions access latest --secret="db-host"
gcloud secrets versions access latest --secret="db-user"
```

### 緊急回滾
```bash
# 查看最近的版本
gcloud run revisions list --service=chatgpt-line-bot --region=asia-east1

# 回滾到前一個版本
gcloud run services update-traffic chatgpt-line-bot \
    --region=asia-east1 \
    --to-revisions=REVISION_NAME=100
```

## 📈 擴展和優化

### 自動擴展配置
```yaml
autoscaling.knative.dev/minScale: "1"    # 最小實例數
autoscaling.knative.dev/maxScale: "100"  # 最大實例數
```

### 效能優化
1. **並發設定**: 根據應用程式特性設定 `containerConcurrency`
2. **資源配置**: 監控使用情況並調整 CPU 和記憶體
3. **連線池**: 優化資料庫連線池大小
4. **快取**: 實施適當的快取策略

### 成本優化
1. **最小實例數**: 根據流量模式調整
2. **資源請求**: 設定合適的 requests 和 limits
3. **冷啟動**: 使用 CPU 分配和最小實例減少冷啟動
4. **監控成本**: 定期檢查 Google Cloud 計費

## 🔍 效能基準

| 指標 | 目標值 | 監控方法 |
|------|--------|----------|
| 可用性 | 99.9% | Cloud Monitoring |
| 回應時間 (P50) | < 2 秒 | Cloud Monitoring |
| 回應時間 (P95) | < 5 秒 | Cloud Monitoring |
| 錯誤率 | < 1% | Cloud Monitoring |
| 冷啟動時間 | < 10 秒 | Cloud Monitoring |

## 📱 WhatsApp 部署特殊需求

### Webhook 設定
WhatsApp Business API 需要特殊的 webhook 設定：

1. **Meta 開發者控制台設定**
   - 登入 [Meta for Developers](https://developers.facebook.com/)
   - 選擇您的 WhatsApp Business App
   - 設定 Webhook URL: `https://your-domain.com/webhooks/whatsapp`
   - 驗證 Token: 與環境變數 `WHATSAPP_VERIFY_TOKEN` 相同

2. **HTTPS 需求**
   - WhatsApp 要求必須使用 HTTPS
   - 確保 SSL 證書有效
   - 支援 TLS 1.2 或更高版本

3. **網域驗證**
   - 網域必須可公開訪問
   - 不能使用 localhost 或內部 IP
   - 建議使用 Load Balancer 提供穩定的端點

### 環境變數設定
確保以下 WhatsApp 環境變數已正確設定：

```bash
# 在 Cloud Run 中設定
gcloud run services update chatgpt-line-bot \
    --region=asia-east1 \
    --set-env-vars WHATSAPP_ACCESS_TOKEN=projects/PROJECT_ID/secrets/whatsapp-access-token/versions/latest \
    --set-env-vars WHATSAPP_PHONE_NUMBER_ID=projects/PROJECT_ID/secrets/whatsapp-phone-number-id/versions/latest \
    --set-env-vars WHATSAPP_APP_SECRET=projects/PROJECT_ID/secrets/whatsapp-app-secret/versions/latest \
    --set-env-vars WHATSAPP_VERIFY_TOKEN=projects/PROJECT_ID/secrets/whatsapp-verify-token/versions/latest
```

### 測試 WhatsApp 整合
```bash
# 測試 webhook 驗證
curl -X GET "https://your-domain.com/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=your_verify_token&hub.challenge=test_challenge"

# 檢查平台狀態
curl https://your-domain.com/health | jq '.checks.platforms'

# 查看 WhatsApp 日誌
gcloud logging read 'resource.type="cloud_run_revision" AND textPayload:"[WHATSAPP]"' --limit=50
```

### 申請流程
1. **Meta Business Account**: 完成商業驗證
2. **WhatsApp Business API**: 申請並等待審核（1-4週）
3. **電話號碼**: 驗證專用電話號碼
4. **測試**: 使用測試號碼進行初步測試
5. **生產**: 審核通過後切換到生產環境

## 📞 支援和聯繫

如遇到問題：
1. 檢查本文件的故障排除章節
2. 查看 Google Cloud 狀態頁面
3. 檢查監控和日誌
4. 聯繫開發團隊

### WhatsApp 特殊問題
- **Webhook 驗證失敗**: 檢查 verify_token 是否正確
- **訊息發送失敗**: 確認 24 小時窗口限制
- **API 認證錯誤**: 檢查 access_token 是否有效
- **媒體下載失敗**: 確認網路連線和權限

---

**注意**: 本部署指南假設你已經熟悉 Google Cloud Platform 和 Docker 的基本概念。如果你是新手，建議先閱讀相關的入門文件。