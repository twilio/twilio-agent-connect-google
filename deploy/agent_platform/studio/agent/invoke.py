"""Interactive test client for an agent built and deployed in Agent Studio.

Studio deploys a source-code (google-adk) app that does not register the
query/stream_query class methods the Vertex AI SDK wraps (its deployment
metadata has no `class_methods`, so the SDK has nothing to bind), so it's
invoked over the `:streamQuery` REST endpoint with an explicit `class_method`
instead — same session-based ADK mechanism as the adk/ example, just called
directly rather than through SDK-bound methods. Set GCP_REASONING_ENGINE_ID
in .env to the deployed agent's resource ID.
"""

import json
import os
import uuid

import google.auth
import google.auth.transport.requests
import requests
from dotenv import load_dotenv

load_dotenv()


def extract_text(raw: str) -> str:
    """Concatenate the text parts from a streamQuery response (concatenated JSON)."""
    decoder = json.JSONDecoder()
    idx, texts = 0, []
    while idx < len(raw):
        while idx < len(raw) and raw[idx] in " \t\r\n,[]":
            idx += 1
        if idx >= len(raw):
            break
        event, idx = decoder.raw_decode(raw, idx)
        for part in event.get("content", {}).get("parts", []):
            if "text" in part:
                texts.append(part["text"])
    return "".join(texts).strip()


def main():
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION")
    agent_id = os.getenv("GCP_REASONING_ENGINE_ID")

    if not project:
        print("\n❌ Error: GOOGLE_CLOUD_PROJECT not set")
        return
    if not location:
        print("\n❌ Error: GOOGLE_CLOUD_LOCATION not set")
        return
    if not agent_id:
        print("\n❌ Error: GCP_REASONING_ENGINE_ID not set — build and deploy an agent in Agent Studio first (see README.md)")
        return

    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    auth_req = google.auth.transport.requests.Request()
    base_url = (
        f"https://{location}-aiplatform.googleapis.com/v1/projects/{project}"
        f"/locations/{location}/reasoningEngines/{agent_id}"
    )
    user_id = "local-test-user"
    session_id = f"local-test-{uuid.uuid4().hex[:8]}"

    print(f"\nConnecting to agent {agent_id} ({project}/{location})...\n")

    if not creds.valid:
        creds.refresh(auth_req)
    headers = {"Authorization": f"Bearer {creds.token}"}
    requests.post(
        f"{base_url}/sessions?sessionId={session_id}",
        headers=headers,
        json={"userId": user_id},
    ).raise_for_status()

    print("Agent ready - press Ctrl+C to exit.\n")
    try:
        while True:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if not creds.valid:
                creds.refresh(auth_req)
                headers = {"Authorization": f"Bearer {creds.token}"}
            resp = requests.post(
                f"{base_url}:streamQuery",
                headers=headers,
                json={
                    "class_method": "async_stream_query",
                    "input": {
                        "user_id": user_id,
                        "session_id": session_id,
                        "message": user_input,
                    },
                },
            )
            resp.raise_for_status()
            print(f"Agent: {extract_text(resp.text) or '(no text response)'}\n")
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
