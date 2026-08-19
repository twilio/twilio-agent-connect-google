"""Tests for VoiceS2SChannel and CXAgentStudioFastAPIServer's voice dispatch."""

import base64
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from tac.channels.websocket_protocol import WebSocketDisconnectError
from tac.core.logging import get_logger

from tac_google.connectors.cx_agent_studio.server import CXAgentStudioFastAPIServer
from tac_google.connectors.cx_agent_studio.voice_s2s.channel import (
    VoiceS2SChannel,
    _extract_path_segment,
)
from tac_google.connectors.cx_agent_studio.voice_s2s.config import VoiceS2SConfig


def make_bare_channel(deployment_id: str | None = None) -> VoiceS2SChannel:
    """Builds a VoiceS2SChannel without __init__ (avoids google.auth.default())."""
    channel = VoiceS2SChannel.__new__(VoiceS2SChannel)
    channel.agent_id = "projects/p/locations/us/apps/a"
    channel.config = VoiceS2SConfig(deployment_id=deployment_id)
    channel.deployment_id = deployment_id
    channel._location = "us"
    channel._project_id = "p"
    channel._conversations = {}
    channel.logger = get_logger(VoiceS2SChannel.__module__)
    channel.tac = SimpleNamespace(trigger_conversation_ended=AsyncMock())
    channel._get_access_token = AsyncMock(return_value="test-token")  # type: ignore[method-assign]
    return channel


class FakeTwilioWebSocket:
    """Fake WebSocketProtocol driven by a scripted queue of inbound events."""

    def __init__(self, incoming_events: list[dict]) -> None:
        self._queue = list(incoming_events)
        self.sent: list[dict] = []
        self.accepted = False
        self.closed = False

    async def accept(self) -> None:
        self.accepted = True

    async def receive_json(self) -> dict:
        if not self._queue:
            raise WebSocketDisconnectError()
        return self._queue.pop(0)

    async def send_text(self, data: str) -> None:
        self.sent.append(json.loads(data))

    async def close(self) -> None:
        self.closed = True


class FakeCesWebSocket:
    """Fake CES BidiRunSession websocket: an async-iterable message queue."""

    def __init__(self, incoming_messages: list[dict]) -> None:
        self._queue = list(incoming_messages)
        self.sent: list[dict] = []
        self.closed = False

    def __aiter__(self) -> "FakeCesWebSocket":
        return self

    async def __anext__(self) -> str:
        if not self._queue:
            raise StopAsyncIteration
        return json.dumps(self._queue.pop(0))

    async def send(self, data: str) -> None:
        self.sent.append(json.loads(data))

    async def close(self) -> None:
        self.closed = True


def make_media_event(payload: bytes) -> dict:
    return {
        "event": "media",
        "media": {"payload": base64.b64encode(payload).decode()},
    }


def make_ces_audio_message(payload: bytes) -> dict:
    return {"sessionOutput": {"audio": base64.b64encode(payload).decode()}}


class TestExtractPathSegment:
    def test_extracts_value_after_segment(self):
        assert _extract_path_segment("projects/p/locations/us/apps/a", "locations") == "us"
        assert _extract_path_segment("projects/p/locations/us/apps/a", "projects") == "p"

    def test_missing_segment_returns_none(self):
        assert _extract_path_segment("projects/p/apps/a", "locations") is None

    def test_segment_as_last_element_returns_none(self):
        assert _extract_path_segment("projects/p/locations", "locations") is None


class TestConfigMessage:
    def test_without_deployment_id(self):
        channel = make_bare_channel()
        message = channel._config_message("projects/p/locations/us/apps/a/sessions/s1")
        assert message == {
            "config": {
                "session": "projects/p/locations/us/apps/a/sessions/s1",
                "inputAudioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 16000},
                "outputAudioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 48000},
            }
        }

    def test_with_deployment_id_includes_deployment(self):
        channel = make_bare_channel(deployment_id="deployments/d1")
        message = channel._config_message("projects/p/locations/us/apps/a/sessions/s1")
        assert message["config"]["deployment"] == "deployments/d1"


