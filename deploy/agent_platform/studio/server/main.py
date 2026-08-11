"""TAC server entrypoint for Cloud Run (Agent Studio app).

Connects Twilio to an Agent Studio app on GCP Agent Platform Runtime and runs
the TAC FastAPI server (Twilio webhooks + ConversationRelay WebSocket). Config
comes from env vars — from studio/.env locally, injected on Cloud Run.
"""

import os

import vertexai
from dotenv import load_dotenv

from tac import TAC, TACConfig
from tac.channels.sms import SMSChannelConfig
from tac.channels.voice import VoiceChannelConfig
from tac.server import TACFastAPIServer
from tac_google.connectors import StudioAgentEngineConnector

load_dotenv()

GCP_PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
GCP_LOCATION = os.environ["GOOGLE_CLOUD_LOCATION"]
REASONING_ENGINE_ID = os.environ["GCP_REASONING_ENGINE_ID"]

client = vertexai.Client(project=GCP_PROJECT, location=GCP_LOCATION)
tac = TAC(config=TACConfig.from_env())
agent = client.agent_engines.get(
    name=f"projects/{GCP_PROJECT}/locations/{GCP_LOCATION}/reasoningEngines/{REASONING_ENGINE_ID}"
)

connector = StudioAgentEngineConnector(
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
