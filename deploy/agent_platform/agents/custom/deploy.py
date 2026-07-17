"""Deploy or update a custom Python agent on GCP Agent Platform Runtime.

Run `python deploy.py`. With no GCP_REASONING_ENGINE_ID in .env it creates a
new agent and prints the ID; with one set it updates that agent.
"""

import os
import subprocess

import vertexai
from dotenv import find_dotenv, load_dotenv, set_key
from google import genai
from vertexai.preview import reasoning_engines

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

    subprocess.run(
        ["gcloud", "services", "enable", "aiplatform.googleapis.com", "--project", project],
        check=True,
    )

    staging_bucket = f"gs://{project}-reasoning-engine-staging"
    result = subprocess.run(["gsutil", "ls", "-b", staging_bucket], capture_output=True)
    if result.returncode != 0:
        print(f"Creating staging bucket: {staging_bucket}")
        subprocess.run(["gsutil", "mb", "-l", location, staging_bucket], check=True)

    vertexai.init(project=project, location=location, staging_bucket=staging_bucket)

    agent = SimpleAgent(project=project)
    requirements = ["google-genai>=2.0.0", "google-cloud-aiplatform>=1.70.0"]

    if agent_id:
        print(f"\nUpdating agent {agent_id} (3-5 minutes)...")
        try:
            existing_agent = reasoning_engines.ReasoningEngine(agent_id)
            existing_agent.update(
                reasoning_engine=agent, requirements=requirements, sys_version="3.11"
            )
            print(f"\n✅ Updated! Agent ID: {agent_id}")
            print("Test with: python invoke.py")
        except Exception as e:
            print(f"❌ Failed to update agent: {e}")
            print("Agent ID may be invalid. Remove GCP_REASONING_ENGINE_ID from .env to create a new agent.")
    else:
        print("\nDeploying new agent (3-5 minutes)...")
        deployed = reasoning_engines.ReasoningEngine.create(
            agent, requirements=requirements, display_name="simple-gemini-agent", sys_version="3.11"
        )
        agent_id = deployed.resource_name.split("/")[-1]
        env_path = find_dotenv()
        if env_path:
            set_key(env_path, "GCP_REASONING_ENGINE_ID", agent_id, quote_mode="never")
        print(f"\n✅ Deployed! Agent ID: {agent_id} (saved to .env)")
        print("Test with: python invoke.py")


if __name__ == "__main__":
    main()
