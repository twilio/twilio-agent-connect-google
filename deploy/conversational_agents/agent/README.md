# Conversational Agents (Dialogflow CX) agent

[Conversational Agents](https://docs.cloud.google.com/dialogflow/cx/docs) is
Google's Dialogflow CX platform. You build the agent in the console; it is
invocable immediately (no deploy needed) over the Dialogflow CX `detectIntent`
API. The TAC server connects Twilio to it over that same API.

## Build the agent

1. Open the [Conversational Agents console](https://conversational-agents.cloud.google.com/)
   and select your project.
2. Click **Create agent → Build your own**.
3. Set the **region**, time zone, and language, then choose how the conversation
   starts:
   - **Playbook** — generative (Gemini) agent driven by natural-language instructions.
   - **Flow** — deterministic state machine (pages, intents, transitions).

   Both are invoked the same way, so either works. For a quick start, pick
   **Playbook** and give it a short instruction (e.g. "You are a helpful
   assistant. Be concise.").
4. Use the **Preview / simulator** on the right to chat-test the agent.

No deploy step is required — the draft agent responds to `detectIntent` right
away. (Deploying to an *environment* is only for pinning a version for
production.)

## Get the agent ID

The connector needs the agent's resource name:

```
projects/<project>/locations/<location>/agents/<agent-id>
```

It is in the console URL, e.g.
`https://conversational-agents.cloud.google.com/projects/<project>/locations/<location>/agents/<agent-id>/...`.
Put it in `.env`:

```
CONVERSATIONAL_AGENT_ID=projects/your-project/locations/us-central1/agents/your-agent-id
```

## Invoke

```bash
python invoke.py
```

`invoke.py` calls
`POST https://<location>-dialogflow.googleapis.com/v3/<agent>/sessions/<session>:detectIntent`
with `{"queryInput": {"text": {"text": "..."}, "languageCode": "en"}}` and reads
the reply from `queryResult.responseMessages[].text.text`.

Authentication uses Application Default Credentials — grant the calling
principal (or Cloud Run service account) the **Dialogflow API Client** role.
User ADC also needs a quota project, which `invoke.py` sets via the
`X-Goog-User-Project` header.
