# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Line Bot that connects to OpenAI Assistant API, deployed on Google Cloud Run with Google Cloud SQL for thread storage. The bot processes both text and audio messages (via Whisper transcription), maintaining conversation threads per user and supporting file search capabilities through OpenAI's Assistant API.

## Development Commands

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
python main.py
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

- **main.py**: Flask application entry point with Line webhook handlers
- **src/models.py**: OpenAI API interface with ModelInterface abstraction
- **src/db.py**: SQLAlchemy-based database layer for user thread management
- **src/config.py**: YAML configuration loader
- **src/utils.py**: Text processing utilities including OpenCC conversion and file reference handling
- **src/logger.py**: Logging configuration

### Key Architecture Patterns

1. **Thread Management**: Each Line user gets a persistent OpenAI Assistant thread stored in PostgreSQL
2. **Message Flow**: Text/Audio → Preprocessing → OpenAI Assistant API → Postprocessing → Line Response
3. **File Reference System**: Assistant responses include file citations that are resolved to readable filenames
4. **Error Handling**: Comprehensive error handling with user-friendly Chinese error messages

### Configuration Structure

The application uses `config/config.yml` with the following sections:
- `line`: Channel access token and secret
- `openai`: API key and assistant ID
- `db`: PostgreSQL connection with SSL certificates
- `text_processing`: Pre/post-processing rules including date string replacement
- `commands`: Custom bot commands (e.g., `/help`, `/reset`)

### Database Schema

```sql
CREATE TABLE user_thread_table (
    user_id VARCHAR(255) PRIMARY KEY,
    thread_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
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

## Text Processing Pipeline

1. **Preprocessing**: Date string replacement (今天/明天/昨天 → YYYY/MM/DD format)
2. **OpenAI Processing**: Assistant API with file search capabilities
3. **Postprocessing**: 
   - Simplified to Traditional Chinese conversion using OpenCC
   - File reference resolution using file_dict mapping
   - Custom text replacements via config

## API Endpoints

- `POST /callback`: Line webhook for message handling
- `GET /`: Health check endpoint
- `GET /chat`: Web chat interface
- `POST /ask`: Web API for chat functionality

## Dependencies

Key Python packages:
- `line-bot-sdk`: Line Bot integration
- `Flask`: Web framework
- `opencc-python-reimplemented`: Chinese text conversion
- `SQLAlchemy` + `psycopg2`: PostgreSQL database
- `pyyaml`: Configuration management
- `gunicorn`: Production WSGI server