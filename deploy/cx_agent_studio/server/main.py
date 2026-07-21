"""TAC server entrypoint for Cloud Run.

Connects Twilio to an agent built in CX Agent Studio and runs the TAC FastAPI
server (Twilio webhooks + ConversationRelay WebSocket). Config comes from env
vars — from cx_agent_studio/.env locally, injected on Cloud Run.
"""

import os

from dotenv import load_dotenv

from tac import TAC, TACConfig
from tac.server import TACFastAPIServer
from tac_google.connectors import CXAgentStudioConnector

load_dotenv()

CX_AGENT_ID = os.environ["CX_AGENT_ID"]

tac = TAC(config=TACConfig.from_env())

connector = CXAgentStudioConnector(tac=tac, agent_id=CX_AGENT_ID)

server = TACFastAPIServer(
    tac=tac,
    voice_channel=connector.voice,
    messaging_channels=[connector.sms],
)

if __name__ == "__main__":
    server.start()
