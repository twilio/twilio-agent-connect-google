# Test Dialogflow CX Playbook Agent

Guide to testing Dialogflow CX playbook agents before connecting to Twilio Agent Connect.

---

## Overview

Test your Dialogflow CX agent directly:
- **Quick validation** - Verify agent responds correctly
- **No Twilio required** - Test without webhooks or phone numbers
- **Session-based** - Tests conversation continuity
- **Easy debugging** - See requests and responses

---

## Prerequisites

### 1. Dialogflow CX Agent

You need a Dialogflow CX agent with playbooks.

**Create in Console:**
1. Go to [Dialogflow CX Console](https://dialogflow.cloud.google.com/cx/)
2. Create an agent
3. Create a playbook with goals and instructions
4. Configure Gemini model (Settings → Generative AI)

### 2. Get Agent ID

From the Console URL:
```
https://conversational-agents.cloud.google.com/projects/PROJECT_ID/locations/LOCATION/agents/AGENT_ID/...
```

Extract:
- **Project ID**: `twlo-agent-builders-1122`
- **Location**: `us-central1`
- **Agent ID**: `95f52547-0d46-4493-a568-6cbecdf949fc`

### 3. Python Dependencies

```bash
# From project root
uv pip install -e ".[dev]"
```

---

## Quick Start

### 1. Configure Environment

Create `.env` file in `deploy/`:

```bash
cd deploy
cp .env.example .env
```

Edit `.env`:
```bash
GOOGLE_CLOUD_PROJECT=twlo-agent-builders-1122
GOOGLE_CLOUD_LOCATION=us-central1
DIALOGFLOW_CX_AGENT_ID=95f52547-0d46-4493-a568-6cbecdf949fc
```

### 2. Authenticate

**Application Default Credentials (Recommended)**:
```bash
gcloud auth application-default login
```

### 3. Test Agent

```bash
cd deploy/dialogflow
python test_dialogflow_simple.py
```

**Example output**:
```
Testing agent 95f52547-0d46-4493-a568-6cbecdf949fc
Location: us-central1

[1] User: Hello, I need help
    Agent: Hello! I'm here to help you. What can I assist you with today?

[2] User: I want to track my order
    Agent: I'd be happy to help you track your order! Could you please provide your order number?

[3] User: Tell me about your pricing
    Agent: I am sorry, I cannot provide information about pricing. Is there anything else I can help you with?

✅ Test complete!
```

---

## How It Works

The test script:

1. Loads configuration from `.env` file
2. Creates a unique session ID for the conversation
3. Connects to Dialogflow CX API using regional endpoint
4. Sends test messages
5. Displays agent responses

**Core logic:**
```python
from google.cloud.dialogflowcx_v3 import SessionsClient

# Create client with regional endpoint
api_endpoint = f"{location}-dialogflow.googleapis.com:443"
client = SessionsClient(client_options={"api_endpoint": api_endpoint})

# Send message
response = client.detect_intent(
    request={
        "session": session_path,
        "query_input": {
            "text": {"text": user_msg},
            "language_code": "en",
        },
    }
)
```

**Session management:**
- Each test run creates a new session
- Same session ID maintains conversation context
- Dialogflow stores history server-side

---

## Customizing Tests

Edit `test_messages` in `test_dialogflow_simple.py`:

```python
test_messages = [
    "Hello, I need help",
    "I want to track my order",
    "Tell me about your pricing",
    "What's your return policy?",  # Add more
]
```

---

## Troubleshooting

### Error: "Permission denied"

Grant Dialogflow API permissions:

```bash
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="user:YOUR_EMAIL@gmail.com" \
  --role="roles/dialogflow.client"
```

### Error: "Agent not found"

Verify your agent exists:
```bash
gcloud dialogflow agents list --location=us-central1 --project=YOUR_PROJECT_ID
```

Check that:
- Agent ID is correct (UUID format)
- Location matches where agent was created
- Project ID is correct

### No response from agent

Test in Console first:
1. Go to [Dialogflow CX Console](https://dialogflow.cloud.google.com/cx/)
2. Select your agent
3. Click **Test Agent** (top right)
4. Type test messages

Check playbook configuration:
- Does it have a defined goal?
- Are instructions clear?
- Is LLM model configured? (Settings → Generative AI)

### Authentication issues

```bash
# Re-authenticate
gcloud auth application-default login

# Or use service account
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

---

## Next Steps

Once testing passes, connect to Twilio:

```bash
cd ../../getting_started/examples
python dialogflow_cx_playbook.py
```

Then:
1. Expose with ngrok: `ngrok http 8000`
2. Configure Twilio webhooks to your ngrok URL
3. Test with voice and SMS

---

## Resources

- [Dialogflow CX Documentation](https://cloud.google.com/dialogflow/cx/docs)
- [Dialogflow CX API Reference](https://cloud.google.com/dialogflow/cx/docs/reference)
- [Dialogflow CX Playbooks Guide](https://cloud.google.com/dialogflow/cx/docs/concept/playbook)
