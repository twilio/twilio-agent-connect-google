# TAC Agent Platform Runtime + Cloud Run Deployment

Deploy Twilio Agent Connect with an agent on GCP Agent Platform Runtime and the
TAC server on Cloud Run.

The flow has two independently deployed pieces:
- **Agent** — your LLM logic (custom Python class, LangChain/LangGraph/AG2, or
  ADK), hosted on Agent Platform Runtime (a.k.a. Reasoning Engine).
- **TAC server** — a FastAPI app that terminates Twilio webhooks + the
  ConversationRelay WebSocket and forwards turns to the agent, on Cloud Run.

The agent has **no knowledge of Twilio**; the server has **no LLM logic**. The
`AgentPlatformRuntimeConnector` is the seam between them.

## Architecture

```mermaid
graph TB
    Customer([👤 Customer<br/>Phone Call / SMS])

    subgraph Twilio["☁️ Twilio Cloud"]
        Phone[📱 Phone Number<br/>+1-XXX-XXX-XXXX]
        Orchestrator[💬 Conversations<br/>Conversation Orchestrator]
        Memory[🧠 Memory Service<br/>Profile & Context]
    end

    subgraph GCP["☁️ Google Cloud"]
        subgraph CloudRun["🏃 Cloud Run"]
            Server[⚙️ TAC Server<br/>WebSocket/HTTP]
        end

        subgraph APR["🤖 Agent Platform Runtime"]
            Agent[🧠 Deployed Agent<br/>query / stream_query]
        end

        Secret[🔐 Secret Manager<br/>Twilio credentials]
    end

    %% Voice Channel Flow (A-D)
    Customer -->|A. Phone Call| Phone
    Phone -->|B. POST /twiml| Server
    Server -->|C. TwiML with<br/>wss:// WebSocket URL| Phone
    Phone <-->|D. Twilio ConversationRelay| Server

    %% Messaging Channel Flow (1-4)
    Customer -->|1. SMS| Phone
    Phone -->|2. POST /webhook| Server
    Server -->|3. Forward to Agent| Agent
    Agent -->|4. SMS Response| Phone

    %% Cloud Run integrations
    Server --> Agent
    Server -.->|reads credentials| Secret
    Agent --> Orchestrator
    Agent --> Memory

    Phone -->|Response| Customer

    style Customer fill:#e1f5ff
    style Twilio fill:#f0f0f0
    style GCP fill:#e8f0fe
    style CloudRun fill:#e6f4ea
    style APR fill:#f3e5f5
    style Agent fill:#e1bee7
    style Secret fill:#fff4e6
```

## Deployment Components

- **Agent** - hosted on Agent Platform Runtime; deployed from [`agents/`](./agents/) (custom / query_agents / adk)
- **Cloud Run Service** - the TAC server (FastAPI), HTTP webhooks and WebSocket endpoints; deployed from [`server/`](./server/)
- **Artifact Registry** - holds the server's container image (created automatically)
- **Secret Manager** - holds the Twilio credentials, read by the Cloud Run service

## Prerequisites

### Required Tools

