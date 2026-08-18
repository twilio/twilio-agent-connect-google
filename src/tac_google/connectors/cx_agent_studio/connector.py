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
from tac.models.handoff import PendingHandoffData
from tac.models.session import ConversationSession
from tac.models.tac import TACMemoryResponse

from tac_google.connectors.cx_agent_studio.voice_s2s import VoiceS2SChannel, VoiceS2SConfig

logger = get_logger(__name__)

_CES_HOST = "ces.googleapis.com"
_RUN_SESSION_TIMEOUT_S = 30


class CXAgentStudioConnector:
    """
    Connector for agents built in CX Agent Studio (Customer Engagement Suite).

    CX Agent Studio agents aren't Agent Platform Runtime (reasoningEngines)
    resources and expose no query/stream_query SDK methods, so this connector
    calls the CES REST API's text `runSession` method directly (v1):

        POST https://ces.googleapis.com/v1/<app>/sessions/<session>:runSession
        body: {"config": {"session": "<app>/sessions/<session>"},
               "inputs": [{"text": "<message>"}]}
        reply: response["outputs"][*]["text"]

    Text is all this connector exchanges with the agent, for both SMS and
    (ConversationRelay) voice — the CES native-audio streaming session isn't
    used here.

    Conversation history is kept server-side by CES: the TAC conversation id
    doubles as the CES session id, so every turn lands in the same session
    and no local history is built. TAC memory is injected only when it
    changes turn-to-turn (see `_maybe_tag_memory`).

    Every CX Agent Studio agent has an `end_session` tool attached by
    default, letting the model decide on its own when a call is done — see
    `_handle_end_session`.

    Args:
        tac: TAC instance for channel integration.
        agent_id: The CES agent (app) resource name, e.g.
            `projects/<project>/locations/<location>/apps/<app-id>`.
        sms_config: Optional SMS channel configuration (SMSChannelConfig or dict).
        voice_config: Pass a `VoiceChannelConfig` for ConversationRelay voice
            (builds `self.voice_cascaded`) or a `VoiceS2SConfig` for native
            speech-to-speech voice (builds `self.voice_s2s`) — the config
            type decides which channel gets built, which is why a plain dict
            isn't accepted here. Omit (None) for no voice channel.

    Attributes:
        voice_cascaded: VoiceChannel for ConversationRelay voice, or None.
        voice_s2s: VoiceS2SChannel for native speech-to-speech voice, or None.
        voice: Whichever of the two above actually got built (or None) — for
            callers that don't care which voice approach is active, e.g. a
            server wiring up `voice_channel=connector.voice`.
        sms: SMSChannel instance for SMS conversations.
    """

    def __init__(
        self,
        tac: TAC,
        agent_id: str,
        sms_config: SMSChannelConfig | dict[str, Any] | None = None,
        voice_config: VoiceChannelConfig | VoiceS2SConfig | None = None,
    ) -> None:
        self.tac = tac
        self.agent_id = agent_id.rstrip("/")
        self._last_injected_memory: dict[str, str] = {}

        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        # Shared across calls for connection pooling. Not guarded against
        # concurrent token refresh, but AuthorizedSession auto-retries a
        # resulting 401 with a fresh refresh.
        self._session = AuthorizedSession(creds)

        self.sms = SMSChannel(tac=tac, config=sms_config)

        self.voice_cascaded: VoiceChannel | None = None
        self.voice_s2s: VoiceS2SChannel | None = None
        self.voice: VoiceChannel | VoiceS2SChannel | None = None
        if isinstance(voice_config, VoiceS2SConfig):
            self.voice_s2s = VoiceS2SChannel(tac=tac, agent_id=self.agent_id, config=voice_config)
            self.voice = self.voice_s2s
        elif isinstance(voice_config, VoiceChannelConfig):
            self.voice_cascaded = VoiceChannel(tac=tac, config=voice_config)
            self.voice = self.voice_cascaded
        elif voice_config is not None:
            raise TypeError(
                f"voice_config must be a VoiceChannelConfig, a VoiceS2SConfig, or None — "
                f"got {type(voice_config).__name__}."
            )

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
            reply = await self._run_session(session, message, context)
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
        caller must commit it only after runSession succeeds, so a failed
        call doesn't silently mark memory as sent.
        """
        conv_id = context.conversation_id
        if not memory_response:
            return user_message, None

        memory_context = MemoryPromptBuilder.build(memory_response, context)
        if not memory_context or self._last_injected_memory.get(conv_id) == memory_context:
            return user_message, None

        return f"{memory_context}\n\n{user_message}", memory_context

    async def _run_session(self, session: str, message: str, context: ConversationSession) -> str:
        url = f"https://{_CES_HOST}/v1/{session}:runSession"
        payload: dict[str, Any] = {"config": {"session": session}, "inputs": [{"text": message}]}

        def call() -> dict[str, Any]:
            response = self._session.post(url, json=payload, timeout=_RUN_SESSION_TIMEOUT_S)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return data

        data = await asyncio.to_thread(call)
        self._handle_end_session(data, context)
        return self._parse_response(data)

    @staticmethod
    def _find_end_session_metadata(outputs: list[Any]) -> dict[str, Any] | None:
        """Returns the `endSession.metadata` dict from wherever it appears in `outputs`.

        `outputs` can hold multiple entries per turn, and the API doesn't
        specify where `endSession` lands among them, so this scans the whole
        list rather than assuming it's outputs[-1].
        """
        for output in outputs:
            if not isinstance(output, dict):
                continue
            end_session = output.get("endSession")
            if isinstance(end_session, dict):
                metadata = end_session.get("metadata")
                return metadata if isinstance(metadata, dict) else {}
        return None

    def _handle_end_session(self, data: dict[str, Any], context: ConversationSession) -> None:
        """Ends the call gracefully if CES's `end_session` tool fired this turn.

        The model decides on its own when to call `end_session` (plain
        completion or escalation — metadata.session_escalated distinguishes
        the two). Once it fires, the CES session is dead: any further turn
        against the same session_id gets rejected with "Session has already
        ended", so without this the conversation would error on every
        subsequent turn until the caller gives up.

        Setting context.pending_handoff_data is the only lever TAC exposes
        for ending a call — it makes VoiceChannel send ConversationRelay's
        WS "end" message after this turn's reply. No action_url is
        configured for this deploy, so Twilio just hangs up regardless of
        session_escalated; handoff_data is required by the model but unread,
        so it's a fixed placeholder.
        """
        outputs = data.get("outputs") or []
        metadata = self._find_end_session_metadata(outputs)
        if metadata is None:
            return

        logger.info(
            "CES ended the session — hanging up",
            conversation_id=context.conversation_id,
            session_escalated=metadata.get("session_escalated"),
            reason=metadata.get("reason"),
        )
        context.pending_handoff_data = PendingHandoffData(handoffData="call_ended")

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

        # end_session commonly fires with no text at all — "I didn't get a
        # response" would be a confusing thing to say as the call ends.
        if self._find_end_session_metadata(outputs) is not None:
            return "Thank you for calling. Goodbye!"

        logger.warning(
            "No text found in CES runSession response",
            output_count=len(outputs),
            output_keys=[sorted(o.keys()) for o in outputs if isinstance(o, dict)],
        )
        return "I didn't get a response from the agent. Please try again."

    def _handle_conversation_ended(self, context: ConversationSession) -> None:
        self._last_injected_memory.pop(context.conversation_id, None)
