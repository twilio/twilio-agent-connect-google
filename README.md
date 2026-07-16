# Twilio Agent Connect Google

**Google Cloud integrations for Twilio Agent Connect** — connect Google Cloud agent services to Twilio's communication channels.

[![PyPI](https://img.shields.io/pypi/v/twilio-agent-connect-google.svg)](https://pypi.org/project/twilio-agent-connect-google/)
[![Python SDK](https://img.shields.io/badge/Python-3.10--3.11-3776AB.svg)](https://github.com/twilio/twilio-agent-connect-google)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Google Cloud-specific connectors for [Twilio Agent Connect (TAC)](https://github.com/twilio/twilio-agent-connect-python), enabling seamless integration with Google Cloud agent services like Agent Platform Runtime, Dialogflow CX, and Agent Development Kit (ADK).

---

## Features

- **AgentPlatformRuntimeConnector** - GCP Agent Platform Runtime (Reasoning Engine) integration
  - Deploy custom agent code (LangChain, LangGraph, ADK, custom Python)
  - Managed runtime with built-in scaling and monitoring
  - Supports any framework deployed to GCP
- **DialogflowCXConnector** (Coming soon) - Dialogflow CX conversational flows
  - UI-configured agents via Google Cloud Console
  - Voice and chat optimized conversational flows
- **ADKConnector** (Coming soon) - Agent Development Kit local agents
  - Local agent SDK/framework
  - Run agents locally or deploy to GCP
- Multi-channel support (SMS + Voice)
- Automatic TAC memory injection

---

## Requirements

- **Python 3.10 or 3.11** (required for GCP Agent Platform Runtime compatibility)
- Google Cloud Project with Vertex AI API enabled
- Twilio account with phone number

> **Note**: Python 3.12+ is not supported because GCP Agent Platform Runtime (Reasoning Engine) only supports Python 3.8-3.11. We recommend Python 3.11 for best compatibility.

## Installation

### With Agent Platform Runtime

```bash
pip install twilio-agent-connect-google[vertex-ai,server]
```

### Development

```bash
# Install with development tools (includes all connectors)
pip install twilio-agent-connect-google[dev]
```

---

## Quick Start

### 1. Prerequisites

**GCP Setup:**
- GCP project with Vertex AI API enabled
- Agent deployed to GCP Agent Platform Runtime (Reasoning Engine)
- Service account with Vertex AI permissions

**Twilio Setup:**
- Twilio Account SID and Auth Token
- Twilio API Key and Secret
- Twilio phone number
- Twilio Conversation Configuration ID

### 2. Environment Variables

Create a `.env` file in the project root:

```bash
# Copy the example file
cp .env.example .env

# Edit with your values
```

Required variables:

```bash
# Twilio Configuration
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_API_KEY=your_api_key          # Starts with SK
TWILIO_API_SECRET=your_api_secret    # Secret for API key
TWILIO_PHONE_NUMBER=+1234567890
TWILIO_CONVERSATION_CONFIGURATION_ID=conv_configuration_xxx

# Server Configuration (for Voice)
TWILIO_VOICE_PUBLIC_DOMAIN=your-domain.ngrok.io

# GCP Configuration
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json  # Optional
GCP_REASONING_ENGINE_ID=your-reasoning-engine-id
```

### 3. Deploy Agent to GCP (One-time Setup)

First, deploy your agent to GCP Agent Platform Runtime. See
[`deploy/agent_platform/agents/README.md`](deploy/agent_platform/agents/README.md)
for all supported deployment methods (custom Python, LangChain, ADK).

**Quick deploy with Gemini 3.5 Flash:**

```bash
# 1. Setup environment
cd deploy/agent_platform/agents/custom
cp .env.example .env
# Edit .env with your GOOGLE_CLOUD_PROJECT

# 2. Authenticate
gcloud auth application-default login

# 3. Deploy
python deploy_custom.py

# 4. Save returned agent ID to .env
# GCP_REASONING_ENGINE_ID=your-agent-id
```

**Or deploy custom agent:**

```python
from google import genai
import vertexai
from vertexai.preview import reasoning_engines

class MyAgent:
    def __init__(self, project: str):
        self.project = project
    
    def query(self, **kwargs):
        input_text = kwargs.get("input", "")
        
        # Use Gemini 3.5 Flash (Enterprise API)
        client = genai.Client(
            enterprise=True,
            project=self.project,
            location="global"
        )
        
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=input_text
        )
        
        return {"output": response.text}

# Deploy
vertexai.init(project="your-project", location="us-central1")
deployed = reasoning_engines.ReasoningEngine.create(
    MyAgent(project="your-project"),
    requirements=["google-genai>=2.0.0"],
    display_name="my-agent",
    sys_version="3.11"
)

print(f"Agent ID: {deployed.resource_name.split('/')[-1]}")
```

### 4. Connect to Twilio

```python
# server.py
import os
import vertexai
from vertexai.preview import reasoning_engines
from tac import TAC, TACConfig
from tac.server import TACFastAPIServer
from tac_google.connectors import AgentPlatformRuntimeConnector

# Initialize Vertex AI
vertexai.init(
    project=os.getenv("GOOGLE_CLOUD_PROJECT"),
    location=os.getenv("GOOGLE_CLOUD_LOCATION")
)

# Initialize TAC
tac = TAC(config=TACConfig.from_env())

# Agent factory - returns deployed reasoning engine
def get_agent(context):
    return reasoning_engines.ReasoningEngine(
        os.getenv("GCP_REASONING_ENGINE_ID")
    )

# Create connector
connector = AgentPlatformRuntimeConnector(
    tac=tac,
    agent_factory=get_agent
)

# Start server
server = TACFastAPIServer(
    tac=tac,
    voice_channel=connector.voice,
    sms_channel=connector.sms
)

server.start()
```

### 5. Run and Test

```bash
# Start the server
python server.py

# In another terminal, expose with ngrok
ngrok http 8000

# Update TWILIO_VOICE_PUBLIC_DOMAIN in .env with your ngrok URL
# Configure Twilio phone number webhook URLs:
#   Voice: https://your-domain.ngrok.io/voice
#   SMS: https://your-domain.ngrok.io/sms
```

---

## Configuration

### TAC Configuration

See [TAC Configuration](https://github.com/twilio/twilio-agent-connect-python#configuration) for full details.

**Required Environment Variables:**

```bash
# Twilio Configuration
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_API_KEY=your_api_key
TWILIO_API_SECRET=your_api_secret
TWILIO_PHONE_NUMBER=+1234567890
TWILIO_CONVERSATION_CONFIGURATION_ID=conv_configuration_xxx

# Server Configuration
TWILIO_VOICE_PUBLIC_DOMAIN=your-domain.ngrok.io
```

### GCP Authentication

**Option 1: Application Default Credentials (ADC)** - Recommended for local development

```bash
gcloud auth application-default login
```

**Option 2: Service Account** - Recommended for production

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

**Option 3: Code-based credentials**

```python
from google.oauth2 import service_account

credentials = service_account.Credentials.from_service_account_file(
    '/path/to/key.json'
)

vertexai.init(
    project="your-project",
    location="us-central1",
    credentials=credentials
)
```

---

## Examples

Full examples available in [`getting_started/examples/`](getting_started/examples/):

- **`agent_platform_runtime.py`** - Deploy custom agents (LangChain, ADK) to GCP Runtime

### Advanced: Context-Aware Agent Routing

Route to different agents based on channel or other context:

```python
def get_agent_by_channel(context):
    """Route to different agents based on channel."""
    if context.channel == "voice":
        return reasoning_engines.ReasoningEngine("voice-agent-id")
    else:
        return reasoning_engines.ReasoningEngine("sms-agent-id")

connector = AgentPlatformRuntimeConnector(
    tac=tac,
    agent_factory=get_agent_by_channel
)
```

---

## Architecture

### AgentPlatformRuntimeConnector

```
┌─────────────┐
│   Twilio    │
│  Voice/SMS  │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│              TAC                    │
│  (Memory, Session Management)       │
└──────────────┬──────────────────────┘
               │
               ▼
┌────────────────────────────────────────┐
│  AgentPlatformRuntimeConnector         │
│  - Per-conversation agent refs         │
│  - Memory injection                    │
│  - Channel routing                     │
└──────────────┬─────────────────────────┘
               │
               ▼
┌────────────────────────────────────────┐
│  GCP Agent Platform Runtime            │
│  (Reasoning Engine)                    │
│                                        │
│  Deployed Agent (LangChain, etc.)      │
└────────────────────────────────────────┘
```

**How it works:**

1. **User sends message** via Twilio (Voice or SMS)
2. **TAC receives message** and manages session/memory
3. **AgentPlatformRuntimeConnector** gets deployed agent reference for the conversation
4. **Memory injection** (first message only) - TAC memory sent to agent
5. **Agent query** - Message sent to deployed GCP agent via `agent.query()`
6. **Response routing** - Agent response routed back to appropriate channel

---

## Supported Agent Frameworks

The **AgentPlatformRuntimeConnector** works with any agent framework that can be deployed to GCP Agent Platform Runtime:

- ✅ **LangChain** - Chains, agents, LCEL
- ✅ **LangGraph** - Multi-agent workflows
- ✅ **Agent Development Kit (ADK)** - Google's agent framework
- ✅ **LlamaIndex** - RAG applications
- ✅ **CrewAI** - Multi-agent systems
- ✅ **Custom Python** - Any Python class with a `query()` method

---

## Deployment

See [`deploy/README.md`](deploy/README.md) for production deployment guides:

- **GCP Cloud Run** - Deploy TAC server with Agent Platform Runtime connector
- **GCP App Engine** - Alternative deployment option
- **GCP Compute Engine** - VM-based deployment

---

## Development

### Setup

```bash
# Clone repository
git clone https://github.com/twilio/twilio-agent-connect-google.git
cd twilio-agent-connect-google

# Install dependencies
make sync

# Setup dev environment
make dev-setup
```

### Code Quality

```bash
# Format code
make format

# Type check
make type-check

# Lint
make lint

# Run tests
make test

# Run all checks
make check
```

---

## Roadmap

### Current

- ✅ **AgentPlatformRuntimeConnector** - Deploy custom agents to GCP Runtime

### Upcoming

- 🚧 **DialogflowCXConnector** - UI-configured conversational agents
- 🚧 **ADKConnector** - Local Agent Development Kit agents
- 🚧 **Streaming support** - Real-time streaming responses
- 🚧 **WebSocket optimization** - Low-latency voice channel

---

## Dependencies

twilio-agent-connect-google depends on:

- **twilio-agent-connect** - Core Twilio Agent Connect framework
  - Requires `[server]` extra for TAC Server support
- **google-cloud-aiplatform** - Vertex AI Python SDK
- **vertexai** - Vertex AI client library

---

## Comparison with AWS

| Feature | AWS (tac-aws) | GCP (tac-google) |
|---------|---------------|------------------|
| **Deploy custom code** | BedrockAgentCoreConnector | AgentPlatformRuntimeConnector |
| **UI-configured agents** | BedrockConnector | DialogflowCXConnector (coming) |
| **Local agent SDK** | StrandsConnector | ADKConnector (coming) |
| **Framework support** | Strands only | LangChain, LangGraph, ADK, custom |
| **Streaming** | HTTP + WebSocket | HTTP (WebSocket coming) |
| **Session management** | Built-in | Managed by agent |

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

## Resources

- **Documentation**: [Twilio Agent Connect Docs](https://www.twilio.com/docs/platform/tac/overview)
- **Python SDK**: [twilio-agent-connect-python](https://github.com/twilio/twilio-agent-connect-python)
- **GCP Agent Platform**: [Vertex AI Agent Platform Docs](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/overview)
- **Examples**: [getting_started/examples/](getting_started/examples/)
