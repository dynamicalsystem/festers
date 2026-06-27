# design

## Problem

Given the festival schedule (`data/schedule.json`) and a set of events the user
*wants* to attend, produce an attendance plan over the three days that:

- never double-books the user (no overlapping attended events),
- respects travel time between venues (a gap large enough to walk/tram there),
- attends as many wanted events as possible (minimise misses), and
- where wants genuinely collide, surfaces the trade-off as an explicit choice
  rather than silently dropping one.

## What makes it interesting (not just a calendar)

1. **Overlap.** At peak (Sat night) five-plus venues run simultaneously. Wanting
   two simultaneous sets is a hard conflict; the tool must pick one and say why.
2. **Repeats.** Some events recur, which gives the optimiser freedom:
   - drop-in *windows* (Mark Fell & Rian Treanor, Ivan Seal, Manchester Soda)
     can be attended at any point in a multi-hour, multi-day window;
   - *grouped* events (`group` field) such as "Reels From The Abyss" or the same
     drop-in across Sat and Sun let the user say "I want this once" and the
     optimiser chooses the cheapest instance.
3. **Travel.** Almost everything is in the central cluster (cheap to hop), but
   North Pier and especially the Pleasure Beach (closing ceremony) are real
   journeys. Travel cost is dominated by those two outliers.
4. **Point sets have no published end time** - we will need an assumed default
   set length (e.g. 45-60 min) as a parameter.

## Model (proposed, first cut)

A weighted interval-selection problem with travel constraints:

- **Items**: each wanted event. For drop-in windows, the "attendance" is a short
  visit of parameterised length placed anywhere inside the window. For grouped
  wants, the item is the group and the optimiser picks one instance.
- **Constraint**: for any two chosen attendances A then B, `start(B) >= end(A) +
  travel(venue_A, venue_B)`.
- **Objective**: maximise sum of want-weights of attended events, minus a small
  travel penalty (to break ties toward less walking), minus a miss penalty.
- **Output**: the ordered plan, the list of dropped wants with the reason, and
  the set of unavoidable either/or decisions for the user to resolve.

Size is tiny (~100 events, a user picks maybe 10-30). This is solvable exactly:
- a greedy / weighted-interval-scheduling pass for a fast first answer, or
- a small ILP (e.g. OR-Tools / PuLP) if we want provable optimality and easy
  addition of constraints later.

Recommend starting with the explicit/greedy solver (no heavy dependency, easy to
explain the "why" behind each choice) and only reaching for an ILP if the
choice-surfacing needs it. **Call out before adding any solver dependency.**

## Travel model

Start with a hand-built zone-to-zone walking-minutes matrix (see
`docs/venues.md`): central cluster ~0-8 min, North Pier and Pleasure Beach as
larger fixed costs. Cheap, no dependencies, good enough to get conflict/travel
trade-offs right. Quantify in loop covering the optimiser.

## Architecture (decided 2026-06-24)

**A small Python service.** A single app holds the schedule, persists wants, and
runs the optimiser server-side, exposing two feature surfaces over shared state:
a *pick* surface (browse + mark wants) and an *optimise* surface (build a plan).

- Framework: FastAPI + uvicorn (async, auto OpenAPI docs, minimal). Call out
  before adding anything heavier.
- Persistence: a JSON file per named plan to start (human-inspectable, no DB
  ops); move to SQLite only if concurrent multi-writer use appears.
- Hosting: uvicorn on a port on the Oracle Cloud box; nginx/systemd later if it
  outlives the weekend. Deploy is dragged into loop-02 to de-risk hosting early.

Chosen over a static client page because we want server-side persistence of
picks (and potentially more than one person's). See `docs/contracts.md` for the
frozen interfaces that let the UI and optimiser tracks proceed in parallel.

## Resolved: UTC stays canonical (Simon, 2026-06-24)

House rule: store date/time in UTC with an explicit timezone. We have complied -
`schedule.json` carries `start_utc`/`end_utc` as canonical UTC plus a local
clock string and `timezone: Europe/London`.

**Decision: keep UTC canonical** (option 1 below). The redundancy of the local
clock field is a cheap price for correctness. The deciding factor is the
deployment reality: this is used on mobile devices, potentially from other
countries, whose device timezone may be wrong or stale. Reasoning in UTC and
formatting to the festival's fixed UTC+01:00 for display avoids that whole class
of oddness. Do it right once rather than chase tz bugs on the weekend.

Consequences for consumers (conflict view, optimiser, UI):
- All time arithmetic (overlap, travel gaps) is done on `start_utc`/`end_utc`.
- `*_local` fields are **display only** - never compute on them, never trust the
  device clock/timezone for scheduling logic.
- Display formats to UTC+01:00 explicitly, not to the device's local time.

Options that were on the table:
1. **Keep UTC canonical as now (chosen)** - rule-compliant; we live with the
   redundancy of the duplicate local field.
2. Keep local clock + `timezone` as canonical for this dataset and derive UTC on
   demand - simpler, but a deviation from the house rule. Rejected.
