#!/bin/bash

# Google Cloud 監控和日誌設定腳本
# 為 ChatGPT Line Bot 設定完整的監控體系

# 設定變數
PROJECT_ID="your-project-id"  # 請替換為你的專案 ID
REGION="asia-east1"
SERVICE_NAME="chatgpt-line-bot"
NOTIFICATION_EMAIL="your-email@example.com"  # 請替換為你的郵箱

# 顏色代碼
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}📊 設定 Google Cloud 監控和日誌${NC}"

# 檢查是否已登入 gcloud
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q "@"; then
    echo -e "${RED}❌ 請先登入 Google Cloud: gcloud auth login${NC}"
    exit 1
fi

# 設定專案
echo -e "${YELLOW}📋 設定 Google Cloud 專案...${NC}"
gcloud config set project $PROJECT_ID

# 啟用必要的 API
echo -e "${YELLOW}🔧 啟用監控相關 API...${NC}"
gcloud services enable \
    monitoring.googleapis.com \
    logging.googleapis.com \
    clouderrorreporting.googleapis.com \
    cloudtrace.googleapis.com \
    cloudprofiler.googleapis.com

# 1. 建立通知頻道
echo -e "${YELLOW}📧 建立通知頻道...${NC}"
cat > notification-channel.json << EOF
{
  "type": "email",
  "displayName": "ChatGPT Line Bot Alerts",
  "description": "Email notifications for ChatGPT Line Bot",
  "labels": {
    "email_address": "$NOTIFICATION_EMAIL"
  }
}
EOF

NOTIFICATION_CHANNEL=$(gcloud alpha monitoring channels create --channel-content-from-file=notification-channel.json --format="value(name)")
echo -e "${GREEN}✅ 通知頻道已建立: $NOTIFICATION_CHANNEL${NC}"

# 2. 建立 Dashboard
echo -e "${YELLOW}📈 建立監控 Dashboard...${NC}"
cat > dashboard.json << 'EOF'
{
  "displayName": "ChatGPT Line Bot Dashboard",
  "mosaicLayout": {
    "tiles": [
      {
        "width": 6,
        "height": 4,
        "xPos": 0,
        "yPos": 0,
        "widget": {
          "title": "Request Count",
          "xyChart": {
            "dataSets": [
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"chatgpt-line-bot\"",
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "perSeriesAligner": "ALIGN_RATE",
                      "crossSeriesReducer": "REDUCE_SUM"
                    }
                  }
                },
                "plotType": "LINE"
              }
            ],
            "timeshiftDuration": "0s",
            "yAxis": {
              "label": "Requests/sec",
              "scale": "LINEAR"
            }
          }
        }
      },
      {
        "width": 6,
        "height": 4,
        "xPos": 6,
        "yPos": 0,
        "widget": {
          "title": "Response Latency",
          "xyChart": {
            "dataSets": [
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"chatgpt-line-bot\" AND metric.type=\"run.googleapis.com/request_latencies\"",
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "perSeriesAligner": "ALIGN_DELTA",
                      "crossSeriesReducer": "REDUCE_PERCENTILE_95"
                    }
                  }
                },
                "plotType": "LINE"
              }
            ],
            "timeshiftDuration": "0s",
            "yAxis": {
              "label": "Latency (ms)",
              "scale": "LINEAR"
            }
          }
        }
      },
      {
        "width": 6,
        "height": 4,
        "xPos": 0,
        "yPos": 4,
        "widget": {
          "title": "Error Rate",
          "xyChart": {
            "dataSets": [
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"chatgpt-line-bot\" AND metric.type=\"run.googleapis.com/request_count\" AND metric.labels.response_code_class!=\"2xx\"",
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "perSeriesAligner": "ALIGN_RATE",
                      "crossSeriesReducer": "REDUCE_SUM"
                    }
                  }
                },
                "plotType": "LINE"
              }
            ],
            "timeshiftDuration": "0s",
            "yAxis": {
              "label": "Errors/sec",
              "scale": "LINEAR"
            }
          }
        }
      },
      {
        "width": 6,
        "height": 4,
        "xPos": 6,
        "yPos": 4,
        "widget": {
          "title": "Instance Count",
          "xyChart": {
            "dataSets": [
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"chatgpt-line-bot\" AND metric.type=\"run.googleapis.com/container/instance_count\"",
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "perSeriesAligner": "ALIGN_MEAN",
                      "crossSeriesReducer": "REDUCE_SUM"
                    }
                  }
                },
                "plotType": "STACKED_AREA"
              }
            ],
            "timeshiftDuration": "0s",
            "yAxis": {
              "label": "Instances",
              "scale": "LINEAR"
            }
          }
        }
      }
    ]
  }
}
EOF

