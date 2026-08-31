"""TAC connector for agents built in Conversational Agents (Dialogflow CX)."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import google.auth
import google.oauth2.credentials
from google.auth.transport.requests import AuthorizedSession
from tac.adapters import MemoryPromptBuilder
from tac.channels.chat import ChatChannelConfig
from tac.channels.rcs import RCSChannelConfig
from tac.channels.sms import SMSChannelConfig
from tac.channels.voice import VoiceChannel, VoiceChannelConfig
from tac.channels.whatsapp import WhatsAppChannelConfig
from tac.core.logging import get_logger
from tac.core.tac import TAC
from tac.models.session import ConversationSession
from tac.models.tac import TACMemoryResponse

from tac_google.connectors._channels import ConnectorChannels

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
    the context (no local history is built). Conversation Memory is injected
    only when it changes turn-to-turn (see `_maybe_tag_memory`).

    Args:
        tac: TAC instance for channel integration.
        agent_id: The Dialogflow CX agent resource name, e.g.
            `projects/<project>/locations/<location>/agents/<agent-id>`.
        language_code: Language code for queries (default "en").
        sms_config, voice_config, chat_config: each is a channel config; the
            channel is always built.
        rcs_config, whatsapp_config: channel config — tuning only. The
            channel is built whenever its Twilio resource is configured
            (TWILIO_RCS_SENDER_ID / TWILIO_WHATSAPP_NUMBER), regardless of
            this argument.

    Attributes:
        voice, sms, chat: the corresponding channel instance.
        rcs, whatsapp: the corresponding channel instance, or None if its
            Twilio resource isn't configured.
    """

    def __init__(
        self,
        tac: TAC,
        agent_id: str,
        language_code: str = "en",
        sms_config: SMSChannelConfig | dict[str, Any] | None = None,
        voice_config: VoiceChannelConfig | dict[str, Any] | None = None,
        rcs_config: RCSChannelConfig | dict[str, Any] | None = None,
        whatsapp_config: WhatsAppChannelConfig | dict[str, Any] | None = None,
        chat_config: ChatChannelConfig | dict[str, Any] | None = None,
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
        self._last_injected_memory: dict[str, str] = {}
        self.language_code = language_code
        host = (
            "dialogflow.googleapis.com"
            if location == "global"
            else f"{location}-dialogflow.googleapis.com"
        )
        self._endpoint = f"https://{host}/v3/{{session}}:detectIntent"

        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
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
        channels = ConnectorChannels(
            tac,
            sms_config=sms_config,
            chat_config=chat_config,
            rcs_config=rcs_config,
            whatsapp_config=whatsapp_config,
        )
        self.sms = channels.sms
        self.rcs = channels.rcs
        self.whatsapp = channels.whatsapp
        self.chat = channels.chat

        self.tac.on_message_ready(self._handle_message)
        self.tac.on_conversation_ended(self._handle_conversation_ended)

        logger.debug("ConversationalAgentsConnector initialized", agent_id=self.agent_id)

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
            session = f"{self.agent_id}/sessions/{uuid.uuid5(_SESSION_NAMESPACE, conv_id)}"
            reply = await self._detect_intent(session, message)
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

        Dialogflow CX replays the full session history on every call
        (confirmed empirically), so re-prepending unchanged memory
        (memory_mode="once") would duplicate it each turn.

        Returns (message, memory_to_commit). memory_to_commit is None when
        nothing should change in self._last_injected_memory; otherwise the
        caller must commit it only after detectIntent succeeds — committing
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

    async def _detect_intent(self, session: str, message: str) -> str:
        url = self._endpoint.format(session=session)
        payload: dict[str, Any] = {
            "queryInput": {"text": {"text": message}, "languageCode": self.language_code}
        }

        def call() -> dict[str, Any]:
            response = self._http.post(
                url, headers=self._quota_headers, json=payload, timeout=_DETECT_INTENT_TIMEOUT_S
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return data

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

    def _handle_conversation_ended(self, context: ConversationSession) -> None:
        self._last_injected_memory.pop(context.conversation_id, None)
