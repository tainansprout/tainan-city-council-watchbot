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
# 1. 複製專案
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

# Facebook Messenger Platform 密鑰
echo -n "$FACEBOOK_APP_ID_SECRET" | gcloud secrets create facebook-app-id --data-file=-
echo -n "$FACEBOOK_APP_SECRET_SECRET" | gcloud secrets create facebook-app-secret --data-file=-
echo -n "$FACEBOOK_PAGE_ACCESS_TOKEN_SECRET" | gcloud secrets create facebook-page-access-token --data-file=-
echo -n "$FACEBOOK_VERIFY_TOKEN_SECRET" | gcloud secrets create facebook-verify-token --data-file=-

# Instagram Business Cloud API 密鑰
echo -n "$INSTAGRAM_APP_ID_SECRET" | gcloud secrets create instagram-app-id --data-file=-
echo -n "$INSTAGRAM_APP_SECRET_SECRET" | gcloud secrets create instagram-app-secret --data-file=-
echo -n "$INSTAGRAM_PAGE_ACCESS_TOKEN_SECRET" | gcloud secrets create instagram-page-access-token --data-file=-
echo -n "$INSTAGRAM_VERIFY_TOKEN_SECRET" | gcloud secrets create instagram-verify-token --data-file=-

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

## 📱 多平台部署特殊需求

### WhatsApp Business API 部署

#### Webhook 設定
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

#### 環境變數設定
確保以下 WhatsApp 環境變數已正確設定：

```bash
# 在 Cloud Run 中設定 (包含 WhatsApp、Messenger 和 Instagram)
gcloud run services update chatgpt-line-bot \
    --region=asia-east1 \
    --set-env-vars WHATSAPP_ACCESS_TOKEN=projects/PROJECT_ID/secrets/whatsapp-access-token/versions/latest \
    --set-env-vars WHATSAPP_PHONE_NUMBER_ID=projects/PROJECT_ID/secrets/whatsapp-phone-number-id/versions/latest \
    --set-env-vars WHATSAPP_APP_SECRET=projects/PROJECT_ID/secrets/whatsapp-app-secret/versions/latest \
    --set-env-vars WHATSAPP_VERIFY_TOKEN=projects/PROJECT_ID/secrets/whatsapp-verify-token/versions/latest \
    --set-env-vars FACEBOOK_APP_ID=projects/PROJECT_ID/secrets/facebook-app-id/versions/latest \
    --set-env-vars FACEBOOK_APP_SECRET=projects/PROJECT_ID/secrets/facebook-app-secret/versions/latest \
    --set-env-vars FACEBOOK_PAGE_ACCESS_TOKEN=projects/PROJECT_ID/secrets/facebook-page-access-token/versions/latest \
    --set-env-vars FACEBOOK_VERIFY_TOKEN=projects/PROJECT_ID/secrets/facebook-verify-token/versions/latest \
    --set-env-vars INSTAGRAM_APP_ID=projects/PROJECT_ID/secrets/instagram-app-id/versions/latest \
    --set-env-vars INSTAGRAM_APP_SECRET=projects/PROJECT_ID/secrets/instagram-app-secret/versions/latest \
    --set-env-vars INSTAGRAM_PAGE_ACCESS_TOKEN=projects/PROJECT_ID/secrets/instagram-page-access-token/versions/latest \
    --set-env-vars INSTAGRAM_VERIFY_TOKEN=projects/PROJECT_ID/secrets/instagram-verify-token/versions/latest
```

#### 測試 WhatsApp 整合
```bash
# 測試 webhook 驗證
curl -X GET "https://your-domain.com/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=your_verify_token&hub.challenge=test_challenge"

# 檢查平台狀態
curl https://your-domain.com/health | jq '.checks.platforms'

# 查看 WhatsApp 日誌
gcloud logging read 'resource.type="cloud_run_revision" AND textPayload:"[WHATSAPP]"' --limit=50
```

#### 申請流程
1. **Meta Business Account**: 完成商業驗證
2. **WhatsApp Business API**: 申請並等待審核（1-4週）
3. **電話號碼**: 驗證專用電話號碼
4. **測試**: 使用測試號碼進行初步測試
5. **生產**: 審核通過後切換到生產環境

### Facebook Messenger Platform 部署

#### Webhook 設定
Messenger Platform 需要特殊的 webhook 設定：

