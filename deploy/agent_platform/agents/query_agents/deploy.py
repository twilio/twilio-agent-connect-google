"""Deploy or update a LangChain agent on GCP Agent Platform Runtime.

Represents the "query() family" (LangChain / LangGraph / AG2) — deployed and
invoked the same way, just a different template class. Run `python deploy.py`;
with no GCP_REASONING_ENGINE_ID in .env it creates a new agent, otherwise updates.
"""

import os
import subprocess

import vertexai
from dotenv import find_dotenv, load_dotenv, set_key
from langchain_google_genai import ChatGoogleGenerativeAI
from vertexai.preview import reasoning_engines

load_dotenv()


def _global_model_builder(model_name, *, model_kwargs=None, project, location):
    """Build the chat model pinned to the global endpoint.

    gemini-3.5-flash is only served on the global endpoint, so the deploy
    region must be overridden here or the agent 404s on its first query.
    """
    return ChatGoogleGenerativeAI(
        model=model_name,
        project=project,
        location="global",
        vertexai=True,
        **(model_kwargs or {}),
    )


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

    agent = reasoning_engines.LangchainAgent(
        model="gemini-3.5-flash",
        system_instruction="Be concise.",
        model_builder=_global_model_builder,
    )
    requirements = ["google-cloud-aiplatform[reasoningengine,langchain]>=1.70.0"]

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
            agent, requirements=requirements, display_name="langchain-agent", sys_version="3.11"
        )
        agent_id = deployed.resource_name.split("/")[-1]
        env_path = find_dotenv()
        if env_path:
            set_key(env_path, "GCP_REASONING_ENGINE_ID", agent_id, quote_mode="never")
        print(f"\n✅ Deployed! Agent ID: {agent_id} (saved to .env)")
        print("Test with: python invoke.py")


if __name__ == "__main__":
    main()
