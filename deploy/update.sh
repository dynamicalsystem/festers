#!/usr/bin/env bash
# Deploy/update festers on the box: pull the new image, restart, health-check,
# and roll back to the previous image if the new one is unhealthy. Idempotent
# and safe to run by hand for a hotfix. Works with docker or podman compose.
#
#   cd deploy && ./update.sh
set -euo pipefail
cd "$(dirname "$0")"

[[ -f festers.env ]] || { echo "missing deploy/festers.env (cp festers.env.example festers.env)" >&2; exit 1; }

# Pick a compose command that exists.
if docker compose version >/dev/null 2>&1; then COMPOSE=(docker compose)
elif podman compose version >/dev/null 2>&1; then COMPOSE=(podman compose)
elif command -v docker-compose >/dev/null 2>&1; then COMPOSE=(docker-compose)
else echo "no docker/podman compose found" >&2; exit 1; fi

PORT="$(grep -E '^FESTERS_PORT=' festers.env | cut -d= -f2)"; PORT="${PORT:-8000}"
HEALTH="http://127.0.0.1:${PORT}/healthz"
IMAGE="ghcr.io/dynamicalsystem/festers"

# Remember the currently-running image so we can roll back to it.
PREV_ID="$("${COMPOSE[@]}" images -q festers 2>/dev/null | head -1 || true)"
[[ -n "$PREV_ID" ]] && { docker image tag "$PREV_ID" "${IMAGE}:rollback" 2>/dev/null \
  || podman image tag "$PREV_ID" "${IMAGE}:rollback" 2>/dev/null || true; }

echo "deploy: pulling latest and restarting"
"${COMPOSE[@]}" pull festers
"${COMPOSE[@]}" up -d festers

health_ok() {
  for _ in $(seq 1 15); do
    curl -fsS --max-time 3 "$HEALTH" >/dev/null 2>&1 && return 0
    sleep 2
  done
  return 1
}

if health_ok; then
  echo "deploy: healthy at $HEALTH"
  exit 0
fi

echo "deploy: UNHEALTHY - rolling back" >&2
if [[ -n "$PREV_ID" ]]; then
  FESTERS_TAG=rollback "${COMPOSE[@]}" up -d festers
  if health_ok; then echo "deploy: rolled back, healthy" >&2; else echo "deploy: ROLLBACK ALSO UNHEALTHY - needs a human" >&2; fi
else
  echo "deploy: no previous image to roll back to - needs a human" >&2
fi
exit 1
