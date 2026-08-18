# CX Agent Studio agent

[CX Agent Studio](https://docs.cloud.google.com/gemini-enterprise-agent-platform/agent-studio)
is the low-code visual builder in the Google Cloud console for
Customer Engagement Suite (CES) agents. You build and deploy the agent in the
UI — there is no deploy script here. The TAC server
([`../server/main.py`](../server/main.py)) then connects Twilio to it.

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

`../server/main.py` defaults to ConversationRelay voice (Twilio does the
STT/TTS). It can also be switched to native speech-to-speech (S2S) voice
instead — Twilio Media Streams carries raw call audio, and CX Agent Studio
does its own speech recognition/synthesis over `BidiRunSession`
(`wss://ces.googleapis.com/ws/google.cloud.ces.v1.SessionService/BidiRunSession/...`),
with no text exchanged for voice and no Twilio-side STT/TTS. See the comments
in `main.py` to switch, and [`../README.md`](../README.md) for the comparison.

`invoke.py` in this folder is a separate, simpler debugging tool — it talks to
the agent over the CX Agent Studio **text** `runSession` API
(`POST https://ces.googleapis.com/v1/<CX_AGENT_ID>/sessions/<session-id>:runSession`)
so you can sanity-check the agent's own logic/responses from a terminal,
independent of the voice/audio path. It doesn't exercise `BidiRunSession` or
audio at all.

Authentication uses Application Default Credentials — the Cloud Run service
account needs the `roles/ces.client` role (granted by `server/deploy.sh`). To
run `invoke.py` locally, log in first so ADC has credentials to use:

```bash
gcloud auth application-default login
```
