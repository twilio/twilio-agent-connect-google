"""
Invoke Deployed Agent

Simple script to test a deployed agent on GCP Agent Platform Runtime.

Usage:
    # Configure .env file first, then run:
    python invoke_agent.py
"""

import os

import vertexai
from dotenv import load_dotenv
from vertexai.preview import reasoning_engines

# Load environment variables from .env file
load_dotenv()


def main():
    """Invoke the deployed agent."""
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    agent_id = os.getenv("GCP_REASONING_ENGINE_ID")

    if not project:
        print("\n❌ Error: GOOGLE_CLOUD_PROJECT environment variable not set")
        return

    if not agent_id:
        print("\n❌ Error: GCP_REASONING_ENGINE_ID environment variable not set")
        print("\nDeploy an agent first:")
        print("  python deploy_custom.py")
        print("\nThen add the agent ID to your .env file")
        return

    print(f"\nConnecting to agent...")
    print(f"  Project: {project}")
    print(f"  Location: {location}")
    print(f"  Agent ID: {agent_id}\n")

    # Initialize Vertex AI
    vertexai.init(project=project, location=location)

    # Get deployed agent
    agent = reasoning_engines.ReasoningEngine(agent_id)

    # Interactive loop
    print("="*70)
    print("  Agent Ready - Type 'quit' to exit")
    print("="*70)
    print()

    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\nGoodbye!")
                break

            # Query agent
            print("Agent: ", end="", flush=True)
            response = agent.query(input=user_input)
            print(response["output"])
            print()

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")


if __name__ == "__main__":
    main()
