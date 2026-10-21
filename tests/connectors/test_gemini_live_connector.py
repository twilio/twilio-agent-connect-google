"""Tests for GeminiLiveConnector and tool execution."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tac_google.connectors.gemini_live.config import GeminiLiveConfig
from tac_google.connectors.gemini_live.connector import GeminiLiveConnector
from tests.connectors.test_gemini_live_channel import (
    FakeLiveSession,
    FakeTwilioWebSocket,
    make_bare_channel,
)


@pytest.mark.asyncio
async def test_tool_dispatch_execution():
    called = {}

    async def sample_tool(name: str, args: dict):
        called["name"] = name
        called["args"] = args
        return {"status": "verified"}

    config = GeminiLiveConfig(
        project_id="test-p",
        tools=[{"name": "verify_order"}],
        tool_dispatcher=sample_tool,
    )
    channel = make_bare_channel(config)

    twilio_ws = FakeTwilioWebSocket(
        [
            {"event": "start", "start": {"streamSid": "MZ1", "callSid": "CA1"}},
            {"event": "stop"},
        ]
    )

    fake_tool_call_part = SimpleNamespace(
        name="verify_order",
        args={"order_id": "12345"},
        id="call-abc",
    )
    fake_tool_response = SimpleNamespace(
        server_content=None,
        tool_call=SimpleNamespace(function_calls=[fake_tool_call_part]),
    )

    fake_session = FakeLiveSession([fake_tool_response])

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

    assert called["name"] == "verify_order"
    assert called["args"] == {"order_id": "12345"}
    assert len(fake_session.sent_tool_responses) == 1
    assert fake_session.sent_tool_responses[0][0]["response"] == {"status": "verified"}
    assert fake_session.sent_tool_responses[0][0]["id"] == "call-abc"


def test_gemini_live_connector_init():
    mock_tac = SimpleNamespace(
        config=SimpleNamespace(voice_public_domain="example.com", voice_websocket_path="/ws/live"),
    )
    config = GeminiLiveConfig(project_id="test-p")
    connector = GeminiLiveConnector(tac=mock_tac, config=config)

    assert connector.channel is not None
    assert connector.voice_s2s is connector.channel
    assert connector.config == config
