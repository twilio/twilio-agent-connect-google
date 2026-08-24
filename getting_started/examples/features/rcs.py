"""Example: RCS channel only.

Sets TWILIO_RCS_SENDER_ID to enable `connector.rcs`, then wires only that
channel to the server (the connector also builds SMS/Voice/Chat, they're
just not passed in).

Prerequisites:
    - An agent built in Conversational Agents (Dialogflow CX)
    - A Twilio RCS sender configured for your account
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
    TWILIO_RCS_SENDER_ID=rcs_sender_xxxxxxxxxxxxxxxxxx
    TWILIO_CONVERSATION_CONFIGURATION_ID=conv_configuration_xxx

Installation:
    pip install twilio-agent-connect-google[conversational-agents,server] python-dotenv

Run:
    python features/rcs.py
"""

import os

from dotenv import load_dotenv
from tac import TAC, TACConfig
from tac.channels.rcs import RCSChannelConfig
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
    rcs_config=RCSChannelConfig(memory_mode="once"),
)

server = TACFastAPIServer(
    tac=tac,
    messaging_channels=[c for c in [connector.rcs] if c is not None],
)

if __name__ == "__main__":
    server.start()
