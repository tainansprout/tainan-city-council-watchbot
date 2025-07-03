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

#### ⚡ 直接運行
```bash
# Development mode (會顯示警告，正常現象)
python main.py

# Production mode (使用 Gunicorn)
python wsgi.py
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

# Deploy to Cloud Run
gcloud run deploy {service-name} \
  --image gcr.io/{project-id}/{image-name} \
  --platform managed \
  --port 8080 \
  --memory 2G \
  --timeout=2m \
  --region {region}
```

## Architecture

### Core Components

#### Application Layer
- **src/app.py**: Multi-platform Flask application with unified webhook handlers
- **main.py**: Legacy entry point (deprecated - use src/app.py)

#### Platform Layer (Strategy Pattern)
- **src/platforms/base.py**: Platform abstraction interfaces and data classes
- **src/platforms/line_handler.py**: LINE platform-specific message handling
- **src/platforms/factory.py**: Platform factory and registry for handler management

#### Service Layer
- **src/services/core_chat_service.py**: Platform-agnostic core conversation logic
- **src/services/chat_service.py**: Legacy service (deprecated)
- **src/services/conversation_manager_orm.py**: Conversation history management
- **src/services/response_formatter.py**: Unified response formatting

#### Model Layer (Factory Pattern)
- **src/models/base.py**: Abstract model interfaces and data structures
- **src/models/openai_model.py**: OpenAI Assistant API integration
- **src/models/anthropic_model.py**: Anthropic Claude API integration
- **src/models/gemini_model.py**: Google Gemini API integration
- **src/models/ollama_model.py**: Local Ollama model integration
- **src/models/factory.py**: Model factory for provider selection

#### Database Layer
- **src/models/database.py**: SQLAlchemy ORM models with multi-platform support
- **src/database/db.py**: Legacy database interface (deprecated)

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
  database: "${DB_NAME}"
  username: "${DB_USER}"
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

### Multi-Platform Webhooks
- `POST /webhook/line`: LINE platform webhook
- `POST /webhook/discord`: Discord platform webhook  
- `POST /webhook/telegram`: Telegram platform webhook
- `POST /callback`: Legacy LINE webhook (deprecated)

### System Endpoints
- `GET /`: Application health check and status
- `GET /health`: Detailed health check with database and model status
- `GET /metrics`: Application metrics and statistics

### Web Interface (Optional)
- `GET /chat`: Web-based chat interface
- `POST /ask`: Web API for direct chat functionality

### Configuration and Management
- `GET /config`: Current configuration status
- `GET /platforms`: Available platform information

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

### Database Initialization
```bash
# Initialize Alembic migrations
alembic init migrations

# Create initial migration
alembic revision --autogenerate -m "Initial multi-platform schema"

# Apply migrations
alembic upgrade head
```

### Platform Migration Commands
```bash
# Run database setup script
./scripts/db.sh init

# Add platform support to existing data
python scripts/db_commands.py migrate-platform-support

# Check migration status
alembic current
alembic history
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
python -m pytest tests/unit/test_core_chat_service.py
```

### Test Structure
- `tests/unit/`: Unit tests for individual components
  - `test_platforms.py`: Platform abstraction tests
  - `test_core_chat_service.py`: Core chat service tests
  - `test_models.py`: AI model integration tests
- `tests/integration/`: End-to-end integration tests
  - `test_platform_integration.py`: Platform workflow tests
  - `test_database_integration.py`: Database and ORM tests

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