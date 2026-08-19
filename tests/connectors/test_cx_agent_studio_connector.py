"""Tests for CXAgentStudioConnector's memory-tagging dedup logic."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from tac_google.connectors.cx_agent_studio.connector import CXAgentStudioConnector


def make_bare_connector() -> CXAgentStudioConnector:
    """Builds a CXAgentStudioConnector without the TAC/channel wiring in __init__."""
    connector = CXAgentStudioConnector.__new__(CXAgentStudioConnector)
    connector.agent_id = "projects/p/locations/us/apps/a"
    connector._last_injected_memory = {}
    return connector


def make_context(conv_id: str = "conv-1") -> SimpleNamespace:
    return SimpleNamespace(conversation_id=conv_id, profile_id="user-1", pending_handoff_data=None)


class TestSmsChannelConstruction:
    def test_sms_channel_built_by_default_when_sms_config_omitted(self):
        with (
            patch(
                "tac_google.connectors.cx_agent_studio.connector.google.auth.default"
            ) as mock_auth,
            patch("tac_google.connectors.cx_agent_studio.connector.AuthorizedSession"),
            patch("tac_google.connectors.cx_agent_studio.connector.SMSChannel") as mock_sms_channel,
        ):
            mock_auth.return_value = (Mock(), None)
            tac = Mock()
            connector = CXAgentStudioConnector(tac=tac, agent_id="projects/p/locations/us/apps/a")

        assert connector.sms is mock_sms_channel.return_value
        mock_sms_channel.assert_called_once()
        assert mock_sms_channel.call_args.kwargs["tac"] is tac

    def test_sms_channel_omitted_when_sms_config_explicitly_none(self):
        with (
            patch(
                "tac_google.connectors.cx_agent_studio.connector.google.auth.default"
            ) as mock_auth,
            patch("tac_google.connectors.cx_agent_studio.connector.AuthorizedSession"),
            patch("tac_google.connectors.cx_agent_studio.connector.SMSChannel") as mock_sms_channel,
        ):
            mock_auth.return_value = (Mock(), None)
            connector = CXAgentStudioConnector(
                tac=Mock(), agent_id="projects/p/locations/us/apps/a", sms_config=None
            )

        assert connector.sms is None
        mock_sms_channel.assert_not_called()

    def test_sms_channel_built_when_sms_config_given(self):
        with (
            patch(
                "tac_google.connectors.cx_agent_studio.connector.google.auth.default"
            ) as mock_auth,
            patch("tac_google.connectors.cx_agent_studio.connector.AuthorizedSession"),
            patch("tac_google.connectors.cx_agent_studio.connector.SMSChannel") as mock_sms_channel,
        ):
            mock_auth.return_value = (Mock(), None)
            sms_config = Mock()
            tac = Mock()
            connector = CXAgentStudioConnector(
                tac=tac, agent_id="projects/p/locations/us/apps/a", sms_config=sms_config
            )

        assert connector.sms is mock_sms_channel.return_value
        mock_sms_channel.assert_called_once_with(tac=tac, config=sms_config)


class TestMaybeTagMemory:
    def test_no_memory_response_returns_message_unchanged(self):
        connector = make_bare_connector()
        message, memory_to_commit = connector._maybe_tag_memory("hello", make_context(), None)
        assert message == "hello"
        assert memory_to_commit is None

    def test_first_turn_prepends_memory(self):
        connector = make_bare_connector()
        with patch(
            "tac_google.connectors.cx_agent_studio.connector.MemoryPromptBuilder.build",
            return_value="user likes pizza",
        ):
            message, memory_to_commit = connector._maybe_tag_memory("hello", make_context(), Mock())
        assert message == "user likes pizza\n\nhello"
        assert memory_to_commit == "user likes pizza"

    def test_unchanged_memory_is_not_reprepended(self):
        """memory_mode="once" returns the same cached memory every turn — CES
        stores each turn's raw text and replays the full history, so
        re-prepending unchanged memory would duplicate it once per turn."""
        connector = make_bare_connector()
        context = make_context()
        connector._last_injected_memory[context.conversation_id] = "user likes pizza"
        with patch(
            "tac_google.connectors.cx_agent_studio.connector.MemoryPromptBuilder.build",
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
            "tac_google.connectors.cx_agent_studio.connector.MemoryPromptBuilder.build",
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
            "tac_google.connectors.cx_agent_studio.connector.MemoryPromptBuilder.build",
            return_value="user likes pizza",
        ):
            message, memory_to_commit = connector._maybe_tag_memory("turn 2", context, Mock())
        assert message == "user likes pizza\n\nturn 2"
        assert memory_to_commit == "user likes pizza"


class TestHandleEndSession:
    def test_no_endsession_leaves_handoff_data_unset(self):
        connector = make_bare_connector()
        context = make_context()
        connector._handle_end_session({"outputs": [{"text": "hi"}]}, context)
        assert context.pending_handoff_data is None

    def test_endsession_sets_pending_handoff_data(self):
        connector = make_bare_connector()
        context = make_context()
        data = {
            "outputs": [
                {
                    "endSession": {
                        "metadata": {"session_escalated": False, "reason": "no more questions"}
                    }
                }
            ]
        }
        connector._handle_end_session(data, context)
        assert context.pending_handoff_data is not None
        assert context.pending_handoff_data.type == "end"
        assert context.pending_handoff_data.handoff_data == "call_ended"

    def test_endsession_escalated_also_sets_pending_handoff_data(self):
        """Both escalated and non-escalated end_session calls get the same
        graceful-hangup treatment for now — there's no human-transfer
        destination wired up yet."""
        connector = make_bare_connector()
        context = make_context()
        data = {"outputs": [{"endSession": {"metadata": {"session_escalated": True}}}]}
        connector._handle_end_session(data, context)
        assert context.pending_handoff_data is not None
        assert context.pending_handoff_data.handoff_data == "call_ended"

    def test_endsession_with_empty_metadata_still_sets_pending_handoff_data(self):
        """`{"endSession": {}}` (no metadata at all) is falsy-looking but must
        still be detected — a truthiness check on the endSession dict itself
        would miss this and leave the dead CES session unhandled."""
        connector = make_bare_connector()
        context = make_context()
        data = {"outputs": [{"endSession": {}}]}
        connector._handle_end_session(data, context)
        assert context.pending_handoff_data is not None
        assert context.pending_handoff_data.handoff_data == "call_ended"

    def test_endsession_not_in_last_output_is_still_found(self):
        """The API reference doesn't guarantee endSession lands on the last
        entry of `outputs` — only that diagnosticInfo is on the
        turnCompleted=true one. Don't assume position."""
        connector = make_bare_connector()
        context = make_context()
        data = {
            "outputs": [
                {"endSession": {"metadata": {"reason": "done"}}},
                {"turnCompleted": True, "diagnosticInfo": {}},
            ]
        }
        connector._handle_end_session(data, context)
        assert context.pending_handoff_data is not None
        assert context.pending_handoff_data.handoff_data == "call_ended"


