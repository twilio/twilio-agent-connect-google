"""Tests for ConversationalAgentsConnector's memory-tagging dedup logic."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from tac_google.connectors.conversational_agents_connector import ConversationalAgentsConnector


def make_bare_connector() -> ConversationalAgentsConnector:
    """Builds a ConversationalAgentsConnector without the TAC/channel wiring in __init__."""
    connector = ConversationalAgentsConnector.__new__(ConversationalAgentsConnector)
    connector.agent_id = "projects/p/locations/us-central1/agents/a"
    connector._last_injected_memory = {}
    return connector


def make_context(conv_id: str = "conv-1") -> SimpleNamespace:
    return SimpleNamespace(conversation_id=conv_id, profile_id="user-1")


class TestChannelConstruction:
    def test_sms_and_voice_omitted_when_configs_omitted(self):
        with (
            patch(
                "tac_google.connectors.conversational_agents_connector.google.auth.default"
            ) as mock_auth,
            patch("tac_google.connectors.conversational_agents_connector.AuthorizedSession"),
            patch("tac_google.connectors._channels.SMSChannel") as mock_sms_channel,
            patch("tac_google.connectors._channels.VoiceChannel") as mock_voice_channel,
        ):
            mock_auth.return_value = (Mock(), None)
            connector = ConversationalAgentsConnector(
                tac=Mock(), agent_id="projects/p/locations/us-central1/agents/a"
            )

        assert connector.sms is None
        assert connector.voice is None
        mock_sms_channel.assert_not_called()
        mock_voice_channel.assert_not_called()

    def test_sms_built_when_sms_config_given(self):
        with (
            patch(
                "tac_google.connectors.conversational_agents_connector.google.auth.default"
            ) as mock_auth,
            patch("tac_google.connectors.conversational_agents_connector.AuthorizedSession"),
            patch("tac_google.connectors._channels.SMSChannel") as mock_sms_channel,
        ):
            mock_auth.return_value = (Mock(), None)
            sms_config = Mock()
            tac = Mock()
            connector = ConversationalAgentsConnector(
                tac=tac,
                agent_id="projects/p/locations/us-central1/agents/a",
                sms_config=sms_config,
            )

        assert connector.sms is mock_sms_channel.return_value
        mock_sms_channel.assert_called_once_with(tac=tac, config=sms_config)

    def test_voice_built_when_voice_config_given(self):
        with (
            patch(
                "tac_google.connectors.conversational_agents_connector.google.auth.default"
            ) as mock_auth,
            patch("tac_google.connectors.conversational_agents_connector.AuthorizedSession"),
            patch("tac_google.connectors._channels.VoiceChannel") as mock_voice_channel,
        ):
            mock_auth.return_value = (Mock(), None)
            voice_config = Mock()
            tac = Mock()
            connector = ConversationalAgentsConnector(
                tac=tac,
                agent_id="projects/p/locations/us-central1/agents/a",
                voice_config=voice_config,
            )

        assert connector.voice is mock_voice_channel.return_value
        mock_voice_channel.assert_called_once_with(tac=tac, config=voice_config)

    def test_sms_omitted_when_sms_config_explicitly_none(self):
        with (
            patch(
                "tac_google.connectors.conversational_agents_connector.google.auth.default"
            ) as mock_auth,
            patch("tac_google.connectors.conversational_agents_connector.AuthorizedSession"),
            patch("tac_google.connectors._channels.SMSChannel") as mock_sms_channel,
        ):
            mock_auth.return_value = (Mock(), None)
            connector = ConversationalAgentsConnector(
                tac=Mock(),
                agent_id="projects/p/locations/us-central1/agents/a",
                sms_config=None,
            )

        assert connector.sms is None
        mock_sms_channel.assert_not_called()

    def test_voice_omitted_when_voice_config_explicitly_none(self):
        with (
            patch(
                "tac_google.connectors.conversational_agents_connector.google.auth.default"
            ) as mock_auth,
            patch("tac_google.connectors.conversational_agents_connector.AuthorizedSession"),
            patch("tac_google.connectors._channels.VoiceChannel") as mock_voice_channel,
        ):
            mock_auth.return_value = (Mock(), None)
            connector = ConversationalAgentsConnector(
                tac=Mock(),
                agent_id="projects/p/locations/us-central1/agents/a",
                voice_config=None,
            )

        assert connector.voice is None
        mock_voice_channel.assert_not_called()


class TestMaybeTagMemory:
    def test_no_memory_response_returns_message_unchanged(self):
        connector = make_bare_connector()
        message, memory_to_commit = connector._maybe_tag_memory("hello", make_context(), None)
        assert message == "hello"
        assert memory_to_commit is None

    def test_first_turn_prepends_memory(self):
        connector = make_bare_connector()
        with patch(
            "tac_google.connectors.conversational_agents_connector.MemoryPromptBuilder.build",
            return_value="user likes pizza",
        ):
            message, memory_to_commit = connector._maybe_tag_memory("hello", make_context(), Mock())
        assert message == "user likes pizza\n\nhello"
        assert memory_to_commit == "user likes pizza"

    def test_unchanged_memory_is_not_reprepended(self):
        """memory_mode="once" returns the same cached memory every turn —
        Dialogflow CX keeps and replays full session history, so
        re-prepending unchanged memory would duplicate it once per turn."""
        connector = make_bare_connector()
        context = make_context()
        connector._last_injected_memory[context.conversation_id] = "user likes pizza"
        with patch(
            "tac_google.connectors.conversational_agents_connector.MemoryPromptBuilder.build",
            return_value="user likes pizza",
        ):
            message, memory_to_commit = connector._maybe_tag_memory("turn 2", context, Mock())
        assert message == "turn 2"
        assert memory_to_commit is None

    def test_changed_memory_is_reprepended(self):
        connector = make_bare_connector()
        context = make_context()
        connector._last_injected_memory[context.conversation_id] = "memory v1"
        with patch(
            "tac_google.connectors.conversational_agents_connector.MemoryPromptBuilder.build",
            return_value="memory v2",
        ):
            message, memory_to_commit = connector._maybe_tag_memory("turn 2", context, Mock())
        assert message == "memory v2\n\nturn 2"
        assert memory_to_commit == "memory v2"

    def test_conversation_ended_clears_tracked_memory(self):
        connector = make_bare_connector()
        context = make_context()
        connector._last_injected_memory[context.conversation_id] = "user likes pizza"
        connector._handle_conversation_ended(context)
        with patch(
            "tac_google.connectors.conversational_agents_connector.MemoryPromptBuilder.build",
            return_value="user likes pizza",
        ):
            message, memory_to_commit = connector._maybe_tag_memory("turn 2", context, Mock())
        assert message == "user likes pizza\n\nturn 2"
        assert memory_to_commit == "user likes pizza"


class TestHandleMessageMemoryCommit:
    @pytest.mark.asyncio
    async def test_successful_call_commits_memory(self):
        connector = make_bare_connector()
        context = make_context()
        with (
            patch.object(connector, "_detect_intent", new=AsyncMock(return_value="reply")),
            patch(
                "tac_google.connectors.conversational_agents_connector.MemoryPromptBuilder.build",
                return_value="user likes pizza",
            ),
        ):
            reply = await connector._handle_message("hello", context, Mock())
        assert reply == "reply"
        assert connector._last_injected_memory[context.conversation_id] == "user likes pizza"

    @pytest.mark.asyncio
    async def test_failed_call_does_not_commit_memory(self):
        """A failed detectIntent call must not mark memory as sent —
        otherwise the next turn (memory_mode="once", unchanged content)
        would skip re-sending memory that Dialogflow never received."""
        connector = make_bare_connector()
        context = make_context()
        with (
            patch.object(
                connector, "_detect_intent", new=AsyncMock(side_effect=RuntimeError("boom"))
            ),
            patch(
                "tac_google.connectors.conversational_agents_connector.MemoryPromptBuilder.build",
                return_value="user likes pizza",
            ),
        ):
            await connector._handle_message("hello", context, Mock())
        assert context.conversation_id not in connector._last_injected_memory
