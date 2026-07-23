#!/bin/bash

# Store the four Twilio credentials in Secret Manager (create or update to match
# .env). The runtime SA is granted read access at deploy time by deploy.sh.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env"   # conversational_agents/.env

if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Error: $ENV_FILE not found — copy .env.example to .env and fill it in first."
    exit 1
fi
set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

PROJECT="${GOOGLE_CLOUD_PROJECT:?GOOGLE_CLOUD_PROJECT must be set in .env}"
SECRET_ENV_KEYS="TWILIO_ACCOUNT_SID TWILIO_AUTH_TOKEN TWILIO_API_KEY TWILIO_API_SECRET"

echo "==> Storing Twilio credentials in Secret Manager ($PROJECT)"
gcloud services enable secretmanager.googleapis.com --project "$PROJECT" --quiet

for key in $SECRET_ENV_KEYS; do
    value="${!key:-}"
    if [ -z "$value" ]; then
        echo "❌ Error: $key must be set in .env"
        exit 1
    fi
    sname="tac-$(printf '%s' "$key" | tr '[:upper:]_' '[:lower:]-')"
    if gcloud secrets describe "$sname" --project "$PROJECT" >/dev/null 2>&1; then
        printf '%s' "$value" | gcloud secrets versions add "$sname" --data-file=- --project "$PROJECT" >/dev/null
    else
        printf '%s' "$value" | gcloud secrets create "$sname" --data-file=- --project "$PROJECT" >/dev/null
    fi
done

echo "✅ Secrets stored"
