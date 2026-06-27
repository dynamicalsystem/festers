# loop-02: service skeleton + event picker

Status: **shipped (code+tests); deployed live.** (Hosting/IaC lives in a
separate private ops repo.)
Track A. Depends on loop-01 (Contract A) and Contract B.

## Observe

The schedule exists as data but there is no way to look at it or to record which
events the user wants. Anything downstream (conflicts, optimiser) needs a wants
object to exist and be persisted.

## Orient

This is the smallest end-to-end slice that is useful on its own: a person can
browse all three days and capture a wishlist on their phone, even before any
conflict or optimisation logic exists. It also stands up the FastAPI app and the
deploy path early, so hosting surprises surface now, not at the end.

## Decide

A FastAPI app that loads `data/schedule.json`, renders the three days grouped by
day/venue, lets the user toggle events (and groups) as wants, and persists the
wants object (Contract B) as a JSON file per `plan_name`. Deploy to the Oracle
box behind uvicorn.

## Act

- [x] FastAPI skeleton; load + validate `schedule.json` on startup (`create_app` calls `load_schedule`, fail-fast).
- [x] Read endpoint: schedule as JSON (`/api/schedule`) and a server-rendered browse view by day (`/`), grouped local_date -> venue.
- [x] Toggle a want (event or group); persist Contract B JSON per plan_name (`POST /plan/{name}/toggle`, `save_wants`).
- [x] Minimal styling good enough to use on a phone (`static/style.css`, phone-first).
- [x] Deploy on the Oracle Cloud server (uvicorn behind Caddy). **Live; the hosting steps and IaC are kept in a separate private ops repo.**

## Outcomes

1. The user can see the entire festival and build a wishlist from their phone.
2. A persisted wants object (Contract B) exists for downstream loops to read.
3. The hosting path on Oracle is proven.

## Tests

- [x] Loading the page lists all 104 events across the three correct days. (`test_browse_lists_all_104_events`, `test_browse_shows_three_festival_days`, `test_sunday_late_events_are_shown_under_sunday`)
- [x] Toggling an event on/off and reloading shows the choice persisted. (`test_toggle_event_persists_and_validates_contract_b`, `test_toggle_is_idempotent_off`)
- [x] The persisted file validates against Contract B. (`Wants.model_validate_json` in `test_toggle_event_persists_and_validates_contract_b`)
- [x] The deployed URL is reachable from a phone off the local network. **Verified live over HTTPS.**
