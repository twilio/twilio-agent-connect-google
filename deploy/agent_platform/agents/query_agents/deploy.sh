#!/bin/bash

# LangChain Agent Deployment Script
# Deploys the LangChain agent (LangchainAgent template) to
# GCP Agent Platform Runtime via deploy_langchain.py.

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    echo "Copy .env.example to .env and fill in GOOGLE_CLOUD_PROJECT first."
    exit 1
fi

echo "================================"
echo "Deploying LangChain Agent"
echo "================================"
echo ""

python3 deploy_langchain.py
