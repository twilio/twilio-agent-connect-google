#!/bin/bash

# ADK Agent Deployment Script
# This script deploys the agent to Google Cloud Agent Runtime

set -e  # Exit on error

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load environment variables from .env
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    exit 1
fi

echo "Loading environment variables from .env..."
export $(grep -v '^#' .env | xargs)

# Read required variables from .env only
PROJECT_ID="${GOOGLE_CLOUD_PROJECT}"
LOCATION_ID="${GOOGLE_CLOUD_LOCATION}"
DISPLAY_NAME="${AGENT_DISPLAY_NAME}"

# Validate required variables
if [ -z "$PROJECT_ID" ]; then
    echo "❌ Error: PROJECT_ID is not set"
    echo "Please set GOOGLE_CLOUD_PROJECT in .env or run: gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

echo "================================"
echo "Deploying ADK Agent"
echo "================================"
echo "Project ID:    $PROJECT_ID"
echo "Region:        $LOCATION_ID"
echo "Display Name:  $DISPLAY_NAME"
echo "Agent Path:    $SCRIPT_DIR"
echo "================================"
echo ""
echo "⏳ Starting deployment (this may take 3-5 minutes)..."
echo ""

# Deploy the agent
adk deploy agent_engine \
    --project="$PROJECT_ID" \
    --region="$LOCATION_ID" \
    --display_name="$DISPLAY_NAME" \
    .

echo ""
echo "================================"
echo "✅ Deployment complete!"
echo "================================"
echo ""
echo "The RESOURCE_ID should be displayed above."
echo "Save it to invoke your agent:"
echo ""
echo "# ADK agents do NOT expose .query() - they use session-based streaming"
echo "# Python SDK"
echo "from vertexai.preview import reasoning_engines"
echo "agent = reasoning_engines.ReasoningEngine('RESOURCE_ID')"
echo "for event in agent.stream_query(message='Hello', user_id='some-user-id'):"
echo "    print(event)"
echo ""
echo "# See invoke_adk.py in this folder for a runnable example."
echo ""
echo "# REST API"
echo "https://$LOCATION_ID-aiplatform.googleapis.com/v1/projects/$PROJECT_ID/locations/$LOCATION_ID/reasoningEngines/RESOURCE_ID:streamQuery"
echo ""
