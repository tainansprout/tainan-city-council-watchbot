# Multi-Platform ChatGPT Line Bot

[中文](README.md) | English

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Test Coverage](https://img.shields.io/badge/coverage-35%25-red.svg)](htmlcov/index.html)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)](https://github.com/tnsprout/ChatGPT-Line-Bot/actions)

This project is a **multi-platform chatbot** supporting LINE, Discord, Telegram and other platforms, integrated with multiple AI model providers (OpenAI, Anthropic Claude, Google Gemini, Ollama). The bot features modular architecture design, deployed on Google Cloud Run with Google Cloud SQL for conversation history management, and supports both text and audio message processing.

**🆕 v2.1 Core Infrastructure Integration Upgrade**: High-performance logging system and security module integration, optimizing performance and simplifying maintenance.

> This project is forked from [ExplainThis's ChatGPT-Line-Bot](https://github.com/TheExplainthis/ChatGPT-Line-Bot)

## Core Features

🤖 **Multi-AI Model Support**: Unified interface integrating OpenAI, Anthropic, Gemini, Ollama  
🌐 **Multi-Platform Support**: Unified management of LINE, Discord, Telegram platforms  
📚 **RAG Knowledge Base**: All models support document retrieval and citation features  
🔗 **Unified Citation Processing**: Consistent citation formatting across models  
🛡️ **Enterprise-Grade Security**: Input validation, rate limiting, error handling  
📊 **Monitoring & Logging**: Complete system monitoring and performance metrics

## Quick Start

### Prerequisites
- Python 3.8+ development environment
- Google Cloud Platform account
- At least one AI model provider API key
- At least one chat platform configuration

### 3-Step Deployment

```bash
# 1. Download and install dependencies
git clone https://github.com/tnsprout/ChatGPT-Line-Bot.git
cd ChatGPT-Line-Bot
pip install -r requirements.txt

# 2. Quick configuration
cp config/config.yml.example config/config.yml
# Edit config.yml with your API keys

# 3. Local development
python main.py
```

## Configuration

### Basic Configuration File (`config/config.yml`)

```yaml
# AI Model configuration
llm:
  provider: "openai"  # openai, anthropic, gemini, ollama

# OpenAI configuration
openai:
  api_key: "${OPENAI_API_KEY}"
  assistant_id: "${OPENAI_ASSISTANT_ID}"

# LINE platform configuration
platforms:
  line:
    enabled: true
    channel_access_token: "${LINE_CHANNEL_ACCESS_TOKEN}"
    channel_secret: "${LINE_CHANNEL_SECRET}"

# Database configuration
db:
  host: "${DB_HOST}"
  port: ${DB_PORT}
  db_name: "${DB_NAME}"
  user: "${DB_USER}"
  password: "${DB_PASSWORD}"
```

### Environment Variables

```bash
# Core settings
export FLASK_ENV=production
export LLM_PROVIDER=openai

# AI model API keys
export OPENAI_API_KEY=sk-proj-xxxxxxxx
export ANTHROPIC_API_KEY=sk-ant-xxxxxxxx
export GEMINI_API_KEY=AIza-xxxxxxxx

# LINE platform
export LINE_CHANNEL_ACCESS_TOKEN=your_token
export LINE_CHANNEL_SECRET=your_secret

# Database
export DB_HOST=your-db-host
export DB_NAME=your_db_name
export DB_USER=your_db_user
export DB_PASSWORD=your_db_password
```

## System Architecture

```
src/
├── core/              # Core infrastructure
│   ├── config.py      # Configuration management
│   ├── logger.py      # Logging system
│   ├── security.py    # Security module
│   └── memory_monitor.py  # Memory monitoring
├── services/          # Business logic layer
│   ├── chat.py        # Chat service
│   ├── audio.py       # Audio processing
│   ├── conversation.py # Conversation management
│   └── response.py    # Response formatting
├── models/            # AI model integration
│   ├── openai_model.py    # OpenAI integration
│   ├── anthropic_model.py # Anthropic integration
│   ├── gemini_model.py    # Gemini integration
│   └── ollama_model.py    # Ollama integration
├── platforms/         # Platform support
│   ├── base.py        # Platform abstraction
│   ├── factory.py     # Platform factory
│   └── line_handler.py # LINE platform handler
└── database/          # Database layer
    ├── connection.py  # Database connection
    ├── models.py      # Data models
    └── operations.py  # Database operations
```

## Deployment

### Google Cloud Run Deployment

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

# Health check
curl https://{service-url}/health
```

### Database Setup

```bash
# Auto-setup database (recommended)
python scripts/db_migration.py auto-setup

# Or use traditional method
python scripts/setup_database.py setup
```

## Development & Testing

### Local Development

```bash
# Development mode
python main.py  # Auto-detects development environment

# Production mode testing
FLASK_ENV=production python main.py
```

### Running Tests

```bash
# Run all tests
python -m pytest

# Run tests with coverage report
python -m pytest --cov=src --cov-report=html

# Run specific test categories
python -m pytest tests/unit/
python -m pytest tests/integration/
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

## Documentation

For detailed configuration and deployment guides, please refer to:

- [Configuration Management Guide](docs/CONFIGURATION.md)
- [Deployment Guide](docs/DEPLOYMENT.md)
- [Security Guide](docs/SECURITY.md)
- [Database Management](docs/ORM_GUIDE.md)
- [Developer Guide](CLAUDE.md)

## FAQ

### Q: Bot not responding after deployment?
1. Check if Webhook URL is configured correctly
2. Verify environment variables are set properly
3. Check Cloud Run logs for troubleshooting

### Q: AI model response errors?
1. Confirm API keys are valid
2. Check model configuration
3. Review application logs for detailed errors

### Q: Database connection failed?
1. Verify database connection parameters
2. Check SSL certificate configuration
3. Validate firewall rules

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the project and create a feature branch
2. Make your changes and write tests
3. Ensure all tests pass
4. Submit a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

If you encounter issues or need assistance:

1. Check the [FAQ](docs/FAQ.md)
2. Submit issues on [GitHub Issues](https://github.com/tnsprout/ChatGPT-Line-Bot/issues)
3. Review the [Developer Guide](CLAUDE.md) for technical details