"""TAC connector for agents built in Conversational Agents (Dialogflow CX)."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import google.auth
import google.oauth2.credentials
from google.auth.transport.requests import AuthorizedSession

from tac.adapters import MemoryPromptBuilder
from tac.channels.sms import SMSChannel, SMSChannelConfig
from tac.channels.voice import VoiceChannel, VoiceChannelConfig
from tac.core.logging import get_logger
from tac.core.tac import TAC
from tac.models.session import ConversationSession
from tac.models.tac import TACMemoryResponse

logger = get_logger(__name__)

# Dialogflow CX session ids are capped at 36 characters, and the TAC
# conversation id is longer, so hash it into a stable UUID (exactly 36 chars).
# Same conversation -> same session id -> Dialogflow keeps the context.
_SESSION_NAMESPACE = uuid.UUID("b2d7f3a1-6c4e-4f2a-9e1b-3c5d7a8f0e21")
_DETECT_INTENT_TIMEOUT_S = 30


class ConversationalAgentsConnector:
    """
    Connector for agents built in Conversational Agents (Dialogflow CX).

    Dialogflow CX agents are invoked over the `detectIntent` REST API (v3):

        POST https://<location>-dialogflow.googleapis.com/v3/<agent>/sessions/<session>:detectIntent
        body: {"queryInput": {"text": {"text": "<message>"}, "languageCode": "en"}}
        reply: response["queryResult"]["responseMessages"][*]["text"]["text"]

    Works for both Playbook- and Flow-based agents — the runtime API is the same.
    Voice runs on Twilio ConversationRelay (text), so only text is exchanged; SMS
    is text too.

    Conversation history is kept server-side by Dialogflow, keyed by session id
    (default 30 min). This connector derives one stable session id per
    conversation (a UUID hash of the TAC conversation id, to fit Dialogflow's
    36-char session id limit) and reuses it on every turn, so Dialogflow keeps
    the context (no local history is built). TAC memory is injected whenever
    TAC supplies it.

    Args:
        tac: TAC instance for channel integration.
        agent_id: The Dialogflow CX agent resource name, e.g.
            `projects/<project>/locations/<location>/agents/<agent-id>`.
        language_code: Language code for queries (default "en").
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
        language_code: str = "en",
        sms_config: SMSChannelConfig | dict[str, Any] | None = None,
        voice_config: VoiceChannelConfig | dict[str, Any] | None = None,
    ) -> None:
        self.tac = tac
        self.agent_id = agent_id.rstrip("/")
        parts = self.agent_id.split("/")
        if (
            len(parts) < 6
            or parts[0] != "projects"
            or parts[2] != "locations"
            or parts[4] != "agents"
        ):
            raise ValueError(
                "agent_id must look like "
                "'projects/<project>/locations/<location>/agents/<agent-id>', "
                f"got {agent_id!r}"
            )
        self._project = parts[1]
        location = parts[3]
        self.language_code = language_code
        host = (
            "dialogflow.googleapis.com"
            if location == "global"
            else f"{location}-dialogflow.googleapis.com"
        )
        self._endpoint = f"https://{host}/v3/{{session}}:detectIntent"

        creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        self._http = AuthorizedSession(creds)
        # The Dialogflow API needs a quota project header only for user ADC
        # (e.g. `gcloud auth application-default login`). A service account
        # (Cloud Run) uses its own project as the quota project and setting the
        # header would require serviceusage.services.use — so only send it for
        # user credentials.
        self._quota_headers = (
            {"X-Goog-User-Project": self._project}
            if isinstance(creds, google.oauth2.credentials.Credentials)
            else {}
        )

        self.voice = VoiceChannel(tac=tac, config=voice_config)
        self.sms = SMSChannel(tac=tac, config=sms_config)

        self.tac.on_message_ready(self._handle_message)

        logger.debug("ConversationalAgentsConnector initialized", agent_id=self.agent_id)

    async def _handle_message(
        self,
        user_message: str,
        context: ConversationSession,
        memory_response: TACMemoryResponse | None,
    ) -> str | None:
        try:
            conv_id = context.conversation_id
            message = user_message

            # memory_mode already decides how often TAC supplies memory_response.
            if memory_response:
                memory_context = MemoryPromptBuilder.build(memory_response, context)
                if memory_context:
                    message = f"{memory_context}\n\n{user_message}"

            session = f"{self.agent_id}/sessions/{uuid.uuid5(_SESSION_NAMESPACE, conv_id)}"
            return await self._detect_intent(session, message)

        except Exception as e:
            logger.error(
                "Error processing message",
                conversation_id=context.conversation_id,
                error=str(e),
                exc_info=True,
            )
            return "I encountered an error processing your message. Please try again."

    async def _detect_intent(self, session: str, message: str) -> str:
        url = self._endpoint.format(session=session)
        payload = {"queryInput": {"text": {"text": message}, "languageCode": self.language_code}}

        def call() -> dict[str, Any]:
            response = self._http.post(
                url, headers=self._quota_headers, json=payload, timeout=_DETECT_INTENT_TIMEOUT_S
            )
            response.raise_for_status()
            return response.json()

        data = await asyncio.to_thread(call)
        return self._parse_response(data)

    def _parse_response(self, data: dict[str, Any]) -> str:
        """Extract the reply text from a Dialogflow CX DetectIntentResponse.

        Reply text lives in queryResult.responseMessages[].text.text (a list).
        """
        messages = data.get("queryResult", {}).get("responseMessages", [])
        texts = [t.strip() for m in messages for t in m.get("text", {}).get("text", [])]
        texts = [t for t in texts if t]
        if texts:
            return " ".join(texts)

        logger.warning(
            "No text found in Dialogflow CX detectIntent response",
            message_count=len(messages),
        )
        return "I didn't get a response from the agent. Please try again."