gcloud monitoring dashboards create --config-from-file=dashboard.json
echo -e "${GREEN}✅ Dashboard 已建立${NC}"

# 3. 建立警報政策
echo -e "${YELLOW}🚨 建立警報政策...${NC}"

# 高錯誤率警報
cat > high-error-rate-policy.json << EOF
{
  "displayName": "ChatGPT Line Bot - High Error Rate",
  "documentation": {
    "content": "Alert when error rate exceeds 5% for 5 minutes"
  },
  "conditions": [
    {
      "displayName": "Error rate > 5%",
      "conditionThreshold": {
        "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$SERVICE_NAME\" AND metric.type=\"run.googleapis.com/request_count\"",
        "aggregations": [
          {
            "alignmentPeriod": "300s",
            "perSeriesAligner": "ALIGN_RATE",
            "crossSeriesReducer": "REDUCE_SUM",
            "groupByFields": ["metric.labels.response_code_class"]
          }
        ],
        "comparison": "COMPARISON_GREATER_THAN",
        "thresholdValue": 0.05,
        "duration": "300s"
      }
    }
  ],
  "notificationChannels": ["$NOTIFICATION_CHANNEL"],
  "enabled": true
}
EOF

gcloud alpha monitoring policies create --policy-from-file=high-error-rate-policy.json

# 高延遲警報
cat > high-latency-policy.json << EOF
{
  "displayName": "ChatGPT Line Bot - High Latency",
  "documentation": {
    "content": "Alert when 95th percentile latency exceeds 10 seconds"
  },
  "conditions": [
    {
      "displayName": "P95 latency > 10s",
      "conditionThreshold": {
        "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$SERVICE_NAME\" AND metric.type=\"run.googleapis.com/request_latencies\"",
        "aggregations": [
          {
            "alignmentPeriod": "300s",
            "perSeriesAligner": "ALIGN_DELTA",
            "crossSeriesReducer": "REDUCE_PERCENTILE_95"
          }
        ],
        "comparison": "COMPARISON_GREATER_THAN",
        "thresholdValue": 10000,
        "duration": "300s"
      }
    }
  ],
  "notificationChannels": ["$NOTIFICATION_CHANNEL"],
  "enabled": true
}
EOF

gcloud alpha monitoring policies create --policy-from-file=high-latency-policy.json

# 服務下線警報
cat > service-down-policy.json << EOF
{
  "displayName": "ChatGPT Line Bot - Service Down",
  "documentation": {
    "content": "Alert when service has no active instances"
  },
  "conditions": [
    {
      "displayName": "No active instances",
      "conditionThreshold": {
        "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$SERVICE_NAME\" AND metric.type=\"run.googleapis.com/container/instance_count\"",
        "aggregations": [
          {
            "alignmentPeriod": "300s",
            "perSeriesAligner": "ALIGN_MEAN",
            "crossSeriesReducer": "REDUCE_SUM"
          }
        ],
        "comparison": "COMPARISON_EQUAL",
        "thresholdValue": 0,
        "duration": "300s"
      }
    }
  ],
  "notificationChannels": ["$NOTIFICATION_CHANNEL"],
  "enabled": true
}
EOF

gcloud alpha monitoring policies create --policy-from-file=service-down-policy.json

echo -e "${GREEN}✅ 警報政策已建立${NC}"

# 4. 設定日誌聚合和分析
echo -e "${YELLOW}📝 設定日誌聚合...${NC}"

