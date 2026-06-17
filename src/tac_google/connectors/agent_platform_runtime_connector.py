"""GCP Agent Platform Runtime connector with channel management."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from tac.adapters import MemoryPromptBuilder
from tac.channels.sms import SMSChannel, SMSChannelConfig
from tac.channels.voice import VoiceChannel, VoiceChannelConfig
from tac.core.logging import get_logger
from tac.core.tac import TAC
from tac.models.session import ConversationSession
from tac.models.tac import TACMemoryResponse

if TYPE_CHECKING:
    from vertexai.preview.reasoning_engines import ReasoningEngine

logger = get_logger(__name__)


class AgentPlatformRuntimeConnector:
    """
    Connector for GCP Agent Platform Runtime (Reasoning Engine) with multi-channel support.

    Connects to agents deployed on Google Cloud's Agent Platform Runtime (also called
    Reasoning Engine or Agent Engine). Supports agents built with LangChain, LangGraph,
    ADK, or custom Python code that have been deployed to GCP infrastructure.

    Manages conversation state locally and formats history as text for stateless agents:
    - Stores conversation history per conversation_id in memory
    - Formats history as text and passes to agent.query(input=formatted_history)
    - Manages Voice and SMS channels
    - Handles memory injection as system message in history

    Args:
        tac: TAC instance for channel integration
        agent: Deployed ReasoningEngine instance (single agent for all conversations)
        sms_config: Optional SMS channel configuration (SMSChannelConfig or dict)
        voice_config: Optional Voice channel configuration (VoiceChannelConfig or dict)

    Attributes:
        voice: VoiceChannel instance for voice conversations
        sms: SMSChannel instance for SMS conversations

    Example:
        ```python
        import vertexai
        from vertexai.preview import reasoning_engines
        from tac import TAC, TACConfig
        from tac.server import TACFastAPIServer
        from tac_google.connectors import AgentPlatformRuntimeConnector

        vertexai.init(project="my-project", location="us-central1")
        tac = TAC(config=TACConfig.from_env())

        agent = reasoning_engines.ReasoningEngine(
            "projects/my-project/locations/us-central1/reasoningEngines/123456"
        )

        connector = AgentPlatformRuntimeConnector(tac=tac, agent=agent)

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
        agent: ReasoningEngine,
        sms_config: SMSChannelConfig | dict[str, Any] | None = None,
        voice_config: VoiceChannelConfig | dict[str, Any] | None = None,
    ) -> None:
        self.tac = tac
        self.agent = agent
        self.conversation_histories: dict[str, list[dict[str, str]]] = {}
        self.voice = VoiceChannel(tac=tac, config=voice_config)
        self.sms = SMSChannel(tac=tac, config=sms_config)

        self.tac.on_message_ready(self._handle_message)
        self.tac.on_conversation_ended(self._handle_conversation_ended)

        logger.debug("AgentPlatformRuntimeConnector initialized")

    async def _handle_message(
        self,
        user_message: str,
        context: ConversationSession,
        memory_response: TACMemoryResponse | None,
    ) -> str | None:
        try:
            conv_id = context.conversation_id

            if conv_id not in self.conversation_histories:
                self.conversation_histories[conv_id] = []

                if memory_response:
                    memory_context = MemoryPromptBuilder.build(memory_response, context)
                    if memory_context:
                        self.conversation_histories[conv_id].append({
                            "role": "system",
                            "content": memory_context
                        })

            self.conversation_histories[conv_id].append({
                "role": "user",
                "content": user_message
            })

            formatted_input = self._format_history_as_text(
                self.conversation_histories[conv_id]
            )

            response = await self._query_agent(self.agent, formatted_input)
            response_text = self._parse_response(response)

            self.conversation_histories[conv_id].append({
                "role": "assistant",
                "content": response_text
            })

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
                "Error processing message",
                conversation_id=context.conversation_id,
                error=str(e),
                exc_info=True,
            )
            error_msg = "I encountered an error processing your message. Please try again."
            if context.channel == "voice" and self.voice:
                await self.voice.send_response(context.conversation_id, error_msg, role="assistant")
            elif context.channel == "sms" and self.sms:
                await self.sms.send_response(context.conversation_id, error_msg, role="assistant")

        return None

    def _format_history_as_text(self, history: list[dict[str, str]]) -> str:
        if not history:
            return ""

        formatted_lines = []

        for msg in history:
            role = msg["role"]
            content = msg["content"]

            if role == "system":
                formatted_lines.append(content)
            elif role == "user":
                formatted_lines.append(f"User: {content}")
            elif role == "assistant":
                formatted_lines.append(f"Assistant: {content}")

        return "\n\n".join(formatted_lines)

    async def _query_agent(
        self,
        agent: ReasoningEngine,
        message: str,
    ) -> dict[str, Any]:
        def query_wrapper(ag: ReasoningEngine, msg: str) -> dict[str, Any]:
            return ag.query(input=msg)

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, query_wrapper, agent, message)
        return response

    def _parse_response(self, response: dict[str, Any]) -> str:
        if isinstance(response, str):
            return response

        if "output" in response:
            output = response["output"]
            if isinstance(output, str):
                return output
            return str(output)

        if "messages" in response and isinstance(response["messages"], list):
            messages = response["messages"]
            if messages:
                last_msg = messages[-1]
                if isinstance(last_msg, dict):
                    if "kwargs" in last_msg and "content" in last_msg["kwargs"]:
                        return last_msg["kwargs"]["content"]
                    if "content" in last_msg:
                        return last_msg["content"]

        return str(response)

    def _handle_conversation_ended(self, context: ConversationSession) -> None:
        conversation_id = context.conversation_id

        if conversation_id in self.conversation_histories:
            del self.conversation_histories[conversation_id]

        logger.debug(
            "Cleaned up conversation history",
            conversation_id=conversation_id,
        )
