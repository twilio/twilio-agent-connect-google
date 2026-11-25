"""Voice-only tracking of memory already sent to the Google agent.

The agent replays the whole session history on every call, so on voice, memory
that hasn't changed since the last turn is not injected again. Voice is pinned to
one instance per call, so a local dict is enough. Messaging turns can land on any
instance and never use it: they tag memory every turn.
"""

from __future__ import annotations

from tac.models.session import ConversationSession
from tac.utils.expiring_dict import ExpiringDict

# CLOSED may reach a different instance than the one holding the entry, so expiry drops it.
_TTL_SECONDS = 24 * 60 * 60
_MAX_ENTRIES = 10_000


def new_injected_memory_cache() -> ExpiringDict[str]:
    return ExpiringDict(ttl_seconds=_TTL_SECONDS, max_entries=_MAX_ENTRIES)


def is_voice(context: ConversationSession) -> bool:
    return context.channel.upper() == "VOICE"


def was_injected(cache: ExpiringDict[str], conv_id: str, memory_context: str) -> bool:
    return conv_id in cache and cache[conv_id] == memory_context
