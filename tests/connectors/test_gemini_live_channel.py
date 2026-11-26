"""Tests for GeminiLiveChannel."""

import base64
import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from tac.channels.websocket_protocol import WebSocketDisconnectError
from tac.core.logging import get_logger

from tac_google.connectors.gemini_live.channel import GeminiLiveChannel
from tac_google.connectors.gemini_live.config import GeminiLiveConfig


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


class FakeLiveSession:
    """Fake Vertex AI Live session for testing bidirectional streaming."""

    def __init__(self, incoming_responses: list[Any]) -> None:
        self._queue = list(incoming_responses)
        self.sent_inputs: list[Any] = []
        self.sent_tool_responses: list[Any] = []
        self.closed = False

    def receive(self):
        class _AsyncGen:
            def __init__(self, items):
                self._items = list(items)

            def __aiter__(self):
                return self

            async def __anext__(self):
                if not self._items:
                    raise StopAsyncIteration
                return self._items.pop(0)

        return _AsyncGen(self._queue)

    async def send(self, *, input=None, end_of_turn=False):
        self.sent_inputs.append({"input": input, "end_of_turn": end_of_turn})

    async def send_tool_response(self, *, function_responses=None):
        self.sent_tool_responses.append(function_responses)

    async def close(self):
        self.closed = True


def make_bare_channel(config: GeminiLiveConfig | None = None) -> GeminiLiveChannel:
    channel = GeminiLiveChannel.__new__(GeminiLiveChannel)
    channel.config = config or GeminiLiveConfig(project_id="test-p")
    channel._location = channel.config.location
    channel._project_id = channel.config.project_id
    channel._conversations = {}
    channel.logger = get_logger(GeminiLiveChannel.__module__)
    channel.tac = SimpleNamespace(trigger_conversation_ended=AsyncMock())
    return channel


def test_channel_twiml():
    channel = make_bare_channel()
    channel.tac = SimpleNamespace(
        config=SimpleNamespace(
            voice_public_domain="example.com",
            voice_websocket_path="/ws/live",
        )
    )
    import asyncio

    twiml = asyncio.run(channel.handle_incoming_call())
    assert "<Stream" in twiml
    assert 'url="wss://example.com/ws/live"' in twiml


@pytest.mark.asyncio
async def test_channel_barge_in_and_audio_flow():
    channel = make_bare_channel()

    # Twilio sends start, then media, then stop
    twilio_ws = FakeTwilioWebSocket(
        [
            {
                "event": "start",
                "start": {"streamSid": "MZ123", "callSid": "CA123"},
            },
            {
                "event": "media",
                "media": {"payload": base64.b64encode(b"\x00" * 160).decode("ascii")},
            },
            {"event": "stop"},
        ]
    )

    # Fake server content containing audio and an interruption signal
    fake_audio_part = SimpleNamespace(
        inline_data=SimpleNamespace(
            mime_type="audio/pcm;rate=24000",
            data=b"\x10\x00" * 240,
        )
    )
    fake_response_turn = SimpleNamespace(
        server_content=SimpleNamespace(
            model_turn=SimpleNamespace(parts=[fake_audio_part]),
            interrupted=False,
        ),
        tool_call=None,
    )
    fake_interrupt_turn = SimpleNamespace(
        server_content=SimpleNamespace(
            model_turn=None,
            interrupted=True,
        ),
        tool_call=None,
    )

    fake_session = FakeLiveSession([fake_response_turn, fake_interrupt_turn])

    class FakeClient:
        class aio:  # noqa: N801
            class live:  # noqa: N801
                @staticmethod
                def connect(*args, **kwargs):
                    class _Ctx:
                        async def __aenter__(self):
                            return fake_session

                        async def __aexit__(self, *args):
                            pass

                    return _Ctx()

    with patch.object(channel, "_get_genai_client", return_value=FakeClient()):
        await channel.handle_media_stream(twilio_ws)

    # Verify twilio accepted
    assert twilio_ws.accepted
    # Verify twilio sent media down to caller
    media_events = [e for e in twilio_ws.sent if e.get("event") == "media"]
    assert len(media_events) == 1
    assert media_events[0]["streamSid"] == "MZ123"

    # Verify clear event sent on interruption (barge-in)
    clear_events = [e for e in twilio_ws.sent if e.get("event") == "clear"]
    assert len(clear_events) == 1
    assert clear_events[0]["streamSid"] == "MZ123"