class TestGetChannelName:
    def test_returns_voice_s2s(self):
        assert make_bare_channel().get_channel_name() == "VOICE_S2S"


class TestHandleIncomingCall:
    @pytest.mark.asyncio
    async def test_explicit_websocket_url_takes_precedence(self):
        channel = make_bare_channel()
        channel.tac = SimpleNamespace(config=SimpleNamespace(voice_public_domain="ignored.example"))
        twiml = await channel.handle_incoming_call(websocket_url="wss://override.example/ws")
        assert "wss://override.example/ws" in twiml
        assert "<Connect>" in twiml

    @pytest.mark.asyncio
    async def test_falls_back_to_configured_public_domain(self):
        channel = make_bare_channel()
        channel.tac = SimpleNamespace(
            config=SimpleNamespace(voice_public_domain="my.example", voice_websocket_path="/ws")
        )
        twiml = await channel.handle_incoming_call()
        assert "wss://my.example/ws" in twiml

    @pytest.mark.asyncio
    async def test_no_url_and_no_public_domain_raises(self):
        channel = make_bare_channel()
        channel.tac = SimpleNamespace(config=SimpleNamespace(voice_public_domain=None))
        with pytest.raises(ValueError, match="WebSocket URL"):
            await channel.handle_incoming_call()


class TestNoOpChannelMethods:
    @pytest.mark.asyncio
    async def test_process_webhook_is_a_noop(self):
        channel = make_bare_channel()
        assert await channel.process_webhook({"any": "data"}) is None

    @pytest.mark.asyncio
    async def test_send_response_raises_not_implemented(self):
        channel = make_bare_channel()
        with pytest.raises(NotImplementedError):
            await channel.send_response("conv-1", "reply")


class TestHandleWebsocket:
    """Exercises the Twilio<->CES media bridge in `handle_websocket`."""

    @pytest.mark.asyncio
    async def test_bidirectional_media_and_graceful_hangup(self):
        channel = make_bare_channel()
        twilio_ws = FakeTwilioWebSocket(
            [
                {"event": "start", "start": {"callSid": "CA1", "streamSid": "MZ1"}},
                make_media_event(b"\xff" * 160),  # caller audio (mulaw silence)
                {"event": "mark", "mark": {"name": "end_of_call"}},
                {"event": "stop"},
            ]
        )
        ces_ws = FakeCesWebSocket(
            [
                make_ces_audio_message(b"\x00\x00" * 480),  # agent audio (linear16 silence)
                {"endSession": {}},
            ]
        )

        with patch("websockets.connect", AsyncMock(return_value=ces_ws)):
            await channel.handle_websocket(twilio_ws)

        assert twilio_ws.accepted
        assert twilio_ws.closed
        assert ces_ws.closed
        channel.tac.trigger_conversation_ended.assert_awaited_once()

        # Caller audio was resampled and forwarded to CES as realtimeInput.
        caller_audio_messages = [
            m for m in ces_ws.sent if "realtimeInput" in m and "audio" in m["realtimeInput"]
        ]
        assert len(caller_audio_messages) == 1

        # Agent audio came back as a Twilio "media" event.
        media_events = [m for m in twilio_ws.sent if m.get("event") == "media"]
        assert len(media_events) == 1
        assert media_events[0]["streamSid"] == "MZ1"

        # A "mark" was sent to Twilio before hanging up on endSession.
        mark_events = [m for m in twilio_ws.sent if m.get("event") == "mark"]
        assert len(mark_events) == 1
        assert mark_events[0]["mark"]["name"] == "end_of_call"

    @pytest.mark.asyncio
    async def test_barge_in_clears_twilio_buffered_audio(self):
        channel = make_bare_channel()
        twilio_ws = FakeTwilioWebSocket(
            [
                {"event": "start", "start": {"callSid": "CA1", "streamSid": "MZ1"}},
                {"event": "stop"},
            ]
        )
        ces_ws = FakeCesWebSocket([{"interruptionSignal": {}}])

        with patch("websockets.connect", AsyncMock(return_value=ces_ws)):
            await channel.handle_websocket(twilio_ws)

        clear_events = [m for m in twilio_ws.sent if m.get("event") == "clear"]
        assert clear_events == [{"event": "clear", "streamSid": "MZ1"}]

    @pytest.mark.asyncio
    async def test_endsession_mark_ack_timeout_still_hangs_up(self):
        """If Twilio never echoes the mark back, the timeout fires and the
        call still ends instead of hanging forever."""
        channel = make_bare_channel()
        twilio_ws = FakeTwilioWebSocket(
            [{"event": "start", "start": {"callSid": "CA1", "streamSid": "MZ1"}}]
        )
        ces_ws = FakeCesWebSocket([{"endSession": {}}])

        with (
            patch("websockets.connect", AsyncMock(return_value=ces_ws)),
            patch(
                "tac_google.connectors.cx_agent_studio.voice_s2s.channel._END_OF_CALL_MARK_TIMEOUT_S",
                0.05,
            ),
        ):
            await channel.handle_websocket(twilio_ws)

        assert ces_ws.closed
        assert twilio_ws.closed

    @pytest.mark.asyncio
    async def test_twilio_disconnect_before_start_cleans_up_without_conversation(self):
        channel = make_bare_channel()
        twilio_ws = FakeTwilioWebSocket([])  # disconnects immediately

        await channel.handle_websocket(twilio_ws)

        assert twilio_ws.accepted
        assert twilio_ws.closed
        channel.tac.trigger_conversation_ended.assert_not_awaited()


