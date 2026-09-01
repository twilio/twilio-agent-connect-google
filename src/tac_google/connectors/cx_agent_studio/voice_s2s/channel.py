"""Native speech-to-speech (S2S) voice channel for CX Agent Studio (CES).

Bridges raw call audio between Twilio Media Streams and CES's
`BidiRunSession`. CES does its own speech recognition/synthesis, and audio
flows continuously with no discrete text turns — unlike `VoiceChannel`
(Twilio ConversationRelay), where Twilio does the STT/TTS.

Since there's no discrete turn, TAC's turn callbacks don't apply here;
`process_webhook`/`send_response` are no-ops just to satisfy `BaseChannel`'s
abstract interface.

Supports neither Conversation Orchestrator nor Conversation Memory for voice,
unlike `VoiceChannel` which supports both.
"""

from __future__ import annotations

import asyncio
import audioop
import base64
import json
import traceback
from typing import Any

import google.auth
from google.auth.transport.requests import Request as GoogleAuthRequest
from tac.channels.base import BaseChannel
from tac.channels.websocket_protocol import WebSocketDisconnectError, WebSocketProtocol
from tac.core.logging import get_logger
from tac.core.tac import TAC
from twilio.twiml.voice_response import VoiceResponse

from tac_google.connectors.cx_agent_studio.voice_s2s.config import VoiceS2SConfig

logger = get_logger(__name__)

_CES_WSS_HOST = "ces.googleapis.com"

# CES accepts MULAW directly too, but that produced garbled audio and
# sluggish barge-in in testing. LINEAR16 works; rates confirmed empirically
# against a captured live-call sample.
_AGENT_AUDIO_ENCODING = "LINEAR16"
_AGENT_INPUT_SAMPLE_RATE = 16000
_AGENT_OUTPUT_SAMPLE_RATE = 48000
_TWILIO_AUDIO_SAMPLE_RATE = 8000

# Twilio buffers/plays outbound media asynchronously, so closing the stream
# right after sending the last chunk can cut it off. This <Connect>-scoped
# mark name lets us wait for Twilio's playback-complete echo before hanging
# up on endSession.
_END_OF_CALL_MARK_NAME = "end_of_call"
_END_OF_CALL_MARK_TIMEOUT_S = 5


def _extract_path_segment(resource_name: str, segment: str) -> str | None:
    """Extract the value following `segment` in a slash-delimited resource name."""
    parts = resource_name.split("/")
    try:
        idx = parts.index(segment)
    except ValueError:
        return None
    return parts[idx + 1] if idx + 1 < len(parts) else None


