# first deploy — cutover to the container

One-time switch from the old host-uvicorn (`festers.service`) deployment to a
rootless podman container, supervised like signal. Run on the box
(`152.67.153.4`). The image already exists at
`ghcr.io/dynamicalsystem/festers:latest`.

> The festival is live — only do this when a brief blip is acceptable. The
> current venv deploy works; this replaces it.

## 1. Get the deploy files + log in to GHCR

```sh
git clone https://github.com/dynamicalsystem/festers ~/festers-app
cd ~/festers-app/deploy
podman login ghcr.io -u dynamicalsystem        # PAT with read:packages (the only delta from signal)
```

## 2. Config + migrate live data

```sh
cp festers.env.example festers.env
$EDITOR festers.env
```
- [ ] **Reuse the live `FESTERS_SECRET`** from the old service, or every existing
      plan id / magic link breaks. (Find it in the old unit's env /
      `~/festers`.)
- [ ] Set `FESTERS_BASE_URL` and the notifier vars. For Signal:
      `FESTERS_SIGNAL_URL=http://signal:8080` and `FESTERS_SIGNAL_FROM=+447377115354`
      (gigbot) — `run.sh` joins `signal-net` so the name resolves. Confirm the
      `signal-net` network exists (`podman network ls`) before `run.sh`.

```sh
# carry over existing wishlists + tokens
mkdir -p ~/.local/state/dynamicalsystem/festers/{plans,auth}
cp -a ~/festers/data/plans/. ~/.local/state/dynamicalsystem/festers/plans/
cp -a ~/festers/data/auth/.  ~/.local/state/dynamicalsystem/festers/auth/
```

## 3. Stop the old service, start the container

```sh
sudo systemctl disable --now festers           # the old uvicorn unit (frees :8000)
./run.sh                                        # podman run + generate the systemd user unit + enable
curl -fsS http://127.0.0.1:8000/healthz         # {"status":"ok","events":...}
```

`run.sh` mirrors signal: rootless container + `podman generate systemd --new`
unit (`container-festers.service`), enabled with linger so it survives reboot.

## 4. Caddy

`festers.caddy` is already on the box pointing at `127.0.0.1:8000`, so:

```sh
sudo systemctl reload caddy
curl -fsS https://festers.dynamicalsystem.com/healthz
```

(If the snippet isn't present: `sudo cp festers.caddy /etc/caddy/conf.d/` first.)

## 5. Turn on auto-deploy

```sh
mkdir -p ~/.config/systemd/user
cp systemd/festers-update.* ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now festers-update.timer
```

Now a merge to `main` lands on the box within ~3 min (pull + restart + health-check).

## Rollback (fast revert to the old deploy)

```sh
systemctl --user disable --now container-festers.service festers-update.timer
sudo systemctl enable --now festers            # back to the venv service
```

Logs: `journalctl --user -u container-festers -f`,
`journalctl --user -u festers-update -f`.
