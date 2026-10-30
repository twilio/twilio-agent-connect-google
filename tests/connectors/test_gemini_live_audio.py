"""Tests for audio conversion utilities in Gemini Live S2S."""

import audioop
import base64

from tac_google.connectors.gemini_live.audio import (
    gemini_pcm_to_twilio_mulaw,
    twilio_mulaw_to_gemini_pcm,
)


def test_twilio_mulaw_to_gemini_pcm():
    # 800 samples of 8kHz silence/tone in 16-bit linear PCM
    raw_pcm_8k = b"\x00\x00" * 800
    mulaw = audioop.lin2ulaw(raw_pcm_8k, 2)
    b64_payload = base64.b64encode(mulaw).decode("ascii")

    pcm_24k, state = twilio_mulaw_to_gemini_pcm(b64_payload)

    # 8kHz -> 24kHz is ~3x upsampling, 800 samples -> ~2400 samples (4800 bytes +/- filter state)
    assert abs(len(pcm_24k) - 4800) <= 8
    assert state is not None


def test_gemini_pcm_to_twilio_mulaw():
    # 2400 samples of 24kHz audio (4800 bytes)
    raw_pcm_24k = b"\x10\x00" * 2400

    b64_payload, state = gemini_pcm_to_twilio_mulaw(raw_pcm_24k)
    decoded_mulaw = base64.b64decode(b64_payload)

    # 24kHz -> 8kHz is 3x downsampling, 2400 samples / 3 = 800 samples (800 bytes mulaw)
    assert len(decoded_mulaw) == 800
    assert state is not None


def test_streaming_state_continuity():
    # Ensure successive calls maintain filter state
    raw_pcm_24k_chunk1 = b"\x10\x00" * 1200
    raw_pcm_24k_chunk2 = b"\x10\x00" * 1200

    payload1, state1 = gemini_pcm_to_twilio_mulaw(raw_pcm_24k_chunk1, None)
    payload2, state2 = gemini_pcm_to_twilio_mulaw(raw_pcm_24k_chunk2, state1)

    assert len(base64.b64decode(payload1)) == 400
    assert len(base64.b64decode(payload2)) == 400
    assert state2 is not None
