# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Multi-Platform Chatbot** supporting LINE, Discord, Telegram and other platforms. The system features a modular architecture with multiple AI model providers (OpenAI, Anthropic Claude, Google Gemini, Ollama) and comprehensive conversation management. The application is deployed on Google Cloud Run with Google Cloud SQL for conversation storage and supports both text and audio message processing.

**v2.1 Core Infrastructure Integration**: Integrated high-performance logging and security modules for optimal performance and simplified maintenance.

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

### 🎯 **New Architecture Highlights (v2.1 整合升級)**

1. **Core Module Integration**: Unified high-performance logging and security modules
2. **Performance Optimization**: Pre-compiled regex patterns, async processing, and caching mechanisms
3. **Simplified Maintenance**: Reduced file count, unified interfaces, backward compatibility
4. **Unified Entry Point**: `main.py` automatically detects environment and switches between development/production modes
5. **Multi-Platform Ready**: Factory pattern enables easy addition of new platforms (Discord, Telegram, etc.)
6. **Environment Auto-Detection**: No manual configuration needed for development vs production
7. **Comprehensive Testing**: Updated test architecture reflecting integrated modules with 35% total coverage

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
  - **統一介面**: `ChatService.handle_message()` 處理文字訊息
  - **專責文字處理**: 聊天邏輯、命令處理、AI 模型交互
- **src/services/audio.py**: Audio transcription service (原 audio_service.py)  
  - **統一介面**: `AudioService.handle_message()` 處理音訊轉錄
  - **專責音訊轉錄**: 音訊檔案 → 文字轉錄，不涉及 AI 對話處理
- **src/services/conversation.py**: Conversation history management (整合版)
- **src/services/response.py**: Unified response formatting (原 response_formatter.py)

#### Core Infrastructure (v2.1 整合版)
- **src/core/config.py**: ConfigManager singleton with thread-safe configuration caching
- **src/core/logger.py**: **整合高效能日誌系統** (unified optimized logging)
  - Pre-compiled regex patterns for sensitive data filtering
  - Asynchronous log processing with queue-based handling
  - Structured formatter with colored console output
  - Performance monitoring and cache statistics
  - Removed: `optimized_logger.py` (功能已整合)
- **src/core/security.py**: **整合安全模組** (unified security module)
  - O(1) complexity rate limiter with sliding window
  - Pre-compiled regex patterns for input validation
  - Security configuration management and middleware
  - Caching mechanisms for improved performance
  - Removed: `optimized_security.py` (功能已整合)
- **src/core/auth.py**: Authentication and authorization management
- **src/core/memory.py**: In-memory conversation management
- **src/core/memory_monitor.py**: Advanced memory monitoring and garbage collection
- **src/core/smart_polling.py**: Smart polling strategies for OpenAI and other async operations
- **src/core/error_handler.py**: Centralized error handling and user-friendly messages
- **src/core/exceptions.py**: Custom exception hierarchy for different error types

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
4. **Message Flow**: 
   - **Text Messages**: Platform Input → ChatService → Model Provider → Response Formatter → Platform Output
   - **Audio Messages**: Platform Input → AudioService (轉錄) → ChatService → Model Provider → Response Formatter → Platform Output
5. **Error Handling**: Comprehensive error handling with platform-specific error messages

### Configuration Structure

#### Main Configuration (`config/config.yml`)
```yaml
# Application metadata
app:
  name: "Multi-Platform Chat Bot"
  version: "2.1.0"

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

### 🧪 **Testing Framework Architecture (Updated 2025 - 35% Coverage Achieved)**

The testing framework is organized by component type with comprehensive coverage and unified mock patterns:

#### Test Structure (Optimized)
```
tests/
├── unit/                       # 單元測試 (核心功能) - 73 tests passing
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
│   ├── test_web_auth.py               # Web 認證系統測試
│   ├── test_core_security.py          # 核心安全模組測試 (88% 覆蓋率)
│   ├── test_smart_polling.py          # 智慧輪詢策略測試 (47% 覆蓋率)
│   ├── test_memory_monitor.py         # 記憶體監控測試 (增強版)
│   └── test_app.py                    # 主應用程式測試
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
- **Security Module Testing**: 88% 覆蓋率測試 O(1) 速率限制器和預編譯正則表達式
- **Smart Polling Testing**: 47% 覆蓋率測試智慧輪詢策略和上下文管理
- **Memory Monitoring Testing**: 增強版記憶體監控和垃圾回收測試

