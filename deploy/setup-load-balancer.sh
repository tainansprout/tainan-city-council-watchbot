#!/bin/bash

cd "$(dirname "$0")"
pushd ..

# 設定變數
PROJECT_ID="your-project-id"  # 請替換為你的專案 ID
REGION="asia-east1"
SERVICE_NAME="chatgpt-line-bot"
LB_NAME="chatgpt-line-bot-lb"
DOMAIN_NAME="your-domain.com"  # 請替換為你的網域

# 顏色代碼
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}⚖️  設定 Google Cloud Load Balancer${NC}"

# 1. 建立 NEG (Network Endpoint Group) 指向 Cloud Run
echo -e "${YELLOW}📡 建立 Network Endpoint Group...${NC}"
gcloud compute network-endpoint-groups create $SERVICE_NAME-neg \
    --region=$REGION \
    --network-endpoint-type=serverless \
    --cloud-run-service=$SERVICE_NAME

# 2. 建立後端服務
echo -e "${YELLOW}🔧 建立後端服務...${NC}"
gcloud compute backend-services create $LB_NAME-backend \
    --global \
    --load-balancing-scheme=EXTERNAL_MANAGED

# 3. 將 NEG 加入後端服務
gcloud compute backend-services add-backend $LB_NAME-backend \
    --global \
    --network-endpoint-group=$SERVICE_NAME-neg \
    --network-endpoint-group-region=$REGION

# 4. 建立 URL Map
echo -e "${YELLOW}🗺️  建立 URL Map...${NC}"
gcloud compute url-maps create $LB_NAME-url-map \
    --default-service=$LB_NAME-backend

# 5. 建立 SSL 憑證（需要網域）
if [ "$DOMAIN_NAME" != "your-domain.com" ]; then
    echo -e "${YELLOW}🔐 建立 SSL 憑證...${NC}"
    gcloud compute ssl-certificates create $LB_NAME-ssl-cert \
        --domains=$DOMAIN_NAME \
        --global
    
    # 6. 建立 HTTPS 代理
    echo -e "${YELLOW}🔒 建立 HTTPS 代理...${NC}"
    gcloud compute target-https-proxies create $LB_NAME-https-proxy \
        --url-map=$LB_NAME-url-map \
        --ssl-certificates=$LB_NAME-ssl-cert
    
    # 7. 建立全域轉發規則
    echo -e "${YELLOW}📍 建立全域轉發規則...${NC}"
    gcloud compute forwarding-rules create $LB_NAME-forwarding-rule \
        --global \
        --target-https-proxy=$LB_NAME-https-proxy \
        --ports=443
    
    # 取得 Load Balancer IP
    LB_IP=$(gcloud compute forwarding-rules describe $LB_NAME-forwarding-rule --global --format="value(IPAddress)")
    
    echo -e "${GREEN}✅ Load Balancer 設定完成！${NC}"
    echo -e "${GREEN}🌐 Load Balancer IP: $LB_IP${NC}"
    echo -e "${YELLOW}📝 請將你的網域 $DOMAIN_NAME 的 A 記錄指向 $LB_IP${NC}"
else
    echo -e "${YELLOW}⚠️  請在腳本中設定你的網域名稱以啟用 HTTPS${NC}"
fi

# 8. 設定 CDN (Cloud CDN)
echo -e "${YELLOW}🚀 啟用 Cloud CDN...${NC}"
gcloud compute backend-services update $LB_NAME-backend \
    --global \
    --enable-cdn \
    --cache-mode=CACHE_ALL_STATIC \
    --default-ttl=3600 \
    --max-ttl=86400 \
    --client-ttl=3600

echo -e "${GREEN}🎉 Load Balancer 和 CDN 設定完成！${NC}"