#!/bin/bash

# Build the server image (Cloud Build), deploy it to Cloud Run, fill in the
# public URL, and print the Twilio webhook URLs.
# Requires the Twilio secrets to exist first: make deploy-secret.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
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
SERVICE="${CLOUD_RUN_SERVICE:-tac-server-studio}"
REPO="${ARTIFACT_REPO:-tac}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/${SERVICE}:latest"
SECRET_ENV_KEYS="TWILIO_ACCOUNT_SID TWILIO_AUTH_TOKEN TWILIO_API_KEY TWILIO_API_SECRET"
# Build + Cloud Run runtime identity: the dedicated tac-deployer SA (create it
# with `make create-sa`). Override with DEPLOY_SERVICE_ACCOUNT if needed.
SA_EMAIL="${DEPLOY_SERVICE_ACCOUNT:-tac-deployer@${PROJECT}.iam.gserviceaccount.com}"

echo "==> Deploying $SERVICE to Cloud Run ($PROJECT / $REGION)"

# --- Build a Cloud Run env-vars file from .env -----------------------------
# Skip keys Cloud Run manages, script-only knobs, and the secret keys.
ENV_YAML="$(mktemp)"
trap 'rm -f "$ENV_YAML"' EXIT
while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
        ''|\#*) continue ;;
    esac
    key="${line%%=*}"
    val="${line#*=}"
    case "$key" in
        PORT|TWILIO_SERVER_PORT|TWILIO_VOICE_PUBLIC_DOMAIN|GOOGLE_APPLICATION_CREDENTIALS) continue ;;
        CLOUD_RUN_SERVICE|ARTIFACT_REPO|DEPLOY_SERVICE_ACCOUNT) continue ;;
    esac
    case " $SECRET_ENV_KEYS " in *" $key "*) continue ;; esac
    val="${val%\"}"; val="${val#\"}"
    printf '%s: "%s"\n' "$key" "$val" >> "$ENV_YAML"
done < "$ENV_FILE"

# --- Reference the Twilio secrets + grant the runtime SA read access ---------
# Secrets must already exist (make deploy-secret). Grant secretAccessor to
# SA_EMAIL here so it matches whatever SA the service actually runs as.
SECRETS_CSV=""
for key in $SECRET_ENV_KEYS; do
    sname="tac-$(printf '%s' "$key" | tr '[:upper:]_' '[:lower:]-')"
    if ! gcloud secrets describe "$sname" --project "$PROJECT" >/dev/null 2>&1; then
        echo "❌ Error: secret '$sname' not found. Run 'make deploy-secret' first."
        exit 1
    fi
    gcloud secrets add-iam-policy-binding "$sname" --project "$PROJECT" \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="roles/secretmanager.secretAccessor" --quiet >/dev/null
    SECRETS_CSV="${SECRETS_CSV:+$SECRETS_CSV,}${key}=${sname}:latest"
done

# --- Enable APIs + ensure Artifact Registry repo (idempotent) --------------
gcloud services enable \
    run.googleapis.com cloudbuild.googleapis.com \
    artifactregistry.googleapis.com aiplatform.googleapis.com \
    --project "$PROJECT" --quiet

# Grant the deploy SA the roles it needs: build (Cloud Build), reading the
# source tarball Cloud Build stages in its auto-created GCS bucket (a fresh
# custom SA has no access to it by default), and runtime (call the agent).
# secretAccessor is granted per-secret by secrets.sh.
for role in roles/cloudbuild.builds.builder roles/storage.objectViewer roles/aiplatform.user; do
    gcloud projects add-iam-policy-binding "$PROJECT" \
        --member="serviceAccount:${SA_EMAIL}" --role="$role" --condition=None --quiet >/dev/null
done

if ! gcloud artifacts repositories describe "$REPO" \
        --location "$REGION" --project "$PROJECT" >/dev/null 2>&1; then
    gcloud artifacts repositories create "$REPO" \
        --repository-format=docker --location "$REGION" --project "$PROJECT"
fi

# --- Build image (context = repo root) -------------------------------------
echo "==> Building image..."
( cd "$REPO_ROOT" && gcloud builds submit \
    --project "$PROJECT" \
    --config deploy/agent_platform/studio/server/cloudbuild.yaml \
    --substitutions=_IMAGE="$IMAGE" \
    --service-account="projects/${PROJECT}/serviceAccounts/${SA_EMAIL}" \
    . )

# --- Deploy ----------------------------------------------------------------
# timeout + no-cpu-throttling keep long-lived WebSocket calls alive;
# min/max-instances 1 because the connector keeps conversation state in memory.
echo "==> Deploying service..."
gcloud run deploy "$SERVICE" \
    --project "$PROJECT" \
    --region "$REGION" \
    --image "$IMAGE" \
    --platform managed \
    --allow-unauthenticated \
    --service-account "$SA_EMAIL" \
    --port 8080 \
    --timeout 3600 \
    --no-cpu-throttling \
    --min-instances 1 \
    --max-instances 1 \
    --memory 1Gi \
    --cpu 1 \
    --env-vars-file "$ENV_YAML" \
    --set-secrets "$SECRETS_CSV"

# --- Fill in the service's own public domain, then re-point it -------------
URL="$(gcloud run services describe "$SERVICE" \
    --project "$PROJECT" --region "$REGION" --format='value(status.url)')"
HOST="${URL#https://}"

gcloud run services update "$SERVICE" \
    --project "$PROJECT" --region "$REGION" \
    --update-env-vars "TWILIO_VOICE_PUBLIC_DOMAIN=${HOST}" --quiet >/dev/null

cat <<EOF

✅ Deployed: $URL

Configure Twilio:
  Conversation Orchestrator status callback : ${URL}/webhook   (POST)
  Voice "A call comes in" webhook           : ${URL}/twiml     (POST)
EOF
