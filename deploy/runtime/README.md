# Deploy Agent to GCP Agent Platform Runtime

Guide to deploying AI agents to GCP Agent Platform Runtime (Reasoning Engine) using **Gemini 3.5 Flash**.

---

## Overview

Deploy your agent to GCP's fully managed serverless platform:
- **Automatic scaling** - Handles traffic spikes
- **Built-in monitoring** - Vertex AI observability
- **Managed dependencies** - Python packages installed automatically
- **API access** - RESTful API + Python SDK

---

## Prerequisites

### 1. Python 3.11

GCP Agent Platform Runtime requires Python 3.11. The repository includes a `.python-version` file for this.

```bash
uv venv --python 3.11
source .venv/bin/activate
```

### 2. GCP Project

You need a GCP project with:
- ✅ Billing enabled
- ✅ Vertex AI API enabled
- ✅ Gemini 3.5 Flash access (see Model Garden setup below)

### 3. Google Cloud CLI

```bash
brew install --cask google-cloud-sdk
```

### 4. Python Dependencies

```bash
# From project root
uv pip install -e ".[dev]"
```

---

## Setup: Enable Gemini 3.5 Flash

Before deploying, you must enable Gemini 3.5 Flash in your GCP project:

1. **Go to Model Garden**: https://console.cloud.google.com/vertex-ai/model-garden?project=YOUR_PROJECT_ID

2. **Find Gemini 3.5 Flash**:
   - Click "Google models" (shows 130+ models)
   - Find "Gemini 3.5 Flash" card
   - Click on it

3. **Check the "View Code" button** to see the latest API usage:
   ```python
   from google import genai
   
   client = genai.Client(
       enterprise=True,  # Use enterprise mode
       project="YOUR_PROJECT_ID",
       location="global"  # Use global location
   )
   ```

Gemini 3.5 Flash uses the **Enterprise Agent Platform API**, not the standard Vertex AI API.

---

## Quick Start

### 1. Configure Environment

Create `.env` file in `deploy/runtime/`:

```bash
cd deploy/runtime
cp .env.example .env
```

Edit `.env`:
```bash
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
```

### 2. Authenticate

**Application Default Credentials (Recommended)**:
```bash
gcloud auth application-default login
```

### 3. Deploy Agent

```bash
cd deploy/runtime
python deploy_adk.py
```

**What happens**:
1. Loads `.env` configuration
2. Creates SimpleAgent class using Gemini 3.5 Flash
3. Deploys to Agent Platform Runtime (takes 3-5 minutes)
4. Returns agent ID

**Example output**:
```
Deploying agent to GCP
Project: your-project-id
Location: us-central1

Staging bucket: gs://your-project-reasoning-engine-staging
Deploying (3-5 minutes)...

✅ Deployed! Agent ID: 9178589478011273216

Add to .env:
GCP_REASONING_ENGINE_ID=9178589478011273216

Test with: python invoke_agent.py
```

### 4. Save Agent ID

Add to `.env`:
```bash
echo "GCP_REASONING_ENGINE_ID=9178589478011273216" >> .env
```

### 5. Test Agent

```bash
python invoke_agent.py
```

Interactive chat:
```
Testing agent 9178589478011273216
Location: us-central1

======================================================================
Test 1: Simple math
======================================================================
Query: Hello! What is 2+2?
Response: Hello! 2 + 2 is 4. 😊

✅ Agent working correctly!
```