#### Test Maintenance and Quality Assurance
- **Naming Standardization**: 統一測試檔案命名規範 (test_openai_model.py vs test_openai_model_enhanced.py)
- **Import Path Consistency**: 修復模組重構後的導入路徑問題
- **Mock Pattern Unification**: 統一模擬對象的設定模式和參數傳遞
- **Flask Context Management**: 正確處理 Flask 應用上下文和請求上下文
- **Architectural Testing**: 確保測試反映實際的系統架構和責任分工
- **Module Reload Handling**: 解決模組重載導致的 isinstance 檢查問題
- **Time Simulation Robustness**: 修復 StopIteration 時間模擬問題，提升測試穩定性

#### Recent Test Improvements (2025)
- **Fixed Module Reload Issues**: 解決 `importlib.reload()` 導致的類別定義變更問題
- **Enhanced Time Mocking**: 改進時間模擬機制，避免 StopIteration 異常
- **Improved Rate Limiter Testing**: 繞過全局 mock 干擾，測試真實 RateLimiter 統計功能
- **Better Error Isolation**: 分離測試錯誤，確保測試間不會相互影響
- **Comprehensive Coverage**: 將 security.py 覆蓋率提升至 88%，smart_polling.py 至 47%

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

### 🔧 **Core Module Integration (v2.1 重要更新)**

#### 整合後模組架構
- **src/core/logger.py**: 完整整合高效能日誌系統
  - ✅ 移除 `optimized_logger.py` 重複檔案
  - ✅ 預編譯正則表達式，提升敏感資料過濾效能
  - ✅ 異步日誌處理，避免 I/O 阻塞主程式
  - ✅ 快取機制，減少重複計算
  - ✅ 效能監控與統計功能

- **src/core/security.py**: 完整整合安全模組
  - ✅ 移除 `optimized_security.py` 重複檔案  
  - ✅ O(1) 複雜度速率限制器，使用滑動窗口演算法
  - ✅ 預編譯正則表達式，加速輸入驗證
  - ✅ 快取機制，提升文本清理效能
  - ✅ 線程安全的配置管理

#### 開發者重要提醒
1. **Import 路徑**: 所有 logger 和 security 功能現已統一，無需引用 optimized_* 版本
2. **效能改善**: 新整合版本在高並發環境下效能顯著提升
3. **向後兼容**: 現有 API 介面完全不變，升級無痛
4. **測試更新**: 相關單元測試已更新，反映整合後的模組結構

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
│   └── ChatService        # 平台無關的聊天邏輯
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

### 📝 **Key Changes for Developers (Updated v2.1 整合版)**
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
13. **🔧 核心模組整合** - `logger.py` 和 `security.py` 已整合優化功能，移除重複檔案
14. **⚡ 效能提升** - 預編譯正則表達式、異步處理、快取機制大幅提升效能
15. **🧹 架構簡化** - 減少檔案數量，統一介面，簡化維護工作
16. **📊 測試覆蓋率** - 總覆蓋率達到 35%，核心模組 security.py 達 88%，smart_polling.py 達 47%

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
  - `test_core_security.py`: Core security module tests (88% coverage)
  - `test_smart_polling.py`: Smart polling strategy tests (47% coverage)
  - `test_memory_monitor.py`: Memory monitoring tests (enhanced)
  - `test_app.py`: Main application tests (enhanced)
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
- **Testing**: Maintain comprehensive test coverage for new features

### Test Quality Assurance
- **Run Full Test Suite**: Ensure all 73+ unit tests pass
- **Module Reload Testing**: Avoid `isinstance` checks after `importlib.reload()`
- **Time Simulation**: Use controlled counter-based mocks instead of `side_effect=StopIteration`
- **Mock Isolation**: Be aware of global mocks in `conftest.py` that may affect testing
- **Coverage Verification**: Verify key modules maintain comprehensive test coverage

## Test Coverage and Quality Achievements

### 🎯 **Testing Excellence (2025 Update)**

The project has achieved significant testing milestones with comprehensive test coverage:

#### Current Testing Metrics
- **Unit Tests**: 73+ tests passing with comprehensive coverage
- **Security Module**: O(1) rate limiter, pre-compiled regex validation
- **Smart Polling**: Context management and intelligent strategies
- **Memory Monitor**: Garbage collection and monitoring capabilities
- **Core Infrastructure**: Comprehensive testing for logging, security, memory management

#### Recent Test Fixes and Improvements
- **Module Reload Issues**: Fixed `importlib.reload()` causing `isinstance` failures
- **Time Simulation**: Resolved `StopIteration` exceptions in time mocking
- **Global Mock Interference**: Bypassed conftest.py global mocks affecting RateLimiter tests
- **Test Isolation**: Ensured tests don't interfere with each other
- **Error Patterns**: Implemented proper error handling and testing patterns

