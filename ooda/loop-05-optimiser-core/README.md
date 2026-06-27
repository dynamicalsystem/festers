# loop-05: optimiser core

Status: **shipped** (pending loop-06 converge). Track B. Depends on loop-01 (A),
loop-04 (C), wants (B). Pure library - no UI - in `festers/optimiser.py`;
tests in `tests/test_optimiser.py` (all green). Converges with the service in
loop-06.

## Observe

Given a wishlist with overlaps, repeats and travel costs, choosing what to
actually attend by hand is fiddly. This is the centrepiece feature.

## Orient

A weighted interval-selection problem with travel constraints (see
`docs/design.md`). Tiny size (~100 events, tens of wants) so it is solvable
exactly. Build it as a pure, well-tested function first - no web, no UI - so it
can be validated in isolation and reused. Start with an explicit greedy /
weighted-interval solver because it can explain *why* each event was dropped;
only reach for an ILP (OR-Tools/PuLP) if choice-surfacing demands it. **Call out
before adding a solver dependency.**

## Decide

`plan(schedule, wants, travel, params) -> Plan` where Plan has: the ordered
attended list, dropped wants each with a reason, and the set of forced either/or
choices. For grouped/window wants, the solver picks the instance(s). Null
`end_utc` uses `default_set_minutes`; windows use `visit_minutes`.

## Act

- [x] Define Plan / decision data structures (`Plan`, `Attendance`, `Dropped`
      with `DropReason`, `ForcedChoice`).
- [x] Solver honouring no-overlap + travel gaps. Exact branch-and-bound DFS over
      candidates sorted by start, state carrying the last attended event (travel
      feasibility is pairwise, which breaks the textbook O(n log n) WIS DP - see
      the module docstring and `_search`). Provably optimal at this scale.
- [x] Instance selection for group and window wants (group: pick up to `count`
      feasible instances; window = long span -> a `visit_minutes` visit placed at
      the earliest point of the span).
- [x] Emit dropped-with-reason (`CLASH`/`TRAVEL`/`UNRESOLVED`/`SHORTFALL`, each
      naming what it lost to) and forced-choice lists (union-find clusters of
      mutually exclusive wanted events).
- [x] Unit tests on hand-built fixtures (clash, repeat/group, travel-infeasible,
      weight preference, point-set default, unresolved ref, group shortfall).

## Outcomes

1. A wishlist becomes a feasible, near-optimal attendance plan with the
   reasoning for every drop and every forced choice made explicit.

## Tests

- [x] Two hard-overlapping wants -> exactly one attended, the other dropped with
      reason (`CLASH`); the trade-off is surfaced as a `ForcedChoice`.
- [x] A grouped want with one feasible instance picks that instance (and a
      single-instance group is attended; `count>1` attends multiple).
- [x] A pair feasible only with enough travel gap is scheduled; an infeasible
      one is dropped citing travel (`TRAVEL`).
- [x] Higher-weight wants are preferred when forced to choose (independent of
      input order).
- [x] No two attended events overlap once travel is included (invariant checked
      directly on the returned plan).
