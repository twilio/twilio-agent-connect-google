"""TAC server entrypoint for Cloud Run.

Runs the TAC FastAPI server, connecting Twilio's voice and messaging channels
to an agent built in CX Agent Studio. Config comes from env vars: from
cx_agent_studio/.env locally, injected on Cloud Run.

Messaging covers SMS and Chat always, plus RCS and WhatsApp when
TWILIO_RCS_SENDER_ID / TWILIO_WHATSAPP_NUMBER are set. All of them share the
one Conversation Orchestrator webhook; each channel picks out its own traffic.

Defaults to the "cascaded" voice approach (ConversationRelay — Twilio does
the STT/TTS). To switch to native speech-to-speech (S2S) voice instead
(Twilio Media Streams carries raw audio, CES does its own STT/TTS; neither
Conversation Orchestrator nor Conversation Memory support voice in this mode),
comment out the "cascaded" block below and uncomment the "s2s" block.
"""

import os

from dotenv import load_dotenv
from tac import TAC, TACConfig
from tac.channels.chat import ChatChannelConfig
from tac.channels.rcs import RCSChannelConfig
from tac.channels.sms import SMSChannelConfig
from tac.channels.voice import VoiceChannelConfig
from tac.channels.whatsapp import WhatsAppChannelConfig

from tac_google.connectors import CXAgentStudioConnector
from tac_google.connectors.cx_agent_studio.server import CXAgentStudioFastAPIServer

# from tac_google.connectors.cx_agent_studio.voice_s2s import VoiceS2SConfig  # s2s

load_dotenv()

CX_AGENT_ID = os.environ["CX_AGENT_ID"]

tac = TAC(config=TACConfig.from_env())

# memory_mode="once" on every channel: CES replays the whole session history
# on each call, so re-injecting unchanged memory every turn would duplicate it.
MESSAGING_CONFIGS = {
    "sms_config": SMSChannelConfig(memory_mode="once"),
    "chat_config": ChatChannelConfig(memory_mode="once"),
    "rcs_config": RCSChannelConfig(memory_mode="once"),
    "whatsapp_config": WhatsAppChannelConfig(memory_mode="once"),
}

# --- cascaded (default): ConversationRelay voice + messaging ----------------
connector = CXAgentStudioConnector(
    tac=tac,
    agent_id=CX_AGENT_ID,
    voice_config=VoiceChannelConfig(memory_mode="once"),
    **MESSAGING_CONFIGS,
)

# --- s2s: native speech-to-speech voice + messaging -------------------------
# connector = CXAgentStudioConnector(
#     tac=tac,
#     agent_id=CX_AGENT_ID,
#     voice_config=VoiceS2SConfig(),
#     **MESSAGING_CONFIGS,
# )

# Every messaging channel the connector actually built. SMS and Chat are
# always built; RCS and WhatsApp only when TWILIO_RCS_SENDER_ID /
# TWILIO_WHATSAPP_NUMBER are set in .env, and are None otherwise — hence the
# filter. Registering a channel matters: channels self-filter on
# author.channel, so an inbound message on an *unregistered* channel is
# silently dropped rather than answered.
messaging_channels = [
    c for c in (connector.sms, connector.chat, connector.rcs, connector.whatsapp) if c is not None
]

server = CXAgentStudioFastAPIServer(
    tac=tac,
    voice_channel=connector.voice,
    messaging_channels=messaging_channels,
)

if __name__ == "__main__":
    server.start()