# 建立 BigQuery 資料集用於日誌分析
bq mk --dataset --location=asia-east1 ${PROJECT_ID}:chatgpt_line_bot_logs

# 建立日誌匯出
gcloud logging sinks create chatgpt-line-bot-logs-sink \
    bigquery.googleapis.com/projects/$PROJECT_ID/datasets/chatgpt_line_bot_logs \
    --log-filter="resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$SERVICE_NAME\""

# 建立錯誤報告匯出
gcloud logging sinks create chatgpt-line-bot-errors-sink \
    bigquery.googleapis.com/projects/$PROJECT_ID/datasets/chatgpt_line_bot_logs \
    --log-filter="resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$SERVICE_NAME\" AND severity>=ERROR"

echo -e "${GREEN}✅ 日誌聚合已設定${NC}"

# 5. 建立自訂指標
echo -e "${YELLOW}📊 建立自訂指標...${NC}"

# 建立 OpenAI API 呼叫次數指標
cat > openai-api-calls-metric.json << 'EOF'
{
  "name": "OpenAI API Calls",
  "description": "Number of OpenAI API calls made",
  "filter": "resource.type=\"cloud_run_revision\" AND jsonPayload.event_type=\"openai_api_call\"",
  "labelExtractors": {
    "status": "EXTRACT(jsonPayload.status)",
    "model": "EXTRACT(jsonPayload.model)"
  },
  "metricDescriptor": {
    "metricKind": "GAUGE",
    "valueType": "INT64"
  }
}
EOF

gcloud logging metrics create openai_api_calls --config-from-file=openai-api-calls-metric.json

echo -e "${GREEN}✅ 自訂指標已建立${NC}"

# 6. 建立性能分析設定
echo -e "${YELLOW}🔍 啟用性能分析...${NC}"

# 在 Cloud Run 服務中啟用 Profiler
gcloud run services update $SERVICE_NAME \
    --region=$REGION \
    --set-env-vars="GOOGLE_CLOUD_PROFILER_ENABLED=true"

echo -e "${GREEN}✅ 性能分析已啟用${NC}"

# 7. 建立 SLI/SLO 配置
echo -e "${YELLOW}📏 建立 SLI/SLO...${NC}"

cat > slo-config.json << EOF
{
  "displayName": "ChatGPT Line Bot SLO",
  "description": "99% of requests should complete within 5 seconds",
  "serviceLevelIndicator": {
    "requestBased": {
      "distributionCut": {
        "distributionFilter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$SERVICE_NAME\" AND metric.type=\"run.googleapis.com/request_latencies\"",
        "range": {
          "max": 5000
        }
      }
    }
  },
  "goal": {
    "target": 0.99,
    "period": "2592000s"
  }
}
EOF

# 注意：SLO API 目前可能需要額外權限，這裡先跳過
echo -e "${YELLOW}⚠️  SLO 配置需要額外設定，請參考文件手動建立${NC}"

# 清理暫存檔案
rm -f notification-channel.json dashboard.json *-policy.json *-metric.json slo-config.json

echo -e "${GREEN}🎉 監控設定完成！${NC}"
echo -e "${YELLOW}📋 設定摘要：${NC}"
echo "1. ✅ Dashboard 已建立"
echo "2. ✅ 警報政策已建立（錯誤率、延遲、服務下線）"
echo "3. ✅ 日誌聚合到 BigQuery"
echo "4. ✅ 自訂指標（OpenAI API 呼叫）"
echo "5. ✅ 性能分析已啟用"
echo ""
echo -e "${YELLOW}📊 監控連結：${NC}"
echo "Dashboard: https://console.cloud.google.com/monitoring/dashboards"
echo "Logs: https://console.cloud.google.com/logs/query"
echo "Metrics: https://console.cloud.google.com/monitoring/metrics-explorer"
echo "Alerts: https://console.cloud.google.com/monitoring/alerting"
echo ""
echo -e "${YELLOW}⚠️  下一步：${NC}"
echo "1. 檢查通知頻道是否正確設定"
echo "2. 測試警報是否正常運作"
echo "3. 根據實際使用情況調整閾值"
echo "4. 考慮建立更多自訂指標"