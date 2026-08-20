"""TAC server entrypoint for Cloud Run.

Connects Twilio to an agent built in Conversational Agents (Dialogflow CX) and
runs the TAC FastAPI server (Twilio webhooks + ConversationRelay WebSocket).
Config comes from env vars — from conversational_agents/.env locally, injected
on Cloud Run.
"""

import os

from dotenv import load_dotenv

from tac import TAC, TACConfig
from tac.channels.sms import SMSChannelConfig
from tac.channels.voice import VoiceChannelConfig
from tac.server import TACFastAPIServer
from tac_google.connectors import ConversationalAgentsConnector

load_dotenv()

CONVERSATIONAL_AGENT_ID = os.environ["CONVERSATIONAL_AGENT_ID"]
DIALOGFLOW_LANGUAGE_CODE = os.environ.get("DIALOGFLOW_LANGUAGE_CODE", "en")

tac = TAC(config=TACConfig.from_env())

connector = ConversationalAgentsConnector(
    tac=tac,
    agent_id=CONVERSATIONAL_AGENT_ID,
    language_code=DIALOGFLOW_LANGUAGE_CODE,
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
