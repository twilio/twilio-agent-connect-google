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
    from vertexai.agent_engines import AgentEngine
    from vertexai.preview.reasoning_engines import ReasoningEngine

logger = get_logger(__name__)


class AgentPlatformRuntimeConnector:
    """
    Connector for GCP Agent Platform Runtime (Reasoning Engine) with multi-channel support.

    Connects to agents deployed on Google Cloud's Agent Platform Runtime (also called
    Reasoning Engine or Agent Engine). Supports agents built with LangChain, LangGraph,
    AG2, custom Python code, or ADK that have been deployed to GCP infrastructure.

    The deployed agent exposes one of two invocation shapes, detected automatically
    from which methods are registered on it at construction time:
    - `query()` family (LangChain, LangGraph, AG2, custom classes): a single
      synchronous call per message. Conversation history is formatted as text
      locally and passed as input on every call.
    - ADK (`stream_query()`): session-based and streaming. A remote session is
      created once per conversation and reused; ADK manages history server-side,
      so no local history text is built for this path.

    Manages Voice and SMS channels and injects TAC memory on the first message
    of each conversation (as a system-message prefix for the query() family, or
    prepended to the first user message when creating the session for ADK).

    IMPORTANT for ADK agents: fetch the agent with `vertexai.agent_engines.get()`,
    NOT `vertexai.preview.reasoning_engines.ReasoningEngine()`. ADK's operation
    schema includes `async`/`async_stream`/`bidi_stream` modes that the older
    ReasoningEngine's method-registration code doesn't recognize - it raises and
    aborts registration entirely when it hits one, so `stream_query` never gets
    attached and this connector silently misdetects the agent as the query()
    family instead (`is_streaming_agent` ends up False). `agent_engines.get()`
    handles all of ADK's operation modes correctly. LangChain/LangGraph/AG2/
    custom classes don't declare those modes, so either SDK works for them, but
    `agent_engines.get()` is the current recommended one regardless.

    Args:
        tac: TAC instance for channel integration
        agent: Deployed agent instance (single agent for all conversations) -
            from `vertexai.agent_engines.get()` (required for ADK) or
            `vertexai.preview.reasoning_engines.ReasoningEngine()`
        sms_config: Optional SMS channel configuration (SMSChannelConfig or dict)
        voice_config: Optional Voice channel configuration (VoiceChannelConfig or dict)

    Attributes:
        voice: VoiceChannel instance for voice conversations
        sms: SMSChannel instance for SMS conversations

    Example:
        ```python
        import vertexai
        from vertexai import agent_engines
        from tac import TAC, TACConfig
        from tac.server import TACFastAPIServer
        from tac_google.connectors import AgentPlatformRuntimeConnector

        vertexai.init(project="my-project", location="us-central1")
        tac = TAC(config=TACConfig.from_env())

        agent = agent_engines.get(
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
        agent: ReasoningEngine | AgentEngine,
        sms_config: SMSChannelConfig | dict[str, Any] | None = None,
        voice_config: VoiceChannelConfig | dict[str, Any] | None = None,
    ) -> None:
        self.tac = tac
        self.agent = agent
        # ADK-deployed agents only register stream_query() (session-based,
        # streaming). LangChain/LangGraph/AG2/custom classes register query()
        # (single synchronous call). Detected once here since the deployed
        # agent's dynamic methods are already bound by the time it's passed in.
        self.is_streaming_agent = hasattr(agent, "stream_query") and not hasattr(agent, "query")
        self.conversation_histories: dict[str, list[dict[str, str]]] = {}
        self.adk_sessions: dict[str, str] = {}
        self.voice = VoiceChannel(tac=tac, config=voice_config)
        self.sms = SMSChannel(tac=tac, config=sms_config)

        self.tac.on_message_ready(self._handle_message)
        self.tac.on_conversation_ended(self._handle_conversation_ended)

        logger.debug(
            "AgentPlatformRuntimeConnector initialized",
            mode="stream_query" if self.is_streaming_agent else "query",
        )

    async def _handle_message(
        self,
        user_message: str,
        context: ConversationSession,
        memory_response: TACMemoryResponse | None,
    ) -> str | None:
        try:
            if self.is_streaming_agent:
                return await self._handle_adk_message(user_message, context, memory_response)
            return await self._handle_query_message(user_message, context, memory_response)

        except Exception as e:
            logger.error(
                "Error processing message",
                conversation_id=context.conversation_id,
                error=str(e),
                exc_info=True,
            )
            return "I encountered an error processing your message. Please try again."

    async def _handle_query_message(
        self,
        user_message: str,
        context: ConversationSession,
        memory_response: TACMemoryResponse | None,
    ) -> str:
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

        return response_text

    async def _handle_adk_message(
        self,
        user_message: str,
        context: ConversationSession,
        memory_response: TACMemoryResponse | None,
    ) -> str:
        conv_id = context.conversation_id
        user_id = context.profile_id or conv_id
        loop = asyncio.get_event_loop()

        if conv_id not in self.adk_sessions:
            session = await loop.run_in_executor(
                None, lambda: self.agent.create_session(user_id=user_id)
            )
            self.adk_sessions[conv_id] = session["id"]

            if memory_response:
                memory_context = MemoryPromptBuilder.build(memory_response, context)
                if memory_context:
                    user_message = f"{memory_context}\n\n{user_message}"

        session_id = self.adk_sessions[conv_id]

        def run_stream_query() -> list[dict[str, Any]]:
            return list(
                self.agent.stream_query(
                    message=user_message,
                    user_id=user_id,
                    session_id=session_id,
                )
            )

        events = await loop.run_in_executor(None, run_stream_query)
        return self._parse_adk_events(events)

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
        agent: ReasoningEngine | AgentEngine,
        message: str,
    ) -> dict[str, Any]:
        def query_wrapper(ag: ReasoningEngine | AgentEngine, msg: str) -> dict[str, Any]:
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
            if isinstance(output, list):
                # LangChain's ChatGoogleGenerativeAI (used by LangchainAgent's
                # default model_builder) returns content blocks, e.g.
                # [{"type": "text", "text": "...", ...}], instead of a plain
                # string in the AgentExecutor output.
                texts = [
                    block["text"]
                    for block in output
                    if isinstance(block, dict) and isinstance(block.get("text"), str)
                ]
                if texts:
                    return "".join(texts)
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

    def _parse_adk_events(self, events: list[dict[str, Any]]) -> str:
        """Extracts the final response text from a stream of ADK events.

        Streamed events include partial chunks and tool-call/tool-response
        events; the final response is the last non-partial event that carries
        text content.
        """
        for event in reversed(events):
            if event.get("partial"):
                continue
            for part in event.get("content", {}).get("parts", []):
                if "text" in part:
                    return part["text"]

        return "I didn't get a response from the agent. Please try again."

    def _handle_conversation_ended(self, context: ConversationSession) -> None:
        conversation_id = context.conversation_id

        self.conversation_histories.pop(conversation_id, None)
        self.adk_sessions.pop(conversation_id, None)

        logger.debug(
            "Cleaned up conversation history",
            conversation_id=conversation_id,
        )
