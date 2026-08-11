# TAC Server on Cloud Run (Agent Studio app)
#
# Build context is the REPO ROOT (see cloudbuild.yaml / deploy.sh), so the
# COPY paths below are repo-relative. The image installs this package with the
# `vertex-ai` + `server` extras and runs this folder's entrypoint (main.py).
FROM python:3.11-slim

WORKDIR /app

# Install only what pip needs to build the wheel first, so layer caching kicks
# in when only the entrypoint changes.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir ".[vertex-ai,server]"

# The server entrypoint (lives in this folder).
COPY deploy/agent_platform/studio/server/main.py ./main.py

# Run as a non-root user (defense-in-depth for a public-facing service).
RUN useradd --create-home --uid 10001 appuser && chown -R appuser /app
USER appuser

# Bind all interfaces (Cloud Run requirement). The app reads TWILIO_SERVER_HOST.
ENV TWILIO_SERVER_HOST=0.0.0.0

# Cloud Run routes traffic to $PORT (default 8080) and rejects a container that
# listens elsewhere. TACServerConfig reads TWILIO_SERVER_PORT, so bridge the two
# at startup. `exec` makes python PID 1 so it receives SIGTERM for graceful
# shutdown on scale-down.
CMD ["sh", "-c", "TWILIO_SERVER_PORT=\"${PORT:-8080}\" exec python main.py"]
