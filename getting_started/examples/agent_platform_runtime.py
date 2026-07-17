"""Example: Connect Twilio to agents deployed on GCP Agent Platform Runtime.

This example shows how to:
1. Connect to an agent deployed on GCP Agent Platform Runtime (Reasoning Engine)
2. Run a TAC FastAPI server that handles Twilio webhooks
3. Use a single agent instance for all conversations (connector manages history locally)

Prerequisites:
    - GCP project with Vertex AI enabled
    - Agent deployed to GCP Agent Platform Runtime (Reasoning Engine)
    - .env file with required environment variables (see .env.example)

Environment Variables (in .env file):
    # GCP Configuration
    GOOGLE_CLOUD_PROJECT=your-gcp-project-id
    GOOGLE_CLOUD_LOCATION=us-central1
    GCP_REASONING_ENGINE_ID=your-reasoning-engine-id

    # Twilio Configuration
    TWILIO_ACCOUNT_SID=your_account_sid
    TWILIO_AUTH_TOKEN=your_auth_token
    TWILIO_API_KEY=your_api_key
    TWILIO_API_SECRET=your_api_secret
    TWILIO_PHONE_NUMBER=+1234567890
    TWILIO_CONVERSATION_CONFIGURATION_ID=conv_configuration_xxx
    TWILIO_VOICE_PUBLIC_DOMAIN=your-domain.ngrok.io

Installation:
    pip install twilio-agent-connect-google[vertex-ai,server] python-dotenv

Run:
    python agent_platform_runtime.py
"""

import os

import vertexai
from dotenv import load_dotenv
from vertexai import agent_engines

from tac import TAC, TACConfig
from tac.server import TACFastAPIServer
from tac_google.connectors import AgentPlatformRuntimeConnector

load_dotenv()

GCP_PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
GCP_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
REASONING_ENGINE_ID = os.environ["GCP_REASONING_ENGINE_ID"]

vertexai.init(project=GCP_PROJECT, location=GCP_LOCATION)
tac = TAC(config=TACConfig.from_env())
agent = agent_engines.get(REASONING_ENGINE_ID)

connector = AgentPlatformRuntimeConnector(tac=tac, agent=agent)

server = TACFastAPIServer(
    tac=tac,
    voice_channel=connector.voice,
    messaging_channels=[connector.sms],
)

if __name__ == "__main__":
    server.start()
