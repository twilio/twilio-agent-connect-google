"""Audio processing utilities for Gemini Live S2S channel.

Handles bidirectional conversion between:
- Twilio Media Streams: 8kHz µ-law (G.711u) mono
- Gemini Live Native Audio: 24kHz 16-bit linear PCM mono
"""

from __future__ import annotations

import audioop
import base64
from typing import Any

TWILIO_AUDIO_SAMPLE_RATE = 8000
GEMINI_LIVE_AUDIO_SAMPLE_RATE = 24000
SAMPLE_WIDTH = 2  # 16-bit linear PCM
CHANNELS = 1  # Mono


def twilio_mulaw_to_gemini_pcm(
    payload_b64: str,
    state: Any = None,
) -> tuple[bytes, Any]:
    """Convert base64-encoded 8kHz µ-law audio from Twilio to raw 24kHz PCM16.

    Args:
        payload_b64: Base64-encoded payload from Twilio Media Streams event.
        state: State tuple returned by previous ratecv call, or None.

    Returns:
        tuple[bytes, Any]: (pcm_24k_bytes, new_state)
    """
    mulaw_bytes = base64.b64decode(payload_b64)
    linear_8k = audioop.ulaw2lin(mulaw_bytes, SAMPLE_WIDTH)
    pcm_24k, new_state = audioop.ratecv(
        linear_8k,
        SAMPLE_WIDTH,
        CHANNELS,
        TWILIO_AUDIO_SAMPLE_RATE,
        GEMINI_LIVE_AUDIO_SAMPLE_RATE,
        state,
    )
    return pcm_24k, new_state


def gemini_pcm_to_twilio_mulaw(
    pcm_24k_bytes: bytes,
    state: Any = None,
) -> tuple[str, Any]:
    """Convert 24kHz PCM16 audio bytes from Gemini Live to base64-encoded 8kHz µ-law.

    Args:
        pcm_24k_bytes: Raw 24kHz 16-bit linear PCM audio chunk.
        state: State tuple returned by previous ratecv call, or None.

    Returns:
        tuple[str, Any]: (base64_mulaw_payload, new_state)
    """
    linear_8k, new_state = audioop.ratecv(
        pcm_24k_bytes,
        SAMPLE_WIDTH,
        CHANNELS,
        GEMINI_LIVE_AUDIO_SAMPLE_RATE,
        TWILIO_AUDIO_SAMPLE_RATE,
        state,
    )
    mulaw_bytes = audioop.lin2ulaw(linear_8k, SAMPLE_WIDTH)
    return base64.b64encode(mulaw_bytes).decode("ascii"), new_state
