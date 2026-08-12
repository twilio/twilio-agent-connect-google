"""GCP integrations for Twilio Agent Connect (TAC).

This top-level package only exposes `__version__`, so `pip install
twilio-agent-connect-google` with no extras never fails on import — each
connector's Google Cloud SDK is only required by its own extra. Import
connectors from `tac_google.connectors` instead, e.g.:

    from tac_google.connectors import ADKAgentEngineConnector

Connectors:
    - ADKAgentEngineConnector: ADK agents deployed to GCP Agent Platform Runtime
    - StudioAgentEngineConnector: Agent Studio apps deployed to GCP Agent Platform Runtime
    - CXAgentStudioConnector: Agents built in CX Agent Studio (Customer Engagement Suite)
    - ConversationalAgentsConnector: Agents built in Conversational Agents (Dialogflow CX)
"""

from tac_google._version import __version__

__all__ = ["__version__"]
