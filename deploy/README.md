# deploy

Standalone deploy of festers on the Oracle box. No tinsnip, no NAS/NFS - just
the GHCR image behind the host Caddy, with state on local disk. (tinsnip was
reviewed and rejected for this: it's a homelab platform hard-wired to NFS/NAS
mounts a single cloud box doesn't have.)

## How it works

```
merge to main ─► release.yml builds & pushes ghcr.io/dynamicalsystem/festers:latest
                                                              │
on the box:  festers-update.timer (~3 min) ─► update.sh ─► pull; changed?
                                                              │ yes
                                                  compose up -d ─► curl /healthz
                                                              │ unhealthy?
                                                              └─► roll back + mark bad build
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

## Auto-deploy on merge (wired: systemd timer)

Hands-off deploys are wired via a **cron-pull systemd user timer** in
`deploy/systemd/`: every ~3 minutes it runs `update.sh`, which pulls `:latest`
and redeploys *only if the image changed*. Safe to leave running because
`:latest` only moves on a green merge, `update.sh` no-ops when nothing changed,
rolls back on a failed health-check, and won't re-deploy a build that already
failed (it records the bad digest in `deploy/.last-failed-digest`).

Install once (rootless, runs without an active login):

```sh
mkdir -p ~/.config/systemd/user
cp deploy/systemd/festers-update.* ~/.config/systemd/user/
systemctl --user daemon-reload
loginctl enable-linger "$USER"
systemctl --user enable --now festers-update.timer
systemctl --user list-timers festers-update.timer   # confirm it's scheduled
journalctl --user -u festers-update.service -f       # watch deploys
```

(Assumes the repo is cloned at `~/festers`; edit `ExecStart` in
`festers-update.service` if not.) To pause auto-deploy during a live event and
deploy by hand instead: `systemctl --user stop festers-update.timer`, then run
`./update.sh` when you choose. A webhook listener is the alternative if you want
push-immediacy over the timer's interval.

## Rolling back

- A failed health-check rolls back automatically to the previous image.
- To roll back a *healthy but wrong* deploy, pin the tag: set `FESTERS_TAG` to a
  known-good commit sha (the image is tagged `sha-<full-sha>`) in `festers.env`
  and run `./update.sh`.

## Pre-reqs the box must have

Docker or podman with the compose plugin, `curl`, a host **Caddy** that serves
`festers.dynamicalsystem.com` (DNS already resolves via the wildcard record), and
a GHCR login that can pull the image.
