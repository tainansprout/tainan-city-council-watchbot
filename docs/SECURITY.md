# 🔐 安全性指南

本專案為開源軟體，包含敏感的 API 金鑰和憑證配置。請務必遵循以下安全性準則。

## ⚠️  重要警告

**絕對不要**在任何情況下將以下敏感資訊提交到版本控制系統：

- API 金鑰（OpenAI、Line Bot、WhatsApp、Messenger、Instagram 等）
- 資料庫密碼
- SSL 憑證和私鑰
- Service Account 金鑰
- WhatsApp Business API 憑證
- Facebook Messenger Platform 憑證
- Instagram Business Cloud API 憑證
- 任何包含敏感資訊的配置檔案

## 🛡️ 敏感資訊管理

### 1. 環境變數

在本地開發時，使用環境變數管理敏感資訊：

```bash
# 建立 .env 檔案（已加入 .gitignore）
cp .env.example .env

# 編輯 .env 檔案，填入實際的值
nano .env
```

### 2. Google Cloud Secret Manager

在生產環境中，使用 Google Cloud Secret Manager：

```bash
# 建立密鑰
echo -n "your_openai_api_key" | gcloud secrets create openai-api-key --data-file=-
echo -n "your_line_token" | gcloud secrets create line-channel-access-token --data-file=-
echo -n "your_line_secret" | gcloud secrets create line-channel-secret --data-file=-

# WhatsApp Business API 密鑰
echo -n "your_whatsapp_access_token" | gcloud secrets create whatsapp-access-token --data-file=-
echo -n "your_whatsapp_phone_number_id" | gcloud secrets create whatsapp-phone-number-id --data-file=-
echo -n "your_whatsapp_app_secret" | gcloud secrets create whatsapp-app-secret --data-file=-
echo -n "your_whatsapp_verify_token" | gcloud secrets create whatsapp-verify-token --data-file=-

# Facebook Messenger Platform 密鑰
echo -n "your_facebook_app_id" | gcloud secrets create facebook-app-id --data-file=-
echo -n "your_facebook_app_secret" | gcloud secrets create facebook-app-secret --data-file=-
echo -n "your_facebook_page_access_token" | gcloud secrets create facebook-page-access-token --data-file=-
echo -n "your_facebook_verify_token" | gcloud secrets create facebook-verify-token --data-file=-

# Instagram Business Cloud API 密鑰
echo -n "your_instagram_app_id" | gcloud secrets create instagram-app-id --data-file=-
echo -n "your_instagram_app_secret" | gcloud secrets create instagram-app-secret --data-file=-
echo -n "your_instagram_page_access_token" | gcloud secrets create instagram-page-access-token --data-file=-
echo -n "your_instagram_verify_token" | gcloud secrets create instagram-verify-token --data-file=-
```

### 3. 配置檔案

所有包含敏感資訊的檔案都已加入 `.gitignore`：

```gitignore
# 敏感檔案
.env
.env.*
config/config.yml
config/ssl/*
*.key
*.crt
*.pem
service-account-key.json
*-credentials.json
```

## 🔒 部署安全性

### 1. Google Cloud Run

使用 Secret Manager 注入敏感資訊：

```yaml
env:
- name: OPENAI_API_KEY
  valueFrom:
    secretKeyRef:
      name: openai-api-key
      key: latest
```

### 2. 服務帳號權限

遵循最小權限原則：

```bash
# 建立服務帳號
gcloud iam service-accounts create chatgpt-line-bot-sa \
    --description="ChatGPT Line Bot Service Account" \
    --display-name="ChatGPT Line Bot"

# 只授予必要權限
gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:chatgpt-line-bot-sa@PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

### 3. 網路安全

```bash
# 限制 Cloud Run 存取
gcloud run services update chatgpt-line-bot \
    --ingress=all \
    --region=asia-east1
```

## 🔐 SSL/TLS 憑證

### 1. 自簽憑證（僅限開發）

```bash
# 生成自簽憑證（開發用）
openssl req -x509 -newkey rsa:4096 -keyout config/ssl/private.key -out config/ssl/cert.crt -days 365 -nodes
```

### 2. 生產環境憑證

使用 Google Cloud Load Balancer 自動管理的 SSL 憑證：

```bash
gcloud compute ssl-certificates create chatgpt-line-bot-ssl \
    --domains=your-domain.com \
    --global
