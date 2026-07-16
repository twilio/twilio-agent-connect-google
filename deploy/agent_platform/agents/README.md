# Deploying Agents to GCP Agent Platform Runtime

Agent Platform Runtime (also called Reasoning Engine or Agent Engine) is
framework-agnostic — it just hosts and autoscales a Python object. What that
object exposes once deployed (and how the connector must call it) depends
entirely on how you built the agent. This folder has one subfolder per
representative deployment method:

| | [`custom/`](./custom/) | [`query_agents/`](./query_agents/) | [`adk/`](./adk/) |
|---|---|---|---|
| Framework | None — a plain Python class | LangChain (`LangchainAgent` template) | Google Agent Development Kit |
| Deploy command | `python deploy_custom.py` (SDK: `ReasoningEngine.create()`) | `python deploy_langchain.py` (SDK: `ReasoningEngine.create()`) | `./deploy.sh` (CLI: `adk deploy agent_engine`) |
| What deploy sets up | Just the packaged agent | Just the packaged agent | Agent + managed Session Service / Memory Bank |
| Client call to invoke | `agent.query(input=...)` | `agent.query(input=...)` | `agent.stream_query(message=, user_id=, session_id=)` |
| Response shape | `dict` (whatever your class returns) | `dict` (`{"output": ...}`) | stream of event dicts |
| Needs session management? | No | No | Yes — `create_session()` once per conversation |

`query_agents/` holds a LangChain example, but the folder name is deliberately
not `langchain/` — it's a stand-in for the whole family of third-party agent
frameworks with an official Reasoning Engine template that expose `query()`.
**LangGraph and AG2 agents behave exactly the same way** (same
`ReasoningEngine.create()` deploy call, same `.query(input=...)` client call,
just a different template class: `vertexai.preview.reasoning_engines.LanggraphAgent`
/ `AG2Agent`). There's no separate example folder for them since the
mechanics are identical.

So in practice there are really only **two invocation shapes** a connector
needs to handle, regardless of how many named frameworks exist:
1. **`query()` family** — custom class, LangChain, LangGraph, AG2: one
   synchronous call, dict response.
2. **ADK** — session-based, streaming, needs `user_id`/`session_id`.

The `AgentPlatformRuntimeConnector` in this repo
(`src/tac_google/connectors/agent_platform_runtime_connector.py`) auto-detects
which shape a deployed agent exposes and calls it accordingly — see that
file for the implementation.

---

## Prerequisites (all three methods)

- **Python 3.11** — GCP Agent Platform Runtime requires it (the repo includes
  a `.python-version` file).
- A **GCP project** with billing and the Vertex AI API enabled.
- **Google Cloud CLI**: `brew install --cask google-cloud-sdk`
- Authenticate: `gcloud auth application-default login`

The `custom/` and `query_agents/` examples use **Gemini 3.5 Flash**, which must
be enabled in your project first: go to
[Model Garden](https://console.cloud.google.com/vertex-ai/model-garden),
find "Gemini 3.5 Flash" under Google models, and enable it. It uses the
**Enterprise Agent Platform API**, not the standard Vertex AI API.

---

## Known gotchas

- **Gemini 3.5 Flash only works via `location="global"`**, not any regional
  endpoint (`us-central1`, `us-west1`, etc. all 404). `custom/` handles this
  by hardcoding `location="global"` in its own `genai.Client()` call; `adk/`
  handles it with a `GlobalGemini` subclass (see `adk/my_agent/agent.py`) since
  ADK's default `Gemini` model reads `GOOGLE_CLOUD_LOCATION` otherwise. This is
  independent of which region you deploy the agent *to* — see next point.
- **Not every region can host an ADK deployment.** We hit
  `Reasoning Engine resource [...] failed to start and cannot serve traffic`
  deploying to `us-west1` with zero container startup logs (build succeeded,
  runtime never came up) — three different fixes (model location, bypassing
  the self-referencing session service) didn't change the outcome. Switching
  `GOOGLE_CLOUD_LOCATION` to `us-central1` fixed it immediately. If ADK deploy
  fails with this exact error and there are no runtime logs at all, try
  `us-central1` before debugging further.
- **ADK agents must be fetched with `vertexai.agent_engines.get()`, not
  `vertexai.preview.reasoning_engines.ReasoningEngine()`.** ADK's operation
  schema declares `async`/`async_stream`/`bidi_stream` modes that
  `ReasoningEngine`'s method-registration code doesn't recognize — it raises
  and aborts registration entirely on the first one it hits, so `stream_query`
  never gets attached (fails silently with `AttributeError`, or gets
  misdetected as the `query()` family by `AgentPlatformRuntimeConnector`).
  `agent_engines.get()` handles all of ADK's modes correctly. `custom/` and
  `query_agents/` don't declare those modes so either SDK works for them, but
  `agent_engines.get()` is the current recommended one regardless.

---

## Quick Start (pick one)

### Custom Python class

```bash
cd deploy/agent_platform/agents/custom
cp .env.example .env       # edit GOOGLE_CLOUD_PROJECT
python deploy_custom.py    # deploy - prints the new agent ID
echo "GCP_REASONING_ENGINE_ID=<printed-id>" >> .env
python invoke_agent.py     # test
```

### Query agents (LangChain example)

```bash
cd deploy/agent_platform/agents/query_agents
pip install -r requirements.txt
cp .env.example .env       # edit GOOGLE_CLOUD_PROJECT
python deploy_langchain.py # deploy - prints the new agent ID
echo "GCP_REASONING_ENGINE_ID=<printed-id>" >> .env
python invoke_langchain.py # test
```

### ADK

```bash
cd deploy/agent_platform/agents/adk/my_agent
pip install -r requirements.txt
cp .env.example .env       # edit GOOGLE_CLOUD_PROJECT
./deploy.sh                # deploy - prints the new resource ID
echo "GCP_REASONING_ENGINE_ID=<printed-id>" >> .env
python invoke_adk.py       # test - uses stream_query(), not query()
```
