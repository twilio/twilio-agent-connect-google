"""Tests for ConversationalAgentsConnector's memory-tagging dedup logic."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

from tac_google.connectors.conversational_agents_connector import ConversationalAgentsConnector


def make_bare_connector() -> ConversationalAgentsConnector:
    """Builds a ConversationalAgentsConnector without the TAC/channel wiring in __init__."""
    connector = ConversationalAgentsConnector.__new__(ConversationalAgentsConnector)
    connector._last_injected_memory = {}
    return connector


def make_context(conv_id: str = "conv-1") -> SimpleNamespace:
    return SimpleNamespace(conversation_id=conv_id, profile_id="user-1")


class TestMaybeTagMemory:
    def test_no_memory_response_returns_message_unchanged(self):
        connector = make_bare_connector()
        result = connector._maybe_tag_memory("hello", make_context(), None)
        assert result == "hello"

    def test_first_turn_prepends_memory(self):
        connector = make_bare_connector()
        with patch(
            "tac_google.connectors.conversational_agents_connector.MemoryPromptBuilder.build",
            return_value="user likes pizza",
        ):
            result = connector._maybe_tag_memory("hello", make_context(), Mock())
        assert result == "user likes pizza\n\nhello"

    def test_unchanged_memory_is_not_reprepended(self):
        """memory_mode="once" returns the same cached memory every turn —
        Dialogflow CX keeps and replays full session history, so
        re-prepending unchanged memory would duplicate it once per turn."""
        connector = make_bare_connector()
        context = make_context()
        with patch(
            "tac_google.connectors.conversational_agents_connector.MemoryPromptBuilder.build",
            return_value="user likes pizza",
        ):
            connector._maybe_tag_memory("turn 1", context, Mock())
            result = connector._maybe_tag_memory("turn 2", context, Mock())
        assert result == "turn 2"

    def test_changed_memory_is_reprepended(self):
        connector = make_bare_connector()
        context = make_context()
        with patch(
            "tac_google.connectors.conversational_agents_connector.MemoryPromptBuilder.build",
            side_effect=["memory v1", "memory v2"],
        ):
            connector._maybe_tag_memory("turn 1", context, Mock())
            result = connector._maybe_tag_memory("turn 2", context, Mock())
        assert result == "memory v2\n\nturn 2"

    def test_conversation_ended_clears_tracked_memory(self):
        connector = make_bare_connector()
        context = make_context()
        with patch(
            "tac_google.connectors.conversational_agents_connector.MemoryPromptBuilder.build",
            return_value="user likes pizza",
        ):
            connector._maybe_tag_memory("turn 1", context, Mock())
            connector._handle_conversation_ended(context)
            result = connector._maybe_tag_memory("turn 2", context, Mock())
        assert result == "user likes pizza\n\nturn 2"
