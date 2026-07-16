"""GCP integrations for Twilio Agent Connect (TAC).

This package provides GCP-specific connectors for TAC:

Connectors:
    - AgentPlatformRuntimeConnector: Deploy custom agents (LangChain, ADK, etc.) to GCP Runtime
    - DialogflowCXConnector: Dialogflow CX conversational flows (coming soon)
    - ADKConnector: Agent Development Kit local agents (coming soon)

Tools:
    - TBD: Tools for function calling with Vertex AI
"""

from tac_google._version import __version__
from tac_google.connectors import AgentPlatformRuntimeConnector

__all__ = [
    "__version__",
    "AgentPlatformRuntimeConnector",
    # Future connectors (to be added as implemented)
    # "DialogflowCXConnector",
    # "ADKConnector",
]
