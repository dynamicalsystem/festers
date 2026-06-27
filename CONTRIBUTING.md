# contributing to festers

Thanks for helping out. The festival is **live this weekend**, so the bar is:
small, reversible changes that pass tests. Read this once; it takes two minutes.

## The model in one line

One short-lived branch per change → pull request → green CI → review → merge →
auto-deploy. Branches are deleted after merge.

## Do we need branches? (yes - and they prevent collisions)

A pull request is, by definition, "merge branch X into `main`" - the source and
target must differ, so you can't open a PR *from* `main` *into* `main`. The only
alternative to branches is everyone committing straight to `main`, and that is
exactly what causes collisions: two people pushing the same branch reject each
other and tangle the history.

A short-lived feature branch gives you an isolated workspace. Conflicts (if any)
surface once, at merge time, where CI and a reviewer can catch them. So: branch,
PR, merge, delete. The branch can live for ten minutes - that's fine.

## Getting set up

You have write access to the repo (you're a collaborator), so you push branches
directly - no fork needed.

```sh
git clone git@github.com:dynamicalsystem/festers.git
cd festers
uv sync --frozen --group dev   # install locked deps + test tools
uv run pytest -q               # everything should be green before you start
uv run uvicorn festers.app:app --reload   # http://127.0.0.1:8000
```

(If you don't have `uv`: https://docs.astral.sh/uv/ - it reads `uv.lock` so you
get the exact same versions CI does.)

## Making a change

```sh
git checkout main && git pull
git checkout -b your-initials/short-description   # e.g. sh/fix-sunday-tz
# ... edit, add tests ...
uv run pytest -q
git push -u origin your-initials/short-description
gh pr create --fill        # or open the PR in the GitHub UI
```

Then: CI runs the test suite on your PR. A maintainer reviews and merges. Merging
to `main` deploys automatically (see `docs/deploy.md`). Delete the branch after.

## House rules that will get a PR bounced

- **No secrets, ever.** `.oci/`, `.env`, tokens, keys. They're gitignored - keep
  it that way. Hosting/IaC is **not** in this repo; it's in a separate private
  ops repo.
- **UTC is canonical.** All time arithmetic uses `start_utc`/`end_utc`. The
  `*_local` fields are display-only - never compute on them or trust the device
  clock. (See `docs/design.md`.)
- **`data/schedule.json` is the source of truth** for the festival data. Changing
  it means re-checking against the source PDF; call it out explicitly in the PR.
- **Add a test** for any behaviour change. The suite is the thing that lets us
  deploy on a merge without a human re-checking by hand.
- **Don't add dependencies** without calling it out in the PR - the stack is
  deliberately minimal (see `docs/design.md`).

## Keep it small

During the festival, prefer several tiny PRs over one big one. Small PRs review
fast, deploy fast, and roll back cleanly if something's off. There's a closing
ceremony to get to.
