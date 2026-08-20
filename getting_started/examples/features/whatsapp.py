"""Example: WhatsApp channel only.

This example shows how to:
1. Connect to an agent built in Conversational Agents (Dialogflow CX)
2. Enable WhatsApp as the connector's only messaging channel by passing
   `whatsapp_config` and leaving `sms_config`/`voice_config` unset

WhatsApp works exactly like any other messaging channel from the connector's
point of view — it's just opt-in via `whatsapp_config`. `connector.messaging`
picks it up automatically, so the server wiring below is identical to any
other example.

Prerequisites:
    - An agent built in Conversational Agents (Dialogflow CX)
    - A Twilio number enabled for WhatsApp (Twilio Sandbox or a registered
      WhatsApp sender), in `whatsapp:+1234567890` format
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
    TWILIO_WHATSAPP_NUMBER=whatsapp:+1234567890
    TWILIO_CONVERSATION_CONFIGURATION_ID=conv_configuration_xxx

Installation:
    pip install twilio-agent-connect-google[conversational-agents,server] python-dotenv

Run:
    python features/whatsapp.py
"""

import os

from dotenv import load_dotenv
from tac import TAC, TACConfig
from tac.channels.whatsapp import WhatsAppChannelConfig
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
    whatsapp_config=WhatsAppChannelConfig(memory_mode="once"),
)

server = TACFastAPIServer(
    tac=tac,
    messaging_channels=connector.messaging,
)

if __name__ == "__main__":
    server.start()