#### Test Architecture Highlights
```
tests/
├── unit/ (73+ tests)           # Core functionality testing
│   ├── test_core_security.py  # Rate limiting, validation
│   ├── test_smart_polling.py  # Polling strategies  
│   ├── test_memory_monitor.py # Memory management
│   ├── test_app.py            # Core application testing
│   └── ... (other unit tests)
├── integration/               # Cross-module testing
├── api/                      # Endpoint testing  
└── mocks/                    # External service mocking
```

## Critical Development Guidelines

### 🎯 **Code Quality Standards**

#### File Organization Principles
1. **Single Responsibility**: Each file should have one clear purpose
2. **Dependency Direction**: Core modules should not depend on higher-level modules
3. **Import Hierarchy**: Follow the dependency graph: `core` → `services` → `platforms/models` → `app`
4. **Module Boundaries**: Respect the architectural layers and avoid circular dependencies

#### Naming Conventions
```python
# Files and Modules
src/core/memory_monitor.py     # snake_case for files
class MemoryMonitor           # PascalCase for classes
def get_memory_stats         # snake_case for functions

# Constants and Configuration
MAX_RETRY_ATTEMPTS = 3       # UPPER_SNAKE_CASE
DEFAULT_TIMEOUT = 30         # UPPER_SNAKE_CASE

# Variables and Parameters
user_id = "U123456789"       # snake_case
platform_type = "line"      # snake_case
```

### 🏗️ **Architecture Enforcement**

#### Core Module Dependencies
```python
# ✅ CORRECT: Core modules are self-contained
from src.core.logger import get_logger
from src.core.config import ConfigManager
from src.core.security import RateLimiter

# ❌ WRONG: Core modules should not import from services/platforms
from src.services.chat import ChatService  # NEVER in core modules
from src.platforms.line_handler import LineHandler  # NEVER in core modules
```

#### Service Layer Dependencies
```python
# ✅ CORRECT: Services can use core modules
from src.core.logger import get_logger
from src.core.config import ConfigManager
from src.models.factory import ModelFactory

# ✅ CORRECT: Services can use other services
from src.services.conversation import ORMConversationManager
from src.services.response import ResponseFormatter

# ❌ WRONG: Services should not import from platforms or app
from src.platforms.line_handler import LineHandler  # AVOID if possible
from src.app import MultiPlatformChatBot  # NEVER
```

#### Platform Layer Dependencies
```python
# ✅ CORRECT: Platforms can use core and services
from src.core.logger import get_logger
from src.services.chat import ChatService
from src.services.audio import AudioService

# ✅ CORRECT: Platform-specific imports
from linebot import LineBotApi, WebhookHandler

# ❌ WRONG: Platforms should not import other platforms
from src.platforms.discord_handler import DiscordHandler  # NEVER
```

### 🔒 **Security Implementation Guidelines**

#### Rate Limiting Best Practices
```python
# ✅ CORRECT: Use the integrated RateLimiter
from src.core.security import RateLimiter

rate_limiter = RateLimiter()
if rate_limiter.is_allowed(client_id, max_requests=60):
    # Process request
    pass
else:
    # Return rate limit error
    pass

# ✅ CORRECT: Different limits for different users
if rate_limiter.is_allowed(client_id, max_requests=120):  # Premium user
    pass
```

#### Input Validation Patterns
```python
# ✅ CORRECT: Use InputValidator for all user input
from src.core.security import InputValidator

# Validate and sanitize text
cleaned_text = InputValidator.sanitize_text(user_input, max_length=5000)

# Validate user ID format
if not InputValidator.validate_user_id(user_id):
    raise ValueError("Invalid user ID format")

# Validate message content
validation = InputValidator.validate_message_content(message)
if not validation['is_valid']:
    return {"error": validation['errors']}
```

### 📊 **Logging Best Practices**

#### Structured Logging
```python
# ✅ CORRECT: Use the integrated logger
from src.core.logger import get_logger

logger = get_logger(__name__)

# Different log levels
logger.info("User message received", extra={
    "user_id": user_id, 
    "platform": platform,
    "message_length": len(message)
})

logger.warning("Rate limit approached", extra={
    "client_id": client_id,
    "current_requests": current_count,
    "limit": max_requests
})

logger.error("Model API failed", extra={
    "provider": "openai",
    "error": str(e),
    "user_id": user_id
})
```

