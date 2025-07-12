# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Multi-Platform Chatbot** supporting LINE, Discord, Telegram and other platforms. The system features a modular architecture with multiple AI model providers (OpenAI, Anthropic Claude, Google Gemini, Ollama) and comprehensive conversation management. The application is deployed on Google Cloud Run with Google Cloud SQL for conversation storage and supports both text and audio message processing.

**v2.1 Core Infrastructure Integration**: Integrated high-performance logging and security modules for optimal performance and simplified maintenance.

## Development Commands

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Setup local environment
cp .env.local.example .env.local
# Edit .env.local with your configuration

# Run development server
python main.py
```

### Docker Development
```bash
# Build and run with Docker Compose
docker-compose up --build
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
  --region {region} \
  --set-env-vars FLASK_ENV=production
```

## Architecture

### Core Components

#### Application Layer
- **main.py**: Unified entry point with automatic environment detection
- **src/app.py**: Multi-platform Flask application with unified webhook handlers

#### Platform Layer (Strategy Pattern)
- **src/platforms/base.py**: Platform abstraction interfaces
- **src/platforms/line_handler.py**: LINE platform implementation
- **src/platforms/factory.py**: Platform factory and registry

#### Service Layer
- **src/services/chat.py**: Core conversation logic
- **src/services/audio.py**: Audio transcription service
- **src/services/conversation.py**: Conversation history management
- **src/services/response.py**: Unified response formatting

#### Core Infrastructure (v2.1)
- **src/core/config.py**: Configuration management
- **src/core/logger.py**: Unified logging system with performance optimization
- **src/core/security.py**: Security middleware with O(1) rate limiting
- **src/core/memory_monitor.py**: Memory monitoring and garbage collection
- **src/core/smart_polling.py**: Intelligent polling strategies

#### Model Layer (Factory Pattern)
- **src/models/base.py**: Abstract model interfaces
- **src/models/openai_model.py**: OpenAI Assistant API integration
- **src/models/anthropic_model.py**: Anthropic Claude API integration
- **src/models/gemini_model.py**: Google Gemini API integration
- **src/models/ollama_model.py**: Local Ollama model integration

#### Database Layer
- **src/database/connection.py**: Database connection management
- **src/database/models.py**: SQLAlchemy ORM models
- **src/database/operations.py**: Database operations toolkit

### Message Processing Flow

The system follows a **strict separation of concerns** architecture to ensure maintainability and extensibility:

#### Text Message Flow
```
User → Platform Handler → App.py → ChatService → Model → Response
```

#### Audio Message Flow  
```
User → Platform Handler → App.py → AudioService → Model (transcription) → App.py → ChatService → Model (chat) → Response
```

#### Detailed Processing Steps

**1. Platform Layer (src/platforms/)**
- **Responsibility**: Webhook parsing, message extraction, media download, response delivery
- **NEVER**: Perform audio transcription or AI model calls
- **Output**: PlatformMessage with raw_data for audio messages

**2. Application Layer (src/app.py)**
- **Responsibility**: Message routing and service coordination
- **Process**: 
  - Receive PlatformMessage from platform handlers
  - Route audio messages to AudioService for transcription
  - Route text messages (including transcribed audio) to ChatService
  - Coordinate response delivery back to platforms

**3. Service Layer**
- **AudioService (src/services/audio.py)**: Audio-to-text transcription only
- **ChatService (src/services/chat.py)**: Text message processing and AI conversation
- **NEVER**: Services should not know about specific platforms

**4. Model Layer (src/models/)**
- **Responsibility**: AI functionality (chat, transcription)
- **NEVER**: Know about platform sources or message routing

### Key Architecture Patterns

1. **Factory Pattern**: Model and platform selection
2. **Strategy Pattern**: Platform-specific message handling  
3. **Dependency Injection**: Model instances injected into services
4. **Separation of Concerns**: Each layer has single responsibility
5. **Multi-Platform Support**: Unified conversation management
6. **Model Agnostic**: Support for multiple AI providers

### Critical Design Principles

⚠️ **NEVER violate these principles**:

1. **Platform handlers MUST NOT call model APIs directly**
2. **Models MUST NOT know about platform types**
3. **Audio transcription MUST happen in AudioService, not platforms**
4. **App.py is the ONLY coordinator between layers**
5. **Each layer should have single responsibility**

📖 **For detailed documentation, see:**
- **Architecture**: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **Interface Specifications**: [docs/INTERFACES.md](docs/INTERFACES.md)  
- **Model Status & Features**: [docs/MODEL_STATUS.md](docs/MODEL_STATUS.md)

## Configuration

### Main Configuration (config/config.yml)
```yaml
# Application
app:
  name: "Multi-Platform Chat Bot"
  version: "2.1.0"

