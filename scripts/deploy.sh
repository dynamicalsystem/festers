#!/usr/bin/env bash
# Deploy festers on the Oracle box. Secret-free by design: it runs AS the deploy
# user with local access, so all credentials stay on the box / in the private
# ops repo. Invoked by .github/workflows/deploy.yml on the self-hosted runner,
# and safe to run by hand for a hotfix (see docs/deploy.md).
#
# Contract with the private ops repo:
#   - the app lives at $FESTERS_DIR (default /opt/festers)
#   - it is served by a systemd service named $FESTERS_SERVICE (default festers)
#   - that service runs `uvicorn festers.app:app` and listens on $HEALTH_URL
#     behind Caddy.
# Anything that needs a secret (Caddy, the systemd unit, the runner token) is the
# ops repo's job, not this script's.
set -euo pipefail

FESTERS_DIR="${FESTERS_DIR:-/opt/festers}"
FESTERS_SERVICE="${FESTERS_SERVICE:-festers}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/healthz}"
RESTART="${FESTERS_RESTART:-sudo systemctl restart}"

cd "$FESTERS_DIR"

# Record where we are so we can roll back to it if the new code is unhealthy.
PREV="$(git rev-parse HEAD)"
echo "deploy: current commit $PREV"

git fetch --quiet origin main
git checkout --quiet main
git reset --hard --quiet origin/main
NEW="$(git rev-parse HEAD)"
echo "deploy: target commit $NEW"

# Install exactly what's locked, then restart the service.
uv sync --frozen
$RESTART "$FESTERS_SERVICE"

# Health-check with a short retry budget; roll back on failure.
health_ok() {
  for _ in $(seq 1 15); do
    if curl -fsS --max-time 3 "$HEALTH_URL" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  return 1
}

if health_ok; then
  echo "deploy: healthy at $NEW"
  exit 0
fi

echo "deploy: UNHEALTHY after $NEW - rolling back to $PREV" >&2
git reset --hard --quiet "$PREV"
uv sync --frozen
$RESTART "$FESTERS_SERVICE"
if health_ok; then
  echo "deploy: rolled back to $PREV, service healthy" >&2
else
  echo "deploy: ROLLBACK ALSO UNHEALTHY - needs a human" >&2
fi
exit 1