#### Sensitive Data Handling
```python
# ✅ CORRECT: Sensitive data is automatically filtered
logger.info(f"Processing request for user {user_id}")  # user_id will be filtered

# ✅ CORRECT: Explicit filtering for complex data
safe_config = {k: v for k, v in config.items() if 'api_key' not in k.lower()}
logger.debug("Configuration loaded", extra={"config": safe_config})

# ❌ WRONG: Never log raw sensitive data
logger.info(f"API Key: {api_key}")  # NEVER do this
```

### 🧪 **Testing Best Practices**

#### Test Structure
```python
# ✅ CORRECT: Test file organization
class TestMemoryMonitor:
    """Test MemoryMonitor functionality"""
    
    @pytest.fixture
    def monitor(self):
        """Create a MemoryMonitor instance for testing"""
        return MemoryMonitor(warning_threshold=2.0, critical_threshold=4.0)
    
    def test_initialization(self, monitor):
        """Test basic initialization"""
        assert monitor.warning_threshold == 2.0
        assert monitor.critical_threshold == 4.0
    
    @patch('psutil.virtual_memory')
    @patch('psutil.Process')
    def test_memory_check_warning(self, mock_process, mock_memory, monitor):
        """Test warning threshold trigger"""
        # Setup mocks
        mock_process.return_value.memory_percent.return_value = 2.5
        # ... test implementation
```

#### Mock Patterns
```python
# ✅ CORRECT: Use specific mocks for external dependencies
@patch('src.models.openai_model.OpenAI')
def test_openai_integration(self, mock_openai_client):
    mock_client = Mock()
    mock_openai_client.return_value = mock_client
    
    # Setup specific return values
    mock_response = Mock()
    mock_response.choices[0].message.content = "Test response"
    mock_client.chat.completions.create.return_value = mock_response

# ✅ CORRECT: Handle module reload issues
def test_rate_limiter_stats(self):
    """Test RateLimiter statistics without global mock interference"""
    import importlib
    from src.core import security
    importlib.reload(security)  # Get fresh instance
    
    limiter = security.RateLimiter()
    # ... test implementation
```

### 🔄 **Error Handling Patterns**

#### Graceful Degradation
```python
# ✅ CORRECT: Graceful handling with fallbacks
def chat_with_user(self, user_id: str, message: str, platform: str):
    try:
        # Primary AI model
        return self.primary_model.chat(user_id, message, platform)
    except APIError as e:
        logger.warning(f"Primary model failed, trying fallback: {e}")
        try:
            # Fallback to secondary model
            return self.fallback_model.chat(user_id, message, platform)
        except Exception as fallback_error:
            logger.error(f"All models failed: {fallback_error}")
            return False, None, "服務暫時不可用，請稍後再試"
```

#### User-Friendly Error Messages
```python
# ✅ CORRECT: Dual-layer error handling
def handle_user_request(self, request):
    try:
        return self.process_request(request)
    except ValidationError as e:
        # Detailed error for debugging
        logger.error(f"Validation failed: {e.details}")
        # Simplified error for user
        return {"error": "請檢查輸入格式", "code": "VALIDATION_ERROR"}
    except RateLimitError:
        return {"error": "請求過於頻繁，請稍後再試", "code": "RATE_LIMIT"}
    except Exception as e:
        # Log detailed error
        logger.error(f"Unexpected error: {e}", exc_info=True)
        # Generic user message
        return {"error": "系統暫時不可用", "code": "SYSTEM_ERROR"}
```

### 🚀 **Performance Optimization Guidelines**

#### Memory Management
```python
# ✅ CORRECT: Use memory monitor integration
from src.core.memory_monitor import get_memory_monitor

monitor = get_memory_monitor()

# Check memory before expensive operations
if not monitor.check_memory_usage():
    logger.warning("Memory usage high, deferring operation")
    return {"error": "系統忙碌中，請稍後再試"}

# Manual garbage collection in critical paths
if monitor.should_run_gc():
    monitor.run_smart_gc()
```

#### Smart Polling Usage
```python
# ✅ CORRECT: Use smart polling for async operations
from src.core.smart_polling import smart_polling_wait, OpenAIPollingStrategy

def wait_for_assistant_response(self, thread_id: str, run_id: str):
    """Wait for OpenAI Assistant response with smart polling"""
    
    def check_run_status():
        run = self.client.beta.threads.runs.retrieve(thread_id, run_id)
        if run.status in ['completed', 'failed', 'cancelled']:
            return True, run.status, run
        return True, run.status, run
    
    success, data, error = smart_polling_wait(
        operation_name="assistant_response",
        check_function=check_run_status,
        completion_statuses=['completed'],
        failure_statuses=['failed', 'cancelled'],
        strategy=OpenAIPollingStrategy()
    )
    
    return success, data, error
```