- **[Google Cloud CLI](https://cloud.google.com/sdk/docs/install)** - Command-line tool for GCP (`brew install --cask google-cloud-sdk`)
- **[Python 3.11](https://www.python.org/downloads/)** - to run the agent deploy scripts (Agent Platform Runtime requires 3.11)

### GCP Account Requirements

- **Active GCP Project** with billing enabled and access to:
  - **Vertex AI** (Agent Platform Runtime)
  - **Cloud Run**, **Cloud Build**, and **Artifact Registry** (enabled automatically by `server/deploy.sh`)
- **Gemini 3.5 Flash** enabled in [Model Garden](https://console.cloud.google.com/vertex-ai/model-garden) (used by the `custom/` and `query_agents/` examples; it uses the Enterprise Agent Platform API)
- **Region:** any region with Vertex AI and Cloud Run availability — set it via `GOOGLE_CLOUD_LOCATION` in `.env`

---

## Quick Start

### 1. Configure Environment

The agent scripts and the server share a **single `.env`** in this folder:

```bash
cd deploy/agent_platform
cp .env.example .env
```

Edit `.env` with your values (leave `GCP_REASONING_ENGINE_ID` blank — the agent
deploy fills it in):

```bash
# GCP Configuration
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=your-region
GCP_REASONING_ENGINE_ID=                            # filled in by the agent deploy

# Twilio Credentials
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_API_KEY=SKxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_API_SECRET=your_api_secret

# Twilio Configuration
TWILIO_PHONE_NUMBER=+1234567890
TWILIO_CONVERSATION_CONFIGURATION_ID=conv_configuration_xxxx
```

**Where to find Twilio values:**
- Account SID & Auth Token: Twilio Console → Account → API keys & tokens
- API Key & Secret: Create new API Key
- Phone Number: Twilio Console → Phone Numbers
- Conversation Configuration ID: Twilio Console → Conversation Orchestrator

The four Twilio credentials (`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`,
`TWILIO_API_KEY`, `TWILIO_API_SECRET`) are stored in Secret Manager by the
deploy; the rest are passed as env vars.

### 2. Authenticate (one-time)

Run once per machine — the credentials persist for future deploys. The project
comes from `.env`, so you don't need `gcloud config set project`.

```bash
gcloud auth login                       # gcloud CLI (server deploy)
gcloud auth application-default login    # ADC (agent deploy scripts)
```

### 3. Create the deploy service account (one-time)

Creates the dedicated `tac-deployer` SA (derived from your project — nothing to
configure). The deploy grants it the roles it needs.

```bash
make create-sa
```

### 4. Deploy

One command deploys the agent, stores the secrets, and deploys the server:

```bash
make deploy-all                 # AGENT=adk by default
make deploy-all AGENT=custom    # or query_agents
```

`deploy-all` runs `deploy-agent` (which writes the new agent ID into `.env`),
then `deploy-secret`, then `deploy-server`. Choose the agent framework with `AGENT=`:

| AGENT | Framework |
|---|---|
| `adk` | Google ADK |
| `custom` | Plain Python class |
| `query_agents` | LangChain (also LangGraph / AG2) |

Or run the steps individually: `make deploy-agent` / `make deploy-secret` / `make deploy-server`.

**Deployment output:**

```
✅ Deployed: https://tac-server-xxxxx.<region>.run.app

Configure Twilio:
  Conversation Orchestrator status callback : https://tac-server-xxxxx.<region>.run.app/webhook   (POST)
  Voice "A call comes in" webhook           : https://tac-server-xxxxx.<region>.run.app/twiml     (POST)
```

Copy these webhook URLs for Twilio configuration. Re-running `make deploy-server`
keeps the same URL.

---

## Twilio Configuration

### Configure Voice Webhook (Phone Number)

1. Go to **Twilio Console → Phone Numbers → Active Numbers**
2. Select your phone number
3. Under "Voice Configuration":
   - **A CALL COMES IN:** Webhook
   - **URL:** Use the `/twiml` URL from deploy output
   - **HTTP Method:** POST
4. Save

### Configure Conversation Webhook (SMS/Messaging)

1. Go to **Twilio Console → Conversation Orchestrator**
2. Select your Conversation Configuration
3. Under "Webhook Configuration":
   - **Webhook URL:** Use the `/webhook` URL from deploy output
   - **HTTP Method:** POST
4. Save

**Note:** SMS flows through the Conversation Orchestrator status callback, **not** the phone number's "A message comes in" webhook. Setting the phone-number messaging webhook does nothing here — you must update the Conversation Configuration above.

---

## View Logs

### Cloud Run Logs

Application logs (startup, agent calls, errors):

```bash
gcloud run services logs read tac-server --project your-project-id --region your-region --limit 50
```

Or go to the [Cloud Logging Console](https://console.cloud.google.com/logs), and filter by **Cloud Run Revision → `tac-server`**.

### Request Logs

To confirm whether Twilio's webhook is **reaching** the service (and with what status code):

```bash
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="tac-server" AND httpRequest.requestUrl!=""' \
  --project your-project-id --limit 25 --freshness=1h \
  --format='table(timestamp, httpRequest.requestMethod, httpRequest.status, httpRequest.requestUrl)'
```

---

## Update Code

- After editing the agent: `make deploy-agent` (with the same `AGENT=`).
- After editing the server or the package: `make deploy-server`.
- After rotating Twilio credentials in `.env`: `make deploy-secret`.
