# Agent Studio

[Agent Studio](https://docs.cloud.google.com/gemini-enterprise-agent-platform/agent-studio)
is a low-code visual builder in the Google Cloud console. You design the agent
in the UI and deploy it from there — there is no `deploy.py` here. Under the
hood it produces a `google-adk` agent on Agent Platform Runtime, the same
runtime the other examples use.

## Create an agent

Prerequisites (one-time, per project):

```bash
gcloud services enable aiplatform.googleapis.com cloudresourcemanager.googleapis.com
```

Then in the console:

1. Go to **Agent Platform → Studio → Agents** and click **Create agent**.
2. Set the **instructions**, **model**, and any **tools** (Google Search, URL
   context, MCP, sub-agents).
3. Use the **Preview** tab to chat-test the agent.
4. Click **Save** (Studio currently stores and deploys agents in **us-west1**
   only).
5. Click **Deploy**, pick the region, and confirm. Deployment creates an Agent
   Runtime instance and takes a few minutes.
6. Open the deployed agent and copy its **resource ID** (the number in
   `.../reasoningEngines/<ID>`).

## Configure

In `../../.env`, set the deployed agent's ID and point the location at
us-west1 (where Studio deploys):

```
GCP_REASONING_ENGINE_ID=<your-agent-id>
GOOGLE_CLOUD_LOCATION=us-west1
```

## Invoke

```bash
python invoke.py
```

`invoke.py` calls the `reasoningEngines:streamQuery` REST endpoint directly.
Studio deploys a source-code app that does not register the SDK
`query`/`stream_query` methods, so the SDK-based clients used by the other
examples do not apply here.