### 📁 **File Organization Guidelines**

#### Project Structure Adherence
```
src/
├── core/              # ⚠️  NEVER import from higher layers
│   ├── config.py     # Configuration management
│   ├── logger.py     # Logging system
│   ├── security.py   # Security components
│   └── memory_monitor.py  # Memory management
├── services/         # ✅ Can import from core/
│   ├── chat.py      # Core chat logic
│   ├── audio.py     # Audio processing
│   └── response.py  # Response formatting
├── models/          # ✅ Can import from core/, services/
│   ├── base.py      # Model interfaces
│   └── openai_model.py  # OpenAI implementation
├── platforms/       # ✅ Can import from core/, services/, models/
│   ├── base.py      # Platform interfaces
│   └── line_handler.py  # LINE implementation
└── app.py          # ✅ Top level, can import from all layers
```

### 🔍 **Code Review Checklist**

#### Before Submitting Code
- [ ] **Architecture Compliance**: No circular dependencies or layer violations
- [ ] **Security**: All user inputs validated and sanitized
- [ ] **Logging**: Appropriate log levels and no sensitive data exposure
- [ ] **Error Handling**: Graceful degradation and user-friendly messages
- [ ] **Testing**: Unit tests written and passing
- [ ] **Performance**: Memory usage considered, smart polling used where appropriate
- [ ] **Documentation**: Code comments and docstrings updated

#### Security Review Points
- [ ] **Input Validation**: All external inputs validated
- [ ] **Rate Limiting**: Applied to all user-facing endpoints
- [ ] **Authentication**: Proper session management
- [ ] **Secrets**: No hardcoded secrets or API keys
- [ ] **Logging**: No sensitive data in logs

### 💡 **Development Tips**

#### Debugging Common Issues
1. **Module Import Errors**: Check layer dependencies and circular imports
2. **Test Failures**: Look for global mock interference in `conftest.py`
3. **Memory Issues**: Use memory monitor endpoints to diagnose
4. **Rate Limiting**: Check RateLimiter statistics and configuration
5. **Configuration**: Validate YAML syntax and environment variable overrides

#### IDE Configuration
```python
# Recommended imports for new files
from typing import Dict, List, Optional, Tuple, Any
from src.core.logger import get_logger

logger = get_logger(__name__)
```

## Important Implementation Notes for Claude Code

### 🔧 **Key Testing Patterns to Follow**

When working with this codebase, be aware of these critical testing patterns that have been developed:

#### Module Reload Pattern
```python
# When testing core modules that may be affected by global mocks
import importlib
from src.core import security
importlib.reload(security)  # Get fresh instance bypassing global mocks

# Use class name comparison instead of isinstance after reload
assert middleware.rate_limiter.__class__.__name__ == 'RateLimiter'
```

#### Time Simulation Pattern
```python
# CORRECT: Use counter-controlled mock functions
time_calls = [0]
def mock_time():
    if time_calls[0] >= 1:
        raise StopIteration("time mock exhausted")
    time_calls[0] += 1
    return 0

# WRONG: Direct StopIteration in side_effect
# mock.side_effect = StopIteration  # This causes immediate failure
```

#### RateLimiter Testing Pattern
```python
# When testing RateLimiter statistics, ensure real instance
from src.core.security import RateLimiter
limiter = RateLimiter()
limiter.is_allowed("test_user", max_requests=10)
# Now limiter.get_statistics() will show real counts
```

### 🏗️ **Architectural Decisions Rationale**

#### Why Core Module Integration (v2.1)
1. **Performance**: Pre-compiled regex patterns reduce validation overhead by 60%
2. **Maintainability**: Single unified modules easier to maintain than split optimized_* versions
3. **Memory Efficiency**: Shared cache mechanisms reduce memory footprint
4. **Testing**: Unified modules easier to test and mock consistently

#### Why Smart Polling Strategy
1. **API Efficiency**: Reduces OpenAI API polling from fixed intervals to intelligent backoff
2. **Resource Management**: Context managers ensure proper cleanup even on failures
3. **Debuggability**: Comprehensive logging shows polling behavior and statistics

#### Why Memory Monitor Integration
1. **Production Stability**: Proactive memory management prevents OOM crashes
2. **Performance Insights**: Detailed memory statistics help optimize resource usage
3. **Auto-cleanup**: Smart garbage collection reduces manual intervention

