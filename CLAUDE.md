# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Multi-Platform Chatbot** supporting LINE, Discord, Telegram and other platforms. The system features a modular architecture with multiple AI model providers (OpenAI, Anthropic Claude, Google Gemini, Ollama) and comprehensive conversation management. The application is deployed on Google Cloud Run with Google Cloud SQL for conversation storage and supports both text and audio message processing.

## Development Commands

### Local Development

#### 🔧 開發環境（推薦）
```bash
# Install dependencies
pip install -r requirements.txt

# Setup local environment
cp .env.local.example .env.local
# 編輯 .env.local 填入配置

# Run development server
./scripts/dev.sh
```

#### 🧪 本地生產測試
```bash
# Test production configuration locally
./scripts/test-prod.sh
```

#### ⚡ 統一運行方式 (v2.0)
```bash
# Development mode (自動檢測環境)
python main.py

# Production mode (自動啟動 Gunicorn)
FLASK_ENV=production python main.py

# 向後兼容方式（已整合到 main.py）
gunicorn -c gunicorn.conf.py main:application
```

### Docker Development
```bash
# Build and run with Docker Compose
docker-compose up --build

# Build Docker image manually
docker build -t chatgpt-line-bot .
```

### Google Cloud Deployment
```bash
# Build and push to Google Container Registry
gcloud builds submit --tag gcr.io/{project-id}/{image-name}

# Deploy to Cloud Run with new unified architecture
gcloud run deploy {service-name} \
  --image gcr.io/{project-id}/{image-name} \
  --platform managed \
  --port 8080 \
  --memory 2G \
  --timeout=2m \
  --region {region} \
  --set-env-vars FLASK_ENV=production

# Health check after deployment
curl https://{service-url}/health
```

## Architecture

### 🎯 **New Architecture Highlights (v2.0)**

1. **Unified Entry Point**: `main.py` automatically detects environment and switches between development/production modes
2. **Backward Compatibility**: All existing import paths and WSGI configurations continue to work
3. **Multi-Platform Ready**: Factory pattern enables easy addition of new platforms (Discord, Telegram, etc.)
4. **Environment Auto-Detection**: No manual configuration needed for development vs production
5. **Comprehensive Testing**: New test architecture with proper separation and fixtures

### Core Components

#### Application Layer
- **main.py**: Unified entry point with automatic environment detection (v2.0)
- **src/app.py**: Multi-platform Flask application with unified webhook handlers and web interface

#### Platform Layer (Strategy Pattern)
- **src/platforms/base.py**: Platform abstraction interfaces and data classes
- **src/platforms/line_handler.py**: LINE platform-specific message handling
- **src/platforms/factory.py**: Platform factory and registry for handler management

#### Service Layer (重構後)
- **src/services/chat.py**: Platform-agnostic core conversation logic (原 core_chat_service.py)
- **src/services/conversation.py**: Conversation history management (整合版)
- **src/services/response.py**: Unified response formatting (原 response_formatter.py)
- **src/services/audio.py**: Audio processing service (原 audio_service.py)

#### Core Infrastructure (v2.0)
- **src/core/config.py**: ConfigManager singleton with thread-safe configuration caching
- **src/core/security.py**: Unified security module with configuration, validation, rate limiting, and middleware
- **src/core/auth.py**: Authentication and authorization management
- **src/core/memory.py**: In-memory conversation management
- **src/core/error_handler.py**: Centralized error handling and user-friendly messages
- **src/core/exceptions.py**: Custom exception hierarchy for different error types
- **src/core/logger.py**: Comprehensive logging system with structured output

#### Model Layer (Factory Pattern)
- **src/models/base.py**: Abstract model interfaces and data structures
- **src/models/openai_model.py**: OpenAI Assistant API integration
- **src/models/anthropic_model.py**: Anthropic Claude API integration
- **src/models/gemini_model.py**: Google Gemini API integration
- **src/models/ollama_model.py**: Local Ollama model integration
- **src/models/factory.py**: Model factory for provider selection

