# Examples

Connect Twilio to agents deployed on GCP Agent Platform Runtime.

---

## Quick Start

### 1. Deploy Agent to GCP

```bash
cd ../../deploy/runtime
python deploy_adk.py
```

Save the agent ID from the output.

### 2. Configure Environment

Create `.env` file:

```bash
GOOGLE_CLOUD_PROJECT=your-project-id
GCP_REASONING_ENGINE_ID=your-agent-id
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_API_KEY=your_api_key
TWILIO_API_SECRET=your_api_secret
TWILIO_PHONE_NUMBER=+1234567890
TWILIO_CONVERSATION_CONFIGURATION_ID=conv_config_xxx
TWILIO_VOICE_PUBLIC_DOMAIN=your-domain.ngrok.io
```

### 3. Authenticate

```bash
gcloud auth application-default login
```

### 4. Run Server

```bash
python agent_platform_runtime.py
```

### 5. Expose with ngrok

```bash
ngrok http 8000
```

### 6. Configure Twilio Webhooks

- Voice: `https://your-domain.ngrok.io/voice`
- SMS: `https://your-domain.ngrok.io/sms`

---

## Architecture

```
Twilio → TAC Server (Local) → Agent (GCP)
```

The TAC server runs locally and connects to your deployed GCP agent.
