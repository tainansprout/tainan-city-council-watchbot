#!/bin/bash

# 取得腳本所在目錄
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 處理命令列參數
DRY_RUN=false
HELP=false
INTERACTIVE=true
START_FROM_STEP=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --help|-h)
      HELP=true
      shift
      ;;
    --auto)
      INTERACTIVE=false
      shift
      ;;
    --start-from)
      START_FROM_STEP="$2"
      shift 2
      ;;
    *)
      echo "未知參數: $1"
      echo "使用 --help 查看說明"
      exit 1
      ;;
  esac
done

# 顯示幫助資訊
if [ "$HELP" = true ]; then
    cat << EOF
ChatGPT Line Bot Google Cloud Run 部署腳本

使用方式:
  $0 [選項]

選項:
  --dry-run           乾運行模式，顯示要執行的指令但不實際執行
  --auto              自動模式，不詢問用戶確認每個步驟
  --start-from STEP   從指定步驟開始執行（用於錯誤修復）
  --help, -h          顯示此幫助資訊

可用步驟:
  setup-project       設定專案和啟用 API
  setup-secrets       配置 Secret Manager
  build-image         建立 Docker 映像
  deploy-service      部署到 Cloud Run
  setup-permissions   設定 IAM 權限

範例:
  $0                                    # 正常部署（互動模式）
  $0 --dry-run                         # 檢查配置並顯示要執行的指令
  $0 --auto                            # 自動執行所有步驟
  $0 --start-from build-image          # 從建立映像步驟開始
  $0 --dry-run --start-from deploy-service  # 從部署步驟開始的乾運行

EOF
    exit 0
fi

# 載入環境變數配置
if [ -f "$SCRIPT_DIR/.env" ]; then
    echo "載入環境變數配置..."
    set -o allexport
    source "$SCRIPT_DIR/.env"
    set +o allexport
else
    echo "警告: 找不到 $SCRIPT_DIR/.env 檔案"
    echo "請複製 $SCRIPT_DIR/.env.example 為 $SCRIPT_DIR/.env 並填入實際的值"
    exit 1
fi

# 驗證必要的環境變數
required_vars=("PROJECT_ID" "REGION" "SERVICE_NAME" "IMAGE_NAME")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "錯誤: 環境變數 $var 未設定"
        exit 1
    fi
done

# 顏色代碼
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 檢查是否應該跳過此步驟
should_skip_step() {
    local step_name="$1"
    
    if [ -n "$START_FROM_STEP" ]; then
        # 步驟順序定義
        declare -A step_order
        step_order["setup-project"]=1
        step_order["setup-secrets"]=2
        step_order["build-image"]=3
        step_order["deploy-service"]=4
        step_order["setup-permissions"]=5
        
        local current_order=${step_order[$step_name]}
        local start_order=${step_order[$START_FROM_STEP]}
        
        if [ "$current_order" -lt "$start_order" ]; then
            return 0  # 應該跳過
        fi
    fi
    
    return 1  # 不應該跳過
}

# 詢問用戶是否執行步驟
ask_user_confirmation() {
    local step_name="$1"
    local description="$2"
    
    if [ "$INTERACTIVE" = false ] || [ "$DRY_RUN" = true ]; then
        return 0  # 自動執行或 dry-run 模式
    fi
    
    echo -e "${YELLOW}⚠️  準備執行: $description${NC}"
    echo "步驟代碼: $step_name"
    read -p "是否執行此步驟？[Y/n/s(跳過)/q(退出)] " -n 1 -r
    echo
    
    case $REPLY in
        [Nn]* )
            echo "跳過此步驟"
            return 1
            ;;
        [Ss]* )
            echo "跳過此步驟"
            return 1
            ;;
        [Qq]* )
            echo "退出腳本"
            exit 0
            ;;
        * )
            return 0
            ;;
    esac
}