# Model configuration
llm:
  provider: "openai"  # openai, anthropic, gemini, ollama

# Platform configurations
platforms:
  line:
    enabled: true
    channel_access_token: "${LINE_CHANNEL_ACCESS_TOKEN}"
    channel_secret: "${LINE_CHANNEL_SECRET}"

# Database
db:
  host: "${DB_HOST}"
  port: ${DB_PORT}
  db_name: "${DB_NAME}"
  user: "${DB_USER}"
  password: "${DB_PASSWORD}"

# Authentication
auth:
  method: "simple_password"
  password: "${TEST_PASSWORD}"
```

### Environment Variables
```bash
# Core
FLASK_ENV=production
LLM_PROVIDER=openai

# AI Models
OPENAI_API_KEY=sk-proj-xxxxxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxxxxx
GEMINI_API_KEY=AIza-xxxxxxxx

# Platform
LINE_CHANNEL_ACCESS_TOKEN=your_token
LINE_CHANNEL_SECRET=your_secret

# Database
DB_HOST=your-db-host
DB_NAME=your_db_name
DB_USER=your_db_user
DB_PASSWORD=your_db_password
```

## Database Management

### Quick Setup
```bash
# Auto-setup database (recommended)
python scripts/db_migration.py auto-setup

# Traditional setup
python scripts/setup_database.py setup

# Direct Alembic (advanced)
alembic upgrade head
```

### Common Commands
```bash
# Check status
python scripts/db_migration.py current

# Create migration
python scripts/db_migration.py create -m "feature_name"

# Upgrade database
python scripts/db_migration.py upgrade
```

## API Endpoints

### Core Endpoints
- `GET /`: Application information
- `GET /health`: System health check
- `GET /metrics`: Application metrics

### Platform Webhooks
- `POST /webhooks/line`: LINE platform webhook
- `POST /webhooks/discord`: Discord platform webhook
- `POST /webhooks/telegram`: Telegram platform webhook

### Web Interface
- `GET /login`: Login page
- `GET /chat`: Chat interface (requires authentication)
- `POST /ask`: Chat API (requires authentication)

## Testing

### Running Tests
```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=src --cov-report=html

# Run specific categories
python -m pytest tests/unit/
python -m pytest tests/integration/
```

### Test Structure
```
tests/
├── unit/           # Unit tests (112+ tests)
├── integration/    # Integration tests
├── api/           # API endpoint tests
└── mocks/         # External service mocks
```

## Development Guidelines

### File Organization
```
src/
├── core/          # Core infrastructure (no higher-level imports)
├── services/      # Business logic (can import from core)
├── models/        # AI model implementations
├── platforms/     # Platform-specific handlers
└── app.py        # Main application (can import from all)
```

### Key Development Patterns

#### Platform Handler Implementation (CORRECT)
```python
# ✅ CORRECT: Platform only downloads and provides raw data
class PlatformHandler(BasePlatformHandler):
    def parse_message(self, event) -> PlatformMessage:
        if message_type == "audio":
            # Only download raw audio data
            raw_data = self._download_audio(audio_url)
            content = "[Audio Message]"  # Placeholder text
            
            return PlatformMessage(
                message_type="audio",
                content=content,
                raw_data=raw_data  # Provide to app layer
            )
```

#### Platform Handler Anti-Pattern (WRONG)
```python
# ❌ WRONG: Platform should NOT transcribe audio
class PlatformHandler(BasePlatformHandler):
    def parse_message(self, event) -> PlatformMessage:
        if message_type == "audio":
            raw_data = self._download_audio(audio_url)
            # ❌ DON'T DO THIS: Platform calling model
            transcribed_text = self.audio_handler.transcribe_audio(raw_data)
            return PlatformMessage(content=transcribed_text)
```

#### App Layer Coordination (CORRECT)
```python
# ✅ CORRECT: App.py coordinates services
def _handle_webhook(self, platform_name: str):
    messages = self.platform_manager.handle_platform_webhook(...)
    
    for message in messages:
        if message.message_type == "audio":
            # Step 1: AudioService transcribes
            audio_result = self.audio_service.handle_message(
                user_id=message.user.user_id,
                audio_content=message.raw_data
            )
            
            if audio_result['success']:
                # Step 2: Create text message for ChatService  
                text_message = PlatformMessage(
                    content=audio_result['transcribed_text'],
                    message_type="text"
                )
                # Step 3: ChatService processes text
                response = self.chat_service.handle_message(text_message)
        else:
            # Direct text processing
            response = self.chat_service.handle_message(message)
