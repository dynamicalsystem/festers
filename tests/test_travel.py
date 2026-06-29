"""Tests for Contract C - the zone-to-zone travel model (loop-04).

The matrix now lives in each festival's data (``Schedule.travel``); these tests
drive it through :func:`festers.travel.make_travel` against the REAL schedule, so
the calibration cannot silently fall out of date with the venue list. The
completeness invariant (every venue-zone pair covered) is now enforced at load
time by ``Schedule`` - exercised in ``test_incomplete_matrix_rejected_at_load``.
"""

from __future__ import annotations

import itertools

import pytest
from pydantic import ValidationError

from festers.schedule import Festival, Schedule, TravelModel, Venue
from festers.travel import make_travel, travel_between_venues


# --- in-cluster default --------------------------------------------------

def test_same_zone_is_small_default_not_zero(real_schedule):
    # ASSUMPTION: even within a zone you walk between venues, so same-zone is a
    # small positive default, never zero-by-accident.
    travel = make_travel(real_schedule)
    same = real_schedule.travel.same_zone_minutes
    for zone in real_schedule.zones:
        assert travel(zone, zone) == same
        assert travel(zone, zone) > 0


# --- symmetry ------------------------------------------------------------

def test_matrix_is_symmetric(real_schedule):
    travel = make_travel(real_schedule)
    for a, b in itertools.product(real_schedule.zones, real_schedule.zones):
        assert travel(a, b) == travel(b, a), f"asymmetric {a}->{b}"


def test_all_pairs_are_positive_ints(real_schedule):
    travel = make_travel(real_schedule)
    for a, b in itertools.product(real_schedule.zones, real_schedule.zones):
        m = travel(a, b)
        assert isinstance(m, int)
        assert m > 0


# --- outliers materially larger -----------------------------------------

def test_outliers_cost_more_than_cluster_hops(real_schedule):
    travel = make_travel(real_schedule)
    # the cheapest non-trivial cluster hop
    cluster = ["central", "central-east", "central-seafront", "central-south"]
    max_cluster_hop = max(
        travel(a, b) for a, b in itertools.combinations(cluster, 2)
    )

    # North Pier (north-seafront) and Pleasure Beach (south-seafront) into the
    # central cluster must be materially larger than any cluster-internal hop.
    np_in = travel("north-seafront", "central")
    pb_in = travel("south-seafront", "central")
    assert np_in > max_cluster_hop
    assert pb_in > max_cluster_hop

    # the two opposite ends of the promenade are the single most expensive trip
    end_to_end = travel("north-seafront", "south-seafront")
    assert end_to_end >= np_in
    assert end_to_end >= pb_in
    assert end_to_end == max(
        travel(a, b) for a, b in itertools.product(real_schedule.zones, real_schedule.zones)
    )


def test_pleasure_beach_is_a_real_journey(real_schedule):
    # design.md: PB is "the one venue that is a real journey (tram)".
    assert make_travel(real_schedule)("south-seafront", "central") >= 15


# --- real-schedule coverage (no KeyError) -------------------------------

def test_every_schedule_zone_is_covered(real_schedule):
    travel = make_travel(real_schedule)
    for a in real_schedule.zones:
        for b in real_schedule.zones:
            travel(a, b)  # must not raise


def test_unknown_zone_raises_keyerror(real_schedule):
    with pytest.raises(KeyError):
        make_travel(real_schedule)("atlantis", "central")


# --- venue convenience ---------------------------------------------------

def test_travel_between_venues_resolves_zones(real_schedule):
    travel = make_travel(real_schedule)
    # NP (north-seafront) -> PB (south-seafront) is the end-to-end worst case.
    assert travel_between_venues(real_schedule, "NP", "PB") == travel(
        "north-seafront", "south-seafront"
    )
    # two venues in the same zone -> same-zone default.
    assert travel_between_venues(real_schedule, "WG", "GT") == \
        real_schedule.travel.same_zone_minutes


# --- load-time completeness ---------------------------------------------

def _festival() -> Festival:
    return Festival(
        id="t", name="T", dates=["2026-06-26"],
        timezone="Europe/London", utc_offset_during_festival="+01:00",
    )


def test_incomplete_matrix_rejected_at_load():
    # Two zones in use but the distinct pair between them is not in the matrix:
    # the schedule must refuse to validate (fail fast, never a runtime KeyError).
    with pytest.raises(ValidationError):
        Schedule(
            festival=_festival(),
            venues=[
                Venue(code="A", name="A", zone="central"),
                Venue(code="B", name="B", zone="south-seafront"),
            ],
            events=[],
            travel=TravelModel(same_zone_minutes=5, pairs=[]),
        )
