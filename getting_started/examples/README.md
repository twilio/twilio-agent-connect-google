# Examples

Connect Twilio to GCP agents:
- **ADK Agent Engine** - ADK agents deployed on GCP Agent Platform Runtime
- **Agent Studio Agent Engine** - Agent Studio apps deployed on GCP Agent Platform Runtime
- **CX Agent Studio** - Agents built in CX Agent Studio (Customer Engagement Suite)
- **Conversational Agents** - Agents built in Conversational Agents (Dialogflow CX)

---

## ADK Agent Engine Example

### 1. Deploy an ADK Agent to GCP

Deploy an ADK agent to Agent Platform Runtime — see
[`deploy/agent_platform/adk/README.md`](../../deploy/agent_platform/adk/README.md)
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
python agent_platform/adk_agent_engine.py
```

### 5. Expose with ngrok

```bash
ngrok http 8000
```

### 6. Configure Twilio Webhooks

- Voice (phone number "A call comes in"): `https://your-domain.ngrok.io/twiml`
- SMS (Conversation Orchestrator status callback): `https://your-domain.ngrok.io/webhook`

---

## Agent Studio Agent Engine Example

### 1. Build and Deploy an Agent in Agent Studio

Build and deploy the agent in the Agent Studio console — see
[`deploy/agent_platform/studio/agent/README.md`](../../deploy/agent_platform/studio/agent/README.md).
Save its resource ID for the `.env` below.

### 2. Configure Environment

Create `.env` file:

```bash
# GCP (Agent Studio currently stores and deploys agents in us-west1 only)
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-west1
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
python agent_platform/studio_agent_engine.py
```

### 5. Expose with ngrok

```bash
ngrok http 8000
```

### 6. Configure Twilio Webhooks

- Voice (phone number "A call comes in"): `https://your-domain.ngrok.io/twiml`
- SMS (Conversation Orchestrator status callback): `https://your-domain.ngrok.io/webhook`

---

## CX Agent Studio Example (cascaded)

### 1. Build an Agent in CX Agent Studio

Build and deploy the agent in the CX Agent Studio console — see
[`deploy/cx_agent_studio/agent/README.md`](../../deploy/cx_agent_studio/agent/README.md).
Copy its resource name for the `.env` below.

### 2. Configure Environment

Create `.env` file:

```bash
# CX Agent Studio (agent lives in the `us` multi-region)
CX_AGENT_ID=projects/your-project/locations/us/apps/your-app-id

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
python cx_agent_studio/cascaded.py
```

### 5. Expose with ngrok

```bash
ngrok http 8000
```

### 6. Configure Twilio Webhooks

- Voice (phone number "A call comes in"): `https://your-domain.ngrok.io/twiml`
- SMS (Conversation Orchestrator status callback): `https://your-domain.ngrok.io/webhook`

---

## CX Agent Studio Example (s2s)

Same agent as above, but voice runs as native speech-to-speech: Twilio sends
raw call audio over Media Streams and CX Agent Studio does its own speech
recognition/synthesis over `BidiRunSession`, instead of Twilio ConversationRelay
doing the STT/TTS. There is no SMS in this example — it's voice-only.

### 1. Build an Agent in CX Agent Studio

Same as above — see
[`deploy/cx_agent_studio/agent/README.md`](../../deploy/cx_agent_studio/agent/README.md).

### 2. Configure Environment

Create `.env` file:

```bash
# CX Agent Studio (agent lives in the `us` multi-region)
CX_AGENT_ID=projects/your-project/locations/us/apps/your-app-id

# Twilio
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_API_KEY=your_api_key
TWILIO_API_SECRET=your_api_secret
TWILIO_PHONE_NUMBER=+1234567890
TWILIO_VOICE_PUBLIC_DOMAIN=your-domain.ngrok.io
```

### 3. Authenticate

```bash
gcloud auth application-default login
```

### 4. Run Server

```bash
python cx_agent_studio/s2s.py
```

### 5. Expose with ngrok

```bash
ngrok http 8000
```

### 6. Configure Twilio Webhooks

- Voice (phone number "A call comes in"): `https://your-domain.ngrok.io/twiml`

---

## Conversational Agents (Dialogflow CX) Example

### 1. Build an Agent in Conversational Agents

Build the agent in the Conversational Agents console — see
[`deploy/conversational_agents/agent/README.md`](../../deploy/conversational_agents/agent/README.md).
No deploy step is needed; copy its resource name for the `.env` below.

### 2. Configure Environment

Create `.env` file:

```bash
# Conversational Agents (Dialogflow CX)
CONVERSATIONAL_AGENT_ID=projects/your-project/locations/us-central1/agents/your-agent-id
DIALOGFLOW_LANGUAGE_CODE=en

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
python conversational_agents.py
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
