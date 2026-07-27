"""Interactive test client for a Conversational Agents (Dialogflow CX) agent.

Invokes the agent over the Dialogflow CX `detectIntent` (v3) API. Set
CONVERSATIONAL_AGENT_ID in .env to the agent resource name:
    projects/<project>/locations/<location>/agents/<agent-id>

Requires Application Default Credentials with the Dialogflow API Client role
(`gcloud auth application-default login`). Works for both Playbook- and
Flow-based agents — the runtime API is the same.
"""

import os
import uuid

import google.auth
import google.oauth2.credentials
from dotenv import load_dotenv
from google.auth.transport.requests import AuthorizedSession

load_dotenv()

_TIMEOUT_S = 30


def dialogflow_host(location: str) -> str:
    return "dialogflow.googleapis.com" if location == "global" else f"{location}-dialogflow.googleapis.com"


def extract_text(data: dict) -> str:
    """Concatenate the text from a Dialogflow CX DetectIntentResponse.

    Reply text lives in queryResult.responseMessages[].text.text (a list).
    """
    messages = data.get("queryResult", {}).get("responseMessages", [])
    parts = [t.strip() for m in messages for t in m.get("text", {}).get("text", [])]
    return " ".join(p for p in parts if p)


def main():
    agent = os.getenv("CONVERSATIONAL_AGENT_ID")
    if not agent:
        print("\n❌ Error: CONVERSATIONAL_AGENT_ID not set — create an agent first (see README.md)")
        return
    agent = agent.rstrip("/")
    _, project, _, location, _, _ = agent.split("/")[:6]
    language = os.getenv("DIALOGFLOW_LANGUAGE_CODE", "en")

    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    client = AuthorizedSession(creds)
    # One session for the whole run so Dialogflow keeps the session state.
    session = f"{agent}/sessions/{uuid.uuid4()}"
    url = f"https://{dialogflow_host(location)}/v3/{session}:detectIntent"
    # The quota project header is only needed (and only valid) for user ADC;
    # a service account would need serviceusage.services.use to set it.
    headers = (
        {"X-Goog-User-Project": project}
        if isinstance(creds, google.oauth2.credentials.Credentials)
        else {}
    )

    print(f"\nConnecting to agent {agent}...\n")
    print("Agent ready - press Ctrl+C to exit.\n")
    try:
        while True:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            response = client.post(
                url,
                headers=headers,
                json={"queryInput": {"text": {"text": user_input}, "languageCode": language}},
                timeout=_TIMEOUT_S,
            )
            response.raise_for_status()
            print(f"Agent: {extract_text(response.json()) or '(no text response)'}\n")
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
