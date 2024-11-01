# Tainan City Council WatchBot

[中文](README.md) | English

This project is a chatbot using Line as the front-end, connected to the OpenAI Assistant API. The bot will be deployed on Google Cloud Run and will use Google Cloud SQL to manage chat thread IDs.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Obtaining OpenAI API Token](#obtaining-openai-api-token)
- [Setting Up OpenAI Assistant API](#setting-up-openai-assistant-api)
- [Configuring the Line Bot](#configuring-the-line-bot)
- [Configuring Google Cloud SQL](#configuring-google-cloud-sql)
- [Finalizing Configuration Files](#finalizing-configuration-files)
- [Deploying to Google Cloud Run](#deploying-to-google-cloud-run)
- [Testing the Application](#testing-the-application)

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

## Finalizing Configuration Files

Prepare the following information:

- `channel_access_token`
- `channel_secret`
- `openai_api_key`
- `assistant_id`

Copy `config/config.yml.example` to `config/config.yml`, then modify its content as follows:

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

## Deploying to Google Cloud Run

1. **Configure Google Cloud Console**

   - Use the following commands to set up Google Cloud authentication and select your project:

     ```bash
     gcloud auth login
     gcloud config set project {your-project-id}
     ```

2. **Build Container Image**

   - Build and push the image to Google Container Registry using:

     ```bash
     gcloud builds submit --tag gcr.io/{your-project-id}/{your-image-name}
     ```

3. **Deploy to Cloud Run**

   - Deploy using the following command:

     ```bash
     gcloud run deploy {your-service-name} \
       --image gcr.io/{your-project-id}/{your-image-name} \
       --platform managed \
       --port 8080
       --memory 2G
       --timeout=2m
       --region {your-region}
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
