"""Example: Connect Twilio to an agent built in CX Agent Studio.

This example shows how to:
1. Connect to an agent built in CX Agent Studio (Customer Engagement Suite)
2. Run a TAC FastAPI server that handles Twilio webhooks + ConversationRelay
3. Let CES keep conversation history server-side (per session id)

The connector talks to the agent over the CES REST API (text runSession) —
Twilio ConversationRelay handles speech, so only text is exchanged.

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
    python cx_agent_studio.py
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