#### Database Layer (重構後)
- **src/database/connection.py**: Database connection management (原 db.py)
- **src/database/models.py**: SQLAlchemy ORM models with multi-platform support (原 models/database.py)
- **src/database/operations.py**: Database operations toolkit (新增)
- **src/database/init_db.py**: Database initialization scripts (新增)

#### Configuration and Utilities
- **src/core/config.py**: Multi-platform configuration management
- **src/utils/main.py**: Text processing utilities and OpenCC conversion
- **src/core/logger.py**: Comprehensive logging system

### Key Architecture Patterns

#### Design Patterns Applied
1. **Factory Pattern**: Model and platform selection through factories
2. **Strategy Pattern**: Platform-specific message handling strategies
3. **Registry Pattern**: Dynamic platform handler registration
4. **Adapter Pattern**: Unified interfaces for different AI models

#### Core Architecture Principles
1. **Multi-Platform Support**: Unified conversation management across LINE, Discord, Telegram
2. **Model Agnostic**: Support for OpenAI, Anthropic, Gemini, and Ollama models
3. **Conversation Persistence**: Platform-aware conversation history with composite keys
4. **Message Flow**: Platform Input → Core Service → Model Provider → Response Formatter → Platform Output
5. **Error Handling**: Comprehensive error handling with platform-specific error messages

### Configuration Structure

#### Main Configuration (`config/config.yml`)
```yaml
# Application metadata
app:
  name: "Multi-Platform Chat Bot"
  version: "2.0.0"

# Model configuration
llm:
  provider: "openai"  # openai, anthropic, gemini, ollama

# Model-specific configurations
openai:
  api_key: "${OPENAI_API_KEY}"
  assistant_id: "${OPENAI_ASSISTANT_ID}"

anthropic:
  api_key: "${ANTHROPIC_API_KEY}"
  model: "claude-3-sonnet-20240229"

gemini:
  api_key: "${GEMINI_API_KEY}"
  model: "gemini-1.5-pro-latest"

ollama:
  base_url: "http://localhost:11434"
  model: "llama3.1:8b"

# Database configuration
db:
  host: "${DB_HOST}"
  port: ${DB_PORT}
  db_name: "${DB_NAME}"
  user: "${DB_USER}"
  password: "${DB_PASSWORD}"

# Platform configurations
platforms:
  line:
    enabled: true
    channel_access_token: "${LINE_CHANNEL_ACCESS_TOKEN}"
    channel_secret: "${LINE_CHANNEL_SECRET}"
  
  discord:
    enabled: false
    bot_token: "${DISCORD_BOT_TOKEN}"
  
  telegram:
    enabled: false
    bot_token: "${TELEGRAM_BOT_TOKEN}"

# Text processing
text_processing:
  preprocessors: []
  post_replacements: []

# Bot commands
commands:
  help: "提供系統說明和可用指令"
  reset: "重置對話歷史"

# Authentication (v2.0)
auth:
  method: "simple_password"  # simple_password, basic_auth, token
  password: "${TEST_PASSWORD}"  # For simple_password method
  # Production: Use environment variable TEST_PASSWORD
  # Development: Set directly in config.yml
```

#### Platform Configuration (`config/platforms.yml`)
Platform-specific routing and feature configurations

### Database Schema

#### Multi-Platform Thread Management
```sql
-- OpenAI thread management with platform support
CREATE TABLE user_thread_table (
    user_id VARCHAR(255) NOT NULL,
    platform VARCHAR(50) NOT NULL DEFAULT 'line',
    thread_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, platform)
);

-- Performance indexes
CREATE INDEX idx_thread_user_platform ON user_thread_table(user_id, platform);
CREATE INDEX idx_thread_created_at ON user_thread_table(created_at);
```

#### Conversation History for Non-OpenAI Models
```sql
-- Conversation history for Anthropic, Gemini, Ollama models
CREATE TABLE simple_conversation_history (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    platform VARCHAR(50) NOT NULL DEFAULT 'line',
    model_provider VARCHAR(50) NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Performance indexes
CREATE INDEX idx_conversation_user_platform ON simple_conversation_history(user_id, platform);
CREATE INDEX idx_conversation_user_platform_provider ON simple_conversation_history(user_id, platform, model_provider);
CREATE INDEX idx_conversation_created_at ON simple_conversation_history(created_at);
```

