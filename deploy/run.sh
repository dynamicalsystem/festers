#!/usr/bin/env bash
# One-time setup: run festers as a rootless podman container and supervise it
# with a `podman generate systemd --new` user unit — the same pattern signal
# uses on the box (no compose). Re-runnable. After this, update.sh handles
# updates. Requires `podman login ghcr.io` first (private image).
set -euo pipefail
cd "$(dirname "$0")"

[[ -f festers.env ]] || { echo "missing deploy/festers.env (cp festers.env.example festers.env)" >&2; exit 1; }

IMAGE="ghcr.io/dynamicalsystem/festers:latest"
STATE="${XDG_STATE_HOME:-$HOME/.local/state}/dynamicalsystem/festers"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
ENVFILE="$(pwd)/festers.env"

# Host IP the container port is published on. Default loopback (a host Caddy
# reaches it directly). On a box where Caddy is itself a container (e.g. Docker
# on its own bridge network), set FESTERS_BIND_HOST in festers.env to that
# bridge's gateway IP so Caddy can reach the service. See deploy/README.md.
BIND_HOST="$(grep -E '^FESTERS_BIND_HOST=' festers.env 2>/dev/null | cut -d= -f2-)"
BIND_HOST="${BIND_HOST:-127.0.0.1}"

mkdir -p "$STATE/plans" "$STATE/auth" "$UNIT_DIR"

podman pull "$IMAGE"

# (Re)create the container — this is the template the unit is generated from.
# --network signal-net: lets festers reach the shared Signal API by DNS name
# `signal:8080` (see deploy/README + signal's service-integration.md). The
# network is created by signal's setup; this only joins it.
podman rm -f festers 2>/dev/null || true
podman run -d --name festers \
  --network signal-net \
  -p "${BIND_HOST}:8000:8000" \
  --env-file "$ENVFILE" \
  -e FESTERS_PLANS_DIR=/app/data/plans -e FESTERS_AUTH_DIR=/app/data/auth \
  -v "$STATE/plans:/app/data/plans" \
  -v "$STATE/auth:/app/data/auth" \
  "$IMAGE"

# Generate + enable the systemd user unit (the supervisor). --new makes it
# recreate the container on each start, so update.sh's pull+restart picks up new
# images. enable-linger keeps it running without an active login.
podman generate systemd --new --name festers > "$UNIT_DIR/container-festers.service"
systemctl --user daemon-reload
systemctl --user enable --now container-festers.service
loginctl enable-linger "$USER" 2>/dev/null || true

echo "done. verify: curl -fsS http://${BIND_HOST}:8000/healthz"