# 執行指令函數（支援 dry-run 和互動確認）
execute_step() {
    local step_name="$1"
    local cmd="$2"
    local description="$3"
    
    # 檢查是否應該跳過此步驟
    if should_skip_step "$step_name"; then
        echo -e "${YELLOW}跳過步驟: $description${NC}"
        return 0
    fi
    
    # 詢問用戶確認
    if ! ask_user_confirmation "$step_name" "$description"; then
        return 0
    fi
    
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}[DRY RUN] $description${NC}"
        echo -e "${BLUE}步驟: $step_name${NC}"
        echo -e "${BLUE}指令: $cmd${NC}"
        echo ""
    else
        echo -e "${YELLOW}執行: $description${NC}"
        eval "$cmd"
        local exit_code=$?
        
        if [ $exit_code -ne 0 ]; then
            echo -e "${RED}❌ 步驟失敗: $description${NC}"
            echo -e "${YELLOW}要從此步驟重新開始，請使用: $0 --start-from $step_name${NC}"
            exit $exit_code
        fi
        
        echo -e "${GREEN}✅ 步驟完成: $description${NC}"
        echo ""
        return $exit_code
    fi
}

if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}🔍 DRY RUN 模式 - 檢查配置並顯示要執行的指令${NC}"
else
    echo -e "${GREEN}🚀 開始部署 ChatGPT Line Bot 到 Google Cloud Run${NC}"
fi

# 檢查是否已登入 gcloud
if [ "$DRY_RUN" = false ]; then
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q "@"; then
        echo -e "${RED}❌ 請先登入 Google Cloud: gcloud auth login${NC}"
        exit 1
    fi
fi

# 配置驗證和顯示
echo -e "${GREEN}📋 配置檢查${NC}"
echo "PROJECT_ID: $PROJECT_ID"
echo "REGION: $REGION"
echo "SERVICE_NAME: $SERVICE_NAME"
echo "IMAGE_NAME: $IMAGE_NAME"
echo "DOCKERFILE_PATH: $DOCKERFILE_PATH"
echo "SERVICE_CONFIG_PATH: $SERVICE_CONFIG_PATH"
echo ""

# 設定專案和啟用 API
execute_step "setup-project" "gcloud config set project $PROJECT_ID && gcloud services enable cloudbuild.googleapis.com run.googleapis.com secretmanager.googleapis.com sql-component.googleapis.com sqladmin.googleapis.com" "📋 設定 Google Cloud 專案並啟用必要的 API"

# 配置 Secret Manager 密鑰
setup_secrets_step() {
    echo -e "${YELLOW}🔐 配置敏感資訊...${NC}"
    
    if [ "$DRY_RUN" = false ] && [ "$INTERACTIVE" = true ]; then
        echo -e "${YELLOW}建議：將敏感資訊設為環境變數，例如：${NC}"
        echo "export OPENAI_API_KEY='your_key_here'"
        echo "export LINE_CHANNEL_ACCESS_TOKEN='your_token_here'"
        echo ""
    fi

    # 在 dry-run 或自動模式下，顯示需要的變數
    if [ "$DRY_RUN" = true ] || [ "$INTERACTIVE" = false ]; then
        OPENAI_KEY='${OPENAI_API_KEY}'
        LINE_TOKEN='${LINE_CHANNEL_ACCESS_TOKEN}'
        LINE_SECRET='${LINE_CHANNEL_SECRET}'
        DB_HOST='${DB_HOST}'
        DB_USER='${DB_USER}'
        DB_PASSWORD='${DB_PASSWORD}'
        DB_NAME='${DB_NAME}'
    else
        OPENAI_KEY=${OPENAI_API_KEY:-$(read -p "請輸入 OpenAI API Key: " && echo $REPLY)}
        LINE_TOKEN=${LINE_CHANNEL_ACCESS_TOKEN:-$(read -p "請輸入 Line Channel Access Token: " && echo $REPLY)}
        LINE_SECRET=${LINE_CHANNEL_SECRET:-$(read -p "請輸入 Line Channel Secret: " && echo $REPLY)}
        DB_HOST=${DB_HOST:-$(read -p "請輸入資料庫主機地址: " && echo $REPLY)}
        DB_USER=${DB_USER:-$(read -p "請輸入資料庫使用者名稱: " && echo $REPLY)}
        DB_PASSWORD=${DB_PASSWORD:-$(read -s -p "請輸入資料庫密碼: " && echo $REPLY && echo)}
        DB_NAME=${DB_NAME:-$(read -p "請輸入資料庫名稱: " && echo $REPLY)}
    fi

    local secrets_cmd="gcloud secrets describe $OPENAI_API_KEY_SECRET --quiet || echo '$OPENAI_KEY' | gcloud secrets create $OPENAI_API_KEY_SECRET --data-file=-; "
    secrets_cmd+="gcloud secrets describe $LINE_CHANNEL_ACCESS_TOKEN_SECRET --quiet || echo '$LINE_TOKEN' | gcloud secrets create $LINE_CHANNEL_ACCESS_TOKEN_SECRET --data-file=-; "
    secrets_cmd+="gcloud secrets describe $LINE_CHANNEL_SECRET_SECRET --quiet || echo '$LINE_SECRET' | gcloud secrets create $LINE_CHANNEL_SECRET_SECRET --data-file=-; "
    secrets_cmd+="gcloud secrets describe $DB_HOST_SECRET --quiet || echo '$DB_HOST' | gcloud secrets create $DB_HOST_SECRET --data-file=-; "
    secrets_cmd+="gcloud secrets describe $DB_USER_SECRET --quiet || echo '$DB_USER' | gcloud secrets create $DB_USER_SECRET --data-file=-; "
    secrets_cmd+="gcloud secrets describe $DB_PASSWORD_SECRET --quiet || echo '$DB_PASSWORD' | gcloud secrets create $DB_PASSWORD_SECRET --data-file=-; "
    secrets_cmd+="gcloud secrets describe $DB_NAME_SECRET --quiet || echo '$DB_NAME' | gcloud secrets create $DB_NAME_SECRET --data-file=-"
    
    return 0
}

