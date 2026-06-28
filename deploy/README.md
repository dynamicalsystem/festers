# deploy

Standalone deploy of festers on the Oracle box. No tinsnip, no NAS/NFS - just
the GHCR image behind the host Caddy, with state on local disk. (tinsnip was
reviewed and rejected for this: it's a homelab platform hard-wired to NFS/NAS
mounts a single cloud box doesn't have.)

## How it works

```
merge to main ─► release.yml builds & pushes ghcr.io/dynamicalsystem/festers:latest
                                                              │
on the box:  deploy/update.sh ──► compose pull + up -d ──► curl /healthz
                                                              │ unhealthy?
                                                              └─► roll back to previous image
```

- The app is a single FastAPI container (`uvicorn festers.app:app`, port 8000),
  bound to **loopback only**; the host **Caddy** is the public entrypoint.
- `data/schedule.json` is baked into the image. Runtime state (`data/plans`,
  `data/auth`) lives on host volumes under `~/.local/state/dynamicalsystem/festers/`
  so it survives restarts and image updates.
- Secrets live in `festers.env` on the box (gitignored), never in the repo.

## First-time setup (on the box)

```sh
# 1. get this repo (deploy dir is all you need)
git clone https://github.com/dynamicalsystem/festers && cd festers/deploy

# 2. configure - fill in FESTERS_SECRET etc.
cp festers.env.example festers.env && editor festers.env

# 3. log in to GHCR so the box can pull the image (one-off; needs a PAT with read:packages)
echo "$GHCR_PAT" | docker login ghcr.io -u <github-user> --password-stdin

# 4. wire up Caddy: add festers.caddy to the host Caddy and reload
sudo cp festers.caddy /etc/caddy/conf.d/festers.caddy && sudo systemctl reload caddy

# 5. first deploy
./update.sh
```

## Releasing a change (the normal path)

1. PR merges to `main` → `release.yml` builds and pushes `:latest` to GHCR.
2. On the box: `cd festers/deploy && ./update.sh` — pulls `:latest`, restarts,
   health-checks `/healthz`, rolls back automatically if it's unhealthy.

`update.sh` is the single source of truth for what a deploy does, whether you run
it by hand or a trigger runs it for you.

## Auto-deploy on merge (optional, the last hop)

`update.sh` covers everything except *triggering* it from a merge. Pick one when
you want hands-off deploys:

- **Cron pull**: a `systemd` timer on the box runs `update.sh` every N minutes.
  Simplest; deploys land within the interval. Since `:latest` only moves on a
  green merge and `update.sh` rolls back on failure, this is safe.
- **Webhook**: a tiny listener on the box runs `update.sh` on a GitHub
  `workflow_run`/`package` webhook. Immediate, a little more to stand up.

Until one is wired, deploys are one command (`./update.sh`) - fine for a live
festival where you may want a human in the loop anyway.

## Rolling back

- A failed health-check rolls back automatically to the previous image.
- To roll back a *healthy but wrong* deploy, pin the tag: set `FESTERS_TAG` to a
  known-good commit sha (the image is tagged `sha-<full-sha>`) in `festers.env`
  and run `./update.sh`.

## Pre-reqs the box must have

Docker or podman with the compose plugin, `curl`, a host **Caddy** that serves
`festers.dynamicalsystem.com` (DNS already resolves via the wildcard record), and
a GHCR login that can pull the image.