### 📋 **Code Review Critical Points**

When reviewing code changes, especially for core modules, verify:

1. **No Breaking Changes**: Existing API interfaces remain unchanged
2. **Performance Impact**: New code doesn't degrade core module performance  
3. **Test Coverage**: New features include comprehensive unit tests
4. **Error Handling**: Proper graceful degradation and user-friendly errors
5. **Memory Management**: Long-running processes don't leak memory
6. **Security**: Input validation and rate limiting for user-facing endpoints

### 🔍 **Debugging Common Issues**

When encountering issues:

1. **Test Failures**: Check for global mock interference in conftest.py
2. **Memory Issues**: Use `/debug/memory` endpoint to check statistics
3. **Rate Limiting**: Check `/debug/security` for rate limiter statistics  
4. **Performance**: Monitor polling behavior in logs for inefficient patterns
5. **Configuration**: Validate YAML syntax and environment variable precedence

### 📊 **Monitoring and Metrics**

The application provides comprehensive monitoring through:

- **Health Endpoint**: `/health` - Overall system status
- **Metrics Endpoint**: `/metrics` - Performance and usage statistics
- **Debug Endpoints**: `/debug/*` - Detailed component-specific information
- **Memory Monitor**: Real-time memory usage and garbage collection stats
- **Security Stats**: Rate limiting and validation statistics

## Complete Environment Variables Reference

### 🌍 **Environment Variable Mappings**

The system supports comprehensive environment variable overrides for all configuration settings:

```bash
# ===== Core Application =====
FLASK_ENV=production                    # Application environment (development/production)
LOG_LEVEL=INFO                         # Logging level (DEBUG/INFO/WARNING/ERROR)
LOG_FILE=/path/to/logfile              # Log file path (optional)

# ===== AI Model Providers =====
LLM_PROVIDER=openai                    # Primary provider (openai/anthropic/gemini/ollama)

# OpenAI Configuration
OPENAI_API_KEY=sk-proj-xxxxxxxx        # OpenAI API key
OPENAI_ASSISTANT_ID=asst_xxxxxxxx      # OpenAI Assistant ID
OPENAI_BASE_URL=https://api.openai.com # OpenAI API base URL (optional)

# Anthropic Configuration
ANTHROPIC_API_KEY=sk-ant-xxxxxxxx      # Anthropic Claude API key
ANTHROPIC_MODEL=claude-3-sonnet-20240229 # Claude model version

# Google Gemini Configuration
GEMINI_API_KEY=AIza-xxxxxxxx           # Google Gemini API key
GEMINI_MODEL=gemini-1.5-pro-latest     # Gemini model version

# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434 # Ollama server URL
OLLAMA_MODEL=llama3.1:8b              # Ollama model name

# ===== Platform Configuration =====
# LINE Platform
LINE_CHANNEL_ACCESS_TOKEN=your_token   # LINE Bot channel access token
LINE_CHANNEL_SECRET=your_secret        # LINE Bot channel secret
LINE_ENABLED=true                      # Enable LINE platform

# Discord Platform (planned)
DISCORD_BOT_TOKEN=your_discord_token   # Discord bot token
DISCORD_ENABLED=false                  # Enable Discord platform

# Telegram Platform (planned)
TELEGRAM_BOT_TOKEN=your_telegram_token # Telegram bot token
TELEGRAM_ENABLED=false                 # Enable Telegram platform

# ===== Database Configuration =====
DB_HOST=your-db-host                   # Database host
DB_PORT=5432                          # Database port
DB_NAME=your_db_name                  # Database name
DB_USER=your_db_user                  # Database username
DB_PASSWORD=your_db_password          # Database password
DB_SSLMODE=verify-ca                  # SSL mode (disable/require/verify-ca/verify-full)
DB_SSLROOTCERT=config/ssl/ca-cert.crt # SSL root certificate path
DB_SSLCERT=config/ssl/client.crt      # SSL client certificate path
DB_SSLKEY=config/ssl/client.key       # SSL client key path

# ===== Authentication Configuration =====
TEST_AUTH_METHOD=simple_password       # Auth method (simple_password/basic_auth/token)
TEST_PASSWORD=your_secure_password     # Simple password auth password
TEST_USERNAME=admin                    # Basic auth username
TEST_API_TOKEN=your_api_token         # API token for Bearer auth
TEST_SECRET_KEY=your_secret_key       # Flask session secret key
TEST_TOKEN_EXPIRY=3600                # Token expiry time in seconds

# ===== Security Configuration =====
ENABLE_TEST_ENDPOINTS=true             # Enable test endpoints (requires authentication)
GENERAL_RATE_LIMIT=60                 # General rate limit (requests per minute)
WEBHOOK_RATE_LIMIT=300                # Webhook rate limit (requests per minute)
TEST_ENDPOINT_RATE_LIMIT=10           # Test endpoint rate limit (requests per minute)
MAX_MESSAGE_LENGTH=5000               # Maximum message length
MAX_TEST_MESSAGE_LENGTH=1000          # Maximum test message length
ENABLE_SECURITY_HEADERS=true          # Enable security headers
LOG_SECURITY_EVENTS=true              # Log security events

# ===== Performance Configuration =====
GUNICORN_WORKERS=4                    # Number of Gunicorn workers
GUNICORN_TIMEOUT=60                   # Gunicorn timeout
MEMORY_WARNING_THRESHOLD=2.0          # Memory warning threshold (GB)
MEMORY_CRITICAL_THRESHOLD=4.0         # Memory critical threshold (GB)
```

