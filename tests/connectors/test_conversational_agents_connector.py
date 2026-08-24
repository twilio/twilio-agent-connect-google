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
            patch(
                "tac_google.connectors.conversational_agents_connector.google.auth.default"
            ) as mock_auth,
            patch("tac_google.connectors.conversational_agents_connector.AuthorizedSession"),
            patch(
                "tac_google.connectors.conversational_agents_connector.VoiceChannel"
            ) as mock_voice_channel,
            patch("tac_google.connectors._channels.SMSChannel") as mock_sms_channel,
            patch("tac_google.connectors._channels.ChatChannel") as mock_chat_channel,
        ):
            mock_auth.return_value = (Mock(), None)
            connector = ConversationalAgentsConnector(
                tac=make_tac_for_channels(),
                agent_id="projects/p/locations/us-central1/agents/a",
            )

        assert connector.voice is mock_voice_channel.return_value
        assert connector.sms is mock_sms_channel.return_value
        assert connector.chat is mock_chat_channel.return_value

    def test_rcs_and_whatsapp_none_when_resource_not_configured(self):
        with (
            patch(
                "tac_google.connectors.conversational_agents_connector.google.auth.default"
            ) as mock_auth,
            patch("tac_google.connectors.conversational_agents_connector.AuthorizedSession"),
            patch("tac_google.connectors._channels.RCSChannel") as mock_rcs_channel,
            patch("tac_google.connectors._channels.WhatsAppChannel") as mock_whatsapp_channel,
        ):
            mock_auth.return_value = (Mock(), None)
            connector = ConversationalAgentsConnector(
                tac=make_tac_for_channels(),
                agent_id="projects/p/locations/us-central1/agents/a",
            )

        assert connector.rcs is None
        assert connector.whatsapp is None
        mock_rcs_channel.assert_not_called()
        mock_whatsapp_channel.assert_not_called()

    def test_rcs_built_when_rcs_sender_id_configured(self):
        with (
            patch(
                "tac_google.connectors.conversational_agents_connector.google.auth.default"
            ) as mock_auth,
            patch("tac_google.connectors.conversational_agents_connector.AuthorizedSession"),
            patch("tac_google.connectors._channels.RCSChannel") as mock_rcs_channel,
        ):
            mock_auth.return_value = (Mock(), None)
            tac = make_tac_for_channels()
            tac.config.rcs_sender_id = "rcs_sender_123"
            connector = ConversationalAgentsConnector(
                tac=tac, agent_id="projects/p/locations/us-central1/agents/a"
            )

        assert connector.rcs is mock_rcs_channel.return_value
        mock_rcs_channel.assert_called_once_with(tac=tac, config=None)

    def test_whatsapp_built_when_whatsapp_number_configured(self):
        with (
            patch(
                "tac_google.connectors.conversational_agents_connector.google.auth.default"
            ) as mock_auth,
            patch("tac_google.connectors.conversational_agents_connector.AuthorizedSession"),
            patch("tac_google.connectors._channels.WhatsAppChannel") as mock_whatsapp_channel,
        ):
            mock_auth.return_value = (Mock(), None)
            tac = make_tac_for_channels()
            tac.config.whatsapp_number = "whatsapp:+15550001234"
            connector = ConversationalAgentsConnector(
                tac=tac, agent_id="projects/p/locations/us-central1/agents/a"
            )

        assert connector.whatsapp is mock_whatsapp_channel.return_value
        mock_whatsapp_channel.assert_called_once_with(tac=tac, config=None)


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
