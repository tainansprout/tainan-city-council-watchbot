# Multi-Platform ChatGPT Line Bot

[中文](README.md) | English

This project is a **multi-platform chatbot** supporting LINE, Discord, Telegram and other platforms, integrated with multiple AI model providers (OpenAI, Anthropic Claude, Google Gemini, Ollama). The bot features modular architecture design, deployed on Google Cloud Run with Google Cloud SQL for conversation history management, and supports both text and audio message processing.

## Core Features

🤖 **Multi-AI Model Support**: Unified interface integrating OpenAI, Anthropic, Gemini, Ollama  
🌐 **Multi-Platform Support**: Unified management of LINE, Discord, Telegram platforms  
📚 **RAG Knowledge Base**: All models support document retrieval and citation features  
🔗 **Unified Citation Processing**: Consistent citation formatting across models  
🎯 **Platform Abstraction**: Factory Pattern supports rapid expansion of new platforms  
🛡️ **Enterprise-Grade Security**: Input validation, rate limiting, error handling  
📊 **Monitoring & Logging**: Complete system monitoring and performance metrics

## Table of Contents

- [Prerequisites](#prerequisites)
- [AI Model Setup](#ai-model-setup)
  - [OpenAI Assistant API](#setting-up-openai-assistant-api)
  - [Anthropic Claude](#setting-up-anthropic-claude)
  - [Google Gemini](#setting-up-google-gemini)
  - [Ollama Local Models](#setting-up-ollama-local-models)
- [Platform Setup](#platform-setup)
  - [LINE Bot](#configuring-the-line-bot)
  - [Discord Bot](#setting-up-discord-bot)
  - [Telegram Bot](#setting-up-telegram-bot)
- [System Configuration](#system-configuration)
  - [Database Setup](#configuring-google-cloud-sql)
  - [Multi-Platform Configuration](#configuration-management)
- [Deployment](#deployment)
  - [Local Development](#local-development-setup)
  - [Google Cloud Run](#deploying-to-google-cloud-run)
- [Development & Testing](#development--testing)

## Prerequisites

### Basic Requirements
- Python 3.8+ development environment
- Google Cloud Platform account (for deployment and database)

### AI Model Providers (choose at least one)
- **OpenAI**: API key and Assistant setup
- **Anthropic Claude**: API key
- **Google Gemini**: API key
- **Ollama**: Local model runtime environment

### Chat Platforms (choose at least one)
- **LINE**: LINE Developers account
- **Discord**: Discord Developer Portal account
- **Telegram**: Telegram BotFather setup

## AI Model Setup

### Obtaining OpenAI API Token

1. Register/Login at [OpenAI Platform](https://platform.openai.com/)
2. Create a new Project from the avatar menu in the upper left corner.
3. Once inside the Project, navigate to Project → API Key.
4. Click `+ Create` in the upper right corner to generate an OpenAI API Token.

### Setting Up Anthropic Claude

1. **Get Claude API Key**
   - Go to [Anthropic Console](https://console.anthropic.com/)
   - Register and log in to your account
   - Create a new API Key in the API Keys page

2. **Choose Model**
   - Recommended to use `claude-3-sonnet-20240229` or `claude-3-haiku-20240307`
   - Choose models that balance performance and cost based on your needs

### Setting Up Google Gemini

1. **Get Gemini API Key**
   - Go to [Google AI Studio](https://aistudio.google.com/)
   - Log in with your Google account
   - Create a new API Key in the API Keys page

2. **Choose Model**
   - Recommended to use `gemini-1.5-pro-latest` or `gemini-1.5-flash-latest`
   - Gemini supports long context and multimodal functionality

### Setting Up Ollama Local Models

1. **Install Ollama**
   ```bash
   # macOS
   brew install ollama
   
   # Linux
   curl -fsSL https://ollama.ai/install.sh | sh
   
   # Windows - Download installer
   # https://ollama.ai/download
   ```

2. **Download Models**
   ```bash
   # Download Llama 3.1 8B model (recommended)
   ollama pull llama3.1:8b
   
   # Or download other models
   ollama pull mistral:7b
   ollama pull codellama:13b
   ```

3. **Start Service**
   ```bash
   ollama serve
   # Default runs on http://localhost:11434
   ```

## Setting Up OpenAI Assistant API

1. **Create an Assistant**
   - Within the project, go to "Playground" at the top, then select "Assistants" on the left to enter the OpenAI Assistant API interface. Create a new Assistant.

2. **Upload Required Files for Database**
   - In the Assistant interface, configure the name and System instructions as the bot's default system prompt. It's recommended to select `gpt-4o` as the model and set Temperature to `0.01`.
   - Go to Tools → File Search, click `+ Files` to upload files you want as the database.

3. **Testing in Playground**
   - Go to [OpenAI Playground](https://platform.openai.com/playground) and test the Assistant's functionality.

4. **Record assistant_id**
   - Under the Assistant name, there's a text string representing the `assistant_id`. Note it down for later use.

## Platform Setup

### Configuring the Line Bot

1. **Create a Line Bot**
   - Log into the [Line Developers Console](https://developers.line.biz/console/)
   - Create a new Provider and Channel (Messaging API).

2. **Get Channel Information**
   - In the Channel settings, obtain the `Channel Access Token` and `Channel Secret`.
   - Under `Basic Settings`, there's a `Channel Secret`. Click `Issue` to generate your `channel_secret`.
   - Under `Messaging API`, there's a `Channel Access Token`. Click `Issue` to generate your `channel_access_token`.

3. **Set Webhook URL**
   - Set the Webhook URL to the Google Cloud Run deployment address (can be updated after deployment)
   - Enable Webhook by toggling the "Use Webhook" switch to on

### Setting Up Discord Bot

1. **Create Discord Application**
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Click "New Application" to create a new application
   - Name your application

2. **Create Bot**
   - Select "Bot" from the left menu
   - Click "Add Bot" to create a bot
   - Copy the Bot Token (keep it secret)

3. **Set Permissions**
   - In "OAuth2" → "URL Generator", select appropriate permissions
   - Generate invite link and add the bot to your server

### Setting Up Telegram Bot

1. **Chat with BotFather**
   - Search for @BotFather in Telegram
   - Send `/newbot` command to create a new bot
   - Follow instructions to set bot name and username

2. **Get Bot Token**
   - BotFather will provide a Bot Token
   - Save this token for configuration

3. **Set Webhook**
   - After deployment, use the following API to set webhook:
   ```bash
   curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
        -H "Content-Type: application/json" \
        -d '{"url": "https://your-app.run.app/webhooks/telegram"}'
   ```

## Configuring Google Cloud SQL

1. **Create Cloud SQL Instance**
   - Go to [Cloud SQL Instances](https://console.cloud.google.com/sql/instances).
   - Click **Create Instance** and choose the required database (e.g., PostgreSQL).

2. **Instance Configuration**
   - Set up the instance name and password.
   - Create an account for connection operations, noting down the username and password.
   - Create the database
   - Use Alembic to create multi-platform database schema:
    ```bash
    # Initialize Alembic (if not already done)
    alembic init alembic
    
    # Create initial migration
    alembic revision --autogenerate -m "Initial multi-platform schema"
    
    # Execute migration
    alembic upgrade head
    ```
    
   - Or manually create multi-platform tables:
    ```sql
    -- OpenAI thread management (multi-platform support)
    CREATE TABLE user_thread_table (
        user_id VARCHAR(255) NOT NULL,
        platform VARCHAR(50) NOT NULL DEFAULT 'line',
        thread_id VARCHAR(255) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, platform)
    );
    
    -- Conversation history for other models (multi-platform support)
    CREATE TABLE simple_conversation_history (
        id SERIAL PRIMARY KEY,
        user_id VARCHAR(255) NOT NULL,
        platform VARCHAR(50) NOT NULL DEFAULT 'line',
        model_provider VARCHAR(50) NOT NULL,
        role VARCHAR(20) NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Create performance indexes
    CREATE INDEX idx_thread_user_platform ON user_thread_table(user_id, platform);
    CREATE INDEX idx_conversation_user_platform ON simple_conversation_history(user_id, platform);
    CREATE INDEX idx_conversation_user_platform_provider ON simple_conversation_history(user_id, platform, model_provider);
    ```

3. **Get Connection Information**
   - After creating the instance, record the following details:
     - Instance Connection Name
     - Host
     - Port
     - Database Name
     - Username
     - Password

4. **Obtain SSL Certificates**
   - Go to the instance details page.
   - Under the **Connections** tab, enable SSL connections.
   - Download the following certificates:
     - Server CA Certificate
     - Client Certificate
     - Client Key
   - Convert these certificates and keys using the following commands:

    ```bash
    openssl x509 -in client-cert.pem -out ssl-cert.crt # Server CA Certificate
    openssl x509 -in server-ca.pem -out ca-cert.crt # Client Certificate
    openssl rsa -in client-key.pem -out ssl-key.key # Client Key
    ```
   - Copy `ssl-cert.crt`, `ca-cert.crt`, and `ssl-key.key` to `config/ssl/`.

## Configuration Management

This project supports flexible configuration management to adapt to different deployment environment needs.

### 🎯 Configuration Priority

**Application Configuration Priority** (higher priority overrides lower priority):
1. `config/config.yml` - Basic configuration file
2. **Environment Variables** - Highest priority (suitable for production)

**Deployment Script Configuration Priority**:
1. `config/deploy/.env` - Deployment configuration file
2. **Environment Variables** - Highest priority
3. Interactive Input - Prompts when configuration is missing

### 📁 Configuration File Locations

```
config/
├── config.yml.example          # Application configuration template
├── config.yml                  # Application configuration (create manually)
└── deploy/
    ├── .env.example            # Deployment configuration template
    ├── .env                    # Deployment configuration (create manually)
    ├── Dockerfile.cloudrun     # Cloud Run Dockerfile
    └── cloudrun-service.yaml   # Cloud Run service configuration
```

### 💻 Local Development Configuration

Prepare the following information:
- `channel_access_token` - Line Channel Access Token
- `channel_secret` - Line Channel Secret
- `openai_api_key` - OpenAI API Key
- `assistant_id` - OpenAI Assistant ID
- Database connection information

**Method 1: Using Configuration File (Recommended)**

```bash
# Copy configuration template
cp config/config.yml.example config/config.yml

# Edit configuration file
vim config/config.yml
```

```yaml
# Application information
app:
  name: "Multi-Platform Chat Bot"
  version: "2.0.0"

# AI model settings (choose one as primary provider)
llm:
  provider: "openai"  # openai, anthropic, gemini, ollama

# AI model provider settings
openai:
  api_key: YOUR_OPENAI_API_KEY
  assistant_id: YOUR_ASSISTANT_ID

anthropic:
  api_key: YOUR_ANTHROPIC_API_KEY
  model: "claude-3-sonnet-20240229"

gemini:
  api_key: YOUR_GEMINI_API_KEY
  model: "gemini-1.5-pro-latest"

ollama:
  base_url: "http://localhost:11434"
  model: "llama3.1:8b"

# Database settings
db:
  host: YOUR_DB_HOST
  port: 5432
  database: YOUR_DB_NAME
  username: YOUR_DB_USER
  password: YOUR_DB_PASSWORD
  sslmode: verify-ca
  sslrootcert: config/ssl/ca-cert.crt
  sslcert: config/ssl/client.crt
  sslkey: config/ssl/client.key

# Platform settings
platforms:
  line:
    enabled: true
    channel_access_token: YOUR_LINE_CHANNEL_ACCESS_TOKEN
    channel_secret: YOUR_LINE_CHANNEL_SECRET
  
  discord:
    enabled: false  # Set to true to enable
    bot_token: YOUR_DISCORD_BOT_TOKEN
  
  telegram:
    enabled: false  # Set to true to enable
    bot_token: YOUR_TELEGRAM_BOT_TOKEN

# Text processing settings
text_processing:
  preprocessors: []
  post_replacements: []

# Command settings
commands:
  help: "Provide system instructions and available commands"
  reset: "Reset conversation history"
```

**Method 2: Using Environment Variables**

```bash
# Basic settings
export LLM_PROVIDER="openai"  # or anthropic, gemini, ollama

# AI model API keys (set according to chosen provider)
export OPENAI_API_KEY="sk-proj-xxxxxxxx"
export OPENAI_ASSISTANT_ID="asst_xxxxxxxx"
export ANTHROPIC_API_KEY="sk-ant-xxxxxxxx"
export GEMINI_API_KEY="AIza-xxxxxxxx"

# Platform settings (enable required platforms)
export LINE_CHANNEL_ACCESS_TOKEN="your_line_token"
export LINE_CHANNEL_SECRET="your_line_secret"
export DISCORD_BOT_TOKEN="your_discord_token"      # Optional: Enable Discord platform
export TELEGRAM_BOT_TOKEN="your_telegram_token"    # Optional: Enable Telegram platform

# Database settings
export DB_HOST="your_db_host"
export DB_USER="your_db_user"
export DB_PASSWORD="your_db_password"
export DB_NAME="your_db_name"

# Run application (using unified entry point)
python main.py
```

### ☁️ Production Environment Configuration

Production environment uses Google Secret Manager to manage sensitive information, injected into containers through environment variables.

**Supported Environment Variable Mapping**:

| Configuration Item | config.yml Path | Environment Variable |
|--------------------|-----------------|---------------------|
| Line Access Token | `platforms.line.channel_access_token` | `LINE_CHANNEL_ACCESS_TOKEN` |
| Line Secret | `platforms.line.channel_secret` | `LINE_CHANNEL_SECRET` |
| OpenAI API Key | `openai.api_key` | `OPENAI_API_KEY` |
| OpenAI Assistant ID | `openai.assistant_id` | `OPENAI_ASSISTANT_ID` |
| Database Host | `db.host` | `DB_HOST` |
| Database User | `db.user` | `DB_USER` |
| Database Password | `db.password` | `DB_PASSWORD` |
| Database Name | `db.db_name` | `DB_NAME` |
| Auth Method | `auth.method` | `TEST_AUTH_METHOD` |
| Log Level | `log_level` | `LOG_LEVEL` |

### 🚀 **Unified Startup Method (v2.0)**

The new version provides a unified entry point that automatically switches run modes based on the environment:

#### Development Environment
```bash
# Auto-detects as development environment, uses Flask development server
python main.py

# Or explicitly specify development environment
FLASK_ENV=development python main.py
```

#### Production Environment
```bash
# Auto-starts Gunicorn production server
FLASK_ENV=production python main.py

# Or use traditional method
gunicorn -c gunicorn.conf.py main:application
```

#### Backward Compatibility
```bash
# Legacy compatible deployment method (integrated into main.py)
gunicorn -c gunicorn.conf.py main:application
```

### 🔍 Configuration Validation

```bash
# Check application configuration
python src/core/config.py

# Check health status
curl http://localhost:8080/health

# Check deployment configuration
./scripts/deploy/deploy-to-cloudrun.sh --dry-run
```

For detailed configuration instructions, please refer to:
- [Configuration Management Guide](docs/CONFIGURATION.md)
- [Deployment Guide](DEPLOYMENT_GUIDE.md)

## Deploying to Google Cloud Run

### 🚀 Quick Deployment (Recommended)

Use our automated deployment scripts:

```bash
# 1. Set up deployment configuration
cp config/deploy/.env.example config/deploy/.env
# Edit config/deploy/.env file with your project settings

# 2. Run automated deployment script
./scripts/deploy/deploy-to-cloudrun.sh

# 3. Check configuration (optional)
./scripts/deploy/deploy-to-cloudrun.sh --dry-run
```

### 📖 Comprehensive Deployment Guide

For complete deployment process, monitoring setup, load balancer configuration, etc., please refer to:
- [Complete Deployment Guide](docs/DEPLOYMENT.md)
- [Configuration Management Guide](docs/CONFIGURATION.md)
- [Running Guide](docs/RUNNING.md)

### 🔧 Manual Deployment (Advanced Users)

If you want to manually control each step:

1. **Configure Google Cloud Console**

   ```bash
   gcloud auth login
   gcloud config set project {your-project-id}
   ```

2. **Build Container Image**

   ```bash
   gcloud builds submit --tag gcr.io/{your-project-id}/{your-image-name} -f config/deploy/Dockerfile.cloudrun .
   ```

3. **Deploy to Cloud Run**

   ```bash
   gcloud run services replace config/deploy/cloudrun-service.yaml --region {your-region}
   ```

   - Replace placeholders with your actual information.

4. **Test Deployment Results**

   - After deployment, a Service URL will be returned, e.g., `https://chatgpt-line-bot-****.run.app`. Note this down.

5. **Set Webhook URL**

   - In the Line Bot settings, set the Webhook URL to the Service URL.
   - Enable Webhook by toggling the "Use Webhook" switch on.
   - Click Verify to check the connection.

## Testing the Application

### 🔐 Web Test Interface (v2.0)

1. **Access Login Page**
   - Go to `https://{your-cloud-run-url}/login`
   - Enter the test password set in `config.yml`
   - After successful login, you'll be automatically redirected to the chat interface

2. **Use Chat Interface**
   - After login, visit `https://{your-cloud-run-url}/chat`
   - Test bot functionality directly in the chat interface
   - Supports text messages and complete conversation history
   - Click "Logout" button to safely logout

3. **API Endpoint Testing**
   ```bash
   # Health check
   curl https://{your-cloud-run-url}/health
   
   # Application information
   curl https://{your-cloud-run-url}/
   ```

### 📱 Testing via LINE

4. **LINE Bot Functionality Test**
   - Send messages to your LINE Bot to test complete functionality
   - Supports text and voice messages
   - Test conversation history and multi-turn conversations

### 🔍 Troubleshooting

5. **Check System Logs**
   - If issues arise, use `gcloud` or Google Cloud Console to check logs
   ```bash
   # View real-time logs
   gcloud logs tail --project={your-project-id}
   ```

### ⚙️ Test Password Configuration

**Production Environment**:
```bash
# Set environment variable (recommended)
export TEST_PASSWORD="your_secure_password_here"
```

**Development Environment**:
```yaml
# Set in config/config.yml
auth:
  method: "simple_password"
  password: "your_test_password"
```

## Development & Testing

### Local Development Setup

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Local Environment Variables**
   ```bash
   # Copy environment template
   cp .env.local.example .env.local
   
   # Edit .env.local with your configurations
   vim .env.local
   ```

3. **Run Development Server**
   
   **🔧 Development Environment (Recommended):**
   ```bash
   # Start using development script
   ./scripts/dev.sh
   ```
   
   **🧪 Local Production Testing:**
   ```bash
   # Test production configuration locally
   ./scripts/test-prod.sh
   ```
   
   **⚡ Direct Execution:**
   ```bash
   # Development mode (warnings are normal)
   python main.py
   
   # Production mode (auto-starts Gunicorn)
   FLASK_ENV=production python main.py
   ```

## System Architecture

### Core Components

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Platform Layer│    │   AI Model Layer │    │   Data Layer    │
├─────────────────┤    ├──────────────────┤    ├─────────────────┤
│ • LINE Bot      │    │ • OpenAI         │    │ • PostgreSQL    │
│ • Discord Bot   │───▶│ • Anthropic      │───▶│ • Thread Mgmt   │
│ • Telegram Bot  │    │ • Gemini         │    │ • Conv History  │
│ • Web Chat      │    │ • Ollama         │    │ • User Data     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
          │                       │                       │
          └───────────────────────┼───────────────────────┘
                                  ▼
                    ┌──────────────────────────┐
                    │    Unified Processing    │
                    ├──────────────────────────┤
                    │ • ChatService (Core)    │
                    │ • ResponseFormatter      │
                    │ • AudioService          │
                    │ • ConversationManager   │
                    └──────────────────────────┘
```

### Unified Citation Processing

All AI models' document citations are unified through `ResponseFormatter`:

**Processing Flow**:
1. **AI Model Response** → Contains RAGResponse (answer + sources)
2. **ResponseFormatter** → Unifies source formatting to readable citations
3. **Final Response** → Consistent citation format `[1]: Document Name`

**Supported Citation Formats**:
- **OpenAI**: Assistant API file citations `[i]` → `[i]: filename`
- **Anthropic**: Claude Files API references `[filename]` → `[i]: filename`  
- **Gemini**: Semantic Retrieval results → `[i]: filename (Relevance: 95%)`
- **Ollama**: Vector search results → `[i]: filename (Similarity: 0.89)`

### Design Patterns

- **Factory Pattern**: Dynamic creation of AI models and platforms
- **Strategy Pattern**: Unified interface for different AI models
- **Registry Pattern**: Registration management for platforms and models
- **Adapter Pattern**: Adaptation of platform-specific features

### Install Test Dependencies

```bash
pip install -r requirements-test.txt
```

### Running Tests

This project uses pytest as the testing framework, including unit tests, integration tests, and API tests.

**Run all tests:**
```bash
pytest
```

**Run specific test types:**
```bash
# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# API tests
pytest tests/api/

# External service mock tests
pytest tests/mocks/
```

**Test coverage report:**
```bash
pytest --cov=src --cov-report=html
```

**Detailed test output:**
```bash
pytest -v
```

**Specify test file:**
```bash
pytest tests/unit/test_models.py
pytest tests/integration/test_chat_flow.py
```

### Code Quality Checks

```bash
# Check code style
flake8 src/ tests/

# Type checking
mypy src/
```

### Test Troubleshooting

If you encounter import errors or cache issues:
```bash
# Clean Python cache files
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
rm -rf .pytest_cache

# Re-run tests
pytest
```

**CI/CD Integration Testing:**
```bash
# Run complete CI/CD simulation test flow
./scripts/ci-test.sh
```

### Test Architecture

- **Unit Tests** (`tests/unit/`): Test individual modules and functions
- **Integration Tests** (`tests/integration/`): Test service integration
- **API Tests** (`tests/api/`): Test Flask endpoints
- **Mock Tests** (`tests/mocks/`): Test external service mocks

### Configuration Files

Test configuration files are located in `pytest.ini`, including the following settings:
- Test paths
- Coverage settings
- Test markers
- Output format

## Notes

- Ensure all sensitive information is stored only in `config/ssl/` and `config/config.yml`.
- Use Google Secret Manager to manage secrets if necessary.
- Follow best practices for security and compliance.

## Support Us

This project is by Tainan Sprout. To support the project, please [donate to Tainan Sprout](https://bit.ly/3RBvPyZ).

## Acknowledgments

This project is forked from [ExplainThis's ChatGPT-Line-Bot](https://github.com/TheExplainthis/ChatGPT-Line-Bot). Special thanks to them.

## License

[MIT](LICENSE)