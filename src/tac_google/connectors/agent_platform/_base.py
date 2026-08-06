"""Shared plumbing for Agent Engine connectors (channel wiring, error handling)."""

from __future__ import annotations

import re
from typing import Any

from tac.channels.sms import SMSChannel, SMSChannelConfig
from tac.channels.voice import VoiceChannel, VoiceChannelConfig
from tac.core.logging import get_logger
from tac.core.tac import TAC
from tac.models.session import ConversationSession
from tac.models.tac import TACMemoryResponse

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
        pass

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
        per call (no separate instructions/context parameter), so memory is
        tagged and re-sent fresh on every message rather than stored — this
        keeps it current for memory_mode="always" without duplicating it in
        the session's stored history.
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
