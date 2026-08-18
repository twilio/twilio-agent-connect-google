"""Tests for VoiceS2SChannel and CXAgentStudioFastAPIServer's voice dispatch."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

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
    return channel


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
