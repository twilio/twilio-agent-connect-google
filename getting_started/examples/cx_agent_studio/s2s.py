"""Example: Native speech-to-speech (S2S) voice with a CX Agent Studio agent.

Call audio flows over Twilio Media Streams and the agent does its own speech
recognition/synthesis over `BidiRunSession` — no ConversationRelay, no
Twilio-side STT/TTS, and no text exchanged. Voice-only (no SMS), and this
mode doesn't support Conversation Orchestrator or TAC Memory.

For text/SMS + ConversationRelay voice instead, see `cascaded.py` in this
same folder.

Prerequisites:
    - An agent built and deployed in CX Agent Studio
    - Application Default Credentials with access to the agent
      (`gcloud auth application-default login`, or a Cloud Run service account
      with the `roles/ces.client` role)
    - .env file with the variables below

Environment Variables (in .env file):
    # CX Agent Studio
    CX_AGENT_ID=projects/your-project/locations/your-location/apps/your-app-id

    # Twilio Configuration
    TWILIO_ACCOUNT_SID=your_account_sid
    TWILIO_AUTH_TOKEN=your_auth_token
    TWILIO_API_KEY=your_api_key
    TWILIO_API_SECRET=your_api_secret
    TWILIO_PHONE_NUMBER=+1234567890
    TWILIO_VOICE_PUBLIC_DOMAIN=your-domain.ngrok.io

Installation:
    pip install twilio-agent-connect-google[cx-agent-studio,server] python-dotenv

Run:
    python cx_agent_studio/s2s.py
"""

import os

from dotenv import load_dotenv
from tac import TAC, TACConfig

from tac_google.connectors import CXAgentStudioConnector
from tac_google.connectors.cx_agent_studio.server import CXAgentStudioFastAPIServer
from tac_google.connectors.cx_agent_studio.voice_s2s import VoiceS2SConfig

load_dotenv()

CX_AGENT_ID = os.environ["CX_AGENT_ID"]

tac = TAC(config=TACConfig.from_env())

connector = CXAgentStudioConnector(
    tac=tac,
    agent_id=CX_AGENT_ID,
    voice_config=VoiceS2SConfig(),
)

server = CXAgentStudioFastAPIServer(
    tac=tac,
    voice_channel=connector.voice_s2s,
)

if __name__ == "__main__":
    server.start()
