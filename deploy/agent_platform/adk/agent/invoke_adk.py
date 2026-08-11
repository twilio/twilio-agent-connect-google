"""Interactive test client for a deployed ADK agent.

ADK agents are session-based and streaming: create a session, then
async_stream_query() yields event dicts. Fetch with client.agent_engines.get()
(the sync create_session/stream_query methods are deprecated in favor of
these async ones).
"""

import asyncio
import os
import uuid

import vertexai
from dotenv import load_dotenv

load_dotenv()


def extract_final_text(events: list) -> str | None:
    """Return the last non-partial event's text from an ADK event stream."""
    for event in reversed(events):
        if event.get("partial"):
            continue
        for part in event.get("content", {}).get("parts", []):
            if "text" in part:
                return part["text"]
    return None


async def main():
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION")
    agent_id = os.getenv("GCP_REASONING_ENGINE_ID")

    if not project:
        print("\n❌ Error: GOOGLE_CLOUD_PROJECT not set")
        return
    if not location:
        print("\n❌ Error: GOOGLE_CLOUD_LOCATION not set")
        return
    if not agent_id:
        print("\n❌ Error: GCP_REASONING_ENGINE_ID not set — deploy an agent first (./deploy.sh)")
        return

    print(f"\nConnecting to agent {agent_id} ({project}/{location})...\n")
    client = vertexai.Client(project=project, location=location)
    resource_name = f"projects/{project}/locations/{location}/reasoningEngines/{agent_id}"
    agent = client.agent_engines.get(name=resource_name)

    user_id = "local-test-user"
    session_id = f"local-test-{uuid.uuid4().hex[:8]}"
    await agent.async_create_session(user_id=user_id, session_id=session_id)

    print("Agent ready - press Ctrl+C to exit.\n")
    try:
        while True:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            events = [
                event
                async for event in agent.async_stream_query(
                    message=user_input, user_id=user_id, session_id=session_id
                )
            ]
            print(f"Agent: {extract_final_text(events) or '(no text response)'}\n")
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    asyncio.run(main())
