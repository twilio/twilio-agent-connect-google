"""Example: Connect Twilio to an ADK agent deployed on GCP Agent Platform Runtime.

This example shows how to:
1. Connect to an ADK agent deployed on GCP Agent Platform Runtime (Reasoning Engine)
2. Run a TAC FastAPI server that handles Twilio webhooks
3. Use a session per conversation, reused across turns (ADK manages history server-side)

Prerequisites:
    - GCP project with Vertex AI enabled
    - ADK agent deployed to GCP Agent Platform Runtime (Reasoning Engine) — see
      deploy/agent_platform/adk/
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
    python agent_platform/adk_agent_engine.py
"""

import os

import vertexai
from dotenv import load_dotenv
from tac import TAC, TACConfig
from tac.channels.sms import SMSChannelConfig
from tac.channels.voice import VoiceChannelConfig
from tac.server import TACFastAPIServer

from tac_google.connectors import ADKAgentEngineConnector

load_dotenv()

GCP_PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
GCP_LOCATION = os.environ["GOOGLE_CLOUD_LOCATION"]
REASONING_ENGINE_ID = os.environ["GCP_REASONING_ENGINE_ID"]

client = vertexai.Client(project=GCP_PROJECT, location=GCP_LOCATION)
tac = TAC(config=TACConfig.from_env())
agent = client.agent_engines.get(
    name=f"projects/{GCP_PROJECT}/locations/{GCP_LOCATION}/reasoningEngines/{REASONING_ENGINE_ID}"
)

connector = ADKAgentEngineConnector(
    tac=tac,
    agent=agent,
    voice_config=VoiceChannelConfig(memory_mode="once"),
    sms_config=SMSChannelConfig(memory_mode="once"),
)

server = TACFastAPIServer(
    tac=tac,
    voice_channel=connector.voice,
    messaging_channels=connector.messaging,
)

if __name__ == "__main__":
    server.start()
