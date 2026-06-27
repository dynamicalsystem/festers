# loop-03: conflict view

Status: **shipped (pure logic + view + tests).** Travel seam built and defaulted
off; flips on when loop-04 (Contract C) lands, no interface change. Track A.
Depends on loop-01 (A) + wants (B).

## Observe

At peak (Saturday night) five-plus venues run at once. A wishlist will contain
events that cannot both be attended. The user needs to see those clashes.

## Orient

Pure time-overlap detection needs only the schedule and the wants - no travel
model, no optimiser. So it ships independently and early. When loop-04 (travel)
lands, the same view upgrades from "same time" to "cannot get there in time"
with no interface change (it just starts calling Contract C).

## Decide

A function over (schedule, wants) that returns every conflicting pair among
wanted events, plus an endpoint/view that lists them grouped by day. Treat null
`end_utc` with the optimiser's `default_set_minutes` assumption so point sets
have a comparable interval.

## Act

- [x] Overlap function: for wanted events, return all clashing pairs. (`conflicts.find_conflicts`, each unordered pair once, never self)
- [x] Handle null `end_utc` via assumed duration; handle group/window wants. (`event_interval`; group wants resolved via `events_in_group`, de-duped by id)
- [x] View: clashes by day, each as "X overlaps Y". (`GET /plan/{name}/conflicts`, `conflicts.html`, grouped by session day)
- [~] (After loop-04) fold travel into feasibility: tight-but-makeable vs clash. **Seam built: `find_conflicts(..., travel=fn)` feeds travel minutes as the `gap` to `Interval.overlaps`. Defaulted off; the view passes `travel_aware=False` until Contract C exists.**

## Outcomes

1. The user sees exactly where their wishlist forces a choice.

## Tests

- [x] Two known-overlapping wanted sets are reported as a conflict. (`test_two_overlapping_wanted_events_are_a_conflict`)
- [x] Two non-overlapping wanted events are not reported. (`test_two_non_overlapping_wanted_events_are_not_reported`)
- [x] A repeated/group want is not flagged against itself. (`test_group_want_not_flagged_against_itself`)
- [x] (Post-04) a pair that overlaps only after travel time is flagged. (`test_travel_seam_turns_a_clean_pair_into_a_conflict` — seam verified now via an injected travel fn)
