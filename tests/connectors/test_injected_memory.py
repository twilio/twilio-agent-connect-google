"""Memory injection with several instances: messaging tags every turn, voice dedupes locally."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from tac.utils.expiring_dict import ExpiringDict

from tac_google.connectors._injected_memory import new_injected_memory_cache
from tac_google.connectors.agent_platform._base import AgentEngineConnectorBase
from tac_google.connectors.conversational_agents_connector import ConversationalAgentsConnector
from tac_google.connectors.cx_agent_studio.connector import CXAgentStudioConnector

MEMORY = "user likes pizza"

# connector class -> module path of its MemoryPromptBuilder
FAMILIES = [
    (AgentEngineConnectorBase, "_maybe_tag_message", "agent_platform._base"),
    (CXAgentStudioConnector, "_maybe_tag_memory", "cx_agent_studio.connector"),
    (ConversationalAgentsConnector, "_maybe_tag_memory", "conversational_agents_connector"),
]


def make_replica(cls: type) -> object:
    """An instance with its own local state, sharing nothing with other replicas."""
    connector = cls.__new__(cls)
    connector._last_injected_memory = new_injected_memory_cache()
    return connector


def make_context(channel: str, conv_id: str = "conv-1") -> SimpleNamespace:
    return SimpleNamespace(
        conversation_id=conv_id, profile_id="user-1", channel=channel, pending_handoff_data=None
    )


def tag(replica: object, method: str, module: str, context: SimpleNamespace, message: str):
    build = f"tac_google.connectors.{module}.MemoryPromptBuilder.build"
    with patch(build, return_value=MEMORY):
        return getattr(replica, method)(message, context, Mock())


@pytest.mark.parametrize(("cls", "method", "module"), FAMILIES)
class TestMessagingAcrossReplicas:
    def test_memory_is_tagged_on_every_turn_whichever_replica_gets_it(self, cls, method, module):
        replicas = [make_replica(cls), make_replica(cls)]
        context = make_context("SMS")
        for turn in range(4):
            message, to_commit = tag(replicas[turn % 2], method, module, context, f"turn {turn}")
            assert MEMORY in message
            assert f"turn {turn}" in message
            assert to_commit is None

    def test_messaging_never_touches_the_local_cache(self, cls, method, module):
        replica = make_replica(cls)
        for channel in ("SMS", "RCS", "WHATSAPP", "CHAT"):
            tag(replica, method, module, make_context(channel), "hi")
        assert len(replica._last_injected_memory) == 0

    def test_messaging_ignores_a_stale_entry_in_the_cache(self, cls, method, module):
        replica = make_replica(cls)
        replica._last_injected_memory["conv-1"] = MEMORY
        message, _ = tag(replica, method, module, make_context("SMS"), "hi")
        assert MEMORY in message


@pytest.mark.parametrize(("cls", "method", "module"), FAMILIES)
class TestVoiceOnOneReplica:
    def test_memory_is_sent_once_per_call(self, cls, method, module):
        replica = make_replica(cls)
        context = make_context("VOICE")

        first, to_commit = tag(replica, method, module, context, "hi")
        assert MEMORY in first
        assert to_commit == MEMORY
        replica._last_injected_memory[context.conversation_id] = to_commit

        second, to_commit = tag(replica, method, module, context, "again")
        assert second == "again"
        assert to_commit is None

    def test_changed_memory_is_sent_again(self, cls, method, module):
        replica = make_replica(cls)
        replica._last_injected_memory["conv-1"] = "older memory"
        message, to_commit = tag(replica, method, module, make_context("VOICE"), "hi")
        assert MEMORY in message
        assert to_commit == MEMORY

    def test_local_cache_is_bounded_and_expiring(self, cls, method, module):
        assert isinstance(make_replica(cls)._last_injected_memory, ExpiringDict)


class TestCXMessagingEndToEnd:
    @pytest.mark.asyncio
    async def test_two_replicas_alternating_send_memory_every_turn(self):
        replicas = [make_replica(CXAgentStudioConnector), make_replica(CXAgentStudioConnector)]
        context = make_context("SMS")
        sent: list[str] = []

        async def run_session(session: str, message: str, ctx: object) -> str:
            sent.append(message)
            return "reply"

        build = "tac_google.connectors.cx_agent_studio.connector.MemoryPromptBuilder.build"
        for turn in range(3):
            replica = replicas[turn % 2]
            replica.agent_id = "projects/p/locations/us/apps/a"
            with (
                patch(build, return_value=MEMORY),
                patch.object(replica, "_run_session", new=run_session),
            ):
                await replica._handle_message(f"turn {turn}", context, Mock())

        assert sent == [f"{MEMORY}\n\nturn {turn}" for turn in range(3)]
