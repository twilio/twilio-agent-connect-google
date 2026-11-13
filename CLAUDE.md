# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Keep it accurate: when a change alters anything described here (behavior, commands, layout, CI), update this file in the same PR.

If a PR, including later pushes to it, conflicts with anything in this file, the PR must also update this file to match before it merges.

## Project Overview

twilio-agent-connect-google is an open-source library providing Google Cloud integrations for Twilio Agent Connect (TAC). It contains connectors that combine a Google Cloud agent runtime integration with multi-channel conversation management.

**Key Architecture**: twilio-agent-connect-google is a separate package that depends on TAC (core Python) as an external dependency. It does NOT contain TAC source code — it imports from the `tac` package.

## Understanding TAC

TAC (Twilio Agent Connect) is middleware that integrates with Twilio platform services:
- **Conversation Orchestrator** - Organizes voice/SMS/WhatsApp into conversations
- **Conversation Memory** - Stores customer context, preferences, and history
- **Conversation Intelligence** - Extracts insights via language operators
- **Knowledge** - Semantic search over knowledge bases

**In twilio-agent-connect-google**: Connectors register `on_message_ready()` and `on_conversation_ended()` callbacks on a `TAC` instance, inject Conversation Memory into the message sent to the Google agent, and route each reply back on the channel it arrived on. The TAC conversation id is the key for per-conversation agent state (an ADK or Dialogflow session, a CES session).

## Development Commands

```bash
make sync              # Install dependencies (uv sync --all-extras --all-packages)
make dev-setup         # Full dev setup (sync + pre-commit hooks)
make format            # Format with ruff
make lint              # Lint check only
make type-check        # mypy (disallow_untyped_defs)
make test              # Run pytest
make check             # All checks (lint + type-check + test)
uv run --group docs mkdocs build --strict   # Build the docs site (fails on broken links)
```

Lint and format run ruff over the whole repo; mypy covers `src/tac_google` and `getting_started`; pytest covers `tests/`.

## Package Structure

```
src/tac_google/
├── __init__.py                          # Only exposes __version__ (see Import Patterns)
├── _version.py
└── connectors/
    ├── __init__.py                      # Public exports for every connector
    ├── _channels.py                     # ConnectorChannels (SMS/Chat always, RCS/WhatsApp when configured)
    ├── agent_platform/                  # Agents on GCP Agent Platform Runtime (Agent Engine)
    │   ├── _base.py                     # AgentEngineConnectorBase (channel wiring, session creation, errors)
    │   ├── adk_connector.py             # ADKAgentEngineConnector
    │   └── studio_connector.py          # StudioAgentEngineConnector
    ├── cx_agent_studio/                 # Agents built in CX Agent Studio (Customer Engagement Suite)
    │   ├── connector.py                 # CXAgentStudioConnector
    │   ├── server.py                    # CXAgentStudioFastAPIServer (adds S2S voice routes)
    │   └── voice_s2s/
    │       ├── channel.py               # VoiceS2SChannel (native speech-to-speech over BidiRunSession)
    │       └── config.py                # VoiceS2SConfig
    └── conversational_agents_connector.py   # ConversationalAgentsConnector (Dialogflow CX)

tests/connectors/                        # pytest suite, one module per connector plus test_channels.py
getting_started/examples/                # Runnable FastAPI examples per connector, plus features/
deploy/                                  # Cloud Run deployment guides (agent_platform, cx_agent_studio, conversational_agents)
docs/                                    # MkDocs sources for the published API reference
```

## Code Conventions

- **Python 3.10 and 3.11**: `requires-python` is `>=3.10,<3.12`. Use modern syntax (`str | None`, `list[str]`) with `from __future__ import annotations`.
- **mypy**: `disallow_untyped_defs` and `disallow_incomplete_defs` are on, so every function needs full type hints. Guard Google SDK type-only imports with `TYPE_CHECKING`.
- **ruff**: Line length 100, rule sets `E W F I B C4 UP N`, isort ordering with `tac_google` as first-party.
- **Imports from TAC**: Always import from the `tac` package; never copy or re-export TAC classes from `tac_google`.

## Dependencies

### Core Dependency

```toml
dependencies = [
    "twilio-agent-connect>=2.3.0,<3",
]
```

### Optional Extras

Each connector's Google Cloud SDK is only required by its own extra, so installing with no extras never fails on import.