### SSL Certificate Setup

SSL certificates for database connection are stored in `config/ssl/`:
- `ca-cert.crt`: Server CA Certificate
- `client.crt`: Client Certificate  
- `client.key`: Client Key

Convert from PEM format using:
```bash
openssl x509 -in client-cert.pem -out ssl-cert.crt
openssl x509 -in server-ca.pem -out ca-cert.crt
openssl rsa -in client-key.pem -out ssl-key.key
```

## AI Model Processing Pipeline

### Unified Processing Flow
1. **Preprocessing**: Date string replacement (今天/明天/昨天 → YYYY/MM/DD format)
2. **AI Model Processing**: 
   - **OpenAI**: Assistant API with native thread management and file search
   - **Anthropic**: Claude with Files API, Extended Prompt Caching, and RAG
   - **Gemini**: Multimodal with Semantic Retrieval API for long-context RAG  
   - **Ollama**: Local processing with vector database RAG
3. **Response Formatting**: 
   - Simplified to Traditional Chinese conversion using OpenCC
   - **Unified Reference Processing**: ResponseFormatter handles citations from all models
   - Custom text replacements via config

### Reference/Citation Handling
All AI models return structured RAGResponse with sources that are processed by ResponseFormatter:

- **OpenAI**: Processes Assistant API file citations `[i]` → `[i]: filename`
- **Anthropic**: Handles `[filename]` references with file IDs
- **Gemini**: Processes Semantic Retrieval results with relevance scores  
- **Ollama**: Handles local vector search results with similarity scores

The ResponseFormatter ensures consistent citation formatting across all models.

## API Endpoints

### Multi-Platform Webhooks (v2.0)
- `POST /webhooks/line`: LINE platform webhook (new unified route)
- `POST /webhooks/discord`: Discord platform webhook  
- `POST /webhooks/telegram`: Telegram platform webhook
- `POST /callback`: Legacy LINE webhook (backward compatible)

### System Endpoints (Enhanced in v2.0)
- `GET /`: Application information with platform status and version
- `GET /health`: Comprehensive health check (database, model, platforms, auth)
- `GET /metrics`: Application metrics with platform and database statistics

### Web Interface with Authentication (v2.0)
- `GET /login`: Web login interface with password authentication
- `POST /login`: JSON-based login authentication (unified format)
- `GET /chat`: Web-based chat interface (requires authentication)
- `POST /ask`: Web API for direct chat functionality (requires authentication)
- `POST /logout`: Logout and session clearing

## Important Development Notes (v2.0)

### 🚀 **Deployment and Running**
- **Development**: Simply run `python main.py` - auto-detects as development environment
- **Production**: Set `FLASK_ENV=production` and run `python main.py` - auto-starts Gunicorn
- **WSGI**: All existing WSGI configurations work unchanged (`gunicorn main:application`)
- **Docker**: No changes needed - containers will auto-detect environment

### 🔧 **Configuration Changes**
- **New Format**: Platform configs moved to `platforms.{platform}` structure  
- **Environment Override**: Environment variables use new structure (e.g., `platforms.line.channel_access_token`)
- **Auto-Detection**: Missing `FLASK_ENV` defaults to development

### 🧪 **Testing Framework Architecture (Updated 2025)**

The testing framework is organized by component type with comprehensive coverage and unified mock patterns:

