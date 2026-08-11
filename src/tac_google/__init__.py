"""GCP integrations for Twilio Agent Connect (TAC).

This package provides GCP-specific connectors for TAC:

Connectors:
    - ADKAgentEngineConnector: ADK agents deployed to GCP Agent Platform Runtime
    - StudioAgentEngineConnector: Agent Studio apps deployed to GCP Agent Platform Runtime
    - CXAgentStudioConnector: Agents built in CX Agent Studio (Customer Engagement Suite)
    - ConversationalAgentsConnector: Agents built in Conversational Agents (Dialogflow CX)

Tools:
    - TBD: Tools for function calling with Vertex AI
"""

from tac_google._version import __version__
from tac_google.connectors import (
    ADKAgentEngineConnector,
    ConversationalAgentsConnector,
    CXAgentStudioConnector,
    StudioAgentEngineConnector,
)

__all__ = [
    "__version__",
    "ADKAgentEngineConnector",
    "ConversationalAgentsConnector",
    "CXAgentStudioConnector",
    "StudioAgentEngineConnector",
]
