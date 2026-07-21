# CX Agent Studio × Twilio — Integration Research

Research and positioning notes for connecting Twilio channels to agents built in
**CX Agent Studio** (Google's Customer Engagement Suite, part of Gemini
Enterprise for Customer Experience).

## Background

There are two ways to connect Twilio to a CX Agent Studio agent.

### 1. Google's "Connect to a platform → Twilio" (existing)

In CX Agent Studio, the **Deploy → Connect to a platform** flow lists Twilio as
a platform option. It is **not a managed connection** — it is backed by an
open-source reference component that you deploy yourself:

- Repo: **[GoogleCloudPlatform/ces-twilio-adapter](https://github.com/GoogleCloudPlatform/ces-twilio-adapter)**
- Created 2025-10-08; last commit 2026-05-22. **Published by Google, not
  maintained by Twilio.**

How it works: you deploy the adapter as a **Google Cloud Run** server. It bridges
**Twilio Media Streams (bidirectional audio WebSocket)** to the CES agent's
**native-audio streaming session** (`BidiRunSession`). The adapter transcodes
audio (μ-law 8 kHz ↔ LINEAR16 16 kHz) and maintains two WebSockets — one to
Twilio, one to CES. It also handles SMS/RCS via the CES text `runSession` REST
API.

### 2. This repo's `CXAgentStudioConnector` (new)

We added a **TAC-based** connector in this repo. Instead of raw media streaming,
it uses **Twilio ConversationRelay**, which does the speech-to-text and
text-to-speech on Twilio's side — so the connector exchanges **text** with the
agent and invokes CX Agent Studio over the **text `runSession`** API. Users still
deploy a **Cloud Run** server (the TAC server) on GCP to run it.

- Connector: [`cx_agent_studio_connector.py`](https://github.com/twilio/twilio-agent-connect-google/blob/gemini-enterprise-cx/src/tac_google/connectors/cx_agent_studio_connector.py)
- Deploy: [`deploy/cx_agent_studio/`](https://github.com/twilio/twilio-agent-connect-google/tree/gemini-enterprise-cx/deploy/cx_agent_studio) (agent built in console + TAC server on Cloud Run)
- Verified live: SMS and Voice, including multi-turn memory (CES keeps history by
  session id).

## Comparison

| | Google `ces-twilio-adapter` | This repo's `CXAgentStudioConnector` |
|---|---|---|
| Ownership | Google reference (not Twilio-maintained) | Twilio, in this repo (TAC-based) |
| Voice transport | Twilio Media Streams (raw audio) | Twilio ConversationRelay (text) |
| CES API | `BidiRunSession` (audio) + `runSession` (text) | `runSession` (text) |
| STT / TTS | CES native audio | ConversationRelay (Twilio) |
| Voice quality | CES native voice, barge-in | ConversationRelay TTS voice |
| Implementation | Two WebSockets + audio transcoding | One WebSocket, text only — simpler |
| TAC memory / orchestration | — | Yes (consistent with the AWS repo) |
| Deploy target | Google Cloud Run | Google Cloud Run |

Both deploy a Cloud Run server; the difference is the transport (audio vs text)
and ownership.

## Proposals

### 1. Get this repo referenced in the CX Agent Studio UI

The "Connect to a platform → Twilio" option currently points to the
Google-published `ces-twilio-adapter`, which Twilio does not maintain and which
uses the heavier audio-streaming approach. We should work with Google to have the
**Twilio integration reference this repo's TAC-based connector** (maintained by
Twilio, consistent with the AWS repo). Requires Google's cooperation to update
the docs/UI.

### 2. Integrate Twilio Streams with Conversation Orchestrator + Memory

Our current connector uses **ConversationRelay**, which is text-based (Twilio
does the STT/TTS), so it does not use CES's native audio — no voice-to-voice.
**ConversationRelay itself does not change.**

The voice-to-voice path uses **Twilio Streams** (raw bidirectional audio) into
CES's native-audio session (`BidiRunSession`) — but Streams today does **not**
integrate with Twilio's **Conversation Orchestrator** and **Memory**. The
proposal is to push development so that **Twilio Streams integrates with
Conversation Orchestrator + Memory**. Once it does, a stream-based connector can
deliver **voice-to-voice** (native audio both ends, natural barge-in) while still
getting orchestration and memory from TAC — combining the best of both
approaches.

### 3. Work with customers to integrate

Partner with customers to validate and harden the integration — e.g. **Copart**
([architecture doc](https://docs.google.com/document/d/18wNzEn2FKg8ZGqcqHyF4H_9DVFq7NCGNuZYwiXxbrOk/edit?usp=sharing)),
whose design already uses a Twilio ↔ CES adapter with escalation to a live agent
via TaskRouter/Flex.

## Additional considerations

- **Trade-off to be explicit about:** the text path (ConversationRelay) is
  simpler, consistent across channels, and adds TAC memory — but gives up CES
  native voice quality/barge-in. The audio path (Streams → native adapter) keeps
  native voice, at the cost of complexity and, today, no Orchestrator/Memory.
  Proposal 2 (Streams + Orchestrator + Memory) is what lets us keep native voice
  *and* get TAC orchestration/memory. Two points to evaluate rather than assume:
  - **Latency** — text-to-text latency is *not* a concern for us.
  - **Cost** — needs real measurement/evaluation to compare the two patterns
    (raw audio streaming vs text `runSession`); voice-to-voice cost is TBD.
- **Human escalation:** TAC already supports handoff to a live agent (Twilio
  Flex). Two follow-ups for this integration: (a) **test the TAC Flex handoff
  through this CX connector** end to end; (b) **research how CES / CX Agent Studio
  signals escalation** (e.g. the agent's `endSession` / handoff intent) and map
  that signal to the TAC/Flex handoff. Copart's design needs this path.
- **Channel coverage (advantage):** because it is TAC-based, this connector can
  serve **any channel TAC supports** — SMS, RCS, WhatsApp, and more — plus Voice
  via ConversationRelay. That is a broader, more consistent channel set than the
  Google adapter (Voice + SMS + RCS), and comes for free from the TAC stack.
