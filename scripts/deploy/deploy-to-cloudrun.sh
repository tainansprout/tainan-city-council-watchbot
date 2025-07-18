#!/bin/bash

# 移動到腳本所在目錄，然後移動到項目根目錄
cd "$(dirname "${BASH_SOURCE[0]}")"
pushd ../.. > /dev/null
PROJECT_ROOT="$(pwd)"
popd > /dev/null

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
required_vars=("PROJECT_ID" "REGION" "SERVICE_NAME" "IMAGE_NAME")
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
execute_step "setup-project" "gcloud config set project $PROJECT_ID" "📋 設定 Google Cloud 專案"

# 建立和推送 Docker 映像
execute_step "build-image" "cd '$PROJECT_ROOT' && gcloud builds submit --tag gcr.io/$PROJECT_ID/$IMAGE_NAME' ." "🐳 建立 Docker 映像"

# 部署到 Cloud Run
execute_step "deploy-service" "cd '$PROJECT_ROOT' && gcloud run deploy $SERVICE_NAME --image asia.gcr.io/$PROJECT_ID/$IMAGE_NAME --platform managed --port 8080 --memory 4G --timeout=3m" "☁️ 部署到 Cloud Run"