#!/usr/bin/env bash
# Update festers: pull the latest image and, only if it changed, restart the
# systemd unit, health-check, and roll back on failure. Safe to run unattended
# (the timer) or by hand. Mirrors how signal runs on the box: rootless podman +
# a `podman generate systemd --new` user unit (no compose). Run ./run.sh once
# first to create the container + unit.
set -euo pipefail
cd "$(dirname "$0")"

IMAGE="ghcr.io/dynamicalsystem/festers"
UNIT="container-festers.service"
HEALTH="http://127.0.0.1:8000/healthz"
FAILED_MARK=".last-failed-digest"      # runtime state; gitignored

command -v podman >/dev/null || { echo "podman not found" >&2; exit 1; }

img_id()     { podman image inspect "$1" --format '{{.Id}}' 2>/dev/null || true; }
running_id() {
  local cid; cid="$(podman ps -aq --filter 'name=^festers$' 2>/dev/null | head -1)"
  [[ -n "$cid" ]] && podman inspect "$cid" --format '{{.Image}}' 2>/dev/null || true
}

podman pull "${IMAGE}:latest" >/dev/null 2>&1 || podman pull "${IMAGE}:latest"
CAND="$(img_id "${IMAGE}:latest")"
RUN="$(running_id)"

# Nothing new -> no-op (keeps the timer quiet, avoids needless restarts).
if [[ -n "$CAND" && "$CAND" == "$RUN" ]]; then
  echo "deploy: already running latest (${CAND:0:19}) - nothing to do"; exit 0
fi
# Latest is the build that already failed its health-check -> stay put, don't flap.
if [[ -n "$CAND" && -f "$FAILED_MARK" && "$CAND" == "$(cat "$FAILED_MARK" 2>/dev/null)" ]]; then
  echo "deploy: latest (${CAND:0:19}) is a known-bad build; staying on current. Fix main or rm $FAILED_MARK." >&2
  exit 0
fi

# Tag the currently-running image so we can roll :latest back to it.
[[ -n "$RUN" ]] && podman image tag "$RUN" "${IMAGE}:rollback" 2>/dev/null || true

echo "deploy: rolling out ${CAND:0:19}"
systemctl --user restart "$UNIT"        # the --new unit recreates the container with the pulled :latest

health_ok() {
  for _ in $(seq 1 15); do
    curl -fsS --max-time 3 "$HEALTH" >/dev/null 2>&1 && return 0
    sleep 2
  done
  return 1
}

if health_ok; then
  echo "deploy: healthy at $HEALTH"; rm -f "$FAILED_MARK"; exit 0
fi

echo "deploy: UNHEALTHY - recording bad build and rolling back" >&2
[[ -n "$CAND" ]] && echo "$CAND" > "$FAILED_MARK"
if [[ -n "$RUN" ]]; then
  podman image tag "${IMAGE}:rollback" "${IMAGE}:latest"   # point :latest back at the good image
  systemctl --user restart "$UNIT"
  if health_ok; then echo "deploy: rolled back, healthy" >&2; else echo "deploy: ROLLBACK ALSO UNHEALTHY - needs a human" >&2; fi
else
  echo "deploy: no previous image to roll back to - needs a human" >&2
fi
exit 1
