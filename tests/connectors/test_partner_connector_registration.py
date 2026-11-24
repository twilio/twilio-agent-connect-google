"""Each connector tags outbound Twilio requests with its partner User-Agent token."""

from collections.abc import Callable
from contextlib import ExitStack
from typing import Any
from unittest.mock import Mock, patch

import pytest
from tac import TAC
from tac.context.base import BaseAPIClient

from tac_google._version import __version__
from tac_google.connectors import (
    ADKAgentEngineConnector,
    ConversationalAgentsConnector,
    CXAgentStudioConnector,
    StudioAgentEngineConnector,
)

AGENT_PLATFORM = "tac_google.connectors.agent_platform"


class FakeTAC:
    """Real `register_partner_connector` over a stand-in holding one real API client."""

    register_partner_connector = TAC.register_partner_connector

    def __init__(self) -> None:
        self.config = Mock(rcs_sender_id=None, whatsapp_number=None)
        self.client = BaseAPIClient("key", "secret")
        self.on_message_ready = Mock()
        self.on_conversation_ended = Mock()


def make_agent() -> Mock:
    agent = Mock()
    agent.api_resource.name = "projects/p/locations/us-central1/reasoningEngines/1"
    return agent


def build_adk(tac: FakeTAC) -> object:
    return ADKAgentEngineConnector(tac=tac, agent=make_agent())


def build_studio(tac: FakeTAC) -> object:
    return StudioAgentEngineConnector(tac=tac, agent=make_agent())


def build_cx(tac: FakeTAC) -> object:
    return CXAgentStudioConnector(tac=tac, agent_id="projects/p/locations/us/apps/a")


def build_conversational(tac: FakeTAC) -> object:
    return ConversationalAgentsConnector(
        tac=tac, agent_id="projects/p/locations/us-central1/agents/a"
    )


CASES = [
    (build_adk, "ADKAgentEngineConnector", [f"{AGENT_PLATFORM}._base"]),
    (build_studio, "StudioAgentEngineConnector", [f"{AGENT_PLATFORM}._base"]),
    (build_cx, "CXAgentStudioConnector", ["tac_google.connectors.cx_agent_studio.connector"]),
    (
        build_conversational,
        "ConversationalAgentsConnector",
        ["tac_google.connectors.conversational_agents_connector"],
    ),
]


@pytest.mark.parametrize(
    ("build", "connector_name", "modules"),
    CASES,
    ids=[name for _, name, _ in CASES],
)
def test_connector_adds_google_partner_token_to_user_agent(
    build: Callable[[FakeTAC], Any], connector_name: str, modules: list[str]
):
    tac = FakeTAC()
    assert "tac-google" not in tac.client._get_user_agent()

    with ExitStack() as stack:
        for module in modules:
            stack.enter_context(patch(f"{module}.google.auth.default", return_value=(Mock(), None)))
            stack.enter_context(patch(f"{module}.AuthorizedSession"))
            stack.enter_context(patch(f"{module}.VoiceChannel"))
        stack.enter_context(patch("tac_google.connectors._channels.SMSChannel"))
        stack.enter_context(patch("tac_google.connectors._channels.ChatChannel"))
        build(tac)

    assert tac.client._get_user_agent().endswith(f" tac-google/{__version__} ({connector_name})")