class TestCXAgentStudioFastAPIServerVoiceDispatch:
    """Only the isinstance dispatch in __init__ is exercised here — building a
    real TACFastAPIServer/FastAPI app is out of scope for this smoke test."""

    def test_rejects_voice_channel_of_wrong_type(self):
        with pytest.raises(TypeError, match="VoiceChannel"):
            CXAgentStudioFastAPIServer(tac=Mock(), voice_channel="not-a-channel")

    def test_voice_s2s_channel_is_stored_and_not_passed_to_super(self, monkeypatch):
        captured = {}

        def fake_super_init(self, *, tac, voice_channel, messaging_channels, config, app):
            captured["voice_channel"] = voice_channel

        monkeypatch.setattr("tac.server.fastapi_server.TACFastAPIServer.__init__", fake_super_init)
        s2s_channel = make_bare_channel()
        server = CXAgentStudioFastAPIServer(tac=Mock(), voice_channel=s2s_channel)

        assert server.voice_s2s_channel is s2s_channel
        assert captured["voice_channel"] is None

    def test_none_entries_in_messaging_channels_are_dropped(self, monkeypatch):
        captured = {}

        def fake_super_init(self, *, tac, voice_channel, messaging_channels, config, app):
            captured["messaging_channels"] = messaging_channels

        monkeypatch.setattr("tac.server.fastapi_server.TACFastAPIServer.__init__", fake_super_init)
        real_channel = Mock()
        CXAgentStudioFastAPIServer(tac=Mock(), messaging_channels=[real_channel, None])

        assert captured["messaging_channels"] == [real_channel]

    def test_messaging_channels_none_passes_through_unchanged(self, monkeypatch):
        captured = {}

        def fake_super_init(self, *, tac, voice_channel, messaging_channels, config, app):
            captured["messaging_channels"] = messaging_channels

        monkeypatch.setattr("tac.server.fastapi_server.TACFastAPIServer.__init__", fake_super_init)
        CXAgentStudioFastAPIServer(tac=Mock(), messaging_channels=None)

        assert captured["messaging_channels"] is None
