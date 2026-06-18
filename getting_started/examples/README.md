# Examples

Connect Twilio to GCP agents:
- **Agent Platform Runtime** - Custom agents (LangChain, LangGraph, ADK)
- **Dialogflow CX** - Playbook-based conversational agents

---

## Agent Platform Runtime Example

### 1. Deploy Agent to GCP

```bash
cd ../../deploy/runtime
python deploy_adk.py
```

Save the agent ID from the output.

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

- Voice: `https://your-domain.ngrok.io/voice`
- SMS: `https://your-domain.ngrok.io/sms`

---

## Dialogflow CX Example

### 1. Create Dialogflow CX Agent

1. Go to [Dialogflow CX Console](https://dialogflow.cloud.google.com/cx/)
2. Create an agent with playbooks
3. Get agent ID from URL

### 2. Configure Environment

Add to `.env`:

```bash
DIALOGFLOW_CX_AGENT_ID=your-agent-uuid
```

### 3. Run Server

```bash
python dialogflow_cx_playbook.py
```

### 4. Expose & Configure

Same as Agent Platform Runtime (steps 5-6 above)

---

## Architecture

```
Twilio → TAC Server (Local) → GCP Agent
                               ↓
                        Agent Platform Runtime
                               or
                        Dialogflow CX
```

The TAC server runs locally and connects to your GCP agent.
