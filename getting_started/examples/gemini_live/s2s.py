"""Example: Native speech-to-speech (S2S) voice channel with Vertex AI Gemini Live API.

Connects Twilio Media Streams directly to Google Cloud Vertex AI's Gemini Live API
(publishers/google/models/gemini-live-2.5-flash-native-audio via google-genai SDK).
Allows custom system instructions, tool execution, and voice customization.

Prerequisites:
    - Application Default Credentials with Vertex AI permissions:
      `gcloud auth application-default login`
    - .env file with Twilio & GCP variables below

Environment Variables:
    GOOGLE_CLOUD_PROJECT=your-project-id
    GOOGLE_CLOUD_LOCATION=us-central1
    TWILIO_ACCOUNT_SID=your_account_sid
    TWILIO_AUTH_TOKEN=your_auth_token
    TWILIO_VOICE_PUBLIC_DOMAIN=your-domain.ngrok.io

Run:
    python getting_started/examples/gemini_live/s2s.py
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from fastapi.responses import Response
from tac import TAC, TACConfig
from tac.server import FastAPIWebSocketAdapter

from tac_google.connectors import GeminiLiveConfig, GeminiLiveConnector

load_dotenv()

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "your-project-id")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

tac = TAC(config=TACConfig.from_env())


# Example async tool dispatcher
async def tool_dispatcher(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "lookup_order":
        order_id = args.get("order_id")
        return {"status": "shipped", "order_id": order_id, "estimated_arrival": "Tomorrow"}
    return {"error": f"Unknown tool: {name}"}


config = GeminiLiveConfig(
    project_id=PROJECT_ID,
    location=LOCATION,
    voice_name="Aoede",
    system_instruction=(
        "You are a friendly, concise AI voice assistant for customer care. "
        "Keep your spoken answers natural, clear, and brief."
    ),
    tools=[
        {
            "function_declarations": [
                {
                    "name": "lookup_order",
                    "description": "Look up shipping status of a customer's order",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "order_id": {"type": "STRING", "description": "The order ID"},
                        },
                        "required": ["order_id"],
                    },
                }
            ]
        }
    ],
    tool_dispatcher=tool_dispatcher,
)

connector = GeminiLiveConnector(tac=tac, config=config)

app = FastAPI()


@app.post("/voice/incoming")
async def voice_incoming() -> Response:
    twiml = await connector.channel.handle_incoming_call()
    return Response(content=twiml, media_type="application/xml")


@app.websocket("/ws/live")
async def websocket_media_stream(websocket: WebSocket) -> None:
    protocol = FastAPIWebSocketAdapter(websocket)
    await connector.channel.handle_media_stream(protocol)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
