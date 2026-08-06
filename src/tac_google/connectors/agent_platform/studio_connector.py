"""Connector for Agent Studio apps deployed on GCP Agent Platform Runtime (Agent Engine)."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

import google.auth
from google.auth.transport.requests import AuthorizedSession
from tac.adapters import MemoryPromptBuilder
from tac.channels.sms import SMSChannelConfig
from tac.channels.voice import VoiceChannelConfig
from tac.core.tac import TAC
from tac.models.session import ConversationSession
from tac.models.tac import TACMemoryResponse

from tac_google.connectors.agent_platform._base import AgentEngineConnectorBase

if TYPE_CHECKING:
    from vertexai._genai.types.common import AgentEngine

__all__ = ["StudioAgentEngineConnector"]


class StudioAgentEngineConnector(AgentEngineConnectorBase):
    """
    Connector for a source-code app deployed from the Agent Studio UI.

    Agent Studio apps are ADK apps under the hood (Studio's own "Get Code"
    feature generates a standard `google.adk` `LlmAgent`), but they aren't
    registered with `query`/`stream_query` methods the SDK can bind to (the
    SDK doesn't detect class methods for them at all), so this connector
    talks to them directly over REST instead of through SDK-bound methods:
    - `POST .../sessions?sessionId=...` to create a session once per
      conversation (confirmed empirically against a deployed Studio agent —
      this is the same Agent Engine Sessions API the ADK connector uses via
      the SDK, just called directly).
    - `POST .../:streamQuery` with `class_method: "async_stream_query"` to
      invoke it, passing only this turn's message and the `session_id` —
      same as the ADK connector, ADK reconstructs the full history from the
      session's stored events on every call, so there's no local
      conversation history to maintain here either.

    TAC memory is injected on every message, wrapped in `<MEMORY>...</MEMORY>`
    ahead of the user's text (wrapped in `<USER_MESSAGE>...</USER_MESSAGE>`),
    for the same reason as the ADK connector: there's no separate
    instructions/context parameter, only the one `message` channel.

    Args:
        tac: TAC instance for channel integration
        agent: Deployed Studio agent instance, from
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
        from tac_google.connectors import StudioAgentEngineConnector

        client = vertexai.Client(project="my-project", location="us-central1")
        tac = TAC(config=TACConfig.from_env())

        agent = client.agent_engines.get(
            name="projects/my-project/locations/us-central1/reasoningEngines/123456"
        )

        connector = StudioAgentEngineConnector(tac=tac, agent=agent)

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
        self.studio_sessions_created: set[str] = set()

        if agent.api_resource is None or agent.api_resource.name is None:
            raise ValueError("agent.api_resource.name is unset — pass a fetched, deployed agent")
        resource_name = agent.api_resource.name  # projects/P/locations/L/reasoningEngines/ID
        location = resource_name.split("/")[3]
        base_url = f"https://{location}-aiplatform.googleapis.com/v1/{resource_name}"
        self._sessions_url = f"{base_url}/sessions"
        self._stream_query_url = f"{base_url}:streamQuery"
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        self._studio_session = AuthorizedSession(creds)

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
        loop = asyncio.get_event_loop()

        if conv_id not in self.studio_sessions_created:

            def create_session() -> None:
                response = self._studio_session.post(
                    f"{self._sessions_url}?sessionId={session_id}",
                    json={"userId": user_id},
                )
                response.raise_for_status()

            await loop.run_in_executor(None, create_session)
            self.studio_sessions_created.add(conv_id)

        if memory_response:
            memory_context = MemoryPromptBuilder.build(memory_response, context)
            if memory_context:
                user_message = self._tag_message(user_message, memory_context)

        def run_stream_query() -> list[dict[str, Any]]:
            response = self._studio_session.post(
                self._stream_query_url,
                json={
                    "class_method": "async_stream_query",
                    "input": {
                        "user_id": user_id,
                        "session_id": session_id,
                        "message": user_message,
                    },
                },
            )
            response.raise_for_status()
            return self._parse_studio_events(response.text)

        events = await loop.run_in_executor(None, run_stream_query)
        return self._parse_event_stream_text(events)

    def _parse_studio_events(self, raw: str) -> list[dict[str, Any]]:
        """Parse a streamQuery REST body (concatenated JSON events) into a list."""
        decoder = json.JSONDecoder()
        idx, events = 0, []
        while idx < len(raw):
            while idx < len(raw) and raw[idx] in " \t\r\n,[]":
                idx += 1
            if idx >= len(raw):
                break
            event, idx = decoder.raw_decode(raw, idx)
            events.append(event)
        return events

    def _handle_conversation_ended(self, context: ConversationSession) -> None:
        self.studio_sessions_created.discard(context.conversation_id)
