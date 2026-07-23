from functools import cached_property

from google.adk.agents.llm_agent import Agent
from google.adk.models import Gemini
from google.genai import Client


class GlobalGemini(Gemini):
    """Gemini pinned to the global endpoint.

    gemini-3.5-flash is only served on the global endpoint, so the deploy
    region must be overridden here or the container 404s on first model call.
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
