"""Native speech-to-speech (S2S) voice channel for Vertex AI Gemini Live API.

Bridges raw call audio between Twilio Media Streams (8kHz µ-law) and
Gemini Live Native Audio (24kHz 16-bit linear PCM) via Vertex AI / google-genai SDK.
"""

from __future__ import annotations

import asyncio
import json
import traceback
from typing import Any

from google import genai
from google.genai import types
from tac.channels.base import BaseChannel
from tac.channels.websocket_protocol import WebSocketDisconnectError, WebSocketProtocol
from tac.core.logging import get_logger
from tac.core.tac import TAC
from twilio.twiml.voice_response import Connect, VoiceResponse

from tac_google.connectors.gemini_live.audio import (
    gemini_pcm_to_twilio_mulaw,
    twilio_mulaw_to_gemini_pcm,
)
from tac_google.connectors.gemini_live.config import GeminiLiveConfig

logger = get_logger(__name__)

_END_OF_CALL_MARK_NAME = "end_of_call"
_END_OF_CALL_MARK_TIMEOUT_S = 5


class GeminiLiveChannel(BaseChannel):
    """Native speech-to-speech voice channel connecting Twilio to Gemini Live API.

    Args:
        tac: TAC instance for conversation lifecycle management.
        config: GeminiLiveConfig instance or configuration dict.
    """

    def __init__(
        self,
        tac: TAC,
        config: GeminiLiveConfig | dict[str, Any],
    ) -> None:
        super().__init__(tac, memory_mode="never")

        if isinstance(config, dict):
            config = GeminiLiveConfig(**config)
        self.config = config
        self._project_id = config.project_id
        self._location = config.location

    def _get_genai_client(self) -> genai.Client:
        """Instantiate genai.Client configured for Vertex AI."""
        return genai.Client(
            vertexai=True,
            project=self._project_id,
            location=self._location,
        )

    def get_channel_name(self) -> str:
        """Return the channel identifier."""
        return "GEMINI_LIVE_S2S"

    async def handle_incoming_call(self, websocket_url: str | None = None) -> str:
        """Generate TwiML that connects the call to Twilio Media Streams.

        Args:
            websocket_url: Per-call override for the WebSocket URL.

        Returns:
            str: TwiML response XML string.
        """
        if websocket_url is not None:
            resolved_websocket_url = websocket_url
        elif getattr(self.tac.config, "voice_public_domain", None):
            resolved_websocket_url = (
                f"wss://{self.tac.config.voice_public_domain}{self.tac.config.voice_websocket_path}"
            )
        else:
            raise ValueError(
                "handle_incoming_call needs a WebSocket URL. Provide websocket_url or set "
                "TWILIO_VOICE_PUBLIC_DOMAIN."
            )

        response = VoiceResponse()
        connect = response.connect()
        connect.stream(url=resolved_websocket_url)
        return str(response)

    async def process_webhook(self, data: dict[str, Any]) -> None:
        """No-op; satisfies BaseChannel interface."""
        return

    async def send_response(self, conversation_id: str, text: str) -> None:
        """No-op; satisfies BaseChannel interface."""
        return

    async def handle_media_stream(self, websocket: WebSocketProtocol) -> None:
        """Main WebSocket loop bridging Twilio Media Streams and Gemini Live session."""
        await websocket.accept()

        conv_id: str | None = None
        stream_sid: str | None = None
        live_session: Any = None
        twilio_to_gemini_state: Any = None
        gemini_to_twilio_state: Any = None
        session_ready = asyncio.Event()
        playback_flushed = asyncio.Event()

        client = self._get_genai_client()

        live_config = types.LiveConnectConfig(
            response_modalities=[types.Modality.AUDIO],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=self.config.voice_name,
                    )
                )
            ),
        )

        if self.config.system_instruction:
            live_config.system_instruction = types.Content(
                parts=[types.Part.from_text(self.config.system_instruction)]
            )

        if self.config.tools:
            live_config.tools = self.config.tools

        async def forward_twilio_to_live(session: Any) -> None:
            nonlocal conv_id, stream_sid, twilio_to_gemini_state
            while True:
                data = await websocket.receive_json()
                event = data.get("event")

                if event == "start":
                    start = data.get("start") or {}
                    stream_sid = start.get("streamSid")
                    call_sid = start.get("callSid")
                    if not call_sid:
                        logger.warning("Media stream 'start' missing callSid", data=data)
                        continue

                    conv_id = call_sid
                    self._start_conversation(conv_id)
                    session_ready.set()

                    if self.config.welcome_greeting:
                        await session.send(
                            input=self.config.welcome_greeting,
                            end_of_turn=True,
                        )

                    logger.info(
                        "Gemini Live session initialized",
                        conversation_id=conv_id,
                        model=self.config.model,
                    )

                elif event == "media":
                    if not session_ready.is_set():
                        continue
                    payload = (data.get("media") or {}).get("payload")
                    if not payload:
                        continue

                    pcm_24k, twilio_to_gemini_state = twilio_mulaw_to_gemini_pcm(
                        payload,
                        twilio_to_gemini_state,
                    )

                    await session.send(
                        input=types.LiveClientRealtimeInput(
                            media_chunks=[
                                types.Blob(
                                    mime_type="audio/pcm;rate=24000",
                                    data=pcm_24k,
                                )
                            ]
                        )
                    )

                elif event == "stop":
                    logger.info("Twilio media stream stopped", conversation_id=conv_id)
                    return

                elif event == "mark":
                    if (data.get("mark") or {}).get("name") == _END_OF_CALL_MARK_NAME:
                        playback_flushed.set()

                else:
                    logger.debug("Ignoring media stream event", event=event)

        async def forward_live_to_twilio(session: Any) -> None:
            nonlocal gemini_to_twilio_state
            await session_ready.wait()

            async for response in session.receive():
                server_content = getattr(response, "server_content", None)
                if server_content:
                    if getattr(server_content, "interrupted", False):
                        # User interrupted the model (barge-in): flush Twilio's playback queue
                        if stream_sid:
                            await websocket.send_text(
                                json.dumps({"event": "clear", "streamSid": stream_sid})
                            )
                        continue

                    model_turn = getattr(server_content, "model_turn", None)
                    if model_turn:
                        parts = getattr(model_turn, "parts", []) or []
                        for part in parts:
                            inline_data = getattr(part, "inline_data", None)
                            if (
                                inline_data
                                and getattr(inline_data, "data", None)
                                and stream_sid
                            ):
                                pcm_chunk = inline_data.data
                                b64_payload, gemini_to_twilio_state = (
                                    gemini_pcm_to_twilio_mulaw(
                                        pcm_chunk, gemini_to_twilio_state
                                    )
                                )
                                await websocket.send_text(
                                    json.dumps(
                                        {
                                            "event": "media",
                                            "streamSid": stream_sid,
                                            "media": {"payload": b64_payload},
                                        }
                                    )
                                )

                # Handle tool/function calls if present
                tool_call = getattr(response, "tool_call", None)
                if tool_call and self.config.tool_dispatcher:
                    function_calls = getattr(tool_call, "function_calls", []) or []
                    function_responses = []
                    for call in function_calls:
                        name = getattr(call, "name", "")
                        args = getattr(call, "args", {}) or {}
                        call_id = getattr(call, "id", None)
                        try:
                            result = await self.config.tool_dispatcher(name, args)
                        except Exception as e:
                            logger.error("Tool execution failed", tool=name, error=str(e))
                            result = {"error": str(e)}

                        resp_item = {"name": name, "response": result}
                        if call_id:
                            resp_item["id"] = call_id
                        function_responses.append(resp_item)

                    if function_responses:
                        await session.send_tool_response(
                            function_responses=function_responses
                        )

        try:
            async with client.aio.live.connect(
                model=self.config.model,
                config=live_config,
            ) as session:
                live_session = session
                twilio_task = asyncio.create_task(forward_twilio_to_live(session))
                live_task = asyncio.create_task(forward_live_to_twilio(session))

                done, pending = await asyncio.wait(
                    {twilio_task, live_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)

                for task in done:
                    exc = task.exception()
                    if exc is not None and not isinstance(exc, WebSocketDisconnectError):
                        logger.error(
                            "GeminiLiveChannel task failed",
                            error=str(exc),
                            traceback=traceback.format_exc(),
                        )
        except WebSocketDisconnectError:
            logger.info("Twilio media stream disconnected normally", conversation_id=conv_id)
        except Exception as e:
            logger.error("Error in Gemini Live S2S media stream", error=str(e), traceback=traceback.format_exc())
        finally:
            if conv_id:
                await self._end_conversation(conv_id)
                await self.tac.trigger_conversation_ended(conv_id)
