"""TAC server entrypoint for Cloud Run.

Connects Twilio to an agent built in CX Agent Studio and runs the TAC FastAPI
server (Twilio webhooks + ConversationRelay WebSocket). Config comes from env
vars — from cx_agent_studio/.env locally, injected on Cloud Run.

Defaults to the "cascaded" voice approach (ConversationRelay — Twilio does
the STT/TTS). To switch to native speech-to-speech (S2S) voice instead
(Twilio Media Streams carries raw audio, CES does its own STT/TTS; neither
Conversation Orchestrator nor TAC Memory support voice in this mode), comment
out the "cascaded" block below and uncomment the "s2s" block.
"""

import os

from dotenv import load_dotenv
from tac import TAC, TACConfig
from tac.channels.sms import SMSChannelConfig
from tac.channels.voice import VoiceChannelConfig

from tac_google.connectors import CXAgentStudioConnector
from tac_google.connectors.cx_agent_studio.server import CXAgentStudioFastAPIServer

# from tac_google.connectors.cx_agent_studio.voice_s2s import VoiceS2SConfig  # s2s

load_dotenv()

CX_AGENT_ID = os.environ["CX_AGENT_ID"]

tac = TAC(config=TACConfig.from_env())

# --- cascaded (default): ConversationRelay voice + SMS ---------------------
connector = CXAgentStudioConnector(
    tac=tac,
    agent_id=CX_AGENT_ID,
    voice_config=VoiceChannelConfig(memory_mode="once"),
    sms_config=SMSChannelConfig(memory_mode="once"),
)

# --- s2s: native speech-to-speech voice + SMS -------------------------------
# connector = CXAgentStudioConnector(
#     tac=tac,
#     agent_id=CX_AGENT_ID,
#     voice_config=VoiceS2SConfig(),
#     sms_config=SMSChannelConfig(memory_mode="once"),
# )

server = CXAgentStudioFastAPIServer(
    tac=tac,
    voice_channel=connector.voice,
    messaging_channels=connector.messaging,
)

if __name__ == "__main__":
    server.start()
