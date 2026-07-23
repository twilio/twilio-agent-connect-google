"""TAC connectors for GCP agent runtimes.

Each connector is imported lazily (on first attribute access) so that
`import tac_google.connectors` doesn't require every connector's optional
dependencies — only the one you actually use.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tac_google.connectors.agent_platform_runtime_connector import (
        AgentPlatformRuntimeConnector,
    )
    from tac_google.connectors.cx_agent_studio_connector import (
        CXAgentStudioConnector,
    )

__all__ = [
    "AgentPlatformRuntimeConnector",
    "CXAgentStudioConnector",
]

_CONNECTOR_MODULES = {
    "AgentPlatformRuntimeConnector": "tac_google.connectors.agent_platform_runtime_connector",
    "CXAgentStudioConnector": "tac_google.connectors.cx_agent_studio_connector",
}


def __getattr__(name: str):
    module_path = _CONNECTOR_MODULES.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    import importlib

    module = importlib.import_module(module_path)
    return getattr(module, name)
