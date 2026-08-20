"""Connector for ADK agents deployed on GCP Agent Platform Runtime (Agent Engine)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tac.channels.chat import ChatChannelConfig
from tac.channels.rcs import RCSChannelConfig
from tac.channels.sms import SMSChannelConfig
from tac.channels.voice import VoiceChannelConfig
from tac.channels.whatsapp import WhatsAppChannelConfig
from tac.core.tac import TAC
from tac.models.session import ConversationSession
from tac.models.tac import TACMemoryResponse

from tac_google.connectors.agent_platform._base import AgentEngineConnectorBase

if TYPE_CHECKING:
    from vertexai._genai.types.common import AgentEngine

__all__ = ["ADKAgentEngineConnector"]


class ADKAgentEngineConnector(AgentEngineConnectorBase):
    """
    Connector for an ADK agent deployed on GCP Agent Platform Runtime (Agent Engine).

    ADK deployments are session-based and streaming: a session is created once
    per conversation (over REST, to get a clean "already exists" signal — see
    `AgentEngineConnectorBase._create_session`) and reused, with
    `async_stream_query()` invoked per message via the SDK — `async_stream_query`
    is always registered for an ADK deployment (ADK's own AdkApp template
    hard-codes this in its `register_operations()`), so no method-detection
    is needed for it.

    TAC memory is injected on every message, wrapped in `<MEMORY>...</MEMORY>`
    ahead of the user's text (wrapped in `<USER_MESSAGE>...</USER_MESSAGE>`),
    since ADK's `stream_query`/`async_stream_query` API has only one content
    channel (`message`) — there is no separate instructions/context parameter.

    Args:
        tac: TAC instance for channel integration
        agent: Deployed ADK agent instance, from
            `vertexai.Client().agent_engines.get(name=...)`.
        sms_config, voice_config, rcs_config, whatsapp_config, chat_config: each
            is a channel config or None (default) to disable that channel.

    Attributes:
        voice, sms, rcs, whatsapp, chat: the corresponding channel instance,
            or None if disabled.
        messaging: All enabled messaging channels above, as a list — hand
            this straight to a server's `messaging_channels=`.

    Example:
        ```python
        import vertexai
        from tac import TAC, TACConfig
        from tac.server import TACFastAPIServer
        from tac_google.connectors import ADKAgentEngineConnector

        client = vertexai.Client(project="my-project", location="us-central1")
        tac = TAC(config=TACConfig.from_env())

        agent = client.agent_engines.get(
            name="projects/my-project/locations/us-central1/reasoningEngines/123456"
        )

        connector = ADKAgentEngineConnector(tac=tac, agent=agent)

        server = TACFastAPIServer(
            tac=tac,
            voice_channel=connector.voice,
            messaging_channels=connector.messaging
        )
        server.start()
        ```
    """

    def __init__(
        self,
        tac: TAC,
        agent: AgentEngine,
        sms_config: SMSChannelConfig | dict[str, Any] | None = None,
        voice_config: VoiceChannelConfig | dict[str, Any] | None = None,
        rcs_config: RCSChannelConfig | dict[str, Any] | None = None,
        whatsapp_config: WhatsAppChannelConfig | dict[str, Any] | None = None,
        chat_config: ChatChannelConfig | dict[str, Any] | None = None,
    ) -> None:
        self.agent = agent
        self.adk_sessions_created: set[str] = set()
        super().__init__(
            tac,
            sms_config,
            voice_config,
            rcs_config=rcs_config,
            whatsapp_config=whatsapp_config,
            chat_config=chat_config,
        )
        self._sessions_url = f"{self._agent_engine_base_url(agent)}/sessions"

    async def _invoke_agent(
        self,
        user_message: str,
        context: ConversationSession,
        memory_response: TACMemoryResponse | None,
    ) -> str:
        conv_id = context.conversation_id
        session_id = self._sanitize_session_id(conv_id)
        user_id = context.profile_id or "anonymous"

        if conv_id not in self.adk_sessions_created:
            await self._create_session(self._sessions_url, session_id, user_id)
            self.adk_sessions_created.add(conv_id)

        user_message, memory_to_commit = self._maybe_tag_message(
            user_message, context, memory_response
        )

        # Only this turn's message is sent — no local conversation history to
        # maintain. ADK reconstructs the full history from the session's
        # stored events (by session_id) and feeds it to the model on every
        # call (Agent.include_contents defaults to "default" = full history).
        events = [
            event
            async for event in self.agent.async_stream_query(  # type: ignore[attr-defined]
                message=user_message,
                user_id=user_id,
                session_id=session_id,
            )
        ]
        if memory_to_commit is not None:
            self._last_injected_memory[conv_id] = memory_to_commit
        return self._parse_event_stream_text(events)

    def _handle_conversation_ended(self, context: ConversationSession) -> None:
        super()._handle_conversation_ended(context)
        self.adk_sessions_created.discard(context.conversation_id)
