# loop-04: travel model

Status: **shipped** (pending loop-06 converge). Track B. Depends on loop-01
(venues/zones). Produces Contract C. Implemented in `festers/travel.py`;
calibration documented per cell in `docs/travel.md`; tests in
`tests/test_travel.py` (all green).

## Observe

The optimiser and the conflict view need to know how long it takes to get from
one venue to another. We have no travel data yet. Almost everything is in the
central cluster (cheap hops); North Pier and the Pleasure Beach are the costly
outliers (the closing ceremony is at the Pleasure Beach).

## Orient

A geocoded routing API is overkill for ~5 zones and a weekend deadline, and adds
a dependency. A hand-built symmetric zone-to-zone walking-minutes matrix is good
enough to get the conflict/travel trade-offs right and needs nothing. Build it
standalone and testable so Track A and the optimiser can consume it independently.

## Decide

Define zones (already on each venue in `schedule.json`), build a symmetric
zone-to-zone minutes matrix, and expose `travel(zoneA, zoneB) -> minutes` (and a
venue-to-venue convenience). Calibrate the outliers against rough real walking/
tram times; do not over-fit the cluster.

## Act

- [x] Enumerate zones from the schedule venues. (`ZONES`; tested to equal
      `schedule.zones` exactly so a new zone fails loudly.)
- [x] Hand-assign the symmetric matrix; document the assumptions per cell.
      (`_DISTINCT_PAIR_MINUTES`, keyed on `frozenset` pairs so symmetry is
      structural; rationale in `docs/travel.md`.)
- [x] Implement and unit-test `travel()` (+ `travel_between_venues`,
      `travel_callable`).

## Outcomes

1. Conflict view and optimiser can ask "can I get from A to B in the gap?".

## Tests

- [x] `travel(z, z)` returns the small in-cluster default, not zero-by-accident.
- [x] The matrix is symmetric (checked over all zone pairs).
- [x] Pleasure Beach / North Pier costs are materially larger than cluster hops;
      end-to-end (NP↔PB) is the single most expensive trip.
- [x] Every zone present in `schedule.json` is covered by the matrix (asserted
      against `real_schedule.zones`; unknown zone raises `KeyError`).
