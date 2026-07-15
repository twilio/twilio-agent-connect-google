# Deployment Guide

Deploy AI agents to GCP and connect them to Twilio.

---

## Deployment Options

### Agent Platform Runtime (Available Now)

Deploy your **agent** to GCP's managed Agent Platform Runtime (Reasoning Engine).

**Location**: [`agent_platform/agents/`](./agent_platform/agents/)
**Guide**: [agent_platform/agents/README.md](./agent_platform/agents/README.md)
— covers the three main ways to deploy an agent (custom Python class,
LangChain, ADK) and how each is invoked.

### Cloud Run (Coming Soon)

Deploy the TAC **server** (not the agent itself) as a containerized service.

### App Engine (Coming Soon)

Deploy the TAC **server** to App Engine.
