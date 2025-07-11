# 🔐 安全性指南

本專案為開源軟體，包含敏感的 API 金鑰和憑證配置。請務必遵循以下安全性準則。

## ⚠️  重要警告

**絕對不要**在任何情況下將以下敏感資訊提交到版本控制系統：

- API 金鑰（OpenAI、Line Bot、WhatsApp 等）
- 資料庫密碼
- SSL 憑證和私鑰
- Service Account 金鑰
- WhatsApp Business API 憑證
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

#### 6. Line Webhook 簽名驗證改進
**問題**: 原本的簽名驗證可能有時序攻擊風險
**修復**:
- 使用 `hmac.compare_digest()` 進行安全比較
- 強化錯誤處理和日誌記錄

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

**最後安全審計**: 2024年6月30日  
**下次安全審計**: 2024年9月30日