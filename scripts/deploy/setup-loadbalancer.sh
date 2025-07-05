#!/bin/bash

# 移動到腳本所在目錄，然後移動到項目根目錄
cd "$(dirname "${BASH_SOURCE[0]}")"
pushd ../.. > /dev/null
PROJECT_ROOT="$(pwd)"
popd > /dev/null

# 載入環境變數配置
if [ -f "$PROJECT_ROOT/config/deploy/.env" ]; then
    echo "載入環境變數配置..."
    set -o allexport
    source "$PROJECT_ROOT/config/deploy/.env"
    set +o allexport
else
    echo "警告: 找不到 $PROJECT_ROOT/config/deploy/.env 檔案"
    echo "請複製 $PROJECT_ROOT/config/deploy/.env.example 為 $PROJECT_ROOT/config/deploy/.env 並填入實際的值"
    exit 1
fi

# 驗證必要的環境變數
required_vars=("PROJECT_ID" "REGION" "SERVICE_NAME" "DOMAIN_NAME" "LOAD_BALANCER_NAME")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "錯誤: 環境變數 $var 未設定"
        exit 1
    fi
done

# 列出所需環境變數及其值，並確認是否繼續
echo "請確認以下環境變數設定："
for var in "${required_vars[@]}"; do
    echo "  $var=${!var}"
done
read -p "請確認是否繼續執行 (y/N): " confirm
if [[ ! $confirm =~ ^[Yy]$ ]]; then
    echo "已取消腳本執行"
    exit 1
fi

# 顏色代碼
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🌐 設定 Google Cloud Load Balancer 和 CDN${NC}"

# 檢查是否已登入 gcloud
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q "@"; then
    echo -e "${RED}❌ 請先登入 Google Cloud: gcloud auth login${NC}"
    exit 1
fi

# 設定專案
echo -e "${YELLOW}📋 設定 Google Cloud 專案...${NC}"
gcloud config set project $PROJECT_ID

# 啟用必要的 API
echo -e "${YELLOW}🔧 啟用 Load Balancer API...${NC}"
gcloud services enable compute.googleapis.com

# 1. 建立 Network Endpoint Group (NEG) 指向 Cloud Run 服務
echo -e "${YELLOW}🔗 建立 Network Endpoint Group...${NC}"
gcloud compute network-endpoint-groups create $SERVICE_NAME-neg \
    --region=$REGION \
    --network-endpoint-type=serverless \
    --cloud-run-service=$SERVICE_NAME

# 2. 建立後端服務
echo -e "${YELLOW}⚙️  建立後端服務...${NC}"
gcloud compute backend-services create $SERVICE_NAME-backend \
    --global \
    --load-balancing-scheme=EXTERNAL_MANAGED \
    --protocol=HTTPS

# 3. 將 NEG 添加到後端服務
echo -e "${YELLOW}🔌 將 NEG 添加到後端服務...${NC}"
gcloud compute backend-services add-backend $SERVICE_NAME-backend \
    --global \
    --network-endpoint-group=$SERVICE_NAME-neg \
    --network-endpoint-group-region=$REGION

# 4. 建立 URL 映射
echo -e "${YELLOW}🗺️  建立 URL 映射...${NC}"
gcloud compute url-maps create $SERVICE_NAME-urlmap \
    --default-service=$SERVICE_NAME-backend

# 5. 建立 SSL 憑證（管理憑證）
echo -e "${YELLOW}🔒 建立 SSL 憑證...${NC}"
gcloud compute ssl-certificates create $SERVICE_NAME-ssl \
    --domains=$DOMAIN_NAME \
    --global

# 6. 建立 HTTPS 代理
echo -e "${YELLOW}🛡️  建立 HTTPS 代理...${NC}"
gcloud compute target-https-proxies create $SERVICE_NAME-https-proxy \
    --url-map=$SERVICE_NAME-urlmap \
    --ssl-certificates=$SERVICE_NAME-ssl

