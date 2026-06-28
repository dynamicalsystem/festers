# deploy

festers runs on the box exactly like signal does: a **rootless podman
container** supervised by a **`podman generate systemd --new` user unit**
(`container-festers.service`). No compose, no NAS — the box has podman 3.4.4,
systemd, linger, and a containerised (Docker) Caddy on `caddy-net`.

## How it works

```
merge to main ─► release.yml builds & pushes ghcr.io/dynamicalsystem/festers:latest
                                                              │
on the box:  festers-update.timer (~3 min) ─► update.sh ─► podman pull; changed?
                                                              │ yes
                                          systemctl --user restart container-festers ─► /healthz
                                                              │ unhealthy?
                                                              └─► roll :latest back + mark bad build
```

- Container is published on **`FESTERS_BIND_HOST:8000`** (loopback by default).
  On this box Caddy is a *container* and can't reach the host loopback, so
  `FESTERS_BIND_HOST=172.20.0.1` (the `caddy-net` gateway); **Caddy** is the
  public entrypoint (`festers.caddy`). `update.sh` health-checks the same host.
- `data/schedule.json` is baked into the image; `data/plans` + `data/auth` are
  host volumes under `~/.local/state/dynamicalsystem/festers/`.
- Secrets live in `festers.env` on the box (gitignored), never in the repo.

## Files

| file | role |
|---|---|
| `run.sh` | one-time setup: `podman run` + `podman generate systemd` the unit |
| `update.sh` | pull + restart unit + health-check + rollback (the deploy mechanic) |
| `festers.env.example` | the `FESTERS_*` vars the app reads, + the deploy-only `FESTERS_BIND_HOST` |
| `festers.caddy` | Caddy reverse-proxy snippet (upstream = `FESTERS_BIND_HOST:8000`) |
| `systemd/festers-update.{service,timer}` | the auto-deploy timer that runs `update.sh` |

## First deploy

See `FIRST-DEPLOY.md` — the one-time cutover from the old venv service.

## Releasing a change

1. PR merges to `main` → `release.yml` pushes `:latest` to GHCR.
2. The timer runs `update.sh` within ~3 min: pulls `:latest`, and **only if the
   digest changed** restarts `container-festers.service`, health-checks
   `/healthz`, and rolls back (re-pointing `:latest` at the previous image) if
   it's unhealthy — recording the bad digest in `.last-failed-digest` so it
   won't flap.

To deploy by hand: `cd deploy && ./update.sh`. To pause auto-deploy:
`systemctl --user stop festers-update.timer`.

## Rolling back

- A failed health-check auto-rolls-back.
- To force a specific build: `podman pull …@<digest>`, tag it `:latest`, then
  `systemctl --user restart container-festers.service`.
