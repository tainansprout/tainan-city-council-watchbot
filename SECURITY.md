# 🔐 安全性指南

本專案為開源軟體，包含敏感的 API 金鑰和憑證配置。請務必遵循以下安全性準則。

## ⚠️  重要警告

**絕對不要**在任何情況下將以下敏感資訊提交到版本控制系統：

- API 金鑰（OpenAI、Line Bot 等）
- 資料庫密碼
- SSL 憑證和私鑰
- Service Account 金鑰
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

## 🔍 安全性檢查清單

在部署前請確認：

- [ ] 所有敏感檔案都在 `.gitignore` 中
- [ ] 沒有硬編碼的 API 金鑰或密碼
- [ ] 使用環境變數或 Secret Manager 管理敏感資訊
- [ ] 服務帳號權限最小化
- [ ] 啟用 HTTPS 和 SSL 憑證
- [ ] 定期輪換 API 金鑰
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

---

**記住：安全性是一個持續的過程，不是一次性的設定。定期檢查和更新你的安全配置。**