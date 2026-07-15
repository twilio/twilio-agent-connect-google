"""
Invoke Deployed ADK Agent

Simple script to test an ADK agent deployed on GCP Agent Platform Runtime.

Unlike the custom-class / LangChain examples elsewhere in `deploy/`, ADK
agents do NOT expose `.query()`. They are session-based and streaming:
you create a session once per conversation, then call `.stream_query()`
which yields a stream of event dicts (not a single response).

Must use `vertexai.agent_engines.get()` (not the older
`vertexai.preview.reasoning_engines.ReasoningEngine`) to fetch the agent.
ADK's operation schema includes `async`/`async_stream`/`bidi_stream` modes
that the older ReasoningEngine's method-registration code doesn't recognize
and aborts on, which means `stream_query` never gets attached at all.

Usage:
    # Configure .env file first, then run:
    python invoke_adk.py
"""

import os

import vertexai
from dotenv import load_dotenv
from vertexai import agent_engines

# Load environment variables from .env file
load_dotenv()


def extract_final_text(events: list) -> str | None:
    """Picks the final response text out of a stream of ADK events.

    Streamed events include partial chunks and tool-call/tool-response
    events; the final response is the last non-partial event that carries
    text content.
    """
    for event in reversed(events):
        if event.get("partial"):
            continue
        for part in event.get("content", {}).get("parts", []):
            if "text" in part:
                return part["text"]
    return None


def main():
    """Invoke the deployed ADK agent."""
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    agent_id = os.getenv("GCP_REASONING_ENGINE_ID")

    if not project:
        print("\n❌ Error: GOOGLE_CLOUD_PROJECT environment variable not set")
        return

    if not agent_id:
        print("\n❌ Error: GCP_REASONING_ENGINE_ID environment variable not set")
        print("\nDeploy an agent first:")
        print("  ./deploy.sh")
        print("\nThen add the printed resource ID to your .env file")
        return

    print("\nConnecting to agent...")
    print(f"  Project: {project}")
    print(f"  Location: {location}")
    print(f"  Agent ID: {agent_id}\n")

    vertexai.init(project=project, location=location)
    agent = agent_engines.get(agent_id)

    user_id = "local-test-user"
    session = agent.create_session(user_id=user_id)
    session_id = session["id"]

    print("=" * 70)
    print("  Agent Ready - Type 'quit' to exit")
    print("=" * 70)
    print()

    while True:
        try:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["quit", "exit", "q"]:
                print("\nGoodbye!")
                break

            events = list(
                agent.stream_query(
                    message=user_input,
                    user_id=user_id,
                    session_id=session_id,
                )
            )
            text = extract_final_text(events) or "(no text response)"
            print(f"Agent: {text}\n")

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")


if __name__ == "__main__":
    main()
