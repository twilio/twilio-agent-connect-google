"""Tests for GeminiLiveConfig."""

import pytest
from pydantic import ValidationError

from tac_google.connectors.gemini_live.config import (
    DEFAULT_GEMINI_LIVE_MODEL,
    DEFAULT_VOICE_NAME,
    DEFAULT_WELCOME_GREETING,
    GeminiLiveConfig,
)


def test_gemini_live_config_defaults():
    config = GeminiLiveConfig(project_id="test-project")
    assert config.project_id == "test-project"
    assert config.location == "us-central1"
    assert config.model == DEFAULT_GEMINI_LIVE_MODEL
    assert config.voice_name == DEFAULT_VOICE_NAME
    assert config.welcome_greeting == DEFAULT_WELCOME_GREETING
    assert config.system_instruction is None
    assert config.tools == []
    assert config.tool_dispatcher is None


def test_gemini_live_config_custom_values():
    async def sample_dispatcher(name, args):
        return {"result": "ok"}

    config = GeminiLiveConfig(
        project_id="custom-project",
        location="us-east4",
        model="publishers/google/models/gemini-live-custom",
        voice_name="Puck",
        welcome_greeting="Welcome to our helpline!",
        system_instruction="You are a helpful customer support agent.",
        tools=[{"name": "check_status"}],
        tool_dispatcher=sample_dispatcher,
    )
    assert config.project_id == "custom-project"
    assert config.location == "us-east4"
    assert config.model == "publishers/google/models/gemini-live-custom"
    assert config.voice_name == "Puck"
    assert config.welcome_greeting == "Welcome to our helpline!"
    assert config.system_instruction == "You are a helpful customer support agent."
    assert len(config.tools) == 1
    assert config.tool_dispatcher is sample_dispatcher


def test_gemini_live_config_extra_forbidden():
    with pytest.raises(ValidationError):
        GeminiLiveConfig(project_id="test-proj", unknown_field="invalid")
