# TAC server deployment for a CX Agent Studio agent.
# Run from deploy/cx_agent_studio/. Configuration comes from ./.env.
# The agent itself is built in the CX Agent Studio console (see agent/README.md).

.PHONY: help create-sa deploy-secret deploy-server deploy-all

help:
	@echo "TAC CX Agent Studio deploy targets:"
	@echo "  make create-sa      - create the dedicated deploy service account (tac-deployer)"
	@echo "  make deploy-secret  - store the Twilio credentials in Secret Manager"
	@echo "  make deploy-server  - build + deploy the TAC server to Cloud Run"
	@echo "  make deploy-all     - deploy-secret + deploy-server"

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

# Deploy everything in order: secrets -> server.
deploy-all: deploy-secret deploy-server
