#!/bin/bash

# Custom Python Agent Deployment Script
# Deploys the custom Python agent (SimpleAgent, no framework) to
# GCP Agent Platform Runtime via deploy_custom.py.

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    echo "Copy .env.example to .env and fill in GOOGLE_CLOUD_PROJECT first."
    exit 1
fi

echo "================================"
echo "Deploying Custom Python Agent"
echo "================================"
echo ""

python3 deploy_custom.py
