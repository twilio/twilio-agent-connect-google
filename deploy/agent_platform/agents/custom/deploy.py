"""Deploy or update a custom Python agent on GCP Agent Platform Runtime.

Run `python deploy.py`. With no GCP_REASONING_ENGINE_ID in .env it creates a
new agent and prints the ID; with one set it updates that agent.
"""

import os

import vertexai
from dotenv import find_dotenv, load_dotenv, set_key
from google import genai
from google.cloud import storage
from vertexai import agent_engines

load_dotenv()


class SimpleAgent:
    """Minimal agent using the GenAI SDK with Gemini 3.5 Flash."""

    def __init__(self, project: str):
        self.project = project

    def query(self, **kwargs):
        input_text = kwargs.get("input", "")
        client = genai.Client(enterprise=True, project=self.project, location="global")
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=f"Be concise.\n\n{input_text}",
        )
        return {"output": response.text}


def main():
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    agent_id = os.getenv("GCP_REASONING_ENGINE_ID")

    if not project:
        print("❌ Error: GOOGLE_CLOUD_PROJECT not set")
        return

    bucket_name = f"{project}-reasoning-engine-staging"
    storage_client = storage.Client(project=project)
    if not storage_client.bucket(bucket_name).exists():
        print(f"Creating staging bucket: gs://{bucket_name}")
        storage_client.create_bucket(bucket_name, location=location)

    vertexai.init(project=project, location=location, staging_bucket=f"gs://{bucket_name}")

    agent = SimpleAgent(project=project)
    requirements = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")

    if agent_id:
        print(f"\nUpdating agent {agent_id} (3-5 minutes)...")
        try:
            agent_engines.get(agent_id).update(agent_engine=agent, requirements=requirements)
            print(f"\n✅ Updated! Agent ID: {agent_id}")
            print("Test with: python invoke.py")
        except Exception as e:
            print(f"❌ Failed to update agent: {e}")
            print("Agent ID may be invalid. Remove GCP_REASONING_ENGINE_ID from .env to create a new agent.")
    else:
        print("\nDeploying new agent (3-5 minutes)...")
        deployed = agent_engines.create(
            agent, requirements=requirements, display_name="simple-gemini-agent"
        )
        agent_id = deployed.resource_name.split("/")[-1]
        env_path = find_dotenv()
        if env_path:
            set_key(env_path, "GCP_REASONING_ENGINE_ID", agent_id, quote_mode="never")
        print(f"\n✅ Deployed! Agent ID: {agent_id} (saved to .env)")
        print("Test with: python invoke.py")


if __name__ == "__main__":
    main()
