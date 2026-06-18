"""
Example: Connect Dialogflow CX Playbook Agent to Twilio Agent Connect

This example demonstrates how to connect a Dialogflow CX agent (including
playbook-based generative agents) to Twilio's voice and SMS channels.

Prerequisites:
- Dialogflow CX agent created with playbooks
- GCP authentication configured (ADC or service account)
- Twilio account with configured phone number
- Environment variables set in .env file

Setup:
1. Create a Dialogflow CX agent with playbooks in GCP Console
2. Copy .env.example to .env and configure:
   - GOOGLE_CLOUD_PROJECT
   - GOOGLE_CLOUD_LOCATION
   - DIALOGFLOW_CX_AGENT_ID
   - Twilio credentials
3. Run: python dialogflow_cx_playbook.py
4. Expose with ngrok: ngrok http 8000
5. Configure Twilio webhooks to point to your ngrok URL
"""

import os

from dotenv import load_dotenv
from google.api_core.client_options import ClientOptions
from google.cloud.dialogflowcx_v3 import SessionsClient
from tac import TAC, TACConfig
from tac.server import TACFastAPIServer
from tac_google.connectors import DialogflowCXConnector

load_dotenv()


def main():
    tac = TAC(config=TACConfig.from_env())

    project_id = os.environ["GOOGLE_CLOUD_PROJECT"]
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    agent_id = os.environ["DIALOGFLOW_CX_AGENT_ID"]

    agent = f"projects/{project_id}/locations/{location}/agents/{agent_id}"

    print(f"Connecting to Dialogflow CX:\n  {agent}\n")

    api_endpoint = f"{location}-dialogflow.googleapis.com:443"
    client = SessionsClient(client_options=ClientOptions(api_endpoint=api_endpoint))

    connector = DialogflowCXConnector(
        tac=tac,
        client=client,
        agent=agent,
    )

    server = TACFastAPIServer(
        tac=tac,
        voice_channel=connector.voice,
        messaging_channels=[connector.sms],
    )

    print("Starting TAC server...")
    print("  Voice: http://localhost:8000/voice")
    print("  SMS: http://localhost:8000/sms\n")

    server.start()


if __name__ == "__main__":
    main()
