# 台南議會觀測機器人

中文 | [English](README.en.md)

本專案是使用 Line 作為前端，連接 OpenAI Assistant API 的聊天機器人。機器人將部署在 Google Cloud Run 上，並使用 Google Cloud SQL 來存取聊天線程 ID。

## 目錄

- [前置準備](#前置準備)
- [設定 OpenAI Assistant API](#設定-openai-assistant-api)
- [設定 Line Bot](#設定-line-bot)
- [設定環境變數](#設定環境變數)
- [設定 Google Cloud SQL](#設定-google-cloud-sql)
- [完成設定檔](#完成設定檔)
- [部署到 Google Cloud Run](#部署到-google-cloud-run)
- [測試程式運作](#測試程式運作)

## 前置準備

- 一個已啟用計費的 Google Cloud Platform 帳戶
- OpenAI API 訪問權限
- Line Developers 帳戶

## 取得 OpenAI 給的 API Token：

1. [OpenAI Platform](https://platform.openai.com/) 平台中註冊/登入帳號

2. 左上方有一個頭像，在那邊建立一個 Project。

3. 進入 Project 後，於左邊尋找 Project → API Key

4. 點選右上角的 `+ Create` ，即可生成 OpenAI 的 API Token。

## 設定 OpenAI Assistant API

1. **建立Assistant**

   - 進入專案後，請在上方點選「Playground」，之後在介面左邊點選「Assistants」，進入OpenAI Assistant API的介面，接著建立一個Assistant。

2. **上傳您需要作為資料庫之檔案**

   - 請在 Assistant 介面上設定名稱與System instructions，作為機器人預設的system prompt。Model建議選取`gpt-4o`，Temperature建議設定為`0.01`。
   - 接著，在 Tools →  File Search中，點選 `+ FIles` 上傳你要作為資料庫的檔案。

3. **在 Playground 測試可用性**

   - 前往 [OpenAI Playground](https://platform.openai.com/playground)
   - 測試您的 Assistant 是否能正常運作。

4. **記錄 assistant_id**

   - 在 Assistant 名字下方有一串文字，即為 `assistant_id`，請記錄下來，稍後會用到。

## 設定 Line Bot

1. **建立 Line Bot**

   - 登入 [Line Developers Console](https://developers.line.biz/console/)
   - 建立新的 Provider 和 Channel（Messaging API）

2. **取得 Channel 資訊**

   - 在 Channel 設定中，取得 `Channel Access Token` 和 `Channel Secret`
   - 在 `Basic Settings` 下方，有一個 `Channel Secret` →  按下 `Issue`，生成後即為 `channel_secret`。
   - 在 `Messaging API` 下方，有一個 `Channel access token` →  按下 `Issue`，生成後即為 `channel_access_token`。

3. **設定 Webhook URL**

   - 將 Webhook URL 設定為稍後部署的 Google Cloud Run 地址（可在部署完成後更新）
   - 啟用 Webhook，將「使用 Webhook」開關切換為開啟

## 設定 Google Cloud SQL

1. **建立 Cloud SQL 個體**

   - 前往 [Cloud SQL Instances](https://console.cloud.google.com/sql/instances)
   - 點選 **建立執行個體**，選擇您需要的資料庫（例如 PostgreSQL）

2. **配置執行個體**

   - 設定執行個體名稱、密碼等資訊
   - 建立連線操作用之帳戶，並記錄使用者名稱與密碼
   - 建立資料庫
   - 使用Cloud SQL Studio於資料庫中執行以下SQL指令以建立Table
    ```sql
    CREATE TABLE user_thread_table (
        user_id VARCHAR(255) PRIMARY KEY,
        thread_id VARCHAR(255),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    ```

3. **取得連線資訊**

   - 在執行個體建立後，記下以下資訊：

     - 執行個體連線名稱（Instance Connection Name）
     - 主機（Host）
     - 埠號（Port）
     - 資料庫名稱（Database Name）
     - 使用者名稱（User）
     - 密碼（Password）

4. **取得 SSL 憑證**

   - 進入執行個體詳情頁面
   - 在 **連線** 標籤下，啟用 SSL 連線
   - 下載：

     - 服務器 CA 憑證（Server CA Certificate）
     - 用戶端憑證（Client Certificate）
     - 用戶端金鑰（Client Key）
   - 執行以下指令轉換以上憑證與金鑰

    ```bash
    openssl x509 -in client-cert.pem -out ssl-cert.crt # Server CA Certificate
    openssl x509 -in server-ca.pem -out ca-cert.crt # Client Certificate
    openssl rsa -in client-key.pem -out ssl-key.key # Client Key
    ```
   - 把 `ssl-cert.crt`、`ca-cert.crt`、`ssl-key.key` 這三個檔案複製到 `config/ssl/`下面

## 完成設定檔

請準備以下資訊：

- `channel_access_token`
- `channel_secret`
- `openai_api_key`
- `assistant_id`

將 `config/config.yml.example` 複製成 `config/config.yml`，內容修改如下：

```yaml
line:
  channel_access_token: YOUR_CHANNEL_ACCESS_TOKEN
  channel_secret: YOUR_CHANNEL_SECRET

openai:
  api_key: YOUR_OPENAI_API_KEY
  assistant_id: YOUR_ASSISTANT_ID

db:
  host: YOUR_DB_HOST
  port: 5432
  db_name: YOUR_DB_NAME
  user: YOUR_DB_USER
  password: YOUR_DB_PASSWORD
  sslmode: verify-ca
  sslrootcert: config/ssl/ca-cert.crt
  sslcert: config/ssl/client.crt
  sslkey: config/ssl/client.key
```

## 部署到 Google Cloud Run

1. **設定Google Cloud Console**

   - 使用以下指令設定Google Cloud認證與專案
     ```bash
     gcloud auth login
     gcloud config set project {your-project-id}
     ```

2. **建立容器映像**

   - 使用以下指令建置並推送映像到 Google Container Registry：

     ```bash
     gcloud builds submit --tag gcr.io/{your-project-id}/{your-image-name}
     ```

3. **部署到 Cloud Run**

   - 使用以下指令部署：

     ```bash
     gcloud run deploy {your-service-name} \
       --image gcr.io/{your-project-id}/{your-image-name} \
       --platform managed \
       --port 8080
       --memory 2G
       --timeout=2m
       --region {your-region}
     ```

   - 請將以上指令中的佔位符替換為您的實際資訊。

4. **測試部署結果**

   - 部署後，會回傳一個Service URL，如 https://chatgpt-line-bot-****.run.app ，請記錄下來。

5. **設定 Webhook URL**

   - 進入Line Bot設定介面，將 Webhook URL 設定 Service URL 地址。
   - 啟用 Webhook，將「使用 Webhook」開關切換為開啟。
   - 點選 Verify，看是否回傳成功。

## 測試程式運作

1. **訪問 Chat 端點**

   - 前往 Service URL，如 `https://{your-cloud-run-url}/chat`，確認應用程式是否運行正常。

2. **透過 Line 測試**

   - 向您的 Line Bot 發送訊息，測試完整功能。

3. **檢查 Log**

   - 如果出現問題，使用 `gcloud` 或 Google Cloud Console 來檢查Log

## 注意事項

- 確保所有敏感資訊只放在 `config/ssl/` 當中及 `config/config.yml`。
- 如有需要，使用 Google Secret Manager 來管理秘密。
- 遵循安全和合規的最佳實踐。

## 捐款支持

本專案由台南新芽進行，若您希望能支持本專案，請[捐款贊助台南新芽](https://bit.ly/3RBvPyZ)。

## 特別感謝

本專案 Fork 自 [ExplainThis 的 ChatGPT-Line-Bot](https://github.com/TheExplainthis/ChatGPT-Line-Bot) 。特此致謝。

## 授權
[MIT](LICENSE)
