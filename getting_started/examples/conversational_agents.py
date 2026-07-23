"""Example: Connect Twilio to an agent built in Conversational Agents (Dialogflow CX).

This example shows how to:
1. Connect to an agent built in Conversational Agents (Dialogflow CX)
2. Run a TAC FastAPI server that handles Twilio webhooks + ConversationRelay
3. Let Dialogflow keep conversation history server-side (per session id)

The connector talks to the agent over the Dialogflow CX detectIntent API —
Twilio ConversationRelay handles speech, so only text is exchanged.

Prerequisites:
    - An agent built in Conversational Agents (Dialogflow CX)
    - Application Default Credentials with the Dialogflow API Client role
      (`gcloud auth application-default login`, or a Cloud Run service account
      with `roles/dialogflow.client`)
    - .env file with the variables below

Environment Variables (in .env file):
    # Conversational Agents (Dialogflow CX)
    CONVERSATIONAL_AGENT_ID=projects/your-project/locations/us-central1/agents/your-agent-id
    DIALOGFLOW_LANGUAGE_CODE=en

    # Twilio Configuration
    TWILIO_ACCOUNT_SID=your_account_sid
    TWILIO_AUTH_TOKEN=your_auth_token
    TWILIO_API_KEY=your_api_key
    TWILIO_API_SECRET=your_api_secret
    TWILIO_PHONE_NUMBER=+1234567890
    TWILIO_CONVERSATION_CONFIGURATION_ID=conv_configuration_xxx
    TWILIO_VOICE_PUBLIC_DOMAIN=your-domain.ngrok.io

Installation:
    pip install twilio-agent-connect-google[conversational-agents,server] python-dotenv

Run:
    python conversational_agents.py
"""

import os

from dotenv import load_dotenv

from tac import TAC, TACConfig
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
)

server = TACFastAPIServer(
    tac=tac,
    voice_channel=connector.voice,
    messaging_channels=[connector.sms],
)

if __name__ == "__main__":
    server.start()
