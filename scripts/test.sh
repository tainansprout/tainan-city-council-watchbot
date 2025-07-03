#!/bin/bash
# 測試運行腳本

set -e

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Change to project directory
cd "$PROJECT_ROOT"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

print_help() {
    echo -e "${BLUE}測試運行腳本${NC}"
    echo ""
    echo "Usage: ./scripts/test.sh <command>"
    echo ""
    echo -e "${GREEN}可用命令:${NC}"
    echo "  unit      - 運行單元測試"
    echo "  models    - 測試所有模型"
    echo "  coverage  - 運行測試並生成覆蓋率報告"
    echo "  quick     - 快速測試 (遇到失敗就停止)"
    echo "  anthropic - 只測試 Anthropic 模型"
    echo "  gemini    - 只測試 Gemini 模型"
    echo "  ollama    - 只測試 Ollama 模型"
    echo "  openai    - 只測試 OpenAI 模型"
    echo "  database  - 測試資料庫和 ORM 功能"
    echo "  integration - 運行整合測試"
    echo "  fix       - 運行最近修復的測試"
    echo ""
    echo -e "${GREEN}範例:${NC}"
    echo "  ./scripts/test.sh unit          # 運行所有單元測試"
    echo "  ./scripts/test.sh coverage      # 生成覆蓋率報告"
    echo "  ./scripts/test.sh anthropic     # 只測試 Anthropic 模型"
    echo ""
}

# Command routing
case "${1:-help}" in
    "unit")
        echo -e "${YELLOW}🧪 運行所有單元測試...${NC}"
        python -m pytest tests/unit/ -v
        ;;
    "models")
        echo -e "${YELLOW}🤖 測試所有模型...${NC}"
        python -m pytest tests/unit/test_*_model.py -v
        ;;
    "coverage")
        echo -e "${YELLOW}📊 運行測試並生成覆蓋率報告...${NC}"
        python -m pytest tests/unit/ --cov=src --cov-report=html --cov-report=term
        echo -e "${GREEN}✅ 覆蓋率報告已生成到 htmlcov/index.html${NC}"
        ;;
    "quick")
        echo -e "${YELLOW}⚡ 快速測試 (遇到失敗就停止)...${NC}"
        python -m pytest tests/unit/ -x --tb=short
        ;;
    "anthropic")
        echo -e "${YELLOW}🧠 測試 Anthropic Claude 模型...${NC}"
        python -m pytest tests/unit/test_anthropic_model.py -v
        ;;
    "gemini")
        echo -e "${YELLOW}💎 測試 Google Gemini 模型...${NC}"
        python -m pytest tests/unit/test_gemini_model.py -v
        ;;
    "ollama")
        echo -e "${YELLOW}🦙 測試 Ollama 本地模型...${NC}"
        python -m pytest tests/unit/test_ollama_model.py -v
        ;;
    "openai")
        echo -e "${YELLOW}🤖 測試 OpenAI 模型...${NC}"
        python -m pytest tests/unit/ -k "openai" -v
        ;;
    "database"|"db")
        echo -e "${YELLOW}🗄️ 測試資料庫和 ORM 功能...${NC}"
        python -m pytest tests/unit/test_database_orm.py -v
        ;;
    "integration")
        echo -e "${YELLOW}🔗 運行整合測試...${NC}"
        python -m pytest tests/integration/ -v -m integration
        ;;
    "fix")
        echo -e "${YELLOW}🔧 運行最近修復的測試...${NC}"
        python -m pytest tests/unit/test_models.py::TestAnthropicModel::test_upload_knowledge_file_success -v
        echo -e "${YELLOW}運行新的 OpenAI 接口測試...${NC}"
        python -m pytest tests/unit/test_anthropic_model.py::TestAnthropicModel::test_chat_with_user_success -v
        echo -e "${YELLOW}運行新的資料庫 ORM 測試...${NC}"
        python -m pytest tests/unit/test_database_orm.py -v
        ;;
    "help"|"-h"|"--help")
        print_help
        ;;
    *)
        echo -e "${RED}未知命令: $1${NC}"
        echo ""
        print_help
        exit 1
        ;;
esac