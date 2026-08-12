"""Tests for ADKAgentEngineConnector."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from tac_google.connectors.agent_platform.adk_connector import ADKAgentEngineConnector


def make_bare_connector(agent: Mock) -> ADKAgentEngineConnector:
    """Builds an ADKAgentEngineConnector without the TAC/channel wiring in __init__."""
    connector = ADKAgentEngineConnector.__new__(ADKAgentEngineConnector)
    connector.agent = agent
    connector.adk_sessions_created = set()
    connector._last_injected_memory = {}
    connector._agent_engine_http = Mock()
    connector._sessions_url = "https://example/sessions"
    return connector


def make_context(conv_id: str = "conv_1") -> SimpleNamespace:
    return SimpleNamespace(conversation_id=conv_id, profile_id="user-1")


async def async_events(events: list[dict]):
    for event in events:
        yield event


class TestInvokeAgent:
    @pytest.mark.asyncio
    async def test_creates_session_once_per_conversation(self):
        agent = Mock()
        agent.async_stream_query = Mock(
            return_value=async_events([{"content": {"parts": [{"text": "hi"}]}}])
        )
        connector = make_bare_connector(agent)
        context = make_context()

        with patch.object(connector, "_create_session", new=AsyncMock()) as create_session:
            await connector._invoke_agent("hello", context, None)
            await connector._invoke_agent("hello again", context, None)

        create_session.assert_awaited_once()
        assert context.conversation_id in connector.adk_sessions_created

    @pytest.mark.asyncio
    async def test_sends_only_this_turns_message(self):
        agent = Mock()
        agent.async_stream_query = Mock(
            return_value=async_events([{"content": {"parts": [{"text": "reply"}]}}])
        )
        connector = make_bare_connector(agent)
        context = make_context()

        with patch.object(connector, "_create_session", new=AsyncMock()):
            reply = await connector._invoke_agent("hello", context, None)

        assert reply == "reply"
        agent.async_stream_query.assert_called_once()
        _, kwargs = agent.async_stream_query.call_args
        assert kwargs["message"] == "hello"
        assert kwargs["session_id"] == "conv-1"

    @pytest.mark.asyncio
    async def test_memory_is_tagged_into_message(self):
        agent = Mock()
        captured = {}

        def capture_stream_query(**kwargs):
            captured.update(kwargs)
            return async_events([{"content": {"parts": [{"text": "reply"}]}}])

        agent.async_stream_query = Mock(side_effect=capture_stream_query)
        connector = make_bare_connector(agent)
        context = make_context()

        with (
            patch.object(connector, "_create_session", new=AsyncMock()),
            patch(
                "tac_google.connectors.agent_platform._base.MemoryPromptBuilder.build",
                return_value="likes pizza",
            ),
        ):
            await connector._invoke_agent("hello", context, Mock())

        assert "likes pizza" in captured["message"]
        assert "hello" in captured["message"]

    @pytest.mark.asyncio
    async def test_failed_call_does_not_commit_memory(self):
        """A failed async_stream_query call must not mark memory as sent —
        otherwise the next turn (memory_mode="once", unchanged content)
        would skip re-sending memory ADK never actually received."""
        agent = Mock()
        agent.async_stream_query = Mock(side_effect=RuntimeError("boom"))
        connector = make_bare_connector(agent)
        context = make_context()

        with (
            patch.object(connector, "_create_session", new=AsyncMock()),
            patch(
                "tac_google.connectors.agent_platform._base.MemoryPromptBuilder.build",
                return_value="likes pizza",
            ),
            pytest.raises(RuntimeError),
        ):
            await connector._invoke_agent("hello", context, Mock())

        assert context.conversation_id not in connector._last_injected_memory


class TestHandleConversationEnded:
    def test_discards_session_and_memory_tracking(self):
        agent = Mock()
        connector = make_bare_connector(agent)
        context = make_context()
        connector.adk_sessions_created.add(context.conversation_id)
        connector._last_injected_memory[context.conversation_id] = "some memory"

        connector._handle_conversation_ended(context)

        assert context.conversation_id not in connector.adk_sessions_created
        assert context.conversation_id not in connector._last_injected_memory
