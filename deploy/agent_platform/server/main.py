"""TAC server entrypoint for Cloud Run.

Connects Twilio to an agent on GCP Agent Platform Runtime and runs the TAC
FastAPI server (Twilio webhooks + ConversationRelay WebSocket). Config comes
from env vars — from agent_platform/.env locally, injected on Cloud Run.
"""

import os

import vertexai
from dotenv import load_dotenv
from vertexai import agent_engines

from tac import TAC, TACConfig
from tac.channels.sms import SMSChannelConfig
from tac.channels.voice import VoiceChannelConfig
from tac.server import TACFastAPIServer
from tac_google.connectors import AgentPlatformRuntimeConnector

load_dotenv()

GCP_PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
GCP_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
REASONING_ENGINE_ID = os.environ["GCP_REASONING_ENGINE_ID"]

vertexai.init(project=GCP_PROJECT, location=GCP_LOCATION)
tac = TAC(config=TACConfig.from_env())
agent = agent_engines.get(REASONING_ENGINE_ID)

connector = AgentPlatformRuntimeConnector(
    tac=tac,
    agent=agent,
    voice_config=VoiceChannelConfig(memory_mode="once"),
    sms_config=SMSChannelConfig(memory_mode="once"),
)

server = TACFastAPIServer(
    tac=tac,
    voice_channel=connector.voice,
    messaging_channels=[connector.sms],
)

if __name__ == "__main__":
    server.start()
