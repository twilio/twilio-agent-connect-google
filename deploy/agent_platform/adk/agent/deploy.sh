#!/bin/bash

# Deploy the ADK agent to Agent Platform Runtime and save the new ID to .env.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
ENV_FILE="$SCRIPT_DIR/../.env"   # adk/.env

if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Error: $ENV_FILE not found — copy .env.example to .env and fill it in first."
    exit 1
fi
set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

PROJECT="${GOOGLE_CLOUD_PROJECT:?GOOGLE_CLOUD_PROJECT must be set in .env}"
REGION="${GOOGLE_CLOUD_LOCATION:?GOOGLE_CLOUD_LOCATION must be set in .env}"
DISPLAY_NAME="tac-agent"

echo "==> Deploying ADK agent (3-5 minutes)..."
output="$(adk deploy agent_engine \
    --project="$PROJECT" \
    --region="$REGION" \
    --display_name="$DISPLAY_NAME" \
    . 2>&1 | tee /dev/stderr)"

# `adk deploy agent_engine` exits 0 even when the deploy itself failed (e.g.
# it creates the instance, then fails and cleans it back up), so `set -e`
# never catches it — check the output text for a failure marker instead of
# trusting the exit code, or we'd save a since-deleted agent_id to .env.
if printf '%s' "$output" | grep -qE 'Failed to deploy|Deploy failed'; then
    echo "❌ Agent deploy failed — see output above. Not saving an agent ID to .env."
    exit 1
fi

agent_id="$(printf '%s' "$output" | grep -oE 'reasoningEngines/[0-9]+' | tail -1 | cut -d/ -f2)"
if [ -z "$agent_id" ]; then
    echo "⚠️  Could not parse the agent ID — set GCP_REASONING_ENGINE_ID in .env manually."
    exit 0
fi

if grep -q '^GCP_REASONING_ENGINE_ID=' "$ENV_FILE"; then
    sed -i.bak "s|^GCP_REASONING_ENGINE_ID=.*|GCP_REASONING_ENGINE_ID=${agent_id}|" "$ENV_FILE"
    rm -f "$ENV_FILE.bak"
else
    printf 'GCP_REASONING_ENGINE_ID=%s\n' "$agent_id" >> "$ENV_FILE"
fi
echo "✅ Deployed ADK agent ${agent_id} (saved to .env)"
