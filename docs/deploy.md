# deploy

How code gets from a merged PR onto the Oracle box, and how to intervene by hand
when the festival is live and you're holding a phone.

## The shape (and why)

This repo is **app code only**. The box, the Caddy/systemd config, the OCI
credentials and the GitHub runner token all live in a **separate private ops
repo**. The split is deliberate: contributors touch the app; nobody but the
maintainer touches the box.

That boundary drives the deploy design: the deploy job runs on a **self-hosted
GitHub Actions runner on the Oracle box** (label `festers-prod`). Because it runs
*on* the box as the deploy user, it already has local access to everything it
needs - so **no secret ever lives in this public repo's Actions**. The job just
pulls the merged commit and runs `scripts/deploy.sh`.

## The flow

```
merge PR to main
   │
   ▼
ci.yml          → runs pytest on a GitHub-hosted runner
   │ (green)
   ▼
deploy.yml      → waits for that ci run to pass for the same commit,
   │              then dispatches to the self-hosted `festers-prod` runner
   ▼
scripts/deploy.sh on the box:
   git reset --hard origin/main
   uv sync --frozen
   restart the `festers` systemd service
   curl /healthz  ──► healthy?  yes → done
                              │ no  → roll back to the previous commit,
                                      restart, re-check, fail loud
```

A red build never reaches the box: `deploy.yml` gates on the `pytest` check
succeeding for the exact commit. Deploys are serialized (`concurrency` group) so
two merges can't race.

## What the ops repo must provide (the contract)

`scripts/deploy.sh` is secret-free and assumes the box is already set up by the
ops repo:

| Thing | Default | Notes |
|---|---|---|
| App checkout | `/opt/festers` | `$FESTERS_DIR` |
| systemd service | `festers` | `$FESTERS_SERVICE`; runs `uvicorn festers.app:app` |
| Health URL | `http://127.0.0.1:8000/healthz` | `$HEALTH_URL`; behind Caddy |
| Restart command | `sudo systemctl restart` | `$FESTERS_RESTART` |

Ops-repo responsibilities (not in this repo):
- Register the self-hosted runner with label `festers-prod` (Settings → Actions →
  Runners), running as the deploy user, as a service so it survives reboot.
- The `festers` systemd unit, the Caddy site, TLS, and the firewall.
- Giving the deploy user passwordless `systemctl restart festers` (or set
  `$FESTERS_RESTART` to whatever does the restart).

## `/healthz`

`GET /healthz` → `200 {"status":"ok","events":104}`. It returns 200 only if the
schedule loaded, which is exactly the "is the new code actually serving"
question the deploy script asks. Caddy/uptime checks can use it too.

## Manual deploy / hotfix (the "you can bypass" path)

`main` is protected (PR + green CI required) but you, as repo admin, can push
straight to `main` for an emergency fix. The deploy workflow still fires on that
push. If you'd rather skip Actions entirely and deploy by hand from the box:

```sh
ssh <box>
cd /opt/festers
bash scripts/deploy.sh        # same pull + restart + health-check + rollback
```

The script is the single source of truth for "what a deploy does", whether CI
runs it or you do.

## Rolling back

A failed health-check rolls back automatically. To roll back a *healthy but
wrong* deploy, point `main` at the good commit and let the pipeline redeploy:

```sh
git revert <bad-sha> && git push      # preferred: keeps history honest
# or, on the box for an instant fix:
cd /opt/festers && git reset --hard <good-sha> && bash scripts/deploy.sh
```

## One-time repo setup (maintainer)

Branch protection that matches "PR + CI, admin can bypass" - run once after the
`ci` workflow has run at least once (so the check name exists):

```sh
gh api -X PUT repos/dynamicalsystem/festers/branches/main/protection \
  -H "Accept: application/vnd.github+json" \
  -f 'required_status_checks[strict]=true' \
  -f 'required_status_checks[contexts][]=pytest' \
  -f 'required_pull_request_reviews[required_approving_review_count]=1' \
  -f 'enforce_admins=false' \
  -f 'restrictions=' \
  -f 'allow_force_pushes=false' \
  -f 'allow_deletions=false'
```

`enforce_admins=false` is what lets you bypass for a live hotfix. Flip it to
`true` after the weekend if you want everyone, including yourself, on PRs.