# 執行 secrets 設定步驟
setup_secrets_step
if [ $? -eq 0 ]; then
    execute_step "setup-secrets" "$secrets_cmd" "🔐 配置 Secret Manager 密鑰"
fi

# 建立和推送 Docker 映像
execute_step "build-image" "cd '$SCRIPT_DIR/..' && gcloud builds submit --tag gcr.io/$PROJECT_ID/$IMAGE_NAME -f '$DOCKERFILE_PATH' ." "🐳 建立 Docker 映像"

# 部署到 Cloud Run
execute_step "deploy-service" "sed -i.bak 's/YOUR_PROJECT_ID/$PROJECT_ID/g' '$SERVICE_CONFIG_PATH' && gcloud run services replace '$SERVICE_CONFIG_PATH' --region=$REGION && mv '$SERVICE_CONFIG_PATH.bak' '$SERVICE_CONFIG_PATH'" "☁️ 部署到 Cloud Run"

# 設定 IAM 權限和取得服務 URL
execute_step "setup-permissions" "gcloud run services add-iam-policy-binding $SERVICE_NAME --region=$REGION --member='allUsers' --role='roles/run.invoker'" "🔒 設定 IAM 權限（允許公開存取）"

# 取得服務 URL（只在非 dry-run 模式下執行）
if [ "$DRY_RUN" = false ]; then
    SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)" 2>/dev/null || echo "https://your-service-url")
    
    echo -e "${GREEN}✅ 部署完成！${NC}"
    echo -e "${GREEN}🌐 服務 URL: $SERVICE_URL${NC}"
    echo -e "${GREEN}🔗 Webhook URL: $SERVICE_URL/webhooks/line${NC}"
    
    echo -e "${YELLOW}📝 後續設定步驟：${NC}"
    echo "1. Line Developers Console 中的 Webhook URL: $SERVICE_URL/webhooks/line"
    echo "2. 啟用 Webhook"
    echo "3. 測試 Bot 功能"
else
    echo -e "${BLUE}[DRY RUN] 部署完成後，請記得：${NC}"
    echo -e "${BLUE}1. 在 Line Developers Console 設定 Webhook URL${NC}"
    echo -e "${BLUE}2. 啟用 Webhook 並測試 Bot 功能${NC}"
fi