```

#### Service Layer Implementation (CORRECT)
```python
# ✅ CORRECT: Services are platform-agnostic
class AudioService:
    def handle_message(self, user_id: str, audio_content: bytes, platform: str):
        # Only transcribes audio, doesn't know about platform specifics
        success, transcribed_text, error = process_audio(audio_content, self.model)
        return {'success': success, 'transcribed_text': transcribed_text}

class ChatService:
    def handle_message(self, message: PlatformMessage):
        # Only processes text, works with any platform
        return self.model.chat_with_user(message.user.user_id, message.content)
```

#### Configuration Management
```python
from src.core.config import ConfigManager

config = ConfigManager().get_config()
```

#### Logging
```python
from src.core.logger import get_logger

logger = get_logger(__name__)
logger.info("Message", extra={"user_id": user_id})
```

#### Error Handling
```python
try:
    result = operation()
except SpecificError as e:
    logger.error(f"Operation failed: {e}")
    return error_response("User-friendly message")
```

#### Memory Management
```python
from src.core.memory_monitor import get_memory_monitor

monitor = get_memory_monitor()
if not monitor.check_memory_usage():
    return {"error": "System busy, try again later"}
```

## Important Development Notes

### v2.1 Integration Updates
- **Core Modules**: `logger.py` and `security.py` are now unified (removed optimized_* versions)
- **Performance**: Pre-compiled regex patterns and async processing
- **Testing**: 86% total coverage with comprehensive unit tests

### Deployment
- **Development**: `python main.py` (auto-detects environment)
- **Production**: `FLASK_ENV=production python main.py` (auto-starts Gunicorn)
- **Docker**: Environment auto-detection works in containers

### Authentication
- **Web Interface**: Session-based authentication
- **API**: JSON-only endpoints
- **Configuration**: Set in `config.yml` under `auth` section

## Dependencies

### Core Framework
- Flask, SQLAlchemy, PyYAML, Gunicorn

### Platform Integrations
- line-bot-sdk, discord.py, python-telegram-bot, slack-sdk

### AI Model Providers
- openai, anthropic, google-generativeai, requests (for Ollama)

### Text Processing
- opencc-python-reimplemented, python-dateutil

### Development
- pytest, mypy, black, flake8

## Collaboration Guidelines

### Communication Preferences
- **Language**: 中文 (Traditional Chinese) for discussions, English for code comments
- **Code Style**: Follow existing patterns in the codebase, use descriptive variable names
- **Commit Messages**: Use conventional commits format (feat:, fix:, docs:, etc.)

### Development Workflow
- **Testing**: Always run tests before committing changes
- **Code Quality**: Run linting and type checking before submitting code
- **Documentation**: Update relevant documentation when adding new features
- **Error Handling**: Implement proper error handling and user-friendly messages
- **Git Operations**: Do not perform git restore or git commit operations unless explicitly requested

### Code Quality Standards
- **Structure**: Ensure clear separation of concerns with well-defined responsibilities for each file
- **DRY Principle**: Avoid redundant code and refactor duplicated logic into reusable components
- **Test Coverage**: Add comprehensive tests for all modified code sections
- **Design Patterns**: Implement appropriate design patterns following current best practices
- **Modern Practices**: Research latest documentation and best practices for all packages, as they may have evolved
- **Architecture Review**: Periodically evaluate code architecture and propose refactoring when necessary
- **Documentation Updates**: Update documentation to reflect any significant changes or architectural modifications

### Task Management
- **Planning**: Break down complex tasks into smaller, manageable steps
- **Progress Updates**: Provide regular updates on task completion status
- **Problem Solving**: Explain approach and reasoning when implementing solutions
- **Code Review**: Focus on functionality, performance, and maintainability

### Project-Specific Guidelines
- **Multi-Platform**: Consider impact on all supported platforms (LINE, Discord, Telegram)
- **AI Models**: Test changes across different model providers (OpenAI, Anthropic, Gemini, Ollama)
- **Database**: Use migration scripts for schema changes
- **Security**: Follow security best practices, especially for user input validation
- **Performance**: Monitor memory usage and optimize for Cloud Run deployment
- **Package Updates**: When using newer package versions, research current best practices and API changes
- **Refactoring**: Regularly assess if code structure can be improved for better maintainability
- **Testing Framework**: Maintain clear test organization matching the source code structure

### Response Style
- **Conciseness**: Keep responses focused and to the point
- **Clarity**: Explain complex concepts in simple terms
- **Practicality**: Provide actionable solutions with working code examples
- **Context Awareness**: Consider the current state of the codebase and recent changes