- `server` - FastAPI server (`twilio-agent-connect[server]`) and `python-dotenv`
- `vertex-ai` - Agent Platform connectors (`google-cloud-aiplatform[reasoningengine,agent-engines]`, `google-genai`, `google-auth`)
- `cx-agent-studio` - CX Agent Studio connector (`google-auth`, `requests`, `websockets`)
- `conversational-agents` - Dialogflow CX connector (`google-auth`, `requests`)
- `dev` - All SDKs plus pytest, ruff, mypy and type stubs
- `docs` is a dependency group (`uv run --group docs ...`), not an extra

## Key Concepts

### Connectors

Connectors combine agent runtime integration with channel management. Each one:
- Builds the channel set: SMS and Chat always; RCS and WhatsApp only when `TWILIO_RCS_SENDER_ID` / `TWILIO_WHATSAPP_NUMBER` is configured. Their `*_config` args are tuning only and never enable a channel.
- Exposes channels as attributes (`voice`, `sms`, `chat`, and `rcs` / `whatsapp`, which are `None` when not configured). Filter out `None` before handing channels to a server.
- Registers with TAC via `on_message_ready()` and `on_conversation_ended()`.
- Injects Conversation Memory into the message sent to the agent.

**ConnectorChannels** (`connectors/_channels.py`): shared builder for SMS, Chat, RCS and WhatsApp. Voice is built by each connector itself because `CXAgentStudioConnector` has to choose between two voice channel types.

**ADKAgentEngineConnector**: ADK agent on Agent Platform Runtime. Creates one session per conversation over REST (for a clean "already exists" signal) and calls `async_stream_query()` per message. Memory is wrapped in `<MEMORY>` ahead of the user text, which is wrapped in `<USER_MESSAGE>`, because the API has a single content channel. The session replays full history, so memory is injected only when it changes between turns (`_maybe_tag_message` in `_base.py`).

**StudioAgentEngineConnector**: Agent Studio app on Agent Platform Runtime. Same session handling as the ADK connector, but invokes the `:streamQuery` REST endpoint directly since Studio apps have no SDK-bound query methods. Memory is injected the same way.

**CXAgentStudioConnector**: CX Agent Studio (CES) agents over the text `runSession` REST API. The TAC conversation id doubles as the CES session id, so CES keeps history and no local history is built. Memory is prepended only when it changes between turns (`_maybe_tag_memory`) because CES replays full history. `voice_config` type picks the voice channel: a `VoiceChannelConfig` builds `voice_cascaded` (ConversationRelay), a `VoiceS2SConfig` builds `voice_s2s`, and `voice` is whichever was built. CES's `end_session` tool is handled in `_handle_end_session`.

