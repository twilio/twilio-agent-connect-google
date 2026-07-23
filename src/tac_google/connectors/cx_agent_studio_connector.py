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
    local history is built). TAC memory is injected into the first message.

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

        self._creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        self._started: set[str] = set()

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
            message = user_message

            # Inject TAC memory once, on the first message of the conversation.
            # CES keeps the rest of the history server-side by session.
            if conv_id not in self._started:
                self._started.add(conv_id)
                if memory_response:
                    memory_context = MemoryPromptBuilder.build(memory_response, context)
                    if memory_context:
                        message = f"{memory_context}\n\n{user_message}"

            session = f"{self.agent_id}/sessions/{conv_id}"
            return await self._run_session(session, message)

        except Exception as e:
            logger.error(
                "Error processing message",
                conversation_id=context.conversation_id,
                error=str(e),
                exc_info=True,
            )
            return "I encountered an error processing your message. Please try again."

    async def _run_session(self, session: str, message: str) -> str:
        url = f"https://{_CES_HOST}/v1/{session}:runSession"
        payload = {"config": {"session": session}, "inputs": [{"text": message}]}

        def call() -> dict[str, Any]:
            # A fresh AuthorizedSession per call: requests.Session isn't
            # guaranteed thread-safe, and this runs in a thread pool.
            with AuthorizedSession(self._creds) as http:
                response = http.post(url, json=payload, timeout=_RUN_SESSION_TIMEOUT_S)
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
            output["text"]
            for output in outputs
            if isinstance(output, dict) and isinstance(output.get("text"), str)
        ]
        if texts:
            return "".join(texts)

        logger.warning("No text found in CES runSession response", response=data)
        return "I didn't get a response from the agent. Please try again."

    def _handle_conversation_ended(self, context: ConversationSession) -> None:
        self._started.discard(context.conversation_id)
        logger.debug(
            "Cleaned up conversation", conversation_id=context.conversation_id
        )
