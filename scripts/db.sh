#!/bin/bash
# Database Management Script - npm run style commands for database operations

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
    echo -e "${BLUE}Database Management Commands${NC}"
    echo ""
    echo "Usage: ./scripts/db.sh <command> [options]"
    echo ""
    echo -e "${GREEN}Available Commands:${NC}"
    echo "  setup     - First-time database setup with ORM"
    echo "  init      - Initialize/upgrade database to latest version"
    echo "  migrate   - Create new migration from model changes"
    echo "  upgrade   - Apply pending migrations"
    echo "  status    - Show current migration status"
    echo "  check     - Check database connection and tables"
    echo "  reset     - Reset database (⚠️  DANGEROUS - deletes all data)"
    echo "  rollback  - Rollback last migration"
    echo ""
    echo -e "${GREEN}Examples:${NC}"
    echo "  ./scripts/db.sh setup                    # First-time setup"
    echo "  ./scripts/db.sh migrate -m \"Add user table\" # Create migration"
    echo "  ./scripts/db.sh upgrade                  # Apply migrations"
    echo "  ./scripts/db.sh check                    # Check connection"
    echo ""
}

# Check if Python script exists
DB_SCRIPT="$SCRIPT_DIR/db_commands.py"
if [ ! -f "$DB_SCRIPT" ]; then
    echo -e "${RED}Error: Database command script not found: $DB_SCRIPT${NC}"
    exit 1
fi

# Command routing
case "${1:-help}" in
    "setup")
        echo -e "${YELLOW}🛠️  Setting up database for the first time...${NC}"
        python "$DB_SCRIPT" setup
        ;;
    "init")
        echo -e "${YELLOW}🚀 Initializing database...${NC}"
        python "$DB_SCRIPT" init
        ;;
    "migrate")
        if [ -n "$3" ] && [ "$2" = "-m" ]; then
            echo -e "${YELLOW}📝 Creating migration: $3${NC}"
            python "$DB_SCRIPT" migrate --message "$3"
        else
            echo -e "${YELLOW}📝 Creating auto migration...${NC}"
            python "$DB_SCRIPT" migrate
        fi
        ;;
    "upgrade")
        echo -e "${YELLOW}⬆️  Upgrading database...${NC}"
        python "$DB_SCRIPT" upgrade
        ;;
    "status")
        echo -e "${YELLOW}📊 Checking migration status...${NC}"
        python "$DB_SCRIPT" status
        ;;
    "check")
        echo -e "${YELLOW}🔍 Checking database connection...${NC}"
        python "$DB_SCRIPT" check
        ;;
    "reset")
        echo -e "${RED}⚠️  WARNING: This will delete all data!${NC}"
        python "$DB_SCRIPT" reset
        ;;
    "rollback")
        echo -e "${YELLOW}⬇️  Rolling back last migration...${NC}"
        python "$DB_SCRIPT" downgrade -r "-1"
        ;;
    "help"|"-h"|"--help")
        print_help
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        echo ""
        print_help
        exit 1
        ;;
esac