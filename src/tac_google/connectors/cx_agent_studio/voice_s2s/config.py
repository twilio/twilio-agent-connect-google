"""Voice S2S channel configuration."""

from pydantic import BaseModel, Field

# Matches tac.channels.voice.channel.DEFAULT_WELCOME_GREETING.
DEFAULT_WELCOME_GREETING = "Hello! How can I assist you today?"


class VoiceS2SConfig(BaseModel):
    """
    Configuration for `VoiceS2SChannel`.

    Attributes:
        deployment_id: Optional CES deployment resource name, for agents
            with a dedicated Twilio channel deployment in the CES console.
        welcome_greeting: Text sent to CES as the session-kickoff turn.
            Unlike ConversationRelay's `welcome_greeting`, this isn't spoken
            verbatim — the agent decides how to respond to it, like any
            other turn. Set to `None` to let the agent's own configured
            greeting play unmodified.
    """

    model_config = {"extra": "forbid"}

    deployment_id: str | None = Field(
        default=None,
        description="CES deployment resource name for this channel's Twilio integration.",
    )
    welcome_greeting: str | None = Field(
        default=DEFAULT_WELCOME_GREETING,
        description="Text sent to CES as the session-kickoff turn. Set to None to use "
        "the agent's own configured greeting instead.",
    )
