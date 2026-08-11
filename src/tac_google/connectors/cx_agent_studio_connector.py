"""TAC connector for agents built in CX Agent Studio (Customer Engagement Suite)."""

from __future__ import annotations

import asyncio
from typing import Any

import google.auth
from google.auth.transport.requests import AuthorizedSession
from tac.adapters import MemoryPromptBuilder
from tac.channels.sms import SMSChannel, SMSChannelConfig
from tac.channels.voice import VoiceChannel, VoiceChannelConfig
from tac.core.logging import get_logger
from tac.core.tac import TAC
from tac.models.session import ConversationSession
from tac.models.tac import TACMemoryResponse

logger = get_logger(__name__)

_CES_HOST = "ces.googleapis.com"
_RUN_SESSION_TIMEOUT_S = 30


class CXAgentStudioConnector:
    """
    Connector for agents built in CX Agent Studio (Customer Engagement Suite).

    CX Agent Studio agents are not Agent Platform Runtime (reasoningEngines)
    resources and expose no query/stream_query SDK methods. They are invoked
    over the CES REST API (`ces.googleapis.com`), so this connector calls the
    text `runSession` method directly (v1):

        POST https://ces.googleapis.com/v1/<app>/sessions/<session>:runSession
        body: {"config": {"session": "<app>/sessions/<session>"},
               "inputs": [{"text": "<message>"}]}
        reply: response["outputs"][*]["text"]

    Voice runs on Twilio ConversationRelay, which does the speech-to-text and
    text-to-speech, so this connector only exchanges text with the agent — the
    CES native-audio streaming session is not used. SMS is text too.

    Conversation history is kept server-side by CES, keyed by session. This
    connector uses the TAC conversation id as the CES session id, so every turn
    of a conversation maps to the same session and CES maintains the context (no
    local history is built). TAC memory is injected only when it changes
    turn-to-turn (see `_maybe_tag_memory`).

    Args:
        tac: TAC instance for channel integration.
        agent_id: The CES agent (app) resource name, e.g.
            `projects/<project>/locations/<location>/apps/<app-id>`.
        sms_config: Optional SMS channel configuration (SMSChannelConfig or dict).
        voice_config: Optional Voice channel configuration (VoiceChannelConfig or dict).

    Attributes:
        voice: VoiceChannel instance for voice conversations.
        sms: SMSChannel instance for SMS conversations.
    """

    def __init__(
        self,
        tac: TAC,
        agent_id: str,
        sms_config: SMSChannelConfig | dict[str, Any] | None = None,
        voice_config: VoiceChannelConfig | dict[str, Any] | None = None,
    ) -> None:
        self.tac = tac
        self.agent_id = agent_id.rstrip("/")
        self._last_injected_memory: dict[str, str] = {}

        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        # Shared across calls for connection pooling. AuthorizedSession/Credentials
        # refresh isn't strictly guarded against concurrent refresh, but the
        # window is narrow (tokens live ~1h) and a resulting 401 is
        # auto-retried with a fresh refresh by AuthorizedSession itself.
        self._session = AuthorizedSession(creds)

        self.voice = VoiceChannel(tac=tac, config=voice_config)
        self.sms = SMSChannel(tac=tac, config=sms_config)

        self.tac.on_message_ready(self._handle_message)
        self.tac.on_conversation_ended(self._handle_conversation_ended)

        logger.debug("CXAgentStudioConnector initialized", agent_id=self.agent_id)

    async def _handle_message(
        self,
        user_message: str,
        context: ConversationSession,
        memory_response: TACMemoryResponse | None,
    ) -> str | None:
        try:
            conv_id = context.conversation_id
            message, memory_to_commit = self._maybe_tag_memory(
                user_message, context, memory_response
            )
            session = f"{self.agent_id}/sessions/{conv_id}"
            reply = await self._run_session(session, message)
            if memory_to_commit is not None:
                self._last_injected_memory[conv_id] = memory_to_commit
            return reply

        except Exception as e:
            logger.error(
                "Error processing message",
                conversation_id=context.conversation_id,
                error=str(e),
                exc_info=True,
            )
            return "I encountered an error processing your message. Please try again."

    def _maybe_tag_memory(
        self,
        user_message: str,
        context: ConversationSession,
        memory_response: TACMemoryResponse | None,
    ) -> tuple[str, str | None]:
        """Prepends memory to the message only when its content has changed.

        CES replays the full session history on every call, so re-prepending
        unchanged memory (memory_mode="once") would duplicate it each turn.

        Returns (message, memory_to_commit). memory_to_commit is None when
        nothing should change in self._last_injected_memory; otherwise the
        caller must commit it only after runSession succeeds — committing
        eagerly would mark memory as sent even if the call fails, silently
        dropping it on retry.
        """
        conv_id = context.conversation_id
        if not memory_response:
            return user_message, None

        memory_context = MemoryPromptBuilder.build(memory_response, context)
        if not memory_context or self._last_injected_memory.get(conv_id) == memory_context:
            return user_message, None

        return f"{memory_context}\n\n{user_message}", memory_context

    async def _run_session(self, session: str, message: str) -> str:
        url = f"https://{_CES_HOST}/v1/{session}:runSession"
        payload = {"config": {"session": session}, "inputs": [{"text": message}]}

        def call() -> dict[str, Any]:
            response = self._session.post(url, json=payload, timeout=_RUN_SESSION_TIMEOUT_S)
            response.raise_for_status()
            return response.json()

        data = await asyncio.to_thread(call)
        return self._parse_response(data)

    def _parse_response(self, data: dict[str, Any]) -> str:
        """Extract the reply text from a CES RunSessionResponse.

        The response carries an `outputs` list of SessionOutput objects; each is
        a union where the text turns hold a `text` field, e.g.
        {"outputs": [{"text": "..."}]}.
        """
        outputs = data.get("outputs") or []
        texts = [
            output["text"].strip()
            for output in outputs
            if isinstance(output, dict) and isinstance(output.get("text"), str)
        ]
        texts = [t for t in texts if t]
        if texts:
            return " ".join(texts)

        logger.warning(
            "No text found in CES runSession response",
            output_count=len(outputs),
            output_keys=[sorted(o.keys()) for o in outputs if isinstance(o, dict)],
        )
        return "I didn't get a response from the agent. Please try again."

    def _handle_conversation_ended(self, context: ConversationSession) -> None:
        self._last_injected_memory.pop(context.conversation_id, None)
