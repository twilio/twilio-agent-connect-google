from functools import cached_property

from google.adk.agents.llm_agent import Agent
from google.adk.models import Gemini
from google.genai import Client


class GlobalGemini(Gemini):
    """Gemini model forced to the global endpoint.

    gemini-3.5-flash (Enterprise Agent Platform API) is only served via the
    global endpoint, not regional ones. The default Gemini client reads
    location from GOOGLE_CLOUD_LOCATION, which is set to a specific region
    (e.g. us-west1) for this deployed Reasoning Engine, so it must be
    overridden here or the container 404s on first model call and crashes
    before it can start serving.
    """

    @cached_property
    def api_client(self) -> Client:
        return Client(vertexai=True, location="global")


root_agent = Agent(
    model=GlobalGemini(model="gemini-3.5-flash"),
    name="root_agent",
    description="A helpful assistant for user questions.",
    instruction="Answer user questions to the best of your knowledge",
)
