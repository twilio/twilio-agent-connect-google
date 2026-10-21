"""Twilio Agent Connect connector for Vertex AI Gemini Live API."""

from __future__ import annotations

from typing import Any

from tac.core.logging import get_logger
from tac.core.tac import TAC

from tac_google.connectors.gemini_live.channel import GeminiLiveChannel
from tac_google.connectors.gemini_live.config import GeminiLiveConfig

logger = get_logger(__name__)


class GeminiLiveConnector:
    """Connector that wires Twilio Media Streams to Google Vertex AI Gemini Live API.

    Args:
        tac: Initialized TAC instance.
        config: GeminiLiveConfig instance or configuration dictionary.
    """

    def __init__(
        self,
        tac: TAC,
        config: GeminiLiveConfig | dict[str, Any],
    ) -> None:
        self.tac = tac
        if isinstance(config, dict):
            config = GeminiLiveConfig(**config)
        self.config = config

        self.channel = GeminiLiveChannel(tac=self.tac, config=self.config)
        self.voice_s2s = self.channel

        logger.info(
            "GeminiLiveConnector initialized",
            project=self.config.project_id,
            model=self.config.model,
            location=self.config.location,
        )
