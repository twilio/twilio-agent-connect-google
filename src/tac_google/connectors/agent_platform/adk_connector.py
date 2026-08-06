"""Connector for ADK agents deployed on GCP Agent Platform Runtime (Agent Engine)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tac.adapters import MemoryPromptBuilder
from tac.channels.sms import SMSChannelConfig
from tac.channels.voice import VoiceChannelConfig
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
    per conversation and reused, with `async_stream_query()` invoked per
    message. `async_create_session`/`async_stream_query` are always registered
    for an ADK deployment (ADK's own AdkApp template hard-codes this in its
    `register_operations()`), so this connector calls them directly with no
    method-detection needed.

    TAC memory is injected on every message, wrapped in `<MEMORY>...</MEMORY>`
    ahead of the user's text (wrapped in `<USER_MESSAGE>...</USER_MESSAGE>`),
    since ADK's `stream_query`/`async_stream_query` API has only one content
    channel (`message`) — there is no separate instructions/context parameter.

    Args:
        tac: TAC instance for channel integration
        agent: Deployed ADK agent instance, from
            `vertexai.Client().agent_engines.get(name=...)`.
        sms_config: Optional SMS channel configuration (SMSChannelConfig or dict)
        voice_config: Optional Voice channel configuration (VoiceChannelConfig or dict)

    Attributes:
        voice: VoiceChannel instance for voice conversations
        sms: SMSChannel instance for SMS conversations

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
            sms_channel=connector.sms
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
    ) -> None:
        self.agent = agent
        self.adk_sessions_created: set[str] = set()
        super().__init__(tac, sms_config, voice_config)

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
            # async_create_session is bound at runtime by _register_api_methods()
            # from the deployed agent's class_methods spec; static stubs don't know it.
            await self.agent.async_create_session(user_id=user_id, session_id=session_id)  # type: ignore[attr-defined]
            self.adk_sessions_created.add(conv_id)

        if memory_response:
            memory_context = MemoryPromptBuilder.build(memory_response, context)
            if memory_context:
                user_message = self._tag_message(user_message, memory_context)

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
        return self._parse_event_stream_text(events)

    def _handle_conversation_ended(self, context: ConversationSession) -> None:
        self.adk_sessions_created.discard(context.conversation_id)
