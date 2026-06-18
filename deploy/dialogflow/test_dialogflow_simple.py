#!/usr/bin/env python3
"""Test Dialogflow CX Playbook Agent."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.cloud.dialogflowcx_v3 import SessionsClient


def main():
    load_dotenv(Path(__file__).parent.parent / ".env")

    project_id = os.environ["GOOGLE_CLOUD_PROJECT"]
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    agent_id = os.environ["DIALOGFLOW_CX_AGENT_ID"]
    language_code = os.getenv("DIALOGFLOW_CX_LANGUAGE_CODE", "en")

    session_id = "test-session-" + os.urandom(8).hex()
    session_path = f"projects/{project_id}/locations/{location}/agents/{agent_id}/sessions/{session_id}"
    api_endpoint = f"{location}-dialogflow.googleapis.com:443"

    print(f"Testing agent {agent_id}")
    print(f"Location: {location}\n")

    try:
        client = SessionsClient(client_options={"api_endpoint": api_endpoint})
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        sys.exit(1)

    test_messages = [
        "Hello, I need help",
        "I want to track my order",
        "Tell me about your pricing",
    ]

    for i, user_msg in enumerate(test_messages, 1):
        print(f"[{i}] User: {user_msg}")

        try:
            response = client.detect_intent(
                request={
                    "session": session_path,
                    "query_input": {
                        "text": {"text": user_msg},
                        "language_code": language_code,
                    },
                }
            )

            response_texts = []
            if hasattr(response, "query_result") and response.query_result:
                for msg in response.query_result.response_messages:
                    if hasattr(msg, "text") and msg.text:
                        response_texts.extend(msg.text.text)

            if response_texts:
                for text in response_texts:
                    print(f"    Agent: {text}")
            else:
                print("    ⚠️  No response")

            print()

        except Exception as e:
            print(f"    ❌ Error: {e}\n")

    print("✅ Test complete!")


if __name__ == "__main__":
    main()