# 7. 建立全球轉發規則
echo -e "${YELLOW}⚡ 建立轉發規則...${NC}"
gcloud compute forwarding-rules create $SERVICE_NAME-forwarding-rule \
    --global \
    --target-https-proxy=$SERVICE_NAME-https-proxy \
    --ports=443

# 8. 取得 Load Balancer IP
LB_IP=$(gcloud compute forwarding-rules describe $SERVICE_NAME-forwarding-rule --global --format="value(IPAddress)")

echo -e "${GREEN}✅ Load Balancer 設定完成！${NC}"
echo -e "${GREEN}🌐 Load Balancer IP: $LB_IP${NC}"
echo -e "${YELLOW}📝 請設定以下 DNS 記錄：${NC}"
echo "  $DOMAIN_NAME A $LB_IP"
echo ""

# 9. 設定 Cloud CDN（可選）
echo -e "${YELLOW}💾 是否要啟用 Cloud CDN？ (y/n)${NC}"
read -r enable_cdn

if [[ $enable_cdn =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}🚀 啟用 Cloud CDN...${NC}"
    
    # 更新後端服務以啟用 CDN
    gcloud compute backend-services update $SERVICE_NAME-backend \
        --global \
        --enable-cdn \
        --cache-mode=CACHE_ALL_STATIC \
        --default-ttl=3600 \
        --max-ttl=86400 \
        --client-ttl=3600
    
    echo -e "${GREEN}✅ Cloud CDN 已啟用${NC}"
else
    echo -e "${YELLOW}⏭️  跳過 CDN 設定${NC}"
fi

# 10. 建立健康檢查
echo -e "${YELLOW}🏥 建立健康檢查...${NC}"
gcloud compute health-checks create http $SERVICE_NAME-health-check \
    --port=8080 \
    --request-path=/health \
    --check-interval=30s \
    --timeout=10s \
    --healthy-threshold=2 \
    --unhealthy-threshold=3

# 將健康檢查添加到後端服務
gcloud compute backend-services update $SERVICE_NAME-backend \
    --global \
    --health-checks=$SERVICE_NAME-health-check

echo -e "${GREEN}🎉 完整的 Load Balancer 設定完成！${NC}"
echo -e "${YELLOW}📋 設定摘要：${NC}"
echo "1. Load Balancer IP: $LB_IP"
echo "2. SSL 憑證會在 DNS 設定完成後自動驗證"
echo "3. 健康檢查端點: /health"
echo "4. CDN 已啟用（如果選擇）"
echo ""
echo -e "${YELLOW}⚠️  注意事項：${NC}"
echo "1. 請將你的網域的 DNS A 記錄指向 $LB_IP"
echo "2. SSL 憑證驗證可能需要幾分鐘到幾小時"
echo "3. 完整生效時間約為 10-15 分鐘"
echo "4. 建議設定 monitoring 和 alerting"

# 建立清理腳本
cat > cleanup-loadbalancer.sh << 'EOF'
#!/bin/bash

# Load Balancer 清理腳本
PROJECT_ID="your-project-id"
SERVICE_NAME="chatgpt-line-bot"
REGION="asia-east1"

echo "🗑️  清理 Load Balancer 資源..."

# 刪除轉發規則
gcloud compute forwarding-rules delete $SERVICE_NAME-forwarding-rule --global --quiet

# 刪除 HTTPS 代理
gcloud compute target-https-proxies delete $SERVICE_NAME-https-proxy --quiet

# 刪除 SSL 憑證
gcloud compute ssl-certificates delete $SERVICE_NAME-ssl --quiet --global

# 刪除 URL 映射
gcloud compute url-maps delete $SERVICE_NAME-urlmap --quiet

# 刪除後端服務
gcloud compute backend-services delete $SERVICE_NAME-backend --global --quiet

# 刪除健康檢查
gcloud compute health-checks delete $SERVICE_NAME-health-check --quiet

# 刪除 NEG
gcloud compute network-endpoint-groups delete $SERVICE_NAME-neg --region=$REGION --quiet

echo "✅ 清理完成"
EOF

chmod +x cleanup-loadbalancer.sh

echo -e "${GREEN}📄 已建立清理腳本: cleanup-loadbalancer.sh${NC}"