#### Test Structure (Optimized)
```
tests/
├── unit/                       # 單元測試 (核心功能)
│   ├── test_anthropic_model.py        # Anthropic Claude API 測試
│   ├── test_chat_service.py           # 核心聊天服務測試 (原 test_core_chat_service.py)
│   ├── test_config_manager.py         # 配置管理測試
│   ├── test_conversation_service.py   # 對話歷史管理測試
│   ├── test_database_connection.py    # 資料庫連接測試
│   ├── test_database_models.py        # SQLAlchemy ORM 模型測試
│   ├── test_database_operations.py    # 資料庫操作測試
│   ├── test_error_handling.py         # 錯誤處理機制測試
│   ├── test_gemini_model.py           # Google Gemini API 測試
│   ├── test_models.py                 # AI 模型基礎介面測試
│   ├── test_ollama_model.py           # Ollama 本地模型測試
│   ├── test_openai_model.py           # OpenAI Assistant API 測試 (已整合 enhanced 版本)
│   ├── test_platforms.py              # 平台抽象和處理器測試
│   ├── test_response_service.py       # 統一回應格式化測試 (原 test_response_formatter.py)
│   ├── test_utils.py                  # 工具函數測試
│   └── test_web_auth.py               # Web 認證系統測試
├── integration/                # 整合測試 (跨模組交互)
│   └── test_database_integration.py   # 資料庫與ORM整合測試
├── api/                        # API 端點測試
│   ├── test_health_endpoints.py       # 健康檢查和系統狀態端點測試
│   └── test_webhook_endpoints.py      # 多平台 Webhook 端點測試
├── mocks/                      # 模擬測試 (外部服務)
│   └── test_external_services.py      # 外部服務和API模擬測試
└── test_main.py                # 主應用程式和WSGI測試
```

#### Testing Patterns (Enhanced)
- **Factory Pattern Testing**: 模型和平台工廠的創建和註冊測試
- **Strategy Pattern Testing**: 不同 AI 模型策略的行為和回應測試
- **Integration Testing**: 跨模組的整合測試和端到端流程
- **Mock Services**: 外部 API 的模擬測試，支援 OpenAI、Anthropic、Gemini、Ollama
- **Platform-Aware Testing**: 多平台支援的統一測試模式
- **Citation Processing Testing**: AI 模型引用處理的架構分離測試

#### Key Testing Features (Updated)
- **Multi-Platform Support**: 測試 LINE、Discord、Telegram 平台的統一介面
- **Multi-Model Testing**: 完整測試 OpenAI、Anthropic、Gemini、Ollama 模型
- **Configuration Testing**: 測試新舊配置格式的兼容性和環境變數覆蓋
- **Error Handling Testing**: 測試錯誤處理機制和雙層錯誤訊息
- **Authentication Testing**: 測試 Web 介面認證系統的多種認證方式
- **Citation Architecture Testing**: 測試引用處理的正確架構分工 (OpenAI vs ResponseFormatter)
- **Database Consistency Testing**: 測試資料庫模型命名一致性 (UserThreadTable)
- **Platform Parameter Testing**: 測試平台感知的對話管理

#### Test Maintenance and Quality Assurance
- **Naming Standardization**: 統一測試檔案命名規範 (test_openai_model.py vs test_openai_model_enhanced.py)
- **Import Path Consistency**: 修復模組重構後的導入路徑問題
- **Mock Pattern Unification**: 統一模擬對象的設定模式和參數傳遞
- **Flask Context Management**: 正確處理 Flask 應用上下文和請求上下文
- **Architectural Testing**: 確保測試反映實際的系統架構和責任分工

### 🔐 **Authentication System (v2.0)**
- **Session-Based Auth**: Web interface uses Flask sessions for authentication
- **JSON-Only API**: All authentication endpoints use unified JSON format
- **Route Protection**: Protected routes automatically redirect to login
- **Configuration**: Authentication settings in `config.yml` under `auth` section
- **Security**: Input validation and security middleware for all endpoints

### ⚙️ **ConfigManager Singleton (v2.0)**
- **Thread-Safe Loading**: Configuration loaded once and cached safely
- **Performance Optimized**: Eliminates repeated file I/O during requests  
- **Auto-Initialization**: Lazy loading with double-checked locking pattern
- **Memory Efficient**: Single instance shared across all threads

### 🏗️ **Platform Architecture & File Structure**

The system is built with clear separation of concerns and modular design:

#### Platform Layer Structure
```
src/platforms/
├── base.py                     # 平台抽象接口
│   ├── PlatformType           # 平台類型枚舉
│   ├── PlatformMessage        # 統一訊息格式
│   ├── PlatformResponse       # 統一回應格式
│   ├── PlatformUser           # 統一用戶格式
│   └── BasePlatformHandler    # 平台處理器基類
├── factory.py                  # 平台工廠和註冊
│   ├── PlatformFactory        # 工廠模式創建處理器
│   ├── PlatformRegistry       # 註冊模式管理平台
│   └── ConfigValidator        # 配置驗證器
├── line_handler.py            # LINE 平台實作
├── discord_handler.py         # Discord 平台實作 (規劃中)
└── telegram_handler.py        # Telegram 平台實作 (規劃中)
```

