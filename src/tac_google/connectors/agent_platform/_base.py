"""Shared plumbing for Agent Engine connectors (channel wiring, error handling)."""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, Any

import google.auth
from google.auth.transport.requests import AuthorizedSession
from tac.adapters import MemoryPromptBuilder
from tac.channels.sms import SMSChannel, SMSChannelConfig
from tac.channels.voice import VoiceChannel, VoiceChannelConfig
from tac.core.logging import get_logger
from tac.core.tac import TAC
from tac.models.session import ConversationSession
from tac.models.tac import TACMemoryResponse

if TYPE_CHECKING:
    from vertexai._genai.types.common import AgentEngine

logger = get_logger(__name__)


class AgentEngineConnectorBase:
    """Base class wiring TAC channels to a single `_invoke_agent` hook.

    Subclasses implement `_invoke_agent` for their specific deployment's
    invocation contract, and may override `_handle_conversation_ended` to
    clean up any per-conversation state they keep.
    """

    def __init__(
        self,
        tac: TAC,
        sms_config: SMSChannelConfig | dict[str, Any] | None = None,
        voice_config: VoiceChannelConfig | dict[str, Any] | None = None,
    ) -> None:
        self.tac = tac
        self.voice = VoiceChannel(tac=tac, config=voice_config)
        self.sms = SMSChannel(tac=tac, config=sms_config)

        self._last_injected_memory: dict[str, str] = {}
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        self._agent_engine_http = AuthorizedSession(creds)

        self.tac.on_message_ready(self._handle_message)
        self.tac.on_conversation_ended(self._handle_conversation_ended)

    async def _invoke_agent(
        self,
        user_message: str,
        context: ConversationSession,
        memory_response: TACMemoryResponse | None,
    ) -> str:
        raise NotImplementedError

    async def _handle_message(
        self,
        user_message: str,
        context: ConversationSession,
        memory_response: TACMemoryResponse | None,
    ) -> str | None:
        try:
            return await self._invoke_agent(user_message, context, memory_response)
        except Exception as e:
            logger.error(
                "Error processing message",
                conversation_id=context.conversation_id,
                error=str(e),
                exc_info=True,
            )
            return "I encountered an error processing your message. Please try again."

    def _handle_conversation_ended(self, context: ConversationSession) -> None:
        self._last_injected_memory.pop(context.conversation_id, None)

    def _maybe_tag_message(
        self,
        user_message: str,
        context: ConversationSession,
        memory_response: TACMemoryResponse | None,
    ) -> tuple[str, str | None]:
        """Injects memory only when it has changed since the last turn.

        ADK and Agent Studio persist every sent message in the session and
        replay the full history on each call, so re-tagging unchanged memory
        (memory_mode="once" returns the same cached memory every turn) would
        duplicate it once per turn already in history. memory_mode="always"
        re-queries per turn and typically returns different content, so it
        keeps getting tagged.

        Returns (message, memory_to_commit). memory_to_commit is None when
        nothing should change in self._last_injected_memory; otherwise the
        caller must commit it only after the message is actually sent —
        committing eagerly would mark memory as sent even if the call fails,
        silently dropping it on retry.
        """
        conv_id = context.conversation_id
        if not memory_response:
            return user_message, None

        memory_context = MemoryPromptBuilder.build(memory_response, context)
        if not memory_context or self._last_injected_memory.get(conv_id) == memory_context:
            return user_message, None

        return self._tag_message(user_message, memory_context), memory_context

    @staticmethod
    def _agent_engine_base_url(agent: AgentEngine) -> str:
        """Builds the Agent Engine REST base URL (.../reasoningEngines/ID) for a deployed agent."""
        if agent.api_resource is None or agent.api_resource.name is None:
            raise ValueError("agent.api_resource.name is unset — pass a fetched, deployed agent")
        resource_name = agent.api_resource.name  # projects/P/locations/L/reasoningEngines/ID
        location = resource_name.split("/")[3]
        return f"https://{location}-aiplatform.googleapis.com/v1/{resource_name}"

    async def _create_session(self, sessions_url: str, session_id: str, user_id: str) -> None:
        """Creates an Agent Engine session over REST, tolerating an already-exists error.

        Called directly over REST rather than through SDK-bound methods: the
        SDK's `async_create_session` wraps every Reasoning Engine failure
        (including a duplicate session ID) in the same generic 400 "Internal
        Server Error" with no way to tell them apart. The Sessions REST API
        is also a plain 400 (INVALID_ARGUMENT, not 409) for a duplicate ID,
        but with a specific message — "Session with user-provided ID ...
        already exists." — confirmed empirically against a deployed agent,
        and distinct from other 400s (e.g. an invalid session_id format
        returns a different message). Session IDs are deterministic (derived
        from conv_id), so a process restart or scale event can lose in-memory
        "already created" tracking while the session itself still exists —
        this is what lets that recover instead of erroring every turn after.
        """
        loop = asyncio.get_running_loop()

        def create_session() -> None:
            response = self._agent_engine_http.post(
                f"{sessions_url}?sessionId={session_id}",
                json={"userId": user_id},
            )
            if response.status_code == 400 and "already exists" in response.text:
                return
            response.raise_for_status()

        await loop.run_in_executor(None, create_session)

    @staticmethod
    def _sanitize_session_id(conv_id: str) -> str:
        """Agent Engine session IDs allow only lowercase letters, digits, and
        hyphens (first/last char must be alphanumeric) — TAC's conversation_id
        uses underscores (e.g. "conv_conversation_..."), so it isn't a valid
        session_id as-is.
        """
        sanitized = re.sub(r"[^a-z0-9-]", "-", conv_id.lower())
        return sanitized.strip("-")

    @staticmethod
    def _tag_message(user_message: str, memory_context: str) -> str:
        """Wraps memory ahead of the user's text in explicit delimiters.

        Both ADK and Agent Studio deployments only expose one content channel
        per call (no separate instructions/context parameter).
        """
        return (
            f"<MEMORY>\n{memory_context}\n</MEMORY>\n\n"
            f"<USER_MESSAGE>\n{user_message}\n</USER_MESSAGE>"
        )

    def _parse_event_stream_text(self, events: list[dict[str, Any]]) -> str:
        """Extracts the final response text from a stream of ADK-shaped events.

        Streamed events include partial chunks and tool-call/tool-response
        events; the final response is the last non-partial event that carries
        text content. Shared by both connectors: the ADK connector's
        `async_stream_query` events and the Studio connector's REST
        `streamQuery` events use this same event shape.
        """
        for event in reversed(events):
            if event.get("partial"):
                continue
            for part in event.get("content", {}).get("parts", []):
                if "text" in part:
                    return str(part["text"])

        return "I didn't get a response from the agent. Please try again."
