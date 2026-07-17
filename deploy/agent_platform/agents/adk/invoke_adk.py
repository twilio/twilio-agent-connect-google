"""Interactive test client for a deployed ADK agent.

ADK agents are session-based and streaming: create a session, then
stream_query() yields event dicts. Fetch with agent_engines.get().
"""

import os

import vertexai
from dotenv import load_dotenv
from vertexai import agent_engines

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


def main():
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    agent_id = os.getenv("GCP_REASONING_ENGINE_ID")

    if not project:
        print("\n❌ Error: GOOGLE_CLOUD_PROJECT not set")
        return
    if not agent_id:
        print("\n❌ Error: GCP_REASONING_ENGINE_ID not set — deploy an agent first (./deploy.sh)")
        return

    print(f"\nConnecting to agent {agent_id} ({project}/{location})...\n")
    vertexai.init(project=project, location=location)
    agent = agent_engines.get(agent_id)

    user_id = "local-test-user"
    session_id = agent.create_session(user_id=user_id)["id"]

    print("Agent ready - type 'quit' to exit.\n")
    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["quit", "exit", "q"]:
                print("\nGoodbye!")
                break
            events = list(
                agent.stream_query(message=user_input, user_id=user_id, session_id=session_id)
            )
            print(f"Agent: {extract_final_text(events) or '(no text response)'}\n")
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")


if __name__ == "__main__":
    main()
