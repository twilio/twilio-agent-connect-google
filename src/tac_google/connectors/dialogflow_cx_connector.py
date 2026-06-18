"""Dialogflow CX connector with playbook support and channel management."""

from __future__ import annotations

import asyncio
from typing import Any

from google.cloud.dialogflowcx_v3.services.sessions import SessionsClient
from tac.adapters import MemoryPromptBuilder
from tac.channels.sms import SMSChannel, SMSChannelConfig
from tac.channels.voice import VoiceChannel, VoiceChannelConfig
from tac.core.logging import get_logger
from tac.core.tac import TAC
from tac.models.session import ConversationSession
from tac.models.tac import TACMemoryResponse


logger = get_logger(__name__)


class DialogflowCXConnector:
    """
    Connector for Dialogflow CX with playbook support and multi-channel integration.

    Connects to Dialogflow CX agents (including playbook-based generative agents)
    deployed on Google Cloud. Manages session state, memory injection, and supports
    both Voice and SMS channels through Twilio Agent Connect.

    Dialogflow CX manages conversation state on the server side, so this connector
    only needs to pass messages and session IDs - no local history management required.

    Args:
        tac: TAC instance for channel integration
        client: Dialogflow CX SessionsClient instance
        agent: Agent path (e.g., 'projects/my-project/locations/us-central1/agents/abc-123')
        language_code: Language code (default: 'en')
        sms_config: Optional SMS channel configuration (SMSChannelConfig or dict)
        voice_config: Optional Voice channel configuration (VoiceChannelConfig or dict)

    Attributes:
        voice: VoiceChannel instance for voice conversations
        sms: SMSChannel instance for SMS conversations

    Example:
        ```python
        from tac import TAC, TACConfig
        from tac.server import TACFastAPIServer
        from tac_google.connectors import DialogflowCXConnector
        from google.api_core.client_options import ClientOptions
        from google.cloud.dialogflowcx_v3 import SessionsClient

        tac = TAC(config=TACConfig.from_env())

        location = "us-central1"
        agent = "projects/my-project/locations/us-central1/agents/abc-123"

        api_endpoint = f"{location}-dialogflow.googleapis.com:443"
        client = SessionsClient(client_options=ClientOptions(api_endpoint=api_endpoint))

        connector = DialogflowCXConnector(
            tac=tac,
            client=client,
            agent=agent,
        )

        server = TACFastAPIServer(
            tac=tac,
            voice_channel=connector.voice,
            messaging_channels=[connector.sms],
        )
        server.start()
        ```

    Environment Variables:
        GOOGLE_CLOUD_PROJECT: GCP project ID
        GOOGLE_CLOUD_LOCATION: GCP location
        DIALOGFLOW_CX_AGENT_ID: Agent ID
        DIALOGFLOW_CX_LANGUAGE_CODE: Language code (optional, default: 'en')
    """

    def __init__(
        self,
        tac: TAC,
        client: SessionsClient,
        agent: str,
        language_code: str = "en",
        sms_config: SMSChannelConfig | dict[str, Any] | None = None,
        voice_config: VoiceChannelConfig | dict[str, Any] | None = None,
    ) -> None:
        self.tac = tac
        self.client = client
        self.agent = agent
        self.language_code = language_code

        # Initialize channels
        self.voice = VoiceChannel(tac=tac, config=voice_config)
        self.sms = SMSChannel(tac=tac, config=sms_config)

        # Register event handlers
        self.tac.on_message_ready(self._handle_message)
        self.tac.on_conversation_ended(self._handle_conversation_ended)

        logger.debug("DialogflowCXConnector initialized", agent=agent)

    async def _handle_message(
        self,
        user_message: str,
        context: ConversationSession,
        memory_response: TACMemoryResponse | None,
    ) -> str | None:
        """Handle incoming messages from TAC."""
        try:
            session_path = f"{self.agent}/sessions/{context.conversation_id}"

            # Inject memory if available (TAC only sends on first message)
            message_to_send = user_message
            if memory_response:
                memory_context = MemoryPromptBuilder.build(memory_response, context)
                if memory_context:
                    message_to_send = f"[System Context]\n{memory_context}\n\n[User Message]\n{user_message}"

            # Call Dialogflow CX (run in executor to avoid blocking)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.detect_intent(
                    request={
                        "session": session_path,
                        "query_input": {
                            "text": {"text": message_to_send},
                            "language_code": self.language_code,
                        },
                    }
                ),
            )

            # Extract response text
            response_text = self._parse_response(response)

            # Send response to appropriate channel
            if context.channel == "voice" and self.voice:
                await self.voice.send_response(
                    context.conversation_id, response_text, role="assistant"
                )
            elif context.channel == "sms" and self.sms:
                await self.sms.send_response(
                    context.conversation_id, response_text, role="assistant"
                )
            else:
                logger.error(
                    f"No channel handler for {context.channel}",
                    conversation_id=context.conversation_id,
                )

        except Exception as e:
            logger.error(
                "Error processing message with Dialogflow CX",
                conversation_id=context.conversation_id,
                error=str(e),
                exc_info=True,
            )
            error_msg = "I encountered an error processing your message. Please try again."
            if context.channel == "voice" and self.voice:
                await self.voice.send_response(
                    context.conversation_id, error_msg, role="assistant"
                )
            elif context.channel == "sms" and self.sms:
                await self.sms.send_response(
                    context.conversation_id, error_msg, role="assistant"
                )

        return None

    def _parse_response(self, response: Any) -> str:
        """
        Parse Dialogflow CX response to extract text.

        Args:
            response: DetectIntentResponse from Dialogflow CX

        Returns:
            Response text string
        """
        # Extract response messages
        if hasattr(response, "query_result") and response.query_result:
            query_result = response.query_result

            # Combine all text response messages
            response_messages = []
            for msg in query_result.response_messages:
                if hasattr(msg, "text") and msg.text:
                    response_messages.extend(msg.text.text)

            if response_messages:
                return "\n".join(response_messages)

            # Fallback to fulfillment text if no response messages
            if hasattr(query_result, "fulfillment_text"):
                return query_result.fulfillment_text

        return "I'm sorry, I couldn't process that request."

    def _handle_conversation_ended(self, context: ConversationSession) -> None:
        """Clean up when conversation ends."""
        logger.debug(
            "Conversation ended",
            conversation_id=context.conversation_id,
        )
