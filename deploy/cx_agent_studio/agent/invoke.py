"""Interactive test client for an agent built in CX Agent Studio (CES).

Invokes the deployed agent over the CES REST `runSession` endpoint — the same
call the connector uses. Set CX_AGENT_ID in ../.env to the agent (app) resource
name. Requires Application Default Credentials with the `roles/ces.client` role
(`gcloud auth application-default login`).
"""

import os
import uuid

import google.auth
from dotenv import load_dotenv
from google.auth.transport.requests import AuthorizedSession

load_dotenv()

CES_HOST = "ces.googleapis.com"


def extract_text(data: dict) -> str:
    """Concatenate the text turns from a CES RunSessionResponse."""
    outputs = data.get("outputs") or []
    texts = [
        output["text"]
        for output in outputs
        if isinstance(output, dict) and isinstance(output.get("text"), str)
    ]
    return "".join(texts).strip()


def main():
    agent_id = os.getenv("CX_AGENT_ID")
    if not agent_id:
        print("\n❌ Error: CX_AGENT_ID not set — build and deploy an agent in CX Agent Studio first (see README.md)")
        return
    agent_id = agent_id.rstrip("/")

    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    client = AuthorizedSession(creds)
    # One session for the whole run so CES keeps the conversation history.
    session = f"{agent_id}/sessions/{uuid.uuid4()}"

    print(f"\nConnecting to agent {agent_id}...\n")
    print("Agent ready - press Ctrl+C to exit.\n")
    try:
        while True:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            response = client.post(
                f"https://{CES_HOST}/v1/{session}:runSession",
                json={"config": {"session": session}, "inputs": [{"text": user_input}]},
            )
            response.raise_for_status()
            print(f"Agent: {extract_text(response.json()) or '(no text response)'}\n")
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
