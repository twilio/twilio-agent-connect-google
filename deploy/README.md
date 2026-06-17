# Deployment Guide

Deploy AI agents to GCP and connect them to Twilio.

---

## Quick Start

### 1. Deploy Agent to GCP

```bash
cd deploy/runtime
python deploy_adk.py
```

Save the agent ID from the output.

### 2. Configure Environment

Create `.env` in `deploy/runtime/`:

```bash
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GCP_REASONING_ENGINE_ID=your-agent-id
```

### 3. Test Agent

```bash
python invoke_agent.py
```

---

## Deployment Options

### Agent Platform Runtime (Available Now)

Deploy your agent to GCP's managed Agent Platform Runtime.

**Location**: [`runtime/`](./runtime/)  
**Guide**: [runtime/README.md](./runtime/README.md)

### Cloud Run (Coming Soon)

Deploy TAC server as a containerized service.

### App Engine (Coming Soon)

Deploy TAC server to App Engine.
