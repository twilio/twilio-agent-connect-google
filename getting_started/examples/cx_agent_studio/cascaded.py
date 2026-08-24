"""Example: Connect Twilio to a CX Agent Studio agent, text/SMS + ConversationRelay voice.

Twilio ConversationRelay handles speech, so the connector only exchanges text
with the agent (CES REST API, text runSession).

For native speech-to-speech voice instead, see `s2s.py` in this same folder.

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
    TWILIO_CONVERSATION_CONFIGURATION_ID=conv_configuration_xxx
    TWILIO_VOICE_PUBLIC_DOMAIN=your-domain.ngrok.io

Installation:
    pip install twilio-agent-connect-google[cx-agent-studio,server] python-dotenv

Run:
    python cx_agent_studio/cascaded.py
"""

import os

from dotenv import load_dotenv
from tac import TAC, TACConfig
from tac.channels.sms import SMSChannelConfig
from tac.channels.voice import VoiceChannelConfig

from tac_google.connectors import CXAgentStudioConnector
from tac_google.connectors.cx_agent_studio.server import CXAgentStudioFastAPIServer

load_dotenv()

CX_AGENT_ID = os.environ["CX_AGENT_ID"]

tac = TAC(config=TACConfig.from_env())

connector = CXAgentStudioConnector(
    tac=tac,
    agent_id=CX_AGENT_ID,
    voice_config=VoiceChannelConfig(memory_mode="once"),
    sms_config=SMSChannelConfig(memory_mode="once"),
)

messaging_channels = [connector.sms, connector.chat, connector.rcs, connector.whatsapp]

server = CXAgentStudioFastAPIServer(
    tac=tac,
    voice_channel=connector.voice,
    messaging_channels=[c for c in messaging_channels if c is not None],
)

if __name__ == "__main__":
    server.start()