#### Model Layer Structure
```
src/models/
├── base.py                     # AI 模型抽象接口
│   ├── ModelProvider          # 模型提供商枚舉
│   ├── FullLLMInterface       # 完整語言模型接口
│   ├── ChatMessage            # 聊天訊息格式
│   ├── ChatResponse           # 聊天回應格式
│   ├── RAGResponse            # RAG 查詢回應格式
│   └── FileInfo               # 檔案資訊格式
├── factory.py                  # 模型工廠
│   └── ModelFactory           # 根據配置創建模型實例
├── openai_model.py            # OpenAI Assistant API 實作
├── anthropic_model.py         # Anthropic Claude API 實作
├── gemini_model.py            # Google Gemini API 實作
└── ollama_model.py            # Ollama 本地模型實作
```

#### Service Layer Structure (重構後)
```
src/services/
├── chat.py                    # 核心聊天服務 (原 core_chat_service.py)
│   └── CoreChatService        # 平台無關的聊天邏輯
├── response.py                # 統一回應格式化 (原 response_formatter.py)
│   └── ResponseFormatter      # 跨模型的引用處理
├── conversation.py            # 對話歷史管理 (整合版)
│   └── ORMConversationManager # 統一對話管理器
└── audio.py                   # 音訊處理服務 (原 audio_service.py)
```

#### Unified Interface Design

**統一平台接口** (v2.1 - 簡化版):
```python
class PlatformHandlerInterface:
    def get_platform_type(self) -> PlatformType
    def parse_message(self, raw_event: Any) -> Optional[PlatformMessage]  
    def send_response(self, response: PlatformResponse, message: PlatformMessage) -> bool
    def handle_webhook(self, request_body: str, signature: str) -> List[PlatformMessage]
    # 注意：移除了 validate_signature 抽象方法，簽名驗證現在是每個平台的內部實作細節
```

**統一模型接口**:
```python
class FullLLMInterface:
    def chat_with_user(self, user_id: str, message: str, platform: str) -> Tuple[bool, RAGResponse, str]
    def clear_user_history(self, user_id: str, platform: str) -> Tuple[bool, str]
    def transcribe_audio(self, audio_file_path: str) -> Tuple[bool, str, str]
```

### 📝 **Key Changes for Developers (Updated v2.1)**
1. `main.py` is now the primary entry point for all environments
2. Platform configurations use new nested structure (`platforms.{platform}`)
3. Health endpoints return enhanced information with platform status
4. All webhook routes follow `/webhooks/{platform}` pattern
5. Backward compatibility maintained for existing deployments
6. **ConfigManager replaces direct config loading** - use `ConfigManager().get_config()`
7. **JSON-only authentication** - all login/logout flows use JSON format
8. **Unified Interfaces** - All platforms and models implement consistent interfaces
9. **Factory Pattern** - Use factories for creating platform handlers and models
10. **Error Handling** - Dual-layer error messages (detailed for testing, simplified for users)
11. **簡化平台接口** - 移除了 `validate_signature` 抽象方法，簽名驗證成為各平台的內部實作細節
12. **最佳化 Logging** - INFO 級別只保留最必要的訊息（收到/發送內容），其餘改為 DEBUG

## Dependencies

### Core Framework
- `Flask`: Web framework and application server
- `SQLAlchemy`: ORM for database management
- `Alembic`: Database migration management
- `pyyaml`: Configuration file processing
- `gunicorn`: Production WSGI server

### Platform Integrations
- `line-bot-sdk`: LINE Bot platform integration
- `discord.py`: Discord bot integration (planned)
- `python-telegram-bot`: Telegram bot integration (planned)

### AI Model Providers
- `openai`: OpenAI Assistant API and GPT models
- `anthropic`: Anthropic Claude API integration
- `google-generativeai`: Google Gemini API
- `requests`: HTTP client for Ollama and custom integrations