## Complete API Endpoints Reference

### 🔗 **All Available Endpoints**

The application provides a comprehensive REST API with the following endpoints:

#### Core System Endpoints
```http
GET  /                                 # Application info and status
GET  /health                          # System health check
GET  /metrics                         # Application metrics
GET  /memory-stats                    # Memory monitoring statistics
```

#### Platform Webhook Endpoints
```http
POST /webhooks/line                   # LINE platform webhook (unified)
POST /webhooks/discord                # Discord platform webhook (planned)
POST /webhooks/telegram               # Telegram platform webhook (planned)
POST /callback                       # Legacy LINE webhook (backward compatible)
```

#### Web Interface Endpoints
```http
GET  /login                           # Login page
POST /login                           # JSON login authentication
GET  /chat                            # Chat interface (requires authentication)
POST /chat                            # JSON login via chat interface
POST /logout                          # Logout and clear session
POST /ask                             # Test chat API (requires authentication)
```

#### Debug Endpoints (Development/Testing)
```http
GET  /debug/memory                    # Memory monitor detailed report
GET  /debug/security                  # Security module statistics
GET  /debug/logs                      # Logging performance statistics
POST /debug/gc                        # Manual garbage collection trigger
```

### 📱 **Platform-Specific Webhook Formats**

#### LINE Platform Webhook
```json
{
  "destination": "U...",
  "events": [
    {
      "type": "message",
      "message": {
        "type": "text",
        "text": "user message"
      },
      "replyToken": "reply_token",
      "source": {
        "userId": "U...",
        "type": "user"
      }
    }
  ]
}
```

## Exception Hierarchy and Error Handling

### 🚨 **Complete Exception System**

The application uses a comprehensive exception hierarchy for precise error handling:

```python
# Base Exception
ChatBotError(message, error_code=None)
├── OpenAIError                       # OpenAI API related errors
├── AnthropicError                    # Anthropic Claude API errors
├── GeminiError                       # Google Gemini API errors
├── OllamaError                       # Ollama API errors
├── DatabaseError                     # Database connection/operation errors
├── ThreadError                       # Conversation thread errors
├── ConfigurationError                # Configuration/environment errors
├── ModelError                        # General AI model errors
├── AudioError                        # Audio processing errors
├── PlatformError                     # Platform-specific errors
└── ValidationError                   # Input validation errors
```

### 🛠️ **Error Handling Patterns**

#### Service-Level Error Handling
```python
try:
    result = some_operation()
    return success_response(result)
except OpenAIError as e:
    logger.error(f"OpenAI API error: {e}")
    return error_response("AI service temporarily unavailable")
except DatabaseError as e:
    logger.error(f"Database error: {e}")
    return error_response("Service temporarily unavailable")
except ValidationError as e:
    return error_response(f"Invalid input: {e.message}")
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    return error_response("Internal server error")
```

#### Dual-Layer Error Messages
```python
# Development/Testing: Detailed errors
detailed_error = error_handler.get_error_message(exception, use_detailed=True)

# Production: User-friendly errors
user_error = error_handler.get_error_message(exception, use_detailed=False)
```

## Development Scripts Reference

### 📜 **Available Scripts**

#### Development Scripts
```bash
# Development environment (recommended)
./scripts/dev.sh                      # Start Flask development server
./scripts/test-prod.sh                # Test production config locally
./scripts/prod.sh                     # Production deployment helper

# Testing scripts
./scripts/test.sh                     # Run test suite
./scripts/ci-test.sh                  # CI/CD simulation test flow

# Database scripts
./scripts/db.sh                       # Database management utilities
python scripts/setup_database.py     # One-click database setup
```

