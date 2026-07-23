# TAC Agent Platform Runtime + Cloud Run deployment.
# Run from deploy/agent_platform/. Configuration comes from ./.env.

AGENT ?= adk

.PHONY: help create-sa deploy-agent deploy-secret deploy-server deploy-all

help:
	@echo "TAC Agent Platform deploy targets:"
	@echo "  make create-sa                 - create the dedicated deploy service account (tac-deployer)"
	@echo "  make deploy-agent [AGENT=...]  - deploy an agent (AGENT=adk|custom|query_agents; default: adk)"
	@echo "  make deploy-secret             - store the Twilio credentials in Secret Manager"
	@echo "  make deploy-server             - build + deploy the TAC server to Cloud Run"
	@echo "  make deploy-all [AGENT=...]    - deploy-agent + deploy-secret + deploy-server"

# Create the dedicated deploy SA (tac-deployer). Project is read from .env; the
# deploy scripts derive the same tac-deployer@<project> email, so nothing to set.
create-sa:
	@project=$$(grep -E '^GOOGLE_CLOUD_PROJECT=' .env | head -1 | cut -d= -f2-); \
	[ -n "$$project" ] || { echo "❌ GOOGLE_CLOUD_PROJECT not set in .env"; exit 1; }; \
	sa="tac-deployer@$$project.iam.gserviceaccount.com"; \
	gcloud iam service-accounts describe "$$sa" --project "$$project" >/dev/null 2>&1 \
	  || gcloud iam service-accounts create tac-deployer --project "$$project" --display-name="TAC deployer"; \
	echo "✅ $$sa"

# Deploy one agent. AGENT selects the method: adk | custom | query_agents.
deploy-agent:
	@case "$(AGENT)" in \
	  adk) cd agents/adk && ./deploy.sh ;; \
	  custom|query_agents) cd agents/$(AGENT) && python deploy.py ;; \
	  *) echo "Unknown AGENT='$(AGENT)' (use: adk | custom | query_agents)"; exit 1 ;; \
	esac

# Store the Twilio credentials in Secret Manager (run before deploy-server).
deploy-secret:
	cd secret && ./secrets.sh

# Build the image and deploy the server to Cloud Run.
deploy-server:
	cd server && ./deploy.sh

# Deploy everything in order: agent (AGENT=...) -> secrets -> server.
# deploy-agent writes the new agent ID into .env so deploy-server picks it up.
deploy-all: deploy-agent deploy-secret deploy-server
