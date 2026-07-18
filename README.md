<div align="center">
  <div>
    <img src="logo.svg" alt="Twilio Agent Connect Google Logo" width="120" height="120">
  </div>

  <h1>
    Twilio Agent Connect Google
  </h1>

  <h2>
    Google Cloud integrations for Twilio Agent Connect — connect Google Cloud agent services to Twilio's communication channels.
  </h2>

  <div align="center">
    <a href="https://pypi.org/project/twilio-agent-connect-google/"><img alt="PyPI" src="https://img.shields.io/pypi/v/twilio-agent-connect-google.svg"/></a>
    <a href="https://github.com/twilio/twilio-agent-connect-google"><img alt="Python SDK" src="https://img.shields.io/badge/Python-3.10--3.11-3776AB.svg"/></a>
    <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-green.svg"/></a>
    <a href="getting_started/examples/"><img alt="Getting Started" src="https://img.shields.io/badge/Getting%20Started-Examples-F22F46.svg"/></a>
  </div>

  <p>
    <a href="https://www.twilio.com/docs/platform/tac/overview">Documentation</a>
    ◆ <a href="https://github.com/twilio/twilio-agent-connect-python">Python SDK</a>
    ◆ <a href="getting_started/examples/">Examples</a>
    ◆ <a href="deploy/">Deployment</a>
  </p>
</div>

Google Cloud-specific connectors for [Twilio Agent Connect (TAC)](https://github.com/twilio/twilio-agent-connect-python), enabling seamless integration with Google Cloud agent services like Agent Platform Runtime (Reasoning Engine), Dialogflow CX, and the Agent Development Kit (ADK).

---

## Features

### Agent Runtime Integration
- **GCP Agent Platform Runtime** (Reasoning Engine) via `AgentPlatformRuntimeConnector` — connect an agent built with any framework; the connector auto-detects its invocation shape:
  - **Custom Python / LangChain / LangGraph / AG2** — single synchronous `query()` call
  - **Google ADK** — session-based, streaming `stream_query()`
- **Dialogflow CX** (coming soon) — UI-configured conversational flows

### Multi-Channel Communication
- **Voice and SMS support** - Single codebase handles both phone calls and text messages
- **Automatic conversation routing** - Messages route to the correct agent instance per conversation
- **Memory injection** - Customer history and preferences automatically included in agent context

### Deployment Options
- **Cloud Run server** ⭐ **Recommended** - Containerized TAC server with a public HTTPS URL and WebSocket support (required for Twilio ConversationRelay voice)
- **Local (ngrok)** - Run the FastAPI server locally against a deployed agent for testing

### Production Ready
- **Twilio webhook validation** - Automatic signature verification for secure integrations
- **Secret Manager** - Twilio credentials stored in Google Secret Manager, injected at runtime
- **Session & memory** - Server-side sessions (ADK) or in-process history (query family), with TAC memory injection

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

> **Note**: Requires **Python 3.10 or 3.11**. Python 3.12+ is not supported because GCP Agent Platform Runtime (Reasoning Engine) only supports Python 3.8–3.11. We recommend Python 3.11.

## Configuration

twilio-agent-connect-google requires TAC environment variables. See [TAC Configuration](https://github.com/twilio/twilio-agent-connect-python#configuration) for details.

### Required Environment Variables

```bash
# GCP Configuration
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=your-region
GCP_REASONING_ENGINE_ID=your-reasoning-engine-id

# Twilio Configuration
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_API_KEY=your_api_key          # Starts with SK
TWILIO_API_SECRET=your_api_secret    # Secret for API key
TWILIO_PHONE_NUMBER=+1234567890
TWILIO_CONVERSATION_CONFIGURATION_ID=conv_configuration_xxx

# Server Configuration (for Voice)
TWILIO_VOICE_PUBLIC_DOMAIN=your-domain.ngrok.io
```

## Examples

Full examples available in [`getting_started/examples/`](getting_started/examples/):

- **`agent_platform_runtime.py`** - Connect Twilio to an agent deployed on GCP Agent Platform Runtime (custom Python, LangChain, or ADK)

## Deployment

See [`deploy/README.md`](deploy/README.md) for production deployment guides:

### Cloud Run (Agent Platform Runtime) ⭐ Recommended
- Deploy your **agent** to Agent Platform Runtime (custom / LangChain / ADK) and the **TAC server** to Cloud Run
- Public HTTPS URL + WebSocket for Twilio ConversationRelay (voice)
- Twilio credentials stored in Secret Manager
- One shared `.env` and a `make` workflow (`create-sa`, `deploy-agent`, `deploy-secret`, `deploy-server`, `deploy-all`)
- See [`deploy/agent_platform/`](deploy/agent_platform/) for the setup guide

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

## Dependencies

twilio-agent-connect-google depends on:
- **twilio-agent-connect** - Core Twilio Agent Connect framework
  - Requires the `[server]` extra for TAC Server support
- **google-cloud-aiplatform** - Vertex AI / Agent Platform Runtime (Reasoning Engine)
- **google-adk** (optional) - Google Agent Development Kit, for ADK agents

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see [LICENSE](LICENSE) file for details.
