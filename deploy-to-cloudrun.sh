#!/bin/bash

# 設定變數
PROJECT_ID="your-project-id"  # 請替換為你的專案 ID
REGION="asia-east1"           # 或你偏好的地區
SERVICE_NAME="chatgpt-line-bot"
IMAGE_NAME="chatgpt-line-bot"

# 顏色代碼
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 開始部署 ChatGPT Line Bot 到 Google Cloud Run${NC}"

# 檢查是否已登入 gcloud
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q "@"; then
    echo -e "${RED}❌ 請先登入 Google Cloud: gcloud auth login${NC}"
    exit 1
fi

# 設定專案
echo -e "${YELLOW}📋 設定 Google Cloud 專案...${NC}"
gcloud config set project $PROJECT_ID

# 啟用必要的 API
echo -e "${YELLOW}🔧 啟用必要的 Google Cloud API...${NC}"
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    secretmanager.googleapis.com \
    sql-component.googleapis.com \
    sqladmin.googleapis.com

# 建立 Secret Manager 密鑰（如果不存在）
echo -e "${YELLOW}🔐 檢查 Secret Manager 密鑰...${NC}"

create_secret_if_not_exists() {
    local secret_name=$1
    local secret_value=$2
    
    if ! gcloud secrets describe $secret_name --quiet >/dev/null 2>&1; then
        echo -e "${YELLOW}建立密鑰: $secret_name${NC}"
        echo -n "$secret_value" | gcloud secrets create $secret_name --data-file=-
    else
        echo -e "${GREEN}密鑰已存在: $secret_name${NC}"
    fi
}

# 從環境變數或提示輸入敏感資訊
echo -e "${YELLOW}🔐 配置敏感資訊...${NC}"
echo -e "${YELLOW}建議：將敏感資訊設為環境變數，例如：${NC}"
echo "export OPENAI_API_KEY='your_key_here'"
echo "export LINE_CHANNEL_ACCESS_TOKEN='your_token_here'"
echo ""

OPENAI_KEY=${OPENAI_API_KEY:-$(read -p "請輸入 OpenAI API Key: " && echo $REPLY)}
LINE_TOKEN=${LINE_CHANNEL_ACCESS_TOKEN:-$(read -p "請輸入 Line Channel Access Token: " && echo $REPLY)}
LINE_SECRET=${LINE_CHANNEL_SECRET:-$(read -p "請輸入 Line Channel Secret: " && echo $REPLY)}
DB_HOST=${DB_HOST:-$(read -p "請輸入資料庫主機地址: " && echo $REPLY)}
DB_USER=${DB_USER:-$(read -p "請輸入資料庫使用者名稱: " && echo $REPLY)}
DB_PASSWORD=${DB_PASSWORD:-$(read -s -p "請輸入資料庫密碼: " && echo $REPLY && echo)}
DB_NAME=${DB_NAME:-$(read -p "請輸入資料庫名稱: " && echo $REPLY)}

create_secret_if_not_exists "openai-api-key" "$OPENAI_KEY"
create_secret_if_not_exists "line-channel-access-token" "$LINE_TOKEN"
create_secret_if_not_exists "line-channel-secret" "$LINE_SECRET"
create_secret_if_not_exists "db-host" "$DB_HOST"
create_secret_if_not_exists "db-user" "$DB_USER"
create_secret_if_not_exists "db-password" "$DB_PASSWORD"
create_secret_if_not_exists "db-name" "$DB_NAME"

# 建立和推送 Docker 映像
echo -e "${YELLOW}🐳 建立 Docker 映像...${NC}"
gcloud builds submit --tag gcr.io/$PROJECT_ID/$IMAGE_NAME -f Dockerfile.cloudrun .

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Docker 映像建立失敗${NC}"
    exit 1
fi

# 部署到 Cloud Run
echo -e "${YELLOW}☁️  部署到 Cloud Run...${NC}"

# 更新 cloudrun-service.yaml 中的專案 ID
sed -i.bak "s/YOUR_PROJECT_ID/$PROJECT_ID/g" cloudrun-service.yaml

# 部署服務
gcloud run services replace cloudrun-service.yaml --region=$REGION

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Cloud Run 部署失敗${NC}"
    exit 1
fi

# 取得服務 URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")

echo -e "${GREEN}✅ 部署成功！${NC}"
echo -e "${GREEN}🌐 服務 URL: $SERVICE_URL${NC}"
echo -e "${GREEN}🔗 Webhook URL: $SERVICE_URL/webhooks/line${NC}"

# 設定 IAM 權限（允許未經身份驗證的訪問）
echo -e "${YELLOW}🔒 設定 IAM 權限...${NC}"
gcloud run services add-iam-policy-binding $SERVICE_NAME \
    --region=$REGION \
    --member="allUsers" \
    --role="roles/run.invoker"

echo -e "${GREEN}🎉 部署完成！請將 Webhook URL 設定到 Line Developers Console${NC}"
echo -e "${YELLOW}📝 記得設定以下內容：${NC}"
echo "1. Line Developers Console 中的 Webhook URL: $SERVICE_URL/webhooks/line"
echo "2. 啟用 Webhook"
echo "3. 測試 Bot 功能"

# 恢復原始檔案
mv cloudrun-service.yaml.bak cloudrun-service.yaml 2>/dev/null || true