# ooda

OODA loops for festers. One folder per loop. Each loop has a `README.md`
stating its **outcomes** (the impact on a user/process) and **tests** (how we
validate that impact). A closed loop gets an `archived.md` with closure metadata
and `[ARCHIVED]` in its README's first heading.

Given the festival is 26-28 June 2026 and today is 2026-06-24, loops are kept
small and each ships usable value on its own (vertical slices, not horizontal
layers). Coupling between loops is only through the frozen interfaces in
`docs/contracts.md`; that is what lets the two tracks below run in parallel.

## Plan

Architecture is a small Python service (FastAPI); see `docs/design.md`.

Loop-01 is the shared foundation. After it, two independent tracks proceed in
parallel, meeting only at the wants object (Contract B) and schedule (A):

```
                loop-01 schedule-data (foundation)
                       |
        Track A (UI/data)        Track B (logic)
        loop-02 service+picker   loop-04 travel-model
        loop-03 conflict-view    loop-05 optimiser-core
                       \            /
                    converge: optimiser endpoint + picker calls it
```

| loop | track | ships | status |
|------|-------|-------|--------|
| 01 schedule-data   | -      | verified `schedule.json` + transcript        | data verified by tests; DQ flags + human sign-off pending |
| 02 service+picker  | A      | FastAPI app: browse 3 days, mark wants, persist | shipped (live Oracle deploy pending) |
| 03 conflict-view   | A      | surfaces every wanted-event time clash        | shipped |
| 04 travel-model    | B      | zone-to-zone walking-minutes matrix (Contract C) | shipped |
| 05 optimiser-core  | B      | pure tested library: wants -> plan + drops + forced choices | shipped |
| 06 converge+deploy | A+B    | optimiser behind an endpoint, picker shows the plan | shipped (deploy pending) |

Each loop merges and ships before/independently of the others on its track.
Loop-02 deliberately pulls the deploy story to the front to de-risk hosting.

## Reality check (festival is in 2 days)

Confidently shippable in time: 01 (verify), 02, 03. Track B (04, 05) and the
converge step (06) are the interesting optimiser work and are at real risk of
landing after the weekend - still worthwhile (reusable next year), but honest
about it. If the optimiser is the priority over UI polish, compress 02 to a
minimal picker and push Track B first.

## Loops

- **loop-01-schedule-data** - festival schedule as trustworthy structured data.
  Status: in review.
- **loop-02-service-and-picker** - Track A. Not started.
- **loop-03-conflict-view** - Track A. Not started.
- **loop-04-travel-model** - Track B. Not started.
- **loop-05-optimiser-core** - Track B. Not started.
- **loop-06-converge** - opens once 02 and 05 ship.