```

## 🚨 事件回應

### 如果敏感資訊意外洩露

1. **立即撤銷**受影響的 API 金鑰
2. **重新生成**新的金鑰和憑證
3. **更新** Secret Manager 中的值
4. **檢查** Git 歷史記錄是否需要清理
5. **監控**異常活動

### Git 歷史清理

如果敏感資訊已提交到 Git：

```bash
# 使用 git-filter-branch 移除敏感檔案
git filter-branch --force --index-filter \
    'git rm --cached --ignore-unmatch config/config.yml' \
    --prune-empty --tag-name-filter cat -- --all

# 強制推送清理後的歷史
git push origin --force --all
```

## 🔐 Web 測試介面安全性 (v2.0)

### 認證配置

新版本包含 Web 測試介面，需要妥善配置認證：

**生產環境設定**：
```bash
# 使用強密碼
export TEST_PASSWORD="$(openssl rand -base64 32)"

# 在 Secret Manager 中儲存
echo -n "$TEST_PASSWORD" | gcloud secrets create test-password --data-file=-
```

**安全最佳實踐**：
- ✅ 使用長度至少 16 字元的強密碼
- ✅ 定期更新測試密碼
- ✅ 考慮使用 IP 白名單限制存取
- ✅ 監控測試介面的使用情況
- ❌ 不要在配置檔案中明文儲存密碼

**Cloud Run 環境變數配置**：
```bash
gcloud run services update chatgpt-line-bot \
    --region=asia-east1 \
    --set-env-vars TEST_PASSWORD="$TEST_PASSWORD"
```

### Session 安全

- **Session 金鑰**: 使用隨機生成的強金鑰
- **過期時間**: 合理設定 session 過期時間
- **安全標頭**: 啟用 CSRF 保護和安全標頭

## 🔍 安全性檢查清單

在部署前請確認：

- [ ] 所有敏感檔案都在 `.gitignore` 中
- [ ] 沒有硬編碼的 API 金鑰或密碼
- [ ] 使用環境變數或 Secret Manager 管理敏感資訊
- [ ] 服務帳號權限最小化
- [ ] 啟用 HTTPS 和 SSL 憑證
- [ ] 定期輪換 API 金鑰
- [ ] 設定強密碼用於 Web 測試介面
- [ ] 配置測試介面認證環境變數
- [ ] 檢查 Session 安全配置
- [ ] 監控存取日誌

## 📊 安全性監控

設定以下監控警報：

```bash
# 異常 API 使用
gcloud logging sinks create security-sink \
    bigquery.googleapis.com/projects/PROJECT_ID/datasets/security_logs \
    --log-filter='protoPayload.methodName="google.cloud.secretmanager.v1.SecretManagerService.AccessSecretVersion"'
```

## 🆘 回報安全問題

如果發現安全漏洞，請：

1. **不要**在公開的 GitHub issue 中報告
2. 發送電子郵件至 security@your-domain.com
3. 提供詳細的漏洞資訊
4. 給予我們合理時間修復問題

## 📚 相關資源

- [Google Cloud Secret Manager](https://cloud.google.com/secret-manager/docs)
- [OpenAI API 安全性最佳實踐](https://platform.openai.com/docs/guides/safety-best-practices)
- [Line Bot 安全性指南](https://developers.line.biz/en/docs/messaging-api/building-bot/)
- [OWASP 安全性指南](https://owasp.org/www-project-top-ten/)

## 🔒 安全審計報告

### 已發現並修復的安全問題

#### 1. 輸入驗證不足
**問題**: 原本的 `/ask` 端點和 Line webhook 缺乏適當的輸入驗證
**修復**: 
- 新增 `InputValidator` 類別進行全面的輸入清理
- 實施長度限制、XSS 防護、危險模式檢測
- 驗證 Line 用戶 ID 格式
- WhatsApp webhook 實施 HMAC-SHA256 簽名驗證
- Messenger webhook 實施 HMAC-SHA1 簽名驗證

#### 2. 敏感資訊洩露風險
**問題**: 日誌可能記錄敏感資訊
**修復**:
- 實施 `SensitiveDataFilter` 自動過濾日誌中的敏感資料
- 使用正則表達式檢測和遮蔽 API 金鑰、token 等

#### 3. 缺乏速率限制
**問題**: 端點容易被濫用
**修復**:
- 實施 `RateLimiter` 類別
- 不同端點採用不同的速率限制策略
- 支援動態配置限制參數

#### 4. 測試端點缺乏保護
**問題**: `/chat` 和 `/ask` 端點在生產環境中暴露
**修復**:
- 新增多重認證機制（密碼、Basic Auth、Token）
- 實施 session 管理和 token 過期機制
- 在生產環境中要求認證才能存取

#### 5. 缺乏安全標頭
**問題**: HTTP 回應缺乏安全標頭
**修復**:
- 實施完整的安全標頭：CSP、HSTS、X-Frame-Options 等
- 根據環境（開發/生產）調整安全策略

#### 6. Webhook 簽名驗證改進
**問題**: 原本的簽名驗證可能有時序攻擊風險
**修復**:
- 使用 `hmac.compare_digest()` 進行安全比較
- 強化錯誤處理和日誌記錄
- WhatsApp: HMAC-SHA256 簽名驗證
- Messenger: HMAC-SHA1 簽名驗證
- Instagram: HMAC-SHA1 簽名驗證
- LINE: HMAC-SHA256 簽名驗證

#### 7. 依賴項版本未固定
**問題**: 使用最新版本可能引入安全漏洞
**修復**:
- 固定所有依賴項的版本範圍
- 選擇穩定且安全的版本

### 安全功能實施

#### 輸入驗證和清理
```python
class InputValidator:
    - sanitize_text(): HTML 編碼、危險模式移除
    - validate_user_id(): Line ID 格式驗證
    - validate_message_content(): 全面訊息驗證
