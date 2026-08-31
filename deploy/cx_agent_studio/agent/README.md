# CX Agent Studio agent

This folder exists to get you two things before you deploy the server:

1. **A working agent, and its `CX_AGENT_ID`.** That resource name is the one
   agent-side value `../.env` needs. [Build the agent](#build-the-agent) and
   [Get the agent ID](#get-the-agent-id) below.
2. **Confidence the agent itself works.** `invoke.py` chats with it from your
   terminal, so you can rule the agent in or out before adding Twilio to the
   picture. See [Debugging with invoke.py](#debugging-with-invokepy).

Nothing here is deployed or imported. The agent is built and deployed in the
Google Cloud console ([CX Agent Studio](https://docs.cloud.google.com/gemini-enterprise-agent-platform/agent-studio)
is the low-code visual builder there for Customer Engagement Suite agents), so
this folder has no agent source and no deploy script. The
[Twilio Agent Connect (TAC)](https://www.twilio.com/docs/conversations/agent-connect)
server ([`../server/main.py`](../server/main.py)) is the part that deploys, to
Cloud Run, and it connects Twilio to the agent over the agent's API.

## Build the agent

1. In the console, open **Gemini Enterprise for CX → CX Agent Studio → Agents**
   and click **Create agent**.
2. Give it a name, set the **instructions**, pick a **model**, and add any
   **tools** (Google Search, data stores, connectors like Salesforce, MCP).
3. Use the **Preview** tab to chat-test the agent.
4. Open the **Deploy** tab. On "How do you want to deploy your agent?" choose
   **Set up API access** (the TAC server calls the agent's API; you do not need
   the web widget or the "Connect to a platform" telephony integration).

## Get the agent ID

**Set up API access** shows a sample `runSession` request. Copy the agent (app)
resource name from it, the part before `/sessions/`, which looks like:

```
projects/<project>/locations/us/apps/<app-id>
```

(CX Agent Studio agents live in the `us` multi-region.) Put it in `../.env` as
`CX_AGENT_ID`:

```
CX_AGENT_ID=projects/your-project/locations/us/apps/your-app-id
```

## Debugging with invoke.py

`invoke.py` is a separate, simpler debugging tool. It talks to the agent over the CX Agent Studio **text** `runSession` API
(`POST https://ces.googleapis.com/v1/<CX_AGENT_ID>/sessions/<session-id>:runSession`)
so you can sanity-check the agent's own logic/responses from a terminal,
independent of the voice/audio path. It doesn't exercise `BidiRunSession` or
audio at all.

Authentication uses Application Default Credentials. The Cloud Run service
account needs the `roles/ces.client` role (granted by `server/deploy.sh`). To
run `invoke.py` locally, log in first so ADC has credentials to use:

```bash
gcloud auth application-default login
```
