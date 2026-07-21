# CX Agent Studio agent

[CX Agent Studio](https://docs.cloud.google.com/gemini-enterprise-agent-platform/agent-studio)
is the low-code visual builder in the Google Cloud console for
Customer Engagement Suite (CES) agents. You build and deploy the agent in the
UI — there is no deploy script here. The TAC server ([`../server`](../server))
then connects Twilio to it over the CES REST API.

## Build the agent

1. In the console, open **Gemini Enterprise for CX → CX Agent Studio → Agents**
   and click **Create agent**.
2. Give it a name, set the **instructions**, pick a **model**, and add any
   **tools** (Google Search, data stores, connectors like Salesforce, MCP, …).
3. Use the **Preview** tab to chat-test the agent.
4. Open the **Deploy** tab. On "How do you want to deploy your agent?" choose
   **Set up API access** (the TAC server calls the agent's API — you do not need
   the web widget or the "Connect to a platform" telephony integration).

## Get the agent ID

**Set up API access** shows a sample `runSession` request. Copy the agent (app)
resource name from it — the part before `/sessions/` — which looks like:

```
projects/<project>/locations/us/apps/<app-id>
```

(CX Agent Studio agents live in the `us` multi-region.) Put it in `../.env` as
`CX_AGENT_ID`:

```
CX_AGENT_ID=projects/your-project/locations/us/apps/your-app-id
```

## How it's invoked

The TAC server calls the CES text method
`POST https://ces.googleapis.com/v1/<CX_AGENT_ID>/sessions/<session-id>:runSession`.
Twilio ConversationRelay handles speech, so only text is exchanged and CES keeps
the conversation history server-side (one session id per conversation).

Authentication uses Application Default Credentials — the Cloud Run service
account needs the `roles/ces.client` role (granted by `server/deploy.sh`).
