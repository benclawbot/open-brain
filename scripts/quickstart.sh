#!/usr/bin/env bash
# Quickstart: bring up the Open Brain docker stack and (optionally) wire it
# into a locally-installed Hermes in a single command.
#
# Usage:
#   bash scripts/quickstart.sh                     # bring up the stack only
#   bash scripts/quickstart.sh --with-hermes       # also wire Hermes memory
#   OPENBRAIN_API_PORT=9000 bash scripts/quickstart.sh
#
# Idempotent: safe to run repeatedly. If the stack is already up it will
# report status and exit.
set -eu

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Pull the optional --with-hermes flag out of argv before passing the rest on.
WITH_HERMES=0
for arg in "$@"; do
  if [ "$arg" = "--with-hermes" ]; then
    WITH_HERMES=1
  fi
done

echo "==> Open Brain quickstart"
echo "    repo: $REPO_ROOT"

# 1. .env bootstrap. Copy from .env.example on first run, then generate
#    credentials via the openbrain CLI if present.
if [ ! -f .env ]; then
  echo "==> creating .env from .env.example"
  cp .env.example .env
fi

# 2. Wait for docker to be ready (it may still be starting on a fresh login).
echo "==> checking docker daemon"
if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found on PATH. Install Docker Desktop first." >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "docker daemon is not responding. Open Docker Desktop and retry." >&2
  exit 1
fi

# 3. Compose up (build if needed).
echo "==> docker compose up -d --build"
docker compose up -d --build

# 4. Wait for the api to come up before doing anything that talks to it.
echo "==> waiting for api on http://127.0.0.1:${OPENBRAIN_API_PORT:-8765}/health"
for i in $(seq 1 60); do
  if curl -sf "http://127.0.0.1:${OPENBRAIN_API_PORT:-8765}/health" >/dev/null 2>&1; then
    echo "    api is healthy"
    break
  fi
  sleep 2
  if [ "$i" = "60" ]; then
    echo "    api did not become healthy in 120s. Check 'docker compose logs api'." >&2
    exit 1
  fi
done

# 5. Pull the embedding model into the ollama container (idempotent).
echo "==> ensuring nomic-embed-text is available in the ollama container"
if docker exec openbrain-ollama ollama list 2>/dev/null | grep -q nomic-embed-text; then
  echo "    nomic-embed-text already present"
else
  docker exec openbrain-ollama ollama pull nomic-embed-text
fi

# 6. Optional: wire into a locally-installed Hermes.
if [ "$WITH_HERMES" = "1" ]; then
  if ! command -v openbrain >/dev/null 2>&1; then
    echo "==> 'openbrain' CLI not on PATH; installing via pipx..."
    command -v pipx >/dev/null 2>&1 || python3 -m pip install --user pipx
    python3 -m pipx ensurepath >/dev/null 2>&1 || true
    pipx install "git+https://github.com/benclawbot/open-brain.git"
  fi
  if command -v hermes >/dev/null 2>&1; then
    echo "==> wiring Open Brain into Hermes"
    openbrain install-hermes --force
    hermes memory setup
  else
    echo "hermes CLI not found on PATH; skipping integration. Install hermes and rerun:"
    echo "    openbrain install-hermes && hermes memory setup"
  fi
fi

cat <<EOF

Open Brain stack is up:
  API        http://127.0.0.1:${OPENBRAIN_API_PORT:-8765}
  Dashboard  http://127.0.0.1:8501
  Postgres   127.0.0.1:5433
  Ollama     127.0.0.1:11434

Next steps:
  openbrain search "what did I decide about X"
  openbrain store "remember this"
  openbrain doctor
EOF