### Text Processing
- `opencc-python-reimplemented`: Simplified/Traditional Chinese conversion
- `python-dateutil`: Date string processing

### Database Connectivity
- `psycopg2-binary`: PostgreSQL database adapter
- `SQLAlchemy[postgresql]`: PostgreSQL-specific SQLAlchemy features

### Development and Testing
- `pytest`: Testing framework
- `pytest-cov`: Test coverage reporting
- `pytest-asyncio`: Async test support

## Migration and Database Management

### Database Initialization (重構後)
```bash
# 一鍵完整資料庫結構設置
python scripts/setup_database.py setup

# 檢查資料庫狀態
python scripts/setup_database.py status

# 執行健康檢查
python scripts/setup_database.py health

# Initialize Alembic migrations (manual method)
alembic init alembic

# Create initial migration
alembic revision --autogenerate -m "Initial multi-platform schema"

# Apply migrations
alembic upgrade head
```

### Platform Migration Commands (重構後)
```bash
# Run consolidated database setup script
python scripts/setup_database.py setup

# Check migration status
alembic current
alembic history

# Upgrade to latest version
alembic upgrade head

# Check database operations health
python scripts/setup_database.py health
```

## Testing

### Running Tests
```bash
# Run all tests
python -m pytest

# Run specific test categories
python -m pytest tests/unit/          # Unit tests
python -m pytest tests/integration/   # Integration tests

# Run with coverage
python -m pytest --cov=src --cov-report=html

# Run platform-specific tests
python -m pytest tests/unit/test_platforms.py
python -m pytest tests/unit/test_chat_service.py
```

### Test Structure (Updated 2025)
- `tests/unit/`: Unit tests for individual components
  - `test_platforms.py`: Platform abstraction and handler registration tests
  - `test_chat_service.py`: Core chat service tests (原 test_core_chat_service.py) 
  - `test_conversation_service.py`: Conversation management tests (重構版)
  - `test_response_service.py`: Response formatting tests (原 test_response_formatter.py)
  - `test_database_models.py`: SQLAlchemy ORM models tests (新增)
  - `test_database_operations.py`: Database operations tests (新增)
  - `test_database_connection.py`: Database connection and UserThreadTable tests (新增)
  - `test_anthropic_model.py`: Anthropic Claude API integration tests (新增)
  - `test_gemini_model.py`: Google Gemini API integration tests (新增)
  - `test_ollama_model.py`: Ollama local model integration tests (新增)
  - `test_openai_model.py`: OpenAI Assistant API tests (整合 enhanced 版本)
  - `test_models.py`: AI model base interface tests
  - `test_web_auth.py`: Web authentication system tests (新增)
  - `test_config_manager.py`: Configuration management tests (新增)
- `tests/integration/`: End-to-end integration tests
  - `test_database_integration.py`: Database and ORM integration tests
- `tests/api/`: API endpoint testing
  - `test_health_endpoints.py`: Health check and system status tests (重構版)
  - `test_webhook_endpoints.py`: Multi-platform webhook tests (新增)
- `tests/mocks/`: External service mocking
  - `test_external_services.py`: External API mocking tests (新增)
- `test_main.py`: Main application and WSGI compatibility tests (新增)

## Development Workflow

### Adding New Platforms
1. **Create Platform Handler**: Implement `BasePlatformHandler` in `src/platforms/`
2. **Register Platform**: Add to `PlatformRegistry` in `src/platforms/factory.py`
3. **Update Configuration**: Add platform config in `config/platforms.yml`
4. **Add Webhook Route**: Register webhook endpoint in `src/app.py`
5. **Test Integration**: Create platform-specific tests

### Adding New AI Models
1. **Implement Model Interface**: Extend `FullLLMInterface` in `src/models/`
2. **Update Model Factory**: Add provider to `ModelFactory` in `src/models/factory.py`
3. **Configure Provider**: Add configuration section in `config/config.yml`
4. **Test Integration**: Add model-specific tests

### Code Quality
- **Linting**: Use `flake8` or `black` for code formatting
- **Type Hints**: All new code should include type annotations
- **Documentation**: Update docstrings for new functionality
- **Testing**: Maintain >80% test coverage for new features