```

#### 速率限制
```python
class RateLimiter:
    - 記憶體內速率限制
    - 自動清理過期記錄
    - 可配置限制參數
```

#### 認證系統
```python
class TestAuth:
    - 多重認證方式支援
    - Session 管理
    - Token 過期處理

class PlatformSecurityManager:
    - 統一平台簽名驗證
    - 多平台速率限制
    - 統一安全策略管理
```

#### 安全中間件
```python
class SecurityMiddleware:
    - 請求前檢查（速率限制、大小限制）
    - 回應後處理（安全標頭）
    - 可配置安全政策
```

### 配置化安全設定

所有安全設定都可透過環境變數配置：

```env
# 認證設定
TEST_AUTH_METHOD=simple_password
TEST_PASSWORD=secure_password

# 速率限制
GENERAL_RATE_LIMIT=60
TEST_ENDPOINT_RATE_LIMIT=10

# 內容限制
MAX_MESSAGE_LENGTH=5000
MAX_TEST_MESSAGE_LENGTH=1000

# 安全功能開關
ENABLE_SECURITY_HEADERS=true
LOG_SECURITY_EVENTS=true
```

## 📈 部署安全建議

### 生產環境設定
1. **設定強密碼**: 使用長且複雜的 `TEST_PASSWORD`
2. **啟用 HTTPS**: 確保所有通訊加密
3. **限制存取**: 考慮使用 VPN 或 IP 白名單
4. **監控日誌**: 定期檢查安全事件日誌
5. **定期更新**: 保持依賴項為最新安全版本

### 網路安全
- 使用 Cloud Run 的內建 DDoS 保護
- 啟用 Cloud Load Balancer 的安全功能
- 設定適當的防火牆規則

### 資料庫安全
- 使用 SSL 連線
- 最小權限原則
- 定期備份和災難恢復計畫

## 📊 安全性監控增強

### 日誌監控
- 速率限制觸發
- 認證失敗嘗試
- 異常請求模式
- 錯誤率監控

### 指標追蹤
- 請求頻率
- 錯誤率
- 回應時間
- 安全事件數量

## 🏛️ 合規性考量

### 資料保護
- 敏感資料自動遮蔽
- 日誌資料保留政策
- 用戶隱私保護

### 安全標準
- OWASP Top 10 威脅防護
- 安全開發生命週期 (SDLC)
- 定期安全審計

## 🚨 緊急回應程序

### 安全事件處理
1. **立即隔離**: 停用受影響的端點
2. **影響評估**: 確定資料洩露範圍
3. **修復行動**: 部署安全修補程式
4. **事後檢討**: 改進安全措施

### 聯繫方式
- 安全團隊：security@example.com
- 緊急聯絡：emergency@example.com

## 📋 擴展的安全檢查清單

### 部署前檢查
- [ ] 所有敏感檔案都在 `.gitignore` 中
- [ ] 沒有硬編碼的 API 金鑰或密碼
- [ ] 使用環境變數或 Secret Manager 管理敏感資訊
- [ ] 服務帳號權限最小化
- [ ] 啟用 HTTPS 和 SSL 憑證
- [ ] 定期輪換 API 金鑰
- [ ] 設定強密碼用於 Web 測試介面
- [ ] 配置測試介面認證環境變數
- [ ] 檢查 Session 安全配置
- [ ] 監控存取日誌
- [ ] 所有敏感資訊使用環境變數
- [ ] 安全標頭正確設定
- [ ] 速率限制已配置
- [ ] 認證機制已啟用
- [ ] 日誌過濾器正常運作

### 定期檢查
- [ ] 依賴項安全更新
- [ ] 存取日誌審查
- [ ] 安全配置驗證
- [ ] 備份和恢復測試
- [ ] 安全審計報告更新
- [ ] 緊急回應程序測試

---

**記住：安全性是一個持續的過程，不是一次性的設定。定期檢查和更新你的安全配置。**

## 📱 多平台安全考量

### Messenger 平台安全特殊考量

#### 1. Facebook App Secret 保護
- **必須**: 使用 Secret Manager 儲存 Facebook App Secret
- **禁止**: 在代碼中明文儲存 App Secret
- **輪替**: 定期更新 App Secret 和 Page Access Token

#### 2. Page Access Token 管理
- **範圍**: 確保 Page Access Token 只有必要的權限
- **過期**: 設定合理的 Token 過期時間
- **監控**: 監控 Token 使用情況和異常活動

#### 3. Webhook 驗證強化
```python
# Messenger 使用 HMAC-SHA1 驗證
def verify_messenger_signature(request_body: str, signature: str) -> bool:
    if not signature.startswith('sha1='):
        return False
    
    signature_hash = signature[5:]
    expected_signature = hmac.new(
        self.app_secret.encode('utf-8'),
        request_body.encode('utf-8'),
        hashlib.sha1
    ).hexdigest()
    
    return hmac.compare_digest(signature_hash, expected_signature)
