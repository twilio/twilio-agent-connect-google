"""Tests for cross-replica tracking of injected memory."""

import hashlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from tac.utils.expiring_dict import ExpiringDict

from tac_google.connectors._injected_memory import (
    METADATA_KEY,
    is_memory_injected,
    new_injected_memory_cache,
    record_memory_injected,
)
from tac_google.connectors.cx_agent_studio.connector import CXAgentStudioConnector

MEMORY = "user likes pizza"
MEMORY_DIGEST = hashlib.sha256(MEMORY.encode()).hexdigest()


class FakeConversation:
    """The metadata Conversation Orchestrator keeps on one conversation, shared by all replicas."""

    def __init__(self) -> None:
        self.metadata: dict[str, str] = {}
        self.reads = 0
        self.patch = AsyncMock(side_effect=self._patch)

    async def _patch(self, conversation_id: str, metadata: dict[str, str]) -> None:
        self.metadata.update(metadata)

    def context(self, channel: str = "SMS", conv_id: str = "conv-1") -> SimpleNamespace:
        async def conversation_metadata() -> dict[str, str]:
            self.reads += 1
            return dict(self.metadata)

        return SimpleNamespace(
            conversation_id=conv_id,
            profile_id="user-1",
            pending_handoff_data=None,
            channel=channel,
            conversation_metadata=conversation_metadata,
        )

    def tac(self) -> Mock:
        tac = Mock()
        tac.conversation_orchestrator_client.patch_conversation_metadata = self.patch
        return tac


class TestIsMemoryInjected:
    @pytest.mark.asyncio
    async def test_local_hit_skips_the_conversation_read(self):
        conversation = FakeConversation()
        local = {"conv-1": MEMORY}
        assert await is_memory_injected(local, conversation.context(), MEMORY)
        assert conversation.reads == 0

    @pytest.mark.asyncio
    async def test_voice_never_reads_the_conversation(self):
        conversation = FakeConversation()
        context = conversation.context(channel="VOICE")
        assert not await is_memory_injected({}, context, MEMORY)
        assert conversation.reads == 0

    @pytest.mark.asyncio
    async def test_messaging_miss_with_nothing_stored(self):
        conversation = FakeConversation()
        assert not await is_memory_injected({}, conversation.context(), MEMORY)

    @pytest.mark.asyncio
    async def test_stored_hash_from_another_replica_counts_and_fills_local(self):
        conversation = FakeConversation()
        conversation.metadata[METADATA_KEY] = MEMORY_DIGEST
        local: dict[str, str] = {}
        assert await is_memory_injected(local, conversation.context(), MEMORY)
        assert local == {"conv-1": MEMORY}

    @pytest.mark.asyncio
    async def test_stored_hash_of_older_memory_does_not_count(self):
        conversation = FakeConversation()
        conversation.metadata[METADATA_KEY] = hashlib.sha256(b"memory v1").hexdigest()
        assert not await is_memory_injected({}, conversation.context(), MEMORY)


class TestLocalCacheExpiry:
    def test_cache_is_bounded_and_expiring(self):
        assert isinstance(new_injected_memory_cache(), ExpiringDict)

    @pytest.mark.asyncio
    async def test_expired_local_entry_falls_back_to_the_stored_hash(self):
        """An instance whose entry expired must not re-inject memory another
        instance (or its own earlier turn) already sent."""
        conversation = FakeConversation()
        conversation.metadata[METADATA_KEY] = MEMORY_DIGEST
        local: ExpiringDict[str] = ExpiringDict(ttl_seconds=60)
        with patch.object(ExpiringDict, "_now", return_value=0.0):
            local["conv-1"] = MEMORY
        with patch.object(ExpiringDict, "_now", return_value=61.0):
            assert "conv-1" not in local
            assert await is_memory_injected(local, conversation.context(), MEMORY)
            assert "conv-1" in local
        assert conversation.reads == 1


class TestRecordMemoryInjected:
    @pytest.mark.asyncio
    async def test_messaging_stores_the_hash_not_the_text(self):
        conversation = FakeConversation()
        local: dict[str, str] = {}
        await record_memory_injected(local, conversation.tac(), conversation.context(), MEMORY)
        assert local == {"conv-1": MEMORY}
        assert conversation.metadata == {METADATA_KEY: MEMORY_DIGEST}
        assert len(MEMORY_DIGEST) <= 512

    @pytest.mark.asyncio
    async def test_voice_only_updates_the_local_dict(self):
        conversation = FakeConversation()
        local: dict[str, str] = {}
        context = conversation.context(channel="VOICE")
        await record_memory_injected(local, conversation.tac(), context, MEMORY)
        assert local == {"conv-1": MEMORY}
        conversation.patch.assert_not_called()

    @pytest.mark.asyncio
    async def test_failed_patch_is_swallowed_and_local_is_still_set(self):
        conversation = FakeConversation()
        conversation.patch.side_effect = RuntimeError("CO down")
        local: dict[str, str] = {}
        await record_memory_injected(local, conversation.tac(), conversation.context(), MEMORY)
        assert local == {"conv-1": MEMORY}

    @pytest.mark.asyncio
    async def test_no_orchestrator_client_is_a_no_op(self):
        conversation = FakeConversation()
        tac = Mock()
        tac.conversation_orchestrator_client = None
        local: dict[str, str] = {}
        await record_memory_injected(local, tac, conversation.context(), MEMORY)
        assert local == {"conv-1": MEMORY}


def make_replica(conversation: FakeConversation) -> CXAgentStudioConnector:
    """A connector instance with its own local state but the shared conversation."""
    connector = CXAgentStudioConnector.__new__(CXAgentStudioConnector)
    connector.agent_id = "projects/p/locations/us/apps/a"
    connector._last_injected_memory = {}
    connector.tac = conversation.tac()
    return connector


class TestTwoReplicas:
    @pytest.mark.asyncio
    async def test_memory_is_sent_once_across_replicas(self):
        conversation = FakeConversation()
        replica_a = make_replica(conversation)
        replica_b = make_replica(conversation)
        context = conversation.context()
        sent: list[str] = []

        async def run_session(session: str, message: str, ctx: object) -> str:
            sent.append(message)
            return "reply"

        build = "tac_google.connectors.cx_agent_studio.connector.MemoryPromptBuilder.build"
        with patch(build, return_value=MEMORY):
            for replica in (replica_a, replica_b, replica_a):
                with patch.object(replica, "_run_session", new=run_session):
                    await replica._handle_message("hi", context, Mock())

        assert sent == [f"{MEMORY}\n\nhi", "hi", "hi"]

    @pytest.mark.asyncio
    async def test_changed_memory_is_sent_again_on_the_other_replica(self):
        conversation = FakeConversation()
        replica_a = make_replica(conversation)
        replica_b = make_replica(conversation)
        context = conversation.context()
        sent: list[str] = []

        async def run_session(session: str, message: str, ctx: object) -> str:
            sent.append(message)
            return "reply"

        build = "tac_google.connectors.cx_agent_studio.connector.MemoryPromptBuilder.build"
        for replica, memory in ((replica_a, "memory v1"), (replica_b, "memory v2")):
            with (
                patch(build, return_value=memory),
                patch.object(replica, "_run_session", new=run_session),
            ):
                await replica._handle_message("hi", context, Mock())

        assert sent == ["memory v1\n\nhi", "memory v2\n\nhi"]
