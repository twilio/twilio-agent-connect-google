"""Shared channel-building logic for connectors, following tac_microsoft's
`AgentFrameworkConnector` design.

SMS and Chat are always built — same as Voice, which every connector builds
itself (see below) — since disabling a channel means not wiring it to a
server, not skipping its construction. RCS and WhatsApp are the exception:
they're built only when their Twilio resource is configured
(`TWILIO_RCS_SENDER_ID` / `TWILIO_WHATSAPP_NUMBER`), since `RCSChannel` /
`WhatsAppChannel` themselves require it and raise ValueError at construction
if it's missing. Their `*_config` args are tuning only (memory_mode, etc.)
and have no effect if the resource isn't configured.

Voice isn't included here: `CXAgentStudioConnector` must pick between
`VoiceChannel` and `VoiceS2SChannel` based on the config type, so every
connector builds Voice itself instead of through this class.
"""

from __future__ import annotations

from typing import Any

from tac.channels.chat import ChatChannel, ChatChannelConfig
from tac.channels.rcs import RCSChannel, RCSChannelConfig
from tac.channels.sms import SMSChannel, SMSChannelConfig
from tac.channels.whatsapp import WhatsAppChannel, WhatsAppChannelConfig
from tac.core.tac import TAC

__all__ = ["ConnectorChannels"]


class ConnectorChannels:
    """Builds a connector's SMS/Chat/RCS/WhatsApp channels.

    Args:
        tac: TAC instance for channel integration.
        sms_config: SMSChannelConfig or dict. SMS is always built.
        chat_config: ChatChannelConfig or dict. Chat is always built.
        rcs_config: RCSChannelConfig or dict — tuning only. RCS is built
            whenever TWILIO_RCS_SENDER_ID is configured, regardless of
            this argument.
        whatsapp_config: WhatsAppChannelConfig or dict — tuning only.
            WhatsApp is built whenever TWILIO_WHATSAPP_NUMBER is
            configured, regardless of this argument.

    Attributes:
        sms: SMSChannel instance.
        chat: ChatChannel instance.
        rcs: RCSChannel instance, or None if TWILIO_RCS_SENDER_ID isn't configured.
        whatsapp: WhatsAppChannel instance, or None if TWILIO_WHATSAPP_NUMBER
            isn't configured.
    """

    def __init__(
        self,
        tac: TAC,
        sms_config: SMSChannelConfig | dict[str, Any] | None = None,
        chat_config: ChatChannelConfig | dict[str, Any] | None = None,
        rcs_config: RCSChannelConfig | dict[str, Any] | None = None,
        whatsapp_config: WhatsAppChannelConfig | dict[str, Any] | None = None,
    ) -> None:
        self.sms = SMSChannel(tac=tac, config=sms_config)
        self.chat = ChatChannel(tac=tac, config=chat_config)
        self.rcs = RCSChannel(tac=tac, config=rcs_config) if tac.config.rcs_sender_id else None
        self.whatsapp = (
            WhatsAppChannel(tac=tac, config=whatsapp_config) if tac.config.whatsapp_number else None
        )
