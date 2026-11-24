"""Tracks which memory text was already sent to the Google agent, across replicas.

The agent replays the whole session history on every call, so memory that was
already injected must not be injected again. Each instance keeps a local dict
(conversation id -> memory text) as a fast path. Messaging turns can land on
any instance, so a hash of the injected memory is also stored on the
Conversation Orchestrator conversation. Voice is pinned to one instance per
call, so it only uses the local dict.

Both reads and writes of the shared hash are best-effort: on any failure the
memory is injected again (a duplicate), never dropped.
"""

from __future__ import annotations

import hashlib

from tac.core.logging import get_logger
from tac.core.tac import TAC
from tac.models.session import ConversationSession
from tac.utils.expiring_dict import ExpiringDict

logger = get_logger(__name__)

#: Conversation metadata key holding the SHA-256 of the last injected memory.
METADATA_KEY = "tac_google.memory_hash"

# Entries are only a fast path (the conversation metadata is the source of truth) and
# CLOSED reaches just one instance, so the others rely on expiry to drop them.
_LOCAL_TTL_SECONDS = 24 * 60 * 60
_LOCAL_MAX_ENTRIES = 10_000


def new_injected_memory_cache() -> ExpiringDict[str]:
    return ExpiringDict(ttl_seconds=_LOCAL_TTL_SECONDS, max_entries=_LOCAL_MAX_ENTRIES)


def _digest(memory_context: str) -> str:
    return hashlib.sha256(memory_context.encode("utf-8")).hexdigest()


def _is_messaging(context: ConversationSession) -> bool:
    return context.channel.upper() != "VOICE"


async def is_memory_injected(
    local: ExpiringDict[str], context: ConversationSession, memory_context: str
) -> bool:
    """True if `memory_context` was already sent for this conversation, on any instance."""
    conv_id = context.conversation_id
    if conv_id in local and local[conv_id] == memory_context:
        return True
    if not _is_messaging(context):
        return False

    stored = (await context.conversation_metadata()).get(METADATA_KEY)
    if stored != _digest(memory_context):
        return False
    local[conv_id] = memory_context
    return True


async def record_memory_injected(
    local: ExpiringDict[str], tac: TAC, context: ConversationSession, memory_context: str
) -> None:
    """Remember that `memory_context` was sent; call only after the agent call succeeded."""
    conv_id = context.conversation_id
    local[conv_id] = memory_context
    if not _is_messaging(context):
        return

    client = tac.conversation_orchestrator_client
    if client is None:
        return
    try:
        await client.patch_conversation_metadata(conv_id, {METADATA_KEY: _digest(memory_context)})
    except Exception as e:
        logger.warning(
            "Failed to store injected-memory hash; memory may be re-injected on another instance",
            conversation_id=conv_id,
            error=str(e),
        )