1. **Meta 開發者控制台設定**
   - 登入 [Meta for Developers](https://developers.facebook.com/)
   - 選擇您的 Messenger App
   - 設定 Webhook URL: `https://your-domain.com/webhooks/messenger`
   - 驗證 Token: 與環境變數 `FACEBOOK_VERIFY_TOKEN` 相同

2. **Facebook 頁面連結**
   - 必須有一個 Facebook 頁面（企業頁面）
   - 在 Messenger Settings 中連結頁面
   - 產生 Page Access Token

3. **HTTPS 需求**
   - Messenger 要求必須使用 HTTPS
   - 確保 SSL 證書有效
   - 支援 TLS 1.2 或更高版本

4. **網域驗證**
   - 網域必須可公開訪問
   - 不能使用 localhost 或內部 IP
   - 建議使用 Load Balancer 提供穩定的端點

#### 環境變數設定
確保以下 Messenger 環境變數已正確設定：

```bash
# 在 Cloud Run 中設定
gcloud run services update chatgpt-line-bot \
    --region=asia-east1 \
    --set-env-vars FACEBOOK_APP_ID=projects/PROJECT_ID/secrets/facebook-app-id/versions/latest \
    --set-env-vars FACEBOOK_APP_SECRET=projects/PROJECT_ID/secrets/facebook-app-secret/versions/latest \
    --set-env-vars FACEBOOK_PAGE_ACCESS_TOKEN=projects/PROJECT_ID/secrets/facebook-page-access-token/versions/latest \
    --set-env-vars FACEBOOK_VERIFY_TOKEN=projects/PROJECT_ID/secrets/facebook-verify-token/versions/latest
```

#### 測試 Messenger 整合
```bash
# 測試 webhook 驗證
curl -X GET "https://your-domain.com/webhooks/messenger?hub.mode=subscribe&hub.verify_token=your_verify_token&hub.challenge=test_challenge"

# 檢查平台狀態
curl https://your-domain.com/health | jq '.checks.platforms'

# 查看 Messenger 日誌
gcloud logging read 'resource.type="cloud_run_revision" AND textPayload:"[MESSENGER]"' --limit=50
```

#### 申請流程
1. **Facebook 開發者帳號**: 建立或使用現有帳號
2. **Facebook 應用程式**: 建立 Business 類型應用程式
3. **Facebook 頁面**: 建立或使用現有企業頁面
4. **Messenger Platform**: 設定和連結頁面
5. **測試**: 使用測試帳號進行初步測試
6. **App Review**: 如需發送給非測試用戶，需通過 Facebook 審核

#### 音訊訊息支援
Messenger 平台已支援音訊訊息轉錄（如同 LINE 平台）：
- ✅ 自動下載音訊附件
- ✅ 使用相同的 AudioHandler 進行轉錄
- ✅ 支援 MP3, AAC 等常見格式
- ✅ 統一的錯誤處理和日誌記錄

### Instagram Business Cloud API 部署

#### Webhook 設定
Instagram Business Cloud API 需要特殊的 webhook 設定：

1. **Meta 開發者控制台設定**
   - 登入 [Meta for Developers](https://developers.facebook.com/)
   - 選擇您的 Instagram App（或建立新的 Business 應用程式）
   - 設定 Webhook URL: `https://your-domain.com/webhooks/instagram`
   - 驗證 Token: 與環境變數 `INSTAGRAM_VERIFY_TOKEN` 相同

2. **Instagram 商業帳號連結**
   - 必須有一個 Instagram 商業帳號（Business Account）
   - 將 Instagram 帳號連接到 Facebook 頁面
   - 在 Instagram Basic Display 中設定權限

3. **HTTPS 需求**
   - Instagram 要求必須使用 HTTPS
   - 確保 SSL 證書有效
   - 支援 TLS 1.2 或更高版本

4. **網域驗證**
   - 網域必須可公開訪問
   - 不能使用 localhost 或內部 IP
   - 建議使用 Load Balancer 提供穩定的端點

#### 環境變數設定
確保以下 Instagram 環境變數已正確設定：

```bash
# 在 Cloud Run 中設定
gcloud run services update chatgpt-line-bot \
    --region=asia-east1 \
    --set-env-vars INSTAGRAM_APP_ID=projects/PROJECT_ID/secrets/instagram-app-id/versions/latest \
    --set-env-vars INSTAGRAM_APP_SECRET=projects/PROJECT_ID/secrets/instagram-app-secret/versions/latest \
    --set-env-vars INSTAGRAM_PAGE_ACCESS_TOKEN=projects/PROJECT_ID/secrets/instagram-page-access-token/versions/latest \
    --set-env-vars INSTAGRAM_VERIFY_TOKEN=projects/PROJECT_ID/secrets/instagram-verify-token/versions/latest
```

#### 測試 Instagram 整合
```bash
# 測試 webhook 驗證
curl -X GET "https://your-domain.com/webhooks/instagram?hub.mode=subscribe&hub.verify_token=your_verify_token&hub.challenge=test_challenge"

# 檢查平台狀態
curl https://your-domain.com/health | jq '.checks.platforms'

# 查看 Instagram 日誌
gcloud logging read 'resource.type="cloud_run_revision" AND textPayload:"[INSTAGRAM]"' --limit=50
```

#### 申請流程
1. **Facebook 開發者帳號**: 建立或使用現有帳號
2. **Facebook 應用程式**: 建立 Business 類型應用程式
3. **Instagram 商業帳號**: 確保有 Instagram 商業帳號
4. **Facebook 頁面連結**: 將 Instagram 帳號連接到 Facebook 頁面
5. **Instagram Basic Display**: 設定和配置權限
6. **測試**: 使用測試帳號進行初步測試
7. **App Review**: 如需完整功能，需通過 Meta 審核

#### Instagram 功能支援
Instagram 平台已支援以下功能：
- ✅ **文字訊息**: 完整的文字內容接收和發送
- ✅ **音訊訊息**: 自動下載和轉錄為文字（如同 LINE 平台）
- ✅ **圖片訊息**: 自動下載圖片檔案
- ✅ **影片訊息**: 支援影片檔案處理
- ✅ **檔案訊息**: 支援各種檔案格式
- ✅ **Story 回覆**: 回覆用戶的 Story 提及和互動
- ✅ **簽名驗證**: HMAC-SHA1 webhook 安全驗證

#### ⚠️ Instagram 限制說明
- **商業帳號**: 僅支援 Instagram 商業帳號
- **用戶發起**: 只能回覆用戶主動發送的訊息
- **24小時窗口**: 使用者互動後24小時內可自由回覆
- **Story 回覆**: 僅能回覆提及商業帳號的 Story
- **頁面綁定**: 需要將 Instagram 帳號連接到 Facebook 頁面
- **審核流程**: 某些功能需要 Meta 審核

## 📞 支援和聯繫

如遇到問題：
1. 檢查本文件的故障排除章節
2. 查看 Google Cloud 狀態頁面
3. 檢查監控和日誌
4. 聯繫開發團隊

### 多平台特殊問題

#### WhatsApp 特殊問題
- **Webhook 驗證失敗**: 檢查 verify_token 是否正確
- **訊息發送失敗**: 確認 24 小時窗口限制
- **API 認證錯誤**: 檢查 access_token 是否有效
- **媒體下載失敗**: 確認網路連線和權限

#### Messenger 特殊問題
- **Webhook 驗證失敗**: 檢查 verify_token 是否正確
- **頁面權杖錯誤**: 確認 Page Access Token 有效且權限正確
- **簽名驗證失敗**: 檢查 App Secret 設定
- **Echo 訊息問題**: 確認 echo 訊息過濾機制正常
- **用戶資訊取得失敗**: 檢查 Graph API 權限
- **音訊轉錄失敗**: 確認媒體下載和處理流程

#### Instagram 特殊問題
- **Webhook 驗證失敗**: 檢查 verify_token 是否正確
- **商業帳號連結失敗**: 確認 Instagram 帳號已連接到 Facebook 頁面
- **頁面權杖錯誤**: 確認 Page Access Token 有效且權限正確
- **簽名驗證失敗**: 檢查 App Secret 設定
- **Story 回覆失敗**: 確認 Story 提及商業帳號且在24小時窗口內
- **用戶資訊取得失敗**: 檢查 Instagram Basic Display API 權限
- **音訊轉錄失敗**: 確認媒體下載和處理流程
- **API 權限錯誤**: 確認已通過 Meta App Review 流程

---

### 常用部署指令

```bash
# 一鍵部署所有平台（包含 Messenger 和 Instagram）
./scripts/deploy/deploy-to-cloudrun.sh --all-platforms

# 僅部署特定平台
./scripts/deploy/deploy-to-cloudrun.sh --platform messenger
./scripts/deploy/deploy-to-cloudrun.sh --platform instagram

# 檢查所有平台狀態
curl https://your-domain.com/health | jq '.checks.platforms'

# 測試所有 webhook 驗證
for platform in line discord telegram whatsapp messenger instagram; do
  echo "Testing $platform webhook..."
  curl -X GET "https://your-domain.com/webhooks/$platform?hub.mode=subscribe&hub.verify_token=test&hub.challenge=test" || echo "$platform webhook not configured"
done
```

---

**注意**: 本部署指南假設你已經熟悉 Google Cloud Platform 和 Docker 的基本概念。如果你是新手，建議先閱讀相關的入門文件。

**Messenger 部署注意事項**: Messenger 平台支援音訊訊息轉錄功能，與 LINE 平台提供相同的使用體驗。確保在部署時正確設定 Facebook App ID、App Secret、Page Access Token 和 Verify Token。

**Instagram 部署注意事項**: Instagram 平台支援音訊訊息轉錄功能、Story 回覆等特色功能，與其他平台提供一致的使用體驗。部署時需要確保 Instagram 商業帳號已正確連接到 Facebook 頁面，並且正確設定 Instagram App ID、App Secret、Page Access Token 和 Verify Token。