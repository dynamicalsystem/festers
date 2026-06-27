## What & why

<!-- One or two lines. What does this change and why does it matter this weekend? -->

## Checklist

- [ ] Branched off latest `main`; branch is short-lived and single-purpose.
- [ ] `uv run pytest -q` passes locally.
- [ ] Touches app code only (no secrets, no `.oci/`, no hosting/IaC - that lives in the private ops repo).
- [ ] If it changes behaviour during the live festival, it's small and reversible.

## Notes for the reviewer

<!-- Anything risky, anything you want a second pair of eyes on. -->