class TestParseResponseEndSession:
    def test_endsession_with_no_text_gets_a_closing_line(self):
        """end_session commonly fires with no text field at all (confirmed
        against a real call) — the generic "I didn't get a response"
        fallback would be a confusing thing to say as the call ends."""
        connector = make_bare_connector()
        data = {"outputs": [{"endSession": {"metadata": {}}}]}
        assert connector._parse_response(data) == "Thank you for calling. Goodbye!"

    def test_endsession_with_text_still_uses_that_text(self):
        connector = make_bare_connector()
        data = {"outputs": [{"text": "Goodbye!", "endSession": {"metadata": {}}}]}
        assert connector._parse_response(data) == "Goodbye!"


class TestHandleMessageMemoryCommit:
    @pytest.mark.asyncio
    async def test_successful_call_commits_memory(self):
        connector = make_bare_connector()
        context = make_context()
        with (
            patch.object(connector, "_run_session", new=AsyncMock(return_value="reply")),
            patch(
                "tac_google.connectors.cx_agent_studio.connector.MemoryPromptBuilder.build",
                return_value="user likes pizza",
            ),
        ):
            reply = await connector._handle_message("hello", context, Mock())
        assert reply == "reply"
        assert connector._last_injected_memory[context.conversation_id] == "user likes pizza"

    @pytest.mark.asyncio
    async def test_failed_call_does_not_commit_memory(self):
        """A failed runSession call must not mark memory as sent — otherwise
        the next turn (memory_mode="once", unchanged content) would skip
        re-sending memory that CES never actually received."""
        connector = make_bare_connector()
        context = make_context()
        with (
            patch.object(
                connector, "_run_session", new=AsyncMock(side_effect=RuntimeError("boom"))
            ),
            patch(
                "tac_google.connectors.cx_agent_studio.connector.MemoryPromptBuilder.build",
                return_value="user likes pizza",
            ),
        ):
            await connector._handle_message("hello", context, Mock())
        assert context.conversation_id not in connector._last_injected_memory
