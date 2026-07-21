"""Deploy or update a LangChain agent on GCP Agent Platform Runtime.

Represents the "query() family" (LangChain / LangGraph / AG2) — deployed and
invoked the same way, just a different template class. Run `python deploy.py`;
with no GCP_REASONING_ENGINE_ID in .env it creates a new agent, otherwise updates.
"""

import os

import vertexai
from dotenv import find_dotenv, load_dotenv, set_key
from google.cloud import storage
from langchain_google_genai import ChatGoogleGenerativeAI
from vertexai import agent_engines

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

    bucket_name = f"{project}-reasoning-engine-staging"
    storage_client = storage.Client(project=project)
    if not storage_client.bucket(bucket_name).exists():
        print(f"Creating staging bucket: gs://{bucket_name}")
        storage_client.create_bucket(bucket_name, location=location)

    vertexai.init(project=project, location=location, staging_bucket=f"gs://{bucket_name}")

    agent = agent_engines.LangchainAgent(
        model="gemini-3.5-flash",
        system_instruction="Be concise.",
        model_builder=_global_model_builder,
    )
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
            agent, requirements=requirements, display_name="langchain-agent"
        )
        agent_id = deployed.resource_name.split("/")[-1]
        env_path = find_dotenv()
        if env_path:
            set_key(env_path, "GCP_REASONING_ENGINE_ID", agent_id, quote_mode="never")
        print(f"\n✅ Deployed! Agent ID: {agent_id} (saved to .env)")
        print("Test with: python invoke.py")


if __name__ == "__main__":
    main()
