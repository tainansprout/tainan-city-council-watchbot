# Tainan City Council WatchBot

[中文](README.md) | English

This project is a chatbot using Line as the front-end, connected to multiple LLM providers including OpenAI Assistant API, Anthropic Claude, Google Gemini, and Ollama. The bot supports RAG (Retrieval-Augmented Generation) functionality and will be deployed on Google Cloud Run with Google Cloud SQL for thread management.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Obtaining OpenAI API Token](#obtaining-openai-api-token)
- [Setting Up OpenAI Assistant API](#setting-up-openai-assistant-api)
- [Configuring the Line Bot](#configuring-the-line-bot)
- [Configuring Google Cloud SQL](#configuring-google-cloud-sql)
- [Finalizing Configuration Files](#finalizing-configuration-files)
- [Deploying to Google Cloud Run](#deploying-to-google-cloud-run)
- [Testing the Application](#testing-the-application)
- [Development & Testing](#development--testing)

## Prerequisites

- A Google Cloud Platform account with billing enabled
- Access to OpenAI API
- A Line Developers account

## Obtaining OpenAI API Token

1. Register/Login at [OpenAI Platform](https://platform.openai.com/)
2. Create a new Project from the avatar menu in the upper left corner.
3. Once inside the Project, navigate to Project → API Key.
4. Click `+ Create` in the upper right corner to generate an OpenAI API Token.

## Setting Up OpenAI Assistant API

1. **Create an Assistant**
   - Within the project, go to "Playground" at the top, then select "Assistants" on the left to enter the OpenAI Assistant API interface. Create a new Assistant.

2. **Upload Required Files for Database**
   - In the Assistant interface, configure the name and System instructions as the bot's default system prompt. It's recommended to select `gpt-4o` as the model and set Temperature to `0.01`.
   - Go to Tools → File Search, click `+ Files` to upload files you want as the database.

3. **Testing in Playground**
   - Go to [OpenAI Playground](https://platform.openai.com/playground) and test the Assistant’s functionality.

4. **Record assistant_id**
   - Under the Assistant name, there’s a text string representing the `assistant_id`. Note it down for later use.

## Configuring the Line Bot

1. **Create a Line Bot**
   - Log into the [Line Developers Console](https://developers.line.biz/console/)
   - Create a new Provider and Channel (Messaging API).

2. **Get Channel Information**
   - In the Channel settings, obtain the `Channel Access Token` and `Channel Secret`.
   - Under `Basic Settings`, there’s a `Channel Secret`. Click `Issue` to generate your `channel_secret`.
   - Under `Messaging API`, there’s a `Channel Access Token`. Click `Issue` to generate your `channel_access_token`.

3. **Set Webhook URL**
   - Set the Webhook URL to the address of the Google Cloud Run deployment (this can be updated post-deployment).
   - Enable the Webhook by toggling the "Use Webhook" switch to on.

## Configuring Google Cloud SQL

1. **Create Cloud SQL Instance**
   - Go to [Cloud SQL Instances](https://console.cloud.google.com/sql/instances).
   - Click **Create Instance** and choose the required database (e.g., PostgreSQL).

2. **Instance Configuration**
   - Set up the instance name and password.
   - Create an account for connection operations, noting down the username and password.
   - Create the database and use Cloud SQL Studio to run the following SQL command to create the table:

    ```sql
    CREATE TABLE user_thread_table (
        user_id VARCHAR(255) PRIMARY KEY,
        thread_id VARCHAR(255),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
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
line:
  channel_access_token: YOUR_CHANNEL_ACCESS_TOKEN
  channel_secret: YOUR_CHANNEL_SECRET

openai:
  api_key: YOUR_OPENAI_API_KEY
  assistant_id: YOUR_ASSISTANT_ID

db:
  host: YOUR_DB_HOST
  port: 5432
  db_name: YOUR_DB_NAME
  user: YOUR_DB_USER
  password: YOUR_DB_PASSWORD
  sslmode: verify-ca
  sslrootcert: config/ssl/ca-cert.crt
  sslcert: config/ssl/client.crt
  sslkey: config/ssl/client.key
```

**Method 2: Using Environment Variables**

```bash
# Set environment variables
export LINE_CHANNEL_ACCESS_TOKEN="your_token"
export LINE_CHANNEL_SECRET="your_secret"
export OPENAI_API_KEY="sk-proj-xxxxxxxx"
export OPENAI_ASSISTANT_ID="asst_xxxxxxxx"
export DB_HOST="your_db_host"
export DB_USER="your_db_user"
export DB_PASSWORD="your_db_password"
export DB_NAME="your_db_name"

# Run application
python main.py
```

### ☁️ Production Environment Configuration

Production environment uses Google Secret Manager to manage sensitive information, injected into containers through environment variables.

**Supported Environment Variable Mapping**:

| Configuration Item | config.yml Path | Environment Variable |
|--------------------|-----------------|---------------------|
| Line Access Token | `line.channel_access_token` | `LINE_CHANNEL_ACCESS_TOKEN` |
| Line Secret | `line.channel_secret` | `LINE_CHANNEL_SECRET` |
| OpenAI API Key | `openai.api_key` | `OPENAI_API_KEY` |
| OpenAI Assistant ID | `openai.assistant_id` | `OPENAI_ASSISTANT_ID` |
| Database Host | `db.host` | `DB_HOST` |
| Database User | `db.user` | `DB_USER` |
| Database Password | `db.password` | `DB_PASSWORD` |
| Database Name | `db.db_name` | `DB_NAME` |
| Auth Method | `auth.method` | `TEST_AUTH_METHOD` |
| Log Level | `log_level` | `LOG_LEVEL` |

### 🔍 Configuration Validation

```bash
# Check application configuration
python src/core/config.py

# Check deployment configuration
./scripts/deploy/deploy-to-cloudrun.sh --dry-run
```

For detailed configuration instructions, please refer to: [Configuration Management Guide](docs/CONFIGURATION.md)

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
   gcloud builds submit --tag gcr.io/{your-project-id}/{your-image-name} -f deploy/Dockerfile.cloudrun .
   ```

3. **Deploy to Cloud Run**

   ```bash
   gcloud run services replace deploy/cloudrun-service.yaml --region {your-region}
   ```

   - Replace placeholders with your actual information.

4. **Test Deployment Results**

   - After deployment, a Service URL will be returned, e.g., `https://chatgpt-line-bot-****.run.app`. Note this down.

5. **Set Webhook URL**

   - In the Line Bot settings, set the Webhook URL to the Service URL.
   - Enable Webhook by toggling the "Use Webhook" switch on.
   - Click Verify to check the connection.

## Testing the Application

1. **Access Chat Endpoint**
   - Go to the Service URL, e.g., `https://{your-cloud-run-url}/chat`, to ensure the app is running smoothly.

2. **Test with Line**
   - Send a message to your Line Bot to test its full functionality.

3. **Check Logs**
   - If issues arise, use `gcloud` or Google Cloud Console to inspect logs.

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
   
   # Production mode (using Gunicorn)
   python wsgi.py
   ```

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

**Type checking:**
```bash
mypy src/
```

**Code linting:**
```bash
flake8 src/
```

### Development Features

- **Multi-LLM Support**: OpenAI, Anthropic Claude, Google Gemini, Ollama
- **RAG Implementation**: File search and retrieval across all model providers
- **Modular Architecture**: Clean separation of concerns with factory patterns
- **Comprehensive Testing**: Unit, integration, and API test suites
- **Type Safety**: Full type annotations with mypy validation
- **Error Handling**: Robust error handling with structured logging
- **Security**: Secret management with Google Secret Manager
- **Monitoring**: Cloud monitoring and alerting integration

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