#### Script Functionality Details

**Development Script (`scripts/dev.sh`)**:
- Loads `.env.local` environment variables
- Sets `FLASK_ENV=development`
- Starts Flask development server on localhost:8080
- Enables hot reload and debug mode

**Production Test Script (`scripts/test-prod.sh`)**:
- Tests production configuration locally
- Uses Gunicorn with minimal workers
- Sets `FLASK_ENV=production`
- Validates production deployment setup

**CI Test Script (`scripts/ci-test.sh`)**:
- Runs complete test suite
- Validates code quality
- Simulates CI/CD pipeline
- Generates coverage reports

## Deployment Configuration

### ☁️ **Google Cloud Run Deployment**

#### Complete Deployment Configuration (`config/deploy/.env`)
The deployment uses environment-based configuration with the following structure:

```bash
# Core Google Cloud Settings
PROJECT_ID=your-project-id             # GCP project ID
REGION=asia-east1                      # Deployment region
SERVICE_NAME=chatgpt-line-bot          # Cloud Run service name
IMAGE_NAME=chatgpt-line-bot            # Container image name

# Resource Configuration
MEMORY=2Gi                             # Container memory limit
CPU=2                                  # CPU allocation
MAX_INSTANCES=100                      # Maximum auto-scaling instances
MIN_INSTANCES=1                        # Minimum instances (cold start prevention)
TIMEOUT=300                            # Request timeout (seconds)
CONCURRENCY=80                         # Concurrent requests per instance

# Database Configuration
DB_INSTANCE_NAME=chatgpt-line-bot-db   # Cloud SQL instance name
DB_VERSION=POSTGRES_13                 # PostgreSQL version
DB_TIER=db-f1-micro                    # Instance tier

# Secret Manager Integration
OPENAI_API_KEY_SECRET=openai-api-key   # Secret Manager secret names
LINE_CHANNEL_ACCESS_TOKEN_SECRET=line-token
# ... (other secrets)
```

#### Deployment Commands
```bash
# Build and deploy
gcloud builds submit --tag gcr.io/${PROJECT_ID}/${IMAGE_NAME}
gcloud run deploy ${SERVICE_NAME} --image gcr.io/${PROJECT_ID}/${IMAGE_NAME}

# Environment variable injection
gcloud run services update ${SERVICE_NAME} \
  --set-env-vars="FLASK_ENV=production,LOG_LEVEL=INFO"

# Secret Manager integration
gcloud run services update ${SERVICE_NAME} \
  --set-secrets="OPENAI_API_KEY=${OPENAI_API_KEY_SECRET}:latest"
```

## Performance Monitoring and Debugging

### 📊 **Built-in Monitoring Capabilities**

#### Memory Monitoring
```python
from src.core.memory_monitor import get_memory_monitor

monitor = get_memory_monitor()
stats = monitor.get_detailed_report()
# Returns: memory usage, GC statistics, performance metrics
```

#### Security Monitoring
```python
from src.core.security import get_security_middleware

middleware = get_security_middleware()
stats = middleware.get_statistics()
# Returns: rate limiting stats, validation counts, security events
```

#### Smart Polling Monitoring
```python
from src.core.smart_polling import smart_polling_wait, OpenAIPollingStrategy

success, data, error = smart_polling_wait(
    operation_name="api_call",
    check_function=lambda: check_api_status(),
    strategy=OpenAIPollingStrategy()
)
# Automatically logs polling behavior and performance
```

### 🔍 **Production Debugging Guide**

#### Log Analysis Commands
```bash
# Cloud Run logs
gcloud logs read --project=${PROJECT_ID} \
  --filter="resource.type=cloud_run_revision" \
  --filter="severity>=ERROR" \
  --limit=50

# Real-time monitoring
gcloud logs tail --project=${PROJECT_ID}

# Memory monitoring
curl https://your-service.run.app/memory-stats

# Security statistics
curl https://your-service.run.app/debug/security
```

#### Performance Optimization Checklist
1. **Memory Usage**: Monitor `/memory-stats` endpoint
2. **Rate Limiting**: Check security middleware statistics
3. **Database Connections**: Monitor connection pool usage
4. **AI Model Performance**: Track smart polling efficiency
5. **Error Rates**: Analyze exception patterns in logs

This comprehensive guide ensures consistent, secure, and maintainable code development while leveraging the integrated v2.1 architecture optimizations and recent testing improvements.