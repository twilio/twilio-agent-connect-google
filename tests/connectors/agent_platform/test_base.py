"""Tests for AgentEngineConnectorBase shared plumbing."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from tac_google.connectors.agent_platform._base import AgentEngineConnectorBase


def make_bare_base() -> AgentEngineConnectorBase:
    """Builds an AgentEngineConnectorBase without the TAC/channel wiring in __init__."""
    base = AgentEngineConnectorBase.__new__(AgentEngineConnectorBase)
    base._last_injected_memory = {}
    base._agent_engine_http = Mock()
    return base


def make_tac_for_channels() -> Mock:
    """A Mock TAC whose config reports no RCS/WhatsApp resource configured —
    plain Mock() attribute access is truthy, which would otherwise make
    tac.config.rcs_sender_id/whatsapp_number look "configured" by accident.
    """
    tac = Mock()
    tac.config = Mock(rcs_sender_id=None, whatsapp_number=None)
    return tac


class TestChannelConstruction:
    def test_sms_voice_chat_always_built(self):
        with (
            patch("tac_google.connectors.agent_platform._base.google.auth.default") as mock_auth,
            patch("tac_google.connectors.agent_platform._base.AuthorizedSession"),
            patch("tac_google.connectors.agent_platform._base.VoiceChannel") as mock_voice_channel,
            patch("tac_google.connectors._channels.SMSChannel") as mock_sms_channel,
            patch("tac_google.connectors._channels.ChatChannel") as mock_chat_channel,
        ):
            mock_auth.return_value = (Mock(), None)
            base = AgentEngineConnectorBase(tac=make_tac_for_channels())

        assert base.voice is mock_voice_channel.return_value
        assert base.sms is mock_sms_channel.return_value
        assert base.chat is mock_chat_channel.return_value

    def test_rcs_and_whatsapp_none_when_resource_not_configured(self):
        with (
            patch("tac_google.connectors.agent_platform._base.google.auth.default") as mock_auth,
            patch("tac_google.connectors.agent_platform._base.AuthorizedSession"),
            patch("tac_google.connectors._channels.RCSChannel") as mock_rcs_channel,
            patch("tac_google.connectors._channels.WhatsAppChannel") as mock_whatsapp_channel,
        ):
            mock_auth.return_value = (Mock(), None)
            base = AgentEngineConnectorBase(tac=make_tac_for_channels())

        assert base.rcs is None
        assert base.whatsapp is None
        mock_rcs_channel.assert_not_called()
        mock_whatsapp_channel.assert_not_called()

    def test_rcs_built_when_rcs_sender_id_configured(self):
        with (
            patch("tac_google.connectors.agent_platform._base.google.auth.default") as mock_auth,
            patch("tac_google.connectors.agent_platform._base.AuthorizedSession"),
            patch("tac_google.connectors._channels.RCSChannel") as mock_rcs_channel,
        ):
            mock_auth.return_value = (Mock(), None)
            tac = make_tac_for_channels()
            tac.config.rcs_sender_id = "rcs_sender_123"
            base = AgentEngineConnectorBase(tac=tac)

        assert base.rcs is mock_rcs_channel.return_value
        mock_rcs_channel.assert_called_once_with(tac=tac, config=None)

    def test_whatsapp_built_when_whatsapp_number_configured(self):
        with (
            patch("tac_google.connectors.agent_platform._base.google.auth.default") as mock_auth,
            patch("tac_google.connectors.agent_platform._base.AuthorizedSession"),
            patch("tac_google.connectors._channels.WhatsAppChannel") as mock_whatsapp_channel,
        ):
            mock_auth.return_value = (Mock(), None)
            tac = make_tac_for_channels()
            tac.config.whatsapp_number = "whatsapp:+15550001234"
            base = AgentEngineConnectorBase(tac=tac)

        assert base.whatsapp is mock_whatsapp_channel.return_value
        mock_whatsapp_channel.assert_called_once_with(tac=tac, config=None)


class TestSanitizeSessionId:
    def test_replaces_underscores_with_hyphens(self):
        assert (
            AgentEngineConnectorBase._sanitize_session_id("conv_conversation_abc123")
            == "conv-conversation-abc123"
        )

    def test_lowercases(self):
        assert AgentEngineConnectorBase._sanitize_session_id("Conv_ABC") == "conv-abc"

    def test_strips_leading_and_trailing_hyphens(self):
        assert AgentEngineConnectorBase._sanitize_session_id("_conv_123_") == "conv-123"


class TestTagMessage:
    def test_wraps_memory_and_message_in_tags(self):
        tagged = AgentEngineConnectorBase._tag_message("hello", "some memory")
        assert (
            tagged == "<MEMORY>\nsome memory\n</MEMORY>\n\n<USER_MESSAGE>\nhello\n</USER_MESSAGE>"
        )


class TestMaybeTagMessage:
    def _context(self, conv_id: str = "conv-1") -> SimpleNamespace:
        return SimpleNamespace(conversation_id=conv_id, profile_id="user-1")

    def test_no_memory_response_returns_message_unchanged(self):
        base = make_bare_base()
        message, memory_to_commit = base._maybe_tag_message("hello", self._context(), None)
        assert message == "hello"
        assert memory_to_commit is None

    def test_empty_memory_context_returns_message_unchanged(self):
        base = make_bare_base()
        with patch(
            "tac_google.connectors.agent_platform._base.MemoryPromptBuilder.build",
            return_value=None,
        ):
            message, memory_to_commit = base._maybe_tag_message("hello", self._context(), Mock())
        assert message == "hello"
        assert memory_to_commit is None

    def test_first_turn_tags_memory(self):
        base = make_bare_base()
        with patch(
            "tac_google.connectors.agent_platform._base.MemoryPromptBuilder.build",
            return_value="user likes pizza",
        ):
            message, memory_to_commit = base._maybe_tag_message("hello", self._context(), Mock())
        assert "user likes pizza" in message
        assert "hello" in message
        assert memory_to_commit == "user likes pizza"

    def test_unchanged_memory_is_not_retagged(self):
        """memory_mode="once" returns the same cached memory every turn — this
        must not be re-tagged, or ADK/Studio's session replay accumulates a
        duplicate copy on every turn."""
        base = make_bare_base()
        context = self._context()
        base._last_injected_memory[context.conversation_id] = "user likes pizza"
        with patch(
            "tac_google.connectors.agent_platform._base.MemoryPromptBuilder.build",
            return_value="user likes pizza",
        ):
            message, memory_to_commit = base._maybe_tag_message("turn 2", context, Mock())
        assert message == "turn 2"
        assert memory_to_commit is None

    def test_changed_memory_is_retagged(self):
        """memory_mode="always" re-queries per turn and typically returns
        different content — that must still get tagged every time."""
        base = make_bare_base()
        context = self._context()
        base._last_injected_memory[context.conversation_id] = "memory v1"
        with patch(
            "tac_google.connectors.agent_platform._base.MemoryPromptBuilder.build",
            return_value="memory v2",
        ):
            message, memory_to_commit = base._maybe_tag_message("turn 2", context, Mock())
        assert "memory v2" in message
        assert "turn 2" in message
        assert memory_to_commit == "memory v2"

    def test_conversation_ended_clears_tracked_memory(self):
        base = make_bare_base()
        context = self._context()
        base._last_injected_memory[context.conversation_id] = "user likes pizza"
        base._handle_conversation_ended(context)
        with patch(
            "tac_google.connectors.agent_platform._base.MemoryPromptBuilder.build",
            return_value="user likes pizza",
        ):
            # After the conversation ends, the same memory content is tagged
            # again on a subsequent (new) conversation reusing the same content.
            message, memory_to_commit = base._maybe_tag_message("turn 2", context, Mock())
        assert "user likes pizza" in message
        assert memory_to_commit == "user likes pizza"


class TestAgentEngineBaseUrl:
    def test_builds_url_from_resource_name(self):
        agent = Mock()
        agent.api_resource.name = "projects/my-proj/locations/us-central1/reasoningEngines/123"
        url = AgentEngineConnectorBase._agent_engine_base_url(agent)
        assert url == (
            "https://us-central1-aiplatform.googleapis.com/v1/"
            "projects/my-proj/locations/us-central1/reasoningEngines/123"
        )

    def test_raises_when_api_resource_missing(self):
        agent = Mock()
        agent.api_resource = None
        with pytest.raises(ValueError):
            AgentEngineConnectorBase._agent_engine_base_url(agent)

    def test_raises_when_resource_name_missing(self):
        agent = Mock()
        agent.api_resource.name = None
        with pytest.raises(ValueError):
            AgentEngineConnectorBase._agent_engine_base_url(agent)


class TestCreateSession:
    @pytest.mark.asyncio
    async def test_success_calls_raise_for_status_which_is_a_noop_for_2xx(self):
        base = make_bare_base()
        base._agent_engine_http.post.return_value = Mock(status_code=200)
        await base._create_session("https://example/sessions", "sess-1", "user-1")
        base._agent_engine_http.post.return_value.raise_for_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_already_exists_is_tolerated(self):
        """The Sessions REST API returns a plain 400 (not 409) with a specific
        "already exists" message for a duplicate session_id — confirmed
        empirically against a deployed agent."""
        base = make_bare_base()
        response = Mock(status_code=400)
        response.text = "Session with user-provided ID 'foo/sessions/sess-1' already exists."
        base._agent_engine_http.post.return_value = response
        await base._create_session("https://example/sessions", "sess-1", "user-1")
        response.raise_for_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_other_400_is_raised(self):
        """A 400 for a different reason (e.g. invalid session_id format) must
        still surface — only the specific already-exists message is
        swallowed."""
        base = make_bare_base()
        response = Mock(status_code=400)
        response.text = "session_id can only contain lowercase letters, digits and hyphens."
        base._agent_engine_http.post.return_value = response
        await base._create_session("https://example/sessions", "sess-1", "user-1")
        response.raise_for_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_other_status_code_is_raised(self):
        base = make_bare_base()
        response = Mock(status_code=500)
        response.text = "Internal Server Error"
        base._agent_engine_http.post.return_value = response
        await base._create_session("https://example/sessions", "sess-1", "user-1")
        response.raise_for_status.assert_called_once()


class TestParseEventStreamText:
    def test_returns_last_non_partial_text(self):
        base = make_bare_base()
        events = [
            {"partial": True, "content": {"parts": [{"text": "Hel"}]}},
            {"content": {"parts": [{"text": "Hello there"}]}},
        ]
        assert base._parse_event_stream_text(events) == "Hello there"

    def test_skips_events_without_text_parts(self):
        base = make_bare_base()
        events = [
            {"content": {"parts": [{"functionCall": {"name": "lookup"}}]}},
            {"content": {"parts": [{"text": "final answer"}]}},
        ]
        assert base._parse_event_stream_text(events) == "final answer"

    def test_returns_fallback_when_no_text_found(self):
        base = make_bare_base()
        assert "didn't get a response" in base._parse_event_stream_text([])
