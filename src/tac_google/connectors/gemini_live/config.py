"""Gemini Live S2S configuration."""

from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, Field

DEFAULT_GEMINI_LIVE_MODEL = "publishers/google/models/gemini-live-2.5-flash-native-audio"
DEFAULT_VOICE_NAME = "Aoede"
DEFAULT_WELCOME_GREETING = "Hello! How can I assist you today?"

ToolDispatcherType = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


class GeminiLiveConfig(BaseModel):
    """Configuration for GeminiLiveChannel.

    Attributes:
        project_id: Google Cloud Project ID.
        location: Google Cloud region (e.g. us-central1).
        model: Vertex AI resource name or model ID.
        voice_name: Voice name for speech generation (e.g. Aoede, Puck, Charon).
        welcome_greeting: Optional kickoff text sent to model on session start.
        system_instruction: Optional system instruction prompt to guide model behavior.
        tools: Optional list of tools (functions / OpenAPI schemas) declared for model.
        tool_dispatcher: Optional async callback for executing tool calls `async def (name, args) -> dict`.
    """

    model_config = {"extra": "forbid"}

    project_id: str = Field(
        ...,
        description="Google Cloud project ID.",
    )
    location: str = Field(
        default="us-central1",
        description="Google Cloud region for Vertex AI Live API.",
    )
    model: str = Field(
        default=DEFAULT_GEMINI_LIVE_MODEL,
        description="Vertex AI Gemini Live native audio model ID.",
    )
    voice_name: str = Field(
        default=DEFAULT_VOICE_NAME,
        description="Voice name for Gemini Live speech generation.",
    )
    welcome_greeting: str | None = Field(
        default=DEFAULT_WELCOME_GREETING,
        description="Kickoff text sent to model on session start. Set to None to disable.",
    )
    system_instruction: str | None = Field(
        default=None,
        description="System instruction prompt guiding agent persona and behavior.",
    )
    tools: list[Any] = Field(
        default_factory=list,
        description="Tools/functions available for the model to call.",
    )
    tool_dispatcher: ToolDispatcherType | None = Field(
        default=None,
        description="Async callback invoked to execute tool calls: (name, args) -> dict.",
    )
