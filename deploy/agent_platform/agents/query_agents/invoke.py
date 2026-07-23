"""
Invoke Deployed LangChain Agent

Simple script to test a LangChain agent deployed on GCP Agent Platform Runtime.

Usage:
    # Configure .env file first, then run:
    python invoke.py
"""

import os

import vertexai
from dotenv import load_dotenv
from vertexai import agent_engines

load_dotenv()


def main():
    """Invoke the deployed LangChain agent."""
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    agent_id = os.getenv("GCP_REASONING_ENGINE_ID")

    if not project:
        print("\n❌ Error: GOOGLE_CLOUD_PROJECT environment variable not set")
        return

    if not agent_id:
        print("\n❌ Error: GCP_REASONING_ENGINE_ID environment variable not set")
        print("\nDeploy an agent first:")
        print("  python deploy.py")
        print("\nThen add the agent ID to your .env file")
        return

    print("\nConnecting to agent...")
    print(f"  Project: {project}")
    print(f"  Location: {location}")
    print(f"  Agent ID: {agent_id}\n")

    vertexai.init(project=project, location=location)
    agent = agent_engines.get(agent_id)

    print("Agent ready - press Ctrl+C to exit.\n")
    try:
        while True:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            response = agent.query(input=user_input)
            print(f"Agent: {response['output']}\n")
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
