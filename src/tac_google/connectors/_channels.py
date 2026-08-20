"""Shared channel-building logic for connectors (follows tac_aws's
`ConnectorChannels` shape).

Every channel is opt-in: None (default) means no channel, any config builds
it. RCSChannel/WhatsAppChannel still require their Twilio resource
(TWILIO_RCS_SENDER_ID / TWILIO_WHATSAPP_NUMBER) and raise ValueError at
construction if it's missing.

CXAgentStudioConnector builds Voice itself instead of through this class,
since it must pick between VoiceChannel and VoiceS2SChannel based on the
config type.
"""

from __future__ import annotations

from typing import Any

from tac.channels.chat import ChatChannel, ChatChannelConfig
from tac.channels.messaging import MessagingChannel
from tac.channels.rcs import RCSChannel, RCSChannelConfig
from tac.channels.sms import SMSChannel, SMSChannelConfig
from tac.channels.voice import VoiceChannel, VoiceChannelConfig
from tac.channels.whatsapp import WhatsAppChannel, WhatsAppChannelConfig
from tac.core.tac import TAC

__all__ = ["ConnectorChannels"]


class ConnectorChannels:
    """Builds a connector's channels and collects the messaging ones.

    Args:
        tac: TAC instance for channel integration.
        voice_config, sms_config, rcs_config, whatsapp_config, chat_config:
            each is a channel config or None (default) to disable that
            channel.

    Attributes:
        voice, sms, rcs, whatsapp, chat: the corresponding channel instance,
            or None if disabled.
        messaging: sms/rcs/whatsapp/chat, whichever are enabled, as a list —
            hand this straight to a server's `messaging_channels=`.
    """

    def __init__(
        self,
        tac: TAC,
        voice_config: VoiceChannelConfig | dict[str, Any] | None = None,
        sms_config: SMSChannelConfig | dict[str, Any] | None = None,
        rcs_config: RCSChannelConfig | dict[str, Any] | None = None,
        whatsapp_config: WhatsAppChannelConfig | dict[str, Any] | None = None,
        chat_config: ChatChannelConfig | dict[str, Any] | None = None,
    ) -> None:
        self.voice = (
            VoiceChannel(tac=tac, config=voice_config) if voice_config is not None else None
        )
        self.sms = SMSChannel(tac=tac, config=sms_config) if sms_config is not None else None
        self.rcs = RCSChannel(tac=tac, config=rcs_config) if rcs_config is not None else None
        self.whatsapp = (
            WhatsAppChannel(tac=tac, config=whatsapp_config)
            if whatsapp_config is not None
            else None
        )
        self.chat = ChatChannel(tac=tac, config=chat_config) if chat_config is not None else None

        self.messaging: list[MessagingChannel] = [
            c for c in (self.sms, self.rcs, self.whatsapp, self.chat) if c is not None
        ]