**ConversationalAgentsConnector**: Dialogflow CX agents (Playbook or Flow) over the `detectIntent` v3 REST API. Derives one stable session id per conversation (a UUID hash of the TAC conversation id, to fit Dialogflow's 36-character limit). Memory is injected only when it changes, like the CES connector.

**VoiceS2SChannel**: Native speech-to-speech voice for CES. Bridges Twilio Media Streams audio to CES `BidiRunSession`, with CES doing its own STT/TTS. There are no discrete turns, so `process_webhook` is a no-op and `send_response` raises `NotImplementedError`, and it supports neither Conversation Orchestrator nor Conversation Memory for voice.

### Server

**CXAgentStudioFastAPIServer**: `TACFastAPIServer` plus the TwiML and WebSocket routes for S2S voice. Pass it a `VoiceChannel`, a `VoiceS2SChannel`, or `None`. Every other connector uses `tac.server.TACFastAPIServer` directly.

## Import Patterns

### Correct Imports

```python
# TAC imports - external dependency
from tac import TAC, TACConfig
from tac.server import TACFastAPIServer

# twilio-agent-connect-google imports - local package
from tac_google.connectors import (
    ADKAgentEngineConnector,
    ConversationalAgentsConnector,
    CXAgentStudioConnector,
    StudioAgentEngineConnector,
)
from tac_google.connectors.cx_agent_studio.server import CXAgentStudioFastAPIServer
```

### Incorrect Imports (DO NOT DO)

```python
# ❌ Wrong - the top-level package only exposes __version__
from tac_google import ADKAgentEngineConnector

# ❌ Wrong - TAC classes live in tac, not tac_google
from tac_google.core import TAC
```

## Example Usage Patterns

### ADK on Agent Platform Runtime

```python
import vertexai
from tac import TAC, TACConfig
from tac.server import TACFastAPIServer
from tac_google.connectors import ADKAgentEngineConnector

client = vertexai.Client(project="my-project", location="us-central1")
tac = TAC(config=TACConfig.from_env())

agent = client.agent_engines.get(
    name="projects/my-project/locations/us-central1/reasoningEngines/123456"
)
connector = ADKAgentEngineConnector(tac=tac, agent=agent)

server = TACFastAPIServer(
    tac=tac,
    voice_channel=connector.voice,
    messaging_channels=[connector.sms],
)
server.start()
```

**See full examples**: `getting_started/examples/agent_platform/`

### CX Agent Studio with Native Voice

```python
from tac_google.connectors import CXAgentStudioConnector, VoiceS2SConfig
from tac_google.connectors.cx_agent_studio.server import CXAgentStudioFastAPIServer

connector = CXAgentStudioConnector(
    tac=tac,
    agent_id="projects/my-project/locations/us/apps/my-app-id",
    voice_config=VoiceS2SConfig(),
)
server = CXAgentStudioFastAPIServer(
    tac=tac,
    voice_channel=connector.voice,
    messaging_channels=[connector.sms, connector.chat],
)
```

**See full examples**: `getting_started/examples/cx_agent_studio/` (`cascaded.py`, `s2s.py`) and `getting_started/examples/conversational_agents.py`

## Testing

Tests live in `tests/connectors/` and use pytest with `@pytest.mark.asyncio` for async tests (see `pytest.ini`). Run with `make test` or `uv run pytest`. Tests should:
- Import from `tac_google` (local) and `tac` (external dependency)
- Mock Google clients and `AuthorizedSession` with pytest fixtures rather than calling Google APIs
- Build a `TAC` stand-in with a `config` attribute when a channel reads `tac.config`; newer TAC releases read more of it

CI's `TAC Compat` matrix also runs lint, mypy and tests against the latest patch of each `twilio-agent-connect` minor in the `pyproject.toml` range (`.github/scripts/tac_versions.py`), so code must work on the oldest supported minor, not just the locked one. The matrix runs on Python 3.10, the oldest version this package supports. Reproduce and fix steps: CONTRIBUTING.md, "SDK Compatibility Checks".

## Updating TAC Dependency

When a new `twilio-agent-connect` release is published to PyPI, bump every `twilio-agent-connect` constraint in `pyproject.toml` together (base dependency and each extra that pulls it), then re-lock and run all checks:

```bash
uv lock --upgrade-package twilio-agent-connect
make sync
make check
```

Raising the lower bound drops older minors from the `TAC Compat` matrix, so only raise it when code needs a newer TAC feature.

## Documentation

- The public API reference is published at https://twilio.github.io/twilio-agent-connect-google/, versioned with `mike` and deployed from `.github/workflows/docs.yml` on each GitHub release.
- API docs are generated from docstrings by MkDocs Material + mkdocstrings, so **docstrings are published documentation**. Write them for both source readers and the rendered site.
- Use **Markdown** in docstrings: `**bold**`, `- ` bullet lists, backticks for identifiers, and fenced code blocks for examples, with a blank line before a list or fenced block.
- TAC core types (`TAC`, `ConversationSession`, ...) resolve to the TAC Python docs via the `inventories` entry in `mkdocs.yml`, so annotating with real TAC types produces cross-repo links.
- `docs/api/*.md` targets individual modules, not the top-level package. When you add a module, add it to the matching docs page.
- `docs/index.md` and `docs/deploy/**` are one-line snippet includes of `README.md` and the `deploy/` guides. Edit the source Markdown, never the stub, and use absolute GitHub URLs for repo-only paths in those files.
- Verify docs changes with `uv run --group docs mkdocs build --strict`.

## Common Pitfalls

1. **Don't import connectors from `tac_google`** - use `tac_google.connectors`.
2. **Don't copy TAC source code** - TAC is a dependency, not vendored.
3. **Don't pass `None` channels to a server** - `connector.rcs` and `connector.whatsapp` are `None` when not configured.
4. **Connectors own the channels** - don't create separate channel instances for them.
5. **Optional dependencies are gated** - each connector needs its own extra installed.
6. **Python 3.12 is not supported** - `requires-python` is `<3.12`.

## Related Documentation

- TAC Core: [twilio-agent-connect-python](https://github.com/twilio/twilio-agent-connect-python)
- TAC AWS sibling: [twilio-agent-connect-aws](https://github.com/twilio/twilio-agent-connect-aws)
- TAC Microsoft sibling: [twilio-agent-connect-microsoft](https://github.com/twilio/twilio-agent-connect-microsoft)
- Google ADK: [google.github.io/adk-docs](https://google.github.io/adk-docs/)
- Dialogflow CX: [cloud.google.com/dialogflow/cx/docs](https://cloud.google.com/dialogflow/cx/docs)
- Examples: `getting_started/examples/`
- Deployment: `deploy/README.md`
- Published API reference: [twilio.github.io/twilio-agent-connect-google](https://twilio.github.io/twilio-agent-connect-google/)
