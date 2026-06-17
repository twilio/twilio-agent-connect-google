"""
Deploy or Update Agent

Deploys a new agent to GCP Agent Platform Runtime, or updates existing agent if ID is set.

Usage:
    # First time (no agent ID in .env):
    python deploy_adk.py
    # Creates new agent and prints ID to add to .env

    # Subsequent deploys (agent ID exists in .env):
    python deploy_adk.py
    # Updates existing agent, same ID
"""

import os
import subprocess

import vertexai
from dotenv import load_dotenv
from vertexai.preview import reasoning_engines

# Load environment variables from .env file
load_dotenv()


class SimpleAgent:
    """Minimal agent using Google GenAI SDK with Gemini 3.5 Flash."""

    def __init__(self, project: str):
        self.project = project

    def query(self, **kwargs):
        from google import genai

        input_text = kwargs.get("input", "")

        # Use GenAI SDK with Enterprise mode
        client = genai.Client(
            enterprise=True,
            project=self.project,
            location="global"
        )

        # Prepend instruction for concise responses (important for SMS)
        prompt = f"Be concise.\n\n{input_text}"

        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt
        )

        return {"output": response.text}


def main():
    """Deploy or update agent on GCP."""
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

    # Create agent instance
    agent = SimpleAgent(project=project)

    # Check if updating existing agent or creating new one
    if agent_id:
        print(f"\nUpdating existing agent")
        print(f"Project: {project}")
        print(f"Location: {location}")
        print(f"Agent ID: {agent_id}\n")

        try:
            # Get existing agent
            existing_agent = reasoning_engines.ReasoningEngine(agent_id)

            # Update it
            print("Updating (3-5 minutes)...")
            existing_agent.update(
                reasoning_engine=agent,
                requirements=["google-genai>=2.0.0"],
                sys_version="3.11",
            )

            print(f"\n✅ Updated! Agent ID: {agent_id}")
            print(f"\nTest with: python invoke_agent.py")

        except Exception as e:
            print(f"❌ Failed to update agent: {e}")
            print("\nAgent ID may be invalid. Remove GCP_REASONING_ENGINE_ID from .env to create new agent.")

    else:
        print(f"\nCreating new agent")
        print(f"Project: {project}")
        print(f"Location: {location}\n")

        # Create new agent
        print("Deploying (3-5 minutes)...")
        deployed = reasoning_engines.ReasoningEngine.create(
            agent,
            requirements=["google-genai>=2.0.0"],
            display_name="simple-gemini-agent",
            sys_version="3.11",
        )

        agent_id = deployed.resource_name.split("/")[-1]
        print(f"\n✅ Deployed! New Agent ID: {agent_id}\n")
        print(f"Add to .env:\nGCP_REASONING_ENGINE_ID={agent_id}\n")
        print(f"Test with: python invoke_agent.py")


if __name__ == "__main__":
    main()
