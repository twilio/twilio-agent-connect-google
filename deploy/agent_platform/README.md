# Connect Twilio to an agent on Agent Platform Runtime

Deploy [Twilio Agent Connect (TAC)](https://www.twilio.com/docs/conversations/agent-connect)
— Twilio's framework for connecting AI agents to voice and messaging channels —
with an agent on GCP Agent Platform Runtime and the TAC server on Cloud Run.
This directory has one fully independent deployment
per agent type — pick one:

- **[`adk/`](./adk/)** — an ADK agent, connected via `ADKAgentEngineConnector`.
- **[`studio/`](./studio/)** — a source-code app built and deployed from the
  Agent Studio console, connected via `StudioAgentEngineConnector`.

Each folder has its own agent, TAC server, Cloud Run deploy, Secret Manager
setup, `.env`, and `Makefile` — nothing is shared between them, so you can
follow either one on its own. See the `README.md` inside each for setup steps.
