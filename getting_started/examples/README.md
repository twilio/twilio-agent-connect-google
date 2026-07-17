# Examples

Connect Twilio to GCP agents:
- **Agent Platform Runtime** - Custom agents (LangChain, LangGraph, ADK)

---

## Agent Platform Runtime Example

### 1. Deploy an Agent to GCP

Deploy an agent to Agent Platform Runtime — see
[`deploy/agent_platform/README.md`](../../deploy/agent_platform/README.md)
(`make deploy-agent`). Save the printed agent ID for the `.env` below.

### 2. Configure Environment

Create `.env` file:

```bash
# GCP
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GCP_REASONING_ENGINE_ID=your-agent-id

# Twilio
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

- Voice (phone number "A call comes in"): `https://your-domain.ngrok.io/twiml`
- SMS (Conversation Orchestrator status callback): `https://your-domain.ngrok.io/webhook`

---

## Architecture

```
Twilio → TAC Server (Local) → GCP Agent
                               ↓
                        Agent Platform Runtime
```

The TAC server runs locally and connects to your GCP agent.
