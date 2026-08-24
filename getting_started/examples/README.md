# Examples

Connect Twilio to GCP agents:
- **ADK Agent Engine** - ADK agents deployed on GCP Agent Platform Runtime
- **Agent Studio Agent Engine** - Agent Studio apps deployed on GCP Agent Platform Runtime
- **CX Agent Studio** - Agents built in CX Agent Studio (Customer Engagement Suite)
- **Conversational Agents** - Agents built in Conversational Agents (Dialogflow CX)

Feature-focused examples (each builds on one of the connectors above to show a
single feature in isolation):
- **WhatsApp channel** ([`features/whatsapp.py`](features/whatsapp.py)) - enable
  WhatsApp by setting `TWILIO_WHATSAPP_NUMBER`
- **RCS channel** ([`features/rcs.py`](features/rcs.py)) - enable RCS by
  setting `TWILIO_RCS_SENDER_ID`
- **Chat channel** ([`features/chat/app.py`](features/chat/app.py)) - browser-based
  web chat via the Twilio Conversations JS SDK, with a runnable local server

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
doing the STT/TTS. SMS still works alongside it.

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
TWILIO_CONVERSATION_CONFIGURATION_ID=conv_config_xxx
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
- SMS (Conversation Orchestrator status callback): `https://your-domain.ngrok.io/webhook`

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

## WhatsApp Channel Example

Same Conversational Agents agent as above, but only WhatsApp is wired to
the server (the connector still builds SMS/Voice/Chat, they're just not
passed in). Requires a Twilio number enabled for WhatsApp (Sandbox or a
registered sender).

### 1. Configure Environment

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
TWILIO_WHATSAPP_NUMBER=whatsapp:+1234567890
TWILIO_CONVERSATION_CONFIGURATION_ID=conv_config_xxx
```

### 2. Authenticate

```bash
gcloud auth application-default login
```

### 3. Run Server

```bash
python features/whatsapp.py
```

### 4. Expose with ngrok

```bash
ngrok http 8000
```

### 5. Configure Twilio Webhooks

Point your WhatsApp sender's incoming-message webhook (Conversation
Orchestrator status callback) at `https://your-domain.ngrok.io/webhook`.

---

## RCS Channel Example

Same as the WhatsApp example above, but with RCS instead. Requires a Twilio
RCS sender configured for your account.

### 1. Configure Environment

Same `.env` as the WhatsApp example, but with `TWILIO_RCS_SENDER_ID` instead
of `TWILIO_WHATSAPP_NUMBER`.

### 2. Authenticate

```bash
gcloud auth application-default login
```

### 3. Run Server

```bash
python features/rcs.py
```

### 4. Expose with ngrok

```bash
ngrok http 8000
```

### 5. Configure Twilio Webhooks

Point your RCS sender's incoming-message webhook (Conversation Orchestrator
status callback) at `https://your-domain.ngrok.io/webhook`.

---

## Chat Channel Example

Browser-based web chat via the Twilio Conversations JS SDK — no ngrok or
Twilio phone number needed, runs entirely on localhost.

### 1. Configure Environment

Uses the Conversational Agents variables from `.env.example` (see the
"Conversational Agents examples" comment block), plus
`TWILIO_CONVERSATIONS_SERVICE_SID`:

```bash
CONVERSATIONAL_AGENT_ID=projects/your-project/locations/us-central1/agents/your-agent-id
DIALOGFLOW_LANGUAGE_CODE=en
TWILIO_CONVERSATIONS_SERVICE_SID=ISxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

`TWILIO_CONVERSATIONS_SERVICE_SID` is the Conversations v1 Service SID
(starts with `IS`) — **not** the Conversation Orchestrator configuration ID.
Your Conversation Orchestrator configuration must have a classic
Conversations service (with Chat enabled) attached: Console → Conversation
Orchestrator → Conversation Configuration → Channel traffic → "+ Add
messaging & chat traffic".

### 2. Authenticate

```bash
gcloud auth application-default login
```

### 3. Run Server

```bash
python features/chat/app.py
```

### 4. Open the Chat UI

Open http://localhost:8000 and pick one of the predefined identities to
start chatting — no ngrok or Twilio webhook configuration needed, the
browser talks to Twilio directly via the Conversations JS SDK.

### How it Works

- **Frontend** (`features/chat/public/index.html`) — fetches an access
  token from `POST /token`, then creates and sends messages through the
  Conversations JS SDK.
- **Backend** (`features/chat/app.py`) — a `TACFastAPIServer` with
  `ConversationalAgentsConnector` + `ChatChannel`; `POST /webhook` receives
  Conversation Orchestrator events, calls Dialogflow CX (`detectIntent`) for
  a response, and sends it back via the Conversation Orchestrator Actions
  API.

```
Browser (Conversations JS SDK) → Twilio Conversations →
  Conversation Orchestrator → webhook → server → Dialogflow CX →
  Conversation Orchestrator Actions API → Twilio Conversations →
  Browser (Conversations JS SDK)
```

Only `connector.chat` is wired to the server — SMS/Voice (which the
connector always builds) are left unwired.

---

## Architecture

```
Twilio → TAC Server (Local) → GCP Agent
                               ↓
                        Agent Platform Runtime
```

The TAC server runs locally and connects to your GCP agent.
