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
        result = base._maybe_tag_message("hello", self._context(), None)
        assert result == "hello"

    def test_empty_memory_context_returns_message_unchanged(self):
        base = make_bare_base()
        with patch(
            "tac_google.connectors.agent_platform._base.MemoryPromptBuilder.build",
            return_value=None,
        ):
            result = base._maybe_tag_message("hello", self._context(), Mock())
        assert result == "hello"

    def test_first_turn_tags_memory(self):
        base = make_bare_base()
        with patch(
            "tac_google.connectors.agent_platform._base.MemoryPromptBuilder.build",
            return_value="user likes pizza",
        ):
            result = base._maybe_tag_message("hello", self._context(), Mock())
        assert "user likes pizza" in result
        assert "hello" in result

    def test_unchanged_memory_is_not_retagged(self):
        """memory_mode="once" returns the same cached memory every turn — this
        must not be re-tagged, or ADK/Studio's session replay accumulates a
        duplicate copy on every turn."""
        base = make_bare_base()
        context = self._context()
        with patch(
            "tac_google.connectors.agent_platform._base.MemoryPromptBuilder.build",
            return_value="user likes pizza",
        ):
            base._maybe_tag_message("turn 1", context, Mock())
            result = base._maybe_tag_message("turn 2", context, Mock())
        assert result == "turn 2"

    def test_changed_memory_is_retagged(self):
        """memory_mode="always" re-queries per turn and typically returns
        different content — that must still get tagged every time."""
        base = make_bare_base()
        context = self._context()
        with patch(
            "tac_google.connectors.agent_platform._base.MemoryPromptBuilder.build",
            side_effect=["memory v1", "memory v2"],
        ):
            base._maybe_tag_message("turn 1", context, Mock())
            result = base._maybe_tag_message("turn 2", context, Mock())
        assert "memory v2" in result
        assert "turn 2" in result

    def test_conversation_ended_clears_tracked_memory(self):
        base = make_bare_base()
        context = self._context()
        with patch(
            "tac_google.connectors.agent_platform._base.MemoryPromptBuilder.build",
            return_value="user likes pizza",
        ):
            base._maybe_tag_message("turn 1", context, Mock())
            base._handle_conversation_ended(context)
            # After the conversation ends, the same memory content is tagged
            # again on a subsequent (new) conversation reusing the same content.
            result = base._maybe_tag_message("turn 2", context, Mock())
        assert "user likes pizza" in result


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
