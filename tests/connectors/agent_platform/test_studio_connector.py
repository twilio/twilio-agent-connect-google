"""Tests for StudioAgentEngineConnector."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from tac_google.connectors.agent_platform.studio_connector import StudioAgentEngineConnector


def make_bare_connector(agent: Mock) -> StudioAgentEngineConnector:
    """Builds a StudioAgentEngineConnector without the TAC/channel wiring in __init__."""
    connector = StudioAgentEngineConnector.__new__(StudioAgentEngineConnector)
    connector.agent = agent
    connector.studio_sessions_created = set()
    connector._last_injected_memory = {}
    connector._agent_engine_http = Mock()
    connector._sessions_url = "https://example/sessions"
    connector._stream_query_url = "https://example:streamQuery"
    return connector


def make_context(conv_id: str = "conv_1") -> SimpleNamespace:
    return SimpleNamespace(conversation_id=conv_id, profile_id="user-1")


def stream_query_response(events: list[dict]) -> Mock:
    response = Mock()
    response.text = "".join(json.dumps(event) for event in events)
    return response


class TestInvokeAgent:
    @pytest.mark.asyncio
    async def test_creates_session_once_per_conversation(self):
        connector = make_bare_connector(Mock())
        connector._agent_engine_http.post.return_value = stream_query_response(
            [{"content": {"parts": [{"text": "hi"}]}}]
        )
        context = make_context()

        with patch.object(connector, "_create_session", new=AsyncMock()) as create_session:
            await connector._invoke_agent("hello", context, None)
            await connector._invoke_agent("hello again", context, None)

        create_session.assert_awaited_once()
        assert context.conversation_id in connector.studio_sessions_created

    @pytest.mark.asyncio
    async def test_sends_only_this_turns_message(self):
        connector = make_bare_connector(Mock())
        connector._agent_engine_http.post.return_value = stream_query_response(
            [{"content": {"parts": [{"text": "reply"}]}}]
        )
        context = make_context()

        with patch.object(connector, "_create_session", new=AsyncMock()):
            reply = await connector._invoke_agent("hello", context, None)

        assert reply == "reply"
        _, kwargs = connector._agent_engine_http.post.call_args
        assert kwargs["json"]["input"]["message"] == "hello"
        assert kwargs["json"]["input"]["session_id"] == "conv-1"
        assert kwargs["json"]["class_method"] == "async_stream_query"

    @pytest.mark.asyncio
    async def test_memory_is_tagged_into_message(self):
        connector = make_bare_connector(Mock())
        connector._agent_engine_http.post.return_value = stream_query_response(
            [{"content": {"parts": [{"text": "reply"}]}}]
        )
        context = make_context()

        with (
            patch.object(connector, "_create_session", new=AsyncMock()),
            patch(
                "tac_google.connectors.agent_platform._base.MemoryPromptBuilder.build",
                return_value="likes pizza",
            ),
        ):
            await connector._invoke_agent("hello", context, Mock())

        _, kwargs = connector._agent_engine_http.post.call_args
        sent_message = kwargs["json"]["input"]["message"]
        assert "likes pizza" in sent_message
        assert "hello" in sent_message


class TestParseStudioEvents:
    def test_parses_concatenated_json_events(self):
        connector = make_bare_connector(Mock())
        raw = json.dumps({"a": 1}) + json.dumps({"b": 2})
        assert connector._parse_studio_events(raw) == [{"a": 1}, {"b": 2}]

    def test_parses_bracketed_comma_separated_events(self):
        connector = make_bare_connector(Mock())
        raw = "[" + json.dumps({"a": 1}) + "," + json.dumps({"b": 2}) + "]"
        assert connector._parse_studio_events(raw) == [{"a": 1}, {"b": 2}]

    def test_empty_input_returns_empty_list(self):
        connector = make_bare_connector(Mock())
        assert connector._parse_studio_events("") == []


class TestHandleConversationEnded:
    def test_discards_session_and_memory_tracking(self):
        connector = make_bare_connector(Mock())
        context = make_context()
        connector.studio_sessions_created.add(context.conversation_id)
        connector._last_injected_memory[context.conversation_id] = "some memory"

        connector._handle_conversation_ended(context)

        assert context.conversation_id not in connector.studio_sessions_created
        assert context.conversation_id not in connector._last_injected_memory
