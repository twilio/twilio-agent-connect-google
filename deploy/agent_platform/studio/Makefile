# TAC Agent Platform Runtime + Cloud Run deployment — Agent Studio app.
# Run from deploy/agent_platform/studio/. Configuration comes from ./.env.
#
# The agent itself is built and deployed from the Agent Studio console (no
# `make deploy-agent` target) — see agent/README.md. Set the resulting agent
# ID in .env before running any of these targets.

.PHONY: help create-sa deploy-secret deploy-server deploy-all

help:
	@echo "TAC Agent Studio deploy targets:"
	@echo "  make create-sa       - create the dedicated deploy service account (tac-deployer)"
	@echo "  make deploy-secret   - store the Twilio credentials in Secret Manager"
	@echo "  make deploy-server   - build + deploy the TAC server to Cloud Run"
	@echo "  make deploy-all      - deploy-secret + deploy-server"
	@echo ""
	@echo "Build and deploy the agent itself from the Agent Studio console — see agent/README.md."

# Create the dedicated deploy SA (tac-deployer). Project is read from .env; the
# deploy scripts derive the same tac-deployer@<project> email, so nothing to set.
create-sa:
	@project=$$(grep -E '^GOOGLE_CLOUD_PROJECT=' .env | head -1 | cut -d= -f2-); \
	[ -n "$$project" ] || { echo "❌ GOOGLE_CLOUD_PROJECT not set in .env"; exit 1; }; \
	sa="tac-deployer@$$project.iam.gserviceaccount.com"; \
	gcloud iam service-accounts describe "$$sa" --project "$$project" >/dev/null 2>&1 \
	  || gcloud iam service-accounts create tac-deployer --project "$$project" --display-name="TAC deployer"; \
	echo "✅ $$sa"

# Store the Twilio credentials in Secret Manager (run before deploy-server).
deploy-secret:
	cd secret && ./secrets.sh

# Build the image and deploy the server to Cloud Run.
deploy-server:
	cd server && ./deploy.sh

# Deploy everything: secrets -> server. (Agent is deployed via the console.)
deploy-all: deploy-secret deploy-server