class VoiceS2SChannel(BaseChannel):
    """
    Native speech-to-speech voice channel for a CX Agent Studio (CES) agent.

    Args:
        tac: TAC instance (used only for conversation lifecycle bookkeeping —
            see module docstring).
        agent_id: The CES agent (app) resource name, e.g.
            `projects/<project>/locations/<location>/apps/<app-id>`.
        config: Voice S2S channel configuration (VoiceS2SConfig or dict).
            If None, uses default configuration (no deployment_id).
    """

    def __init__(
        self,
        tac: TAC,
        agent_id: str,
        config: VoiceS2SConfig | dict[str, Any] | None = None,
    ) -> None:
        super().__init__(tac, memory_mode="never")

        if isinstance(config, dict):
            config = VoiceS2SConfig(**config)
        elif config is None:
            config = VoiceS2SConfig()
        self.config = config

        self.agent_id = agent_id.rstrip("/")
        self.deployment_id = config.deployment_id

        self._location = _extract_path_segment(self.agent_id, "locations") or "us"
        self._project_id = _extract_path_segment(self.agent_id, "projects")

        self._credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )

        logger.debug(
            "VoiceS2SChannel initialized",
            agent_id=self.agent_id,
            deployment_id=self.deployment_id,
        )

    def get_channel_name(self) -> str:
        return "VOICE_S2S"

    async def handle_incoming_call(self, websocket_url: str | None = None) -> str:
        """Generate TwiML that connects the call to Twilio Media Streams.

        Unlike ConversationRelay, this carries raw audio — CES does its own
        speech recognition/synthesis over `BidiRunSession`.

        TODO: only `websocket_url` is configurable right now. We'll likely
        want to expose more `<Stream>`/`<Connect>` TwiML options later (e.g.
        `name`, `status_callback`, custom `<Parameter>`s) — see
        `VoiceChannel`'s layered `TwiMLOptions` for the pattern to follow.

        Args:
            websocket_url: Per-call override for the WebSocket URL, supplied
                by the *host* (the code owning the route — e.g. a custom
                server) for transport facts this channel can't derive, such
                as a per-call affinity token. Takes precedence over the
                `TACConfig.voice_public_domain`-derived default.
        """
        if websocket_url is not None:
            resolved_websocket_url = websocket_url
        elif self.tac.config.voice_public_domain:
            resolved_websocket_url = (
                f"wss://{self.tac.config.voice_public_domain}{self.tac.config.voice_websocket_path}"
            )
        else:
            raise ValueError(
                "handle_incoming_call needs a WebSocket URL. Set TWILIO_VOICE_PUBLIC_DOMAIN "
                "(or TACConfig.voice_public_domain)."
            )

        response = VoiceResponse()
        connect = response.connect()
        connect.stream(url=resolved_websocket_url)
        return str(response)

    def _config_message(self, session: str) -> dict[str, Any]:
        config: dict[str, Any] = {
            "session": session,
            "inputAudioConfig": {
                "audioEncoding": _AGENT_AUDIO_ENCODING,
                "sampleRateHertz": _AGENT_INPUT_SAMPLE_RATE,
            },
            "outputAudioConfig": {
                "audioEncoding": _AGENT_AUDIO_ENCODING,
                "sampleRateHertz": _AGENT_OUTPUT_SAMPLE_RATE,
            },
        }
        if self.deployment_id:
            config["deployment"] = self.deployment_id
        return {"config": config}

    async def _get_access_token(self) -> str:
        """Return a valid access token, refreshing only if the cached one has expired.

        No lock needed: concurrent calls share ``self._credentials``, and a
        redundant refresh from two calls racing at expiry is harmless.
        """

        def refresh() -> str:
            if not self._credentials.valid:
                self._credentials.refresh(GoogleAuthRequest())
            token = self._credentials.token
            if token is None:
                raise RuntimeError("Google credentials refreshed but no access token was set.")
            return str(token)

        return await asyncio.to_thread(refresh)

    async def handle_websocket(self, websocket: WebSocketProtocol) -> None:
        """Bridge one call's Twilio Media Streams connection to a CES
        `BidiRunSession` websocket for the lifetime of the call.

        Opens the CES connection once Twilio's `start` event arrives (the
        CES session id is derived from the Twilio call sid), then runs
        Twilio→CES and CES→Twilio concurrently until either side ends the
        call — the first to finish cancels the other.
        """
        await websocket.accept()
        logger.debug("Media stream WebSocket accepted")

        conv_id: str | None = None
        stream_sid: str | None = None
        ces_ws: Any = None
        twilio_to_ces_state: Any = None
        ces_to_twilio_state: Any = None
        ces_ready = asyncio.Event()
        playback_flushed = asyncio.Event()

        async def forward_twilio_to_ces() -> None:
            nonlocal conv_id, stream_sid, ces_ws, twilio_to_ces_state
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

                    token = await self._get_access_token()
                    headers = {"Authorization": f"Bearer {token}"}
                    if self._project_id:
                        headers["X-Goog-User-Project"] = self._project_id

                    import websockets

                    session = f"{self.agent_id}/sessions/{call_sid}"
                    bidi_run_session_url = (
                        f"wss://{_CES_WSS_HOST}/ws/google.cloud.ces.v1.SessionService/"
                        f"BidiRunSession/locations/{self._location}"
                    )
                    ces_ws = await websockets.connect(
                        bidi_run_session_url,
                        max_size=2**22,
                        additional_headers=headers,
                    )
                    await ces_ws.send(json.dumps(self._config_message(session)))
                    # Without a kickstart, the agent stays silent until the caller speaks.
                    kickstart_message: dict[str, Any]
                    if self.config.welcome_greeting:
                        kickstart_message = {
                            "realtimeInput": {"text": self.config.welcome_greeting}
                        }
                    else:
                        kickstart_message = {"realtimeInput": {"event": {"event": "session_start"}}}
                    await ces_ws.send(json.dumps(kickstart_message))
                    ces_ready.set()
                    logger.info(
                        "CES BidiRunSession connected",
                        conversation_id=conv_id,
                        session=session,
                    )

                elif event == "media":
                    if ces_ws is None:
                        continue
                    payload = (data.get("media") or {}).get("payload")
                    if not payload:
                        continue
                    mulaw_audio = base64.b64decode(payload)
                    linear_audio = audioop.ulaw2lin(mulaw_audio, 2)
                    resampled, twilio_to_ces_state = audioop.ratecv(
                        linear_audio,
                        2,
                        1,
                        _TWILIO_AUDIO_SAMPLE_RATE,
                        _AGENT_INPUT_SAMPLE_RATE,
                        twilio_to_ces_state,
                    )
                    await ces_ws.send(
                        json.dumps(
                            {"realtimeInput": {"audio": base64.b64encode(resampled).decode()}}
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

        async def forward_ces_to_twilio() -> None:
            nonlocal ces_to_twilio_state
            await ces_ready.wait()
            async for message in ces_ws:
                data = json.loads(message)

                if "endSession" in data:
                    logger.info("CES ended the S2S session", conversation_id=conv_id)
                    if stream_sid:
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "event": "mark",
                                    "streamSid": stream_sid,
                                    "mark": {"name": _END_OF_CALL_MARK_NAME},
                                }
                            )
                        )
                        try:
                            await asyncio.wait_for(
                                playback_flushed.wait(), timeout=_END_OF_CALL_MARK_TIMEOUT_S
                            )
                        except asyncio.TimeoutError:
                            logger.warning(
                                "Timed out waiting for Twilio to confirm playback before "
                                "hanging up",
                                conversation_id=conv_id,
                            )
                    return

                if "interruptionSignal" in data:
                    # Barge-in: flush Twilio's buffered agent audio.
                    if stream_sid:
                        await websocket.send_text(
                            json.dumps({"event": "clear", "streamSid": stream_sid})
                        )
                    continue

                session_output = data.get("sessionOutput") or {}
                audio_b64 = session_output.get("audio")
                if not audio_b64 or not stream_sid:
                    continue

                agent_audio = base64.b64decode(audio_b64)
                resampled, ces_to_twilio_state = audioop.ratecv(
                    agent_audio,
                    2,
                    1,
                    _AGENT_OUTPUT_SAMPLE_RATE,
                    _TWILIO_AUDIO_SAMPLE_RATE,
                    ces_to_twilio_state,
                )
                mulaw_audio = audioop.lin2ulaw(resampled, 2)
                await websocket.send_text(
                    json.dumps(
                        {
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {"payload": base64.b64encode(mulaw_audio).decode()},
                        }
                    )
                )

        try:
            twilio_task = asyncio.create_task(forward_twilio_to_ces())
            ces_task = asyncio.create_task(forward_ces_to_twilio())
            done, pending = await asyncio.wait(
                {twilio_task, ces_task}, return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            for task in done:
                exc = task.exception()
                if exc is not None:
                    logger.error(
                        "VoiceS2SChannel task failed",
                        error=str(exc),
                        traceback="".join(
                            traceback.format_exception(type(exc), exc, exc.__traceback__)
                        ),
                    )
        except WebSocketDisconnectError:
            logger.info("Media stream WebSocket disconnected", conversation_id=conv_id)
        finally:
            if ces_ws is not None:
                await ces_ws.close()
            try:
                await websocket.close()
            except Exception:
                pass
            if conv_id:
                await self._end_conversation(conv_id)

    async def process_webhook(
        self, webhook_data: dict[str, Any], idempotency_token: str | None = None
    ) -> None:
        """Not used — S2S has no Conversation Orchestrator text-turn webhook."""
        logger.debug("process_webhook is a no-op for VoiceS2SChannel", data=webhook_data)

    async def send_response(
        self,
        conversation_id: str,
        response: Any,
        role: str | None = None,
    ) -> None:
        """Not used — audio is forwarded directly inside `handle_websocket`,
        there's no discrete turn to push a response for."""
        raise NotImplementedError(
            "VoiceS2SChannel exchanges audio directly over the media-stream "
            "websocket; send_response is not used."
        )
