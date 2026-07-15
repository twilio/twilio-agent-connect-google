"""TAC connectors for GCP agent runtimes."""

from tac_google.connectors.agent_platform_runtime_connector import (
    AgentPlatformRuntimeConnector,
)

# Future connectors will be imported as they are implemented
# from tac_google.connectors.adk_connector import ADKConnector

__all__ = [
    "AgentPlatformRuntimeConnector",
    # Future connectors:
    # "ADKConnector",
]