```

#### 4. Echo 訊息過濾
- **自動過濾**: 自動忽略機器人本身發送的 echo 訊息
- **檢查機制**: 檢查 `is_echo` 標記防止訊息迴圈
- **日誌記錄**: 記錄 echo 訊息過濾情況用於除錯

#### 5. 音訊訊息安全
- **下載驗證**: 驗證媒體 URL 的合法性
- **檔案類型**: 檢查下載的音訊檔案類型
- **大小限制**: 設定合理的檔案大小限制
- **轉錄安全**: 使用安全的語音轉文字服務

#### 6. 用戶資訊私隱
- **最小資料**: 僅取得必要的用戶資訊
- **資料保護**: 不儲存非必要的用戶資訊
- **資料加密**: 敏感用戶資料加密儲存
- **存取日誌**: 記錄用戶資料存取日誌

### Instagram 平台安全特殊考量

#### 1. Instagram App Secret 保護
- **必須**: 使用 Secret Manager 儲存 Instagram App Secret
- **禁止**: 在代碼中明文儲存 App Secret
- **輪替**: 定期更新 App Secret 和 Page Access Token

#### 2. Page Access Token 管理
- **範圍**: 確保 Page Access Token 只有必要的權限
- **商業帳號**: 確認 Instagram 帳號已連接到 Facebook 頁面
- **監控**: 監控 Token 使用情況和異常活動

#### 3. Webhook 驗證強化
```python
# Instagram 使用 HMAC-SHA1 驗證（與 Messenger 相同）
def verify_instagram_signature(request_body: str, signature: str) -> bool:
    if not signature.startswith('sha1='):
        return False
    
    signature_hash = signature[5:]
    expected_signature = hmac.new(
        self.app_secret.encode('utf-8'),
        request_body.encode('utf-8'),
        hashlib.sha1
    ).hexdigest()
    
    return hmac.compare_digest(signature_hash, expected_signature)
