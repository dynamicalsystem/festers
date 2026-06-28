# first deploy — cutover to the container

One-time switch from the old host-uvicorn deployment to the GHCR container. Run
on the box (`152.67.153.4`). The image already exists at
`ghcr.io/dynamicalsystem/festers:latest`. After this, merges auto-deploy.

> ⚠️ Two things differ per box and **must** be checked first (step 0) — getting
> them wrong loses data or breaks the live site.

## 0. Find out two box facts first

```sh
# a) name of the OLD festers service (so you can stop it in step 3)
systemctl list-units --all | grep -i fester        # note the unit name

# b) is Caddy a HOST binary or a CONTAINER? (decides step 4)
systemctl status caddy 2>/dev/null && echo "=> host Caddy"     # Option A
docker ps --format '{{.Names}}' | grep -i caddy && echo "=> containerised Caddy"  # Option B
```

## 1. Repo + config

```sh
git clone https://github.com/dynamicalsystem/festers && cd festers/deploy
cp festers.env.example festers.env
$EDITOR festers.env
```

- [ ] **Reuse the existing `FESTERS_SECRET`** from the old deployment. If it
      changes, every existing plan id and magic link breaks. Copy the old value.
- [ ] Set `FESTERS_BASE_URL=https://festers.dynamicalsystem.com` and the
      notifier vars (Signal/SMTP) to match the old config.

## 2. Migrate live data

The old deployment persisted wishlists in its `data/plans/` (and tokens in
`data/auth/`). Copy them into the new volume location so nothing is lost:

```sh
mkdir -p ~/.local/state/dynamicalsystem/festers/{plans,auth}
cp -a /path/to/old/data/plans/. ~/.local/state/dynamicalsystem/festers/plans/
cp -a /path/to/old/data/auth/.  ~/.local/state/dynamicalsystem/festers/auth/
```

(Find the old path from the old service's `WorkingDirectory`/`FESTERS_PLANS_DIR`.)

## 3. Log in to GHCR + stop the old service

```sh
echo "$GHCR_PAT" | docker login ghcr.io -u dynamicalsystem --password-stdin   # PAT needs read:packages

sudo systemctl stop <old-festers-service>
sudo systemctl disable <old-festers-service>
ss -ltnp | grep -E ':8000|172\.20\.0\.1' || echo "port free"   # nothing should still hold it
```

## 4. Wire Caddy — pick the branch from step 0

**Option A — host Caddy** (can reach loopback): the default compose binds
`127.0.0.1:8000`, so the snippet works as-is.

```sh
sudo cp festers.caddy /etc/caddy/conf.d/ && sudo systemctl reload caddy
```

**Option B — containerised Caddy on `caddy-net`** (can't reach host loopback):
put festers on `caddy-net` and proxy by name. Edit `docker-compose.yml`:

```yaml
    networks: [caddy-net]      # under the festers service
# ...and at the file bottom:
networks:
  caddy-net:
    external: true
```

Then set the snippet to `reverse_proxy festers:8000` (not `127.0.0.1:8000`),
add it to Caddy's config, and reload. This is the cleaner end state — it retires
the old `172.20.0.1` bridge hack entirely.

## 5. Deploy + verify

```sh
./update.sh                                              # pull :latest, start, /healthz check, auto-rollback
curl -fsS https://festers.dynamicalsystem.com/healthz    # expect {"status":"ok","events":...}
```

Then open the site, request a magic link, and confirm a migrated plan loads.

## 6. Turn on auto-deploy

```sh
mkdir -p ~/.config/systemd/user
cp systemd/festers-update.* ~/.config/systemd/user/
systemctl --user daemon-reload && loginctl enable-linger "$USER"
systemctl --user enable --now festers-update.timer
```

## Rollback

- A failed health-check auto-rolls-back to the previous image.
- Full revert to the old deployment: `docker compose -f docker-compose.yml down`
  then `sudo systemctl start <old-festers-service>`.
- Logs: `docker compose -f docker-compose.yml logs -f`,
  `journalctl --user -u festers-update -f`.
