#!/usr/bin/env bash
# Deploy/update festers on the box: pull the latest image and, only if it
# changed, restart + health-check + roll back on failure. Idempotent and safe to
# run unattended on a timer (see deploy/systemd/) or by hand for a hotfix.
# Works with docker or podman compose.
#
#   cd deploy && ./update.sh
set -euo pipefail
cd "$(dirname "$0")"

[[ -f festers.env ]] || { echo "missing deploy/festers.env (cp festers.env.example festers.env)" >&2; exit 1; }

# Pick a container runtime + compose front-end that exist.
if docker compose version >/dev/null 2>&1; then CLI=docker; COMPOSE=(docker compose)
elif podman compose version >/dev/null 2>&1; then CLI=podman; COMPOSE=(podman compose)
elif command -v docker-compose >/dev/null 2>&1; then CLI=docker; COMPOSE=(docker-compose)
else echo "no docker/podman compose found" >&2; exit 1; fi

PORT="$(grep -E '^FESTERS_PORT=' festers.env | cut -d= -f2)"; PORT="${PORT:-8000}"
HEALTH="http://127.0.0.1:${PORT}/healthz"
IMAGE="ghcr.io/dynamicalsystem/festers"
FAILED_MARK=".last-failed-digest"      # runtime state; gitignored

img_id() { $CLI image inspect "$1" --format '{{.Id}}' 2>/dev/null || true; }
running_id() {
  local cid; cid="$("${COMPOSE[@]}" ps -q festers 2>/dev/null | head -1)"
  [[ -n "$cid" ]] && $CLI inspect "$cid" --format '{{.Image}}' 2>/dev/null || true
}

"${COMPOSE[@]}" pull festers >/dev/null 2>&1 || "${COMPOSE[@]}" pull festers
CAND="$(img_id "${IMAGE}:latest")"
RUN="$(running_id)"

# Nothing new -> no-op (keeps the timer quiet, avoids needless restarts).
if [[ -n "$CAND" && "$CAND" == "$RUN" ]]; then
  echo "deploy: already running latest (${CAND:0:19}) - nothing to do"; exit 0
fi
# Latest is the image that already failed its health-check -> stay put, don't flap.
if [[ -n "$CAND" && -f "$FAILED_MARK" && "$CAND" == "$(cat "$FAILED_MARK" 2>/dev/null)" ]]; then
  echo "deploy: latest (${CAND:0:19}) is a known-bad build; staying on current. Fix main or rm $FAILED_MARK." >&2
  exit 0
fi

# Tag the currently-running image so we can roll back to it.
[[ -n "$RUN" ]] && $CLI image tag "$RUN" "${IMAGE}:rollback" 2>/dev/null || true

echo "deploy: rolling out ${CAND:0:19}"
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
  rm -f "$FAILED_MARK"
  exit 0
fi

echo "deploy: UNHEALTHY - recording bad build and rolling back" >&2
[[ -n "$CAND" ]] && echo "$CAND" > "$FAILED_MARK"
if [[ -n "$RUN" ]]; then
  FESTERS_TAG=rollback "${COMPOSE[@]}" up -d festers
  if health_ok; then echo "deploy: rolled back, healthy" >&2; else echo "deploy: ROLLBACK ALSO UNHEALTHY - needs a human" >&2; fi
else
  echo "deploy: no previous image to roll back to - needs a human" >&2
fi
exit 1
