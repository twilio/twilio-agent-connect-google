"""
Deploy or Update a LangChain Agent

Deploys a LangChain agent (via the official `LangchainAgent` template) to GCP
Agent Platform Runtime, or updates the existing agent if an ID is set.

This represents the "query() family" of deployments: LangGraph and AG2 agents
are deployed and invoked the same way (a single synchronous `.query(input=...)`
call), just with a different template class.

Usage:
    # First time (no agent ID in .env):
    python deploy_langchain.py
    # Creates new agent and prints ID to add to .env

    # Subsequent deploys (agent ID exists in .env):
    python deploy_langchain.py
    # Updates existing agent, same ID
"""

import os
import subprocess

import vertexai
from dotenv import load_dotenv
from vertexai.preview import reasoning_engines

# Load environment variables from .env file
load_dotenv()


def _global_model_builder(model_name, *, model_kwargs=None, project, location):
    """Builds the chat model pinned to the global endpoint.

    gemini-3.5-flash (Enterprise Agent Platform API) is only served via the
    global endpoint, not regional ones. LangchainAgent's default model
    builder passes through whatever `location` the Reasoning Engine itself
    is deployed to (e.g. us-central1), so it must be overridden here or the
    deployed agent 404s on its first real query.
    """
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=model_name,
        project=project,
        location="global",
        vertexai=True,
        **(model_kwargs or {}),
    )


def main():
    """Deploy or update the LangChain agent on GCP."""
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    agent_id = os.getenv("GCP_REASONING_ENGINE_ID")

    if not project:
        print("❌ Error: GOOGLE_CLOUD_PROJECT environment variable not set")
        return

    # Create staging bucket
    staging_bucket = f"gs://{project}-reasoning-engine-staging"
    result = subprocess.run(
        ["gsutil", "ls", "-b", staging_bucket],
        capture_output=True,
    )
    if result.returncode != 0:
        print(f"Creating staging bucket: {staging_bucket}")
        subprocess.run(["gsutil", "mb", "-l", location, staging_bucket], check=True)

    # Initialize Vertex AI
    vertexai.init(project=project, location=location, staging_bucket=staging_bucket)

    # Create the LangChain agent instance (AgentExecutor under the hood)
    agent = reasoning_engines.LangchainAgent(
        model="gemini-3.5-flash",
        system_instruction="Be concise.",
        model_builder=_global_model_builder,
    )

    requirements = [
        "google-cloud-aiplatform[reasoningengine,langchain]>=1.70.0",
    ]

    # Check if updating existing agent or creating new one
    if agent_id:
        print("\nUpdating existing agent")
        print(f"Project: {project}")
        print(f"Location: {location}")
        print(f"Agent ID: {agent_id}\n")

        try:
            existing_agent = reasoning_engines.ReasoningEngine(agent_id)

            print("Updating (3-5 minutes)...")
            existing_agent.update(
                reasoning_engine=agent,
                requirements=requirements,
                sys_version="3.11",
            )

            print(f"\n✅ Updated! Agent ID: {agent_id}")
            print("\nTest with: python invoke_langchain.py")

        except Exception as e:
            print(f"❌ Failed to update agent: {e}")
            print("\nAgent ID may be invalid. Remove GCP_REASONING_ENGINE_ID from .env to create new agent.")

    else:
        print("\nCreating new agent")
        print(f"Project: {project}")
        print(f"Location: {location}\n")

        print("Deploying (3-5 minutes)...")
        deployed = reasoning_engines.ReasoningEngine.create(
            agent,
            requirements=requirements,
            display_name="langchain-agent",
            sys_version="3.11",
        )

        agent_id = deployed.resource_name.split("/")[-1]
        print(f"\n✅ Deployed! New Agent ID: {agent_id}\n")
        print(f"Add to .env:\nGCP_REASONING_ENGINE_ID={agent_id}\n")
        print("Test with: python invoke_langchain.py")


if __name__ == "__main__":
    main()
