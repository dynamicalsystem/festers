## What & why

<!-- One or two lines. What does this change and why does it matter this weekend? -->

## Checklist

- [ ] Branched off latest `main`; branch is short-lived and single-purpose.
- [ ] `uv run pytest -q` passes locally.
- [ ] No secrets (no `.oci/`, no `.env`, no `deploy/festers.env`). The `deploy/` config is secret-free; real values live on the box.
- [ ] If it changes behaviour during the live festival, it's small and reversible.

## Notes for the reviewer

<!-- Anything risky, anything you want a second pair of eyes on. -->