```

#### 4. Story 回覆安全
- **權限檢查**: 確認只能回覆提及商業帳號的 Story
- **時間窗口**: 確保在24小時窗口內回覆
- **內容過濾**: 對 Story 回覆內容進行適當過濾
- **頻率限制**: 防止 Story 回覆功能被濫用

#### 5. 音訊訊息安全
- **下載驗證**: 驗證媒體 URL 的合法性
- **檔案類型**: 檢查下載的音訊檔案類型
- **大小限制**: 設定合理的檔案大小限制
- **轉錄安全**: 使用安全的語音轉文字服務

#### 6. 用戶資訊私隱
- **最小資料**: 僅取得必要的用戶資訊
- **資料保護**: 不儲存非必要的用戶資訊
- **資料加密**: 敏感用戶資料加密儲存
- **存取日誌**: 記錄用戶資料存取日誌

#### 7. Instagram Basic Display API 安全
- **權限最小化**: 只申請必要的 Instagram API 權限
- **審核遵循**: 遵循 Meta App Review 的安全要求
- **資料使用**: 按照 Instagram 平台政策使用用戶資料
- **隱私合規**: 確保符合各地隱私法規要求

### WhatsApp 平台安全特殊考量

#### 1. Business Verification
- **身份驗證**: 完成 Meta Business Account 驗證
- **審核流程**: 遵循 WhatsApp Business API 審核要求
- **文件保管**: 安全保管相關審核文件

#### 2. Phone Number Security
- **號碼保護**: 保護 WhatsApp 電話號碼不被濫用
- **雙重驗證**: 啟用電話號碼的雙重驗證
- **定期審查**: 定期檢查電話號碼使用情況

#### 3. Media Upload Security
- **檔案類型**: 限制允許上傳的媒體檔案類型
- **大小限制**: 設定合理的檔案大小限制
- **掃描檢查**: 對上傳檔案進行惡意軟體掃描
- **內容過濾**: 過濾不適當或違法內容

### 多平台統一安全策略

#### 1. 統一認證管理
```python
# 統一的平台認證檢查
class PlatformSecurityManager:
    def verify_platform_signature(self, platform: str, body: str, signature: str) -> bool:
        if platform == "line":
            return self.verify_line_signature(body, signature)
        elif platform == "whatsapp":
            return self.verify_whatsapp_signature(body, signature)
        elif platform == "messenger":
            return self.verify_messenger_signature(body, signature)
        elif platform == "instagram":
            return self.verify_instagram_signature(body, signature)
        else:
            return False
```

#### 2. 統一速率限制
- **平台獨立**: 每個平台獨立的速率限制
- **全局限制**: 全局累計速率限制
- **動態調整**: 根據平台特性調整限制

#### 3. 統一日誌記錄
- **結構化日誌**: 使用結構化格式記錄所有平台事件
- **安全事件**: 統一記錄安全相關事件
- **敏感資料過濾**: 自動過濾所有平台的敏感資料

#### 4. 統一監控和警告
- **平台狀態**: 監控所有平台的連線狀態
- **異常檢查**: 檢查異常訊息模式
- **安全警告**: 統一的安全事件警告系統

### 部署安全檢查清單（更新）

#### Messenger 特定檢查
- [ ] Facebook App ID 和 App Secret 在 Secret Manager 中安全儲存
- [ ] Page Access Token 權限最小化
- [ ] Webhook URL 使用 HTTPS
- [ ] HMAC-SHA1 簽名驗證正常運作
- [ ] Echo 訊息過濾機制正常
- [ ] 音訊下載和處理安全
- [ ] 用戶資訊取得權限檢查
- [ ] Graph API 請求速率限制
- [ ] Facebook 頁面管理員權限
- [ ] 安全日誌記錄和監控

#### WhatsApp 特定檢查
- [ ] WhatsApp Business Account 驗證完成
- [ ] Access Token 和 App Secret 安全儲存
- [ ] 電話號碼安全管理
- [ ] HMAC-SHA256 簽名驗證
- [ ] 24小時訊息窗口限制理解
- [ ] 媒體檔案上傳安全檢查
- [ ] Meta Business API 率限管理
- [ ] Webhook 端點可公開存取
- [ ] SSL/TLS 憑證有效性
- [ ] 審核程序遵循和文件保存

#### Instagram 特定檢查
- [ ] Instagram App ID 和 App Secret 在 Secret Manager 中安全儲存
- [ ] Instagram 商業帳號已連接到 Facebook 頁面
- [ ] Page Access Token 權限最小化
- [ ] Webhook URL 使用 HTTPS
- [ ] HMAC-SHA1 簽名驗證正常運作
- [ ] Story 回覆權限和時間窗口檢查
- [ ] 音訊下載和處理安全
- [ ] 用戶資訊取得權限檢查
- [ ] Instagram Basic Display API 權限最小化
- [ ] Meta App Review 流程遵循
- [ ] 安全日誌記錄和監控
- [ ] Graph API 請求速率限制

#### 多平台統一檢查
- [ ] 所有平台的認證資料都在 Secret Manager
- [ ] 統一的安全中間件配置
- [ ] 所有 webhook 都使用 HTTPS
- [ ] 速率限制和監控系統運作正常
- [ ] 日誌過濾器過濾所有平台的敏感資料
- [ ] 各平台的錯誤處理和回復機制
- [ ] 統一的安全事件警告和通知
- [ ] 在線健康檢查包含所有平台
- [ ] 定期安全審計和測試
- [ ] 緊急回應計劃包含所有平台

**最後安全審計**: 2024年6月30日  
**下次安全審計**: 2024年9月30日  
**Messenger 平台審計**: 2024年7月11日  
**Instagram 平台審計**: 2024年7月11日