"""
Chat Example for Twilio Agent Connect Google (Conversational Agents / Dialogflow CX)

Demonstrates ChatChannel with the Twilio Conversations JS SDK. Messages flow
through Twilio's infrastructure:

    Browser (Conversations JS SDK) -> Twilio Conversations ->
    Conversation Orchestrator -> webhook -> server -> Dialogflow CX ->
    Conversation Orchestrator Send API -> Twilio Conversations ->
    Browser (Conversations JS SDK)

See the "Chat Channel Example" section in ../../README.md for setup and
usage instructions.
"""

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from tac import TAC, TACConfig
from tac.channels.chat import ChatChannelConfig
from tac.server import TACFastAPIServer
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import ChatGrant

from tac_google.connectors import ConversationalAgentsConnector

load_dotenv()

CONVERSATIONAL_AGENT_ID = os.environ["CONVERSATIONAL_AGENT_ID"]
DIALOGFLOW_LANGUAGE_CODE = os.environ.get("DIALOGFLOW_LANGUAGE_CODE", "en")

tac = TAC(config=TACConfig.from_env())

# Example-level setup check (not required by the SDK): the V1 Chat backend
# needs a classic Conversations service — with Chat enabled on it — attached
# to the Conversation Orchestrator configuration.
configuration_id = os.environ["TWILIO_CONVERSATION_CONFIGURATION_ID"]
response = requests.get(
    f"https://conversations.twilio.com/v2/ControlPlane/Configurations/{configuration_id}",
    auth=(os.environ["TWILIO_API_KEY"], os.environ["TWILIO_API_SECRET"]),
)
response.raise_for_status()
if not (response.json().get("conversationsV1Bridge") or {}).get("serviceId"):
    sys.exit(
        f"Configuration '{configuration_id}' has no classic Conversations service attached. "
        "Attach one (with Chat enabled) via Console → Conversation Orchestrator → "
        'Conversation Configuration → Channel traffic → "+ Add messaging & chat traffic".'
    )

connector = ConversationalAgentsConnector(
    tac=tac,
    agent_id=CONVERSATIONAL_AGENT_ID,
    language_code=DIALOGFLOW_LANGUAGE_CODE,
    chat_config=ChatChannelConfig(memory_mode="once"),
)

if __name__ == "__main__":
    server = TACFastAPIServer(tac=tac, messaging_channels=[connector.chat])

    # Layer the chat UI routes onto the same FastAPI app TAC provides.
    static_dir = Path(__file__).parent / "public"
    server.app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @server.app.get("/")
    async def index() -> FileResponse:
        return FileResponse(str(static_dir / "index.html"))

    @server.app.post("/token")
    async def generate_token(request: Request) -> JSONResponse:
        """Generate a Conversations SDK access token."""
        body = await request.json()
        identity = body.get("identity")
        if not identity:
            return JSONResponse({"error": "Identity is required"}, status_code=400)

        account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        api_key = os.environ.get("TWILIO_API_KEY")
        api_secret = os.environ.get("TWILIO_API_SECRET")
        service_sid = os.environ.get("TWILIO_CONVERSATIONS_SERVICE_SID")
        if not all([account_sid, api_key, api_secret, service_sid]):
            return JSONResponse({"error": "Missing Twilio credentials"}, status_code=500)

        token = AccessToken(account_sid, api_key, api_secret, identity=identity, ttl=3600)
        token.add_grant(ChatGrant(service_sid=service_sid))
        jwt = token.to_jwt()
        if isinstance(jwt, bytes):
            jwt = jwt.decode("utf-8")
        return JSONResponse({"token": jwt})

    server.start()
