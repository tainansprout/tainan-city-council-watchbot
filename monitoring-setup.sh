#!/bin/bash

# 設定變數
PROJECT_ID="your-project-id"
REGION="asia-east1"
SERVICE_NAME="chatgpt-line-bot"

# 顏色代碼
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}📊 設定 Google Cloud 監控和警報${NC}"

# 1. 啟用 Cloud Monitoring API
echo -e "${YELLOW}🔧 啟用監控 API...${NC}"
gcloud services enable monitoring.googleapis.com
gcloud services enable logging.googleapis.com

# 2. 建立警報政策
echo -e "${YELLOW}🚨 建立警報政策...${NC}"

# CPU 使用率警報
cat > cpu-alert-policy.yaml << EOF
displayName: "Cloud Run CPU 使用率過高"
conditions:
  - displayName: "CPU 使用率 > 80%"
    conditionThreshold:
      filter: 'resource.type="cloud_run_revision" AND resource.labels.service_name="$SERVICE_NAME"'
      comparison: COMPARISON_GREATER_THAN
      thresholdValue: 0.8
      duration: 300s
      aggregations:
        - alignmentPeriod: 60s
          perSeriesAligner: ALIGN_MEAN
          crossSeriesReducer: REDUCE_MEAN
          groupByFields:
            - resource.labels.service_name
notificationChannels: []
alertStrategy:
  autoClose: 604800s
enabled: true
EOF

# 記憶體使用率警報  
cat > memory-alert-policy.yaml << EOF
displayName: "Cloud Run 記憶體使用率過高"
conditions:
  - displayName: "記憶體使用率 > 85%"
    conditionThreshold:
      filter: 'resource.type="cloud_run_revision" AND resource.labels.service_name="$SERVICE_NAME"'
      comparison: COMPARISON_GREATER_THAN
      thresholdValue: 0.85
      duration: 300s
      aggregations:
        - alignmentPeriod: 60s
          perSeriesAligner: ALIGN_MEAN
          crossSeriesReducer: REDUCE_MEAN
          groupByFields:
            - resource.labels.service_name
notificationChannels: []
alertStrategy:
  autoClose: 604800s
enabled: true
EOF

# 錯誤率警報
cat > error-rate-alert-policy.yaml << EOF
displayName: "Cloud Run 錯誤率過高"
conditions:
  - displayName: "5xx 錯誤率 > 5%"
    conditionThreshold:
      filter: 'resource.type="cloud_run_revision" AND resource.labels.service_name="$SERVICE_NAME"'
      comparison: COMPARISON_GREATER_THAN
      thresholdValue: 0.05
      duration: 300s
      aggregations:
        - alignmentPeriod: 60s
          perSeriesAligner: ALIGN_RATE
          crossSeriesReducer: REDUCE_MEAN
          groupByFields:
            - resource.labels.service_name
notificationChannels: []
alertStrategy:
  autoClose: 604800s
enabled: true
EOF

# 建立警報政策
gcloud alpha monitoring policies create --policy-from-file=cpu-alert-policy.yaml
gcloud alpha monitoring policies create --policy-from-file=memory-alert-policy.yaml
gcloud alpha monitoring policies create --policy-from-file=error-rate-alert-policy.yaml

# 3. 設定日誌接收器
echo -e "${YELLOW}📝 設定日誌接收器...${NC}"

# 建立 BigQuery 資料集用於日誌分析
bq mk --dataset --location=asia-east1 $PROJECT_ID:chatgpt_line_bot_logs

# 建立日誌接收器
gcloud logging sinks create chatgpt-line-bot-sink \
    bigquery.googleapis.com/projects/$PROJECT_ID/datasets/chatgpt_line_bot_logs \
    --log-filter='resource.type="cloud_run_revision" AND resource.labels.service_name="$SERVICE_NAME"'

# 4. 建立自訂監控儀表板
echo -e "${YELLOW}📈 建立監控儀表板...${NC}"

cat > dashboard-config.json << EOF
{
  "displayName": "ChatGPT Line Bot 監控儀表板",
  "mosaicLayout": {
    "tiles": [
      {
        "width": 6,
        "height": 4,
        "widget": {
          "title": "請求數量",
          "xyChart": {
            "dataSets": [
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$SERVICE_NAME\"",
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "perSeriesAligner": "ALIGN_RATE",
                      "crossSeriesReducer": "REDUCE_SUM"
                    }
                  }
                }
              }
            ]
          }
        }
      },
      {
        "width": 6,
        "height": 4,
        "xPos": 6,
        "widget": {
          "title": "回應延遲",
          "xyChart": {
            "dataSets": [
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$SERVICE_NAME\"",
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "perSeriesAligner": "ALIGN_MEAN",
                      "crossSeriesReducer": "REDUCE_MEAN"
                    }
                  }
                }
              }
            ]
          }
        }
      }
    ]
  }
}
EOF

gcloud monitoring dashboards create --config-from-file=dashboard-config.json

echo -e "${GREEN}✅ 監控設定完成！${NC}"
echo -e "${YELLOW}📝 可在 Google Cloud Console 中查看：${NC}"
echo "- 監控: https://console.cloud.google.com/monitoring"
echo "- 日誌: https://console.cloud.google.com/logs"
echo "- 儀表板: https://console.cloud.google.com/monitoring/dashboards"

# 清理暫存檔案
rm -f cpu-alert-policy.yaml memory-alert-policy.yaml error-rate-alert-policy.yaml dashboard-config.json