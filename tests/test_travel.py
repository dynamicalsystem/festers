"""Tests for Contract C - the zone-to-zone travel model (loop-04).

Hand-built expectations plus invariants checked against the REAL schedule so the
matrix cannot silently fall out of date with the venue list.
"""

from __future__ import annotations

import itertools

import pytest

from festers.travel import (
    SAME_ZONE_MINUTES,
    ZONES,
    travel,
    travel_between_venues,
    travel_callable,
)


# --- in-cluster default --------------------------------------------------

@pytest.mark.parametrize("zone", sorted(ZONES))
def test_same_zone_is_small_default_not_zero(zone):
    # ASSUMPTION: even within a zone you walk between venues, so same-zone is a
    # small positive default, never zero-by-accident.
    assert travel(zone, zone) == SAME_ZONE_MINUTES
    assert travel(zone, zone) > 0


# --- symmetry ------------------------------------------------------------

def test_matrix_is_symmetric():
    for a, b in itertools.product(ZONES, ZONES):
        assert travel(a, b) == travel(b, a), f"asymmetric {a}->{b}"


def test_all_pairs_are_positive_ints():
    for a, b in itertools.product(ZONES, ZONES):
        m = travel(a, b)
        assert isinstance(m, int)
        assert m > 0


# --- outliers materially larger -----------------------------------------

def test_outliers_cost_more_than_cluster_hops():
    # the cheapest non-trivial cluster hop
    cluster = ["central", "central-east", "central-seafront", "central-south"]
    cluster_hops = [
        travel(a, b) for a, b in itertools.combinations(cluster, 2)
    ]
    max_cluster_hop = max(cluster_hops)

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
        travel(a, b) for a, b in itertools.product(ZONES, ZONES)
    )


def test_pleasure_beach_is_a_real_journey():
    # design.md: PB is "the one venue that is a real journey (tram)".
    assert travel("south-seafront", "central") >= 15


# --- real-schedule coverage (no KeyError) -------------------------------

def test_every_schedule_zone_is_covered(real_schedule):
    for a in real_schedule.zones:
        for b in real_schedule.zones:
            travel(a, b)  # must not raise


def test_zones_constant_matches_real_schedule(real_schedule):
    # The module's ZONES must be a superset of whatever the data actually uses;
    # ideally exactly equal so dead cells get noticed.
    assert real_schedule.zones <= ZONES
    assert ZONES == real_schedule.zones


def test_unknown_zone_raises_keyerror():
    with pytest.raises(KeyError):
        travel("atlantis", "central")


# --- venue convenience ---------------------------------------------------

def test_travel_between_venues_resolves_zones(real_schedule):
    # NP (north-seafront) -> PB (south-seafront) is the end-to-end worst case.
    assert travel_between_venues(real_schedule, "NP", "PB") == travel(
        "north-seafront", "south-seafront"
    )
    # two venues in the same zone -> same-zone default.
    assert travel_between_venues(real_schedule, "WG", "GT") == SAME_ZONE_MINUTES


def test_travel_callable_is_a_simple_zone_pair_callable():
    f = travel_callable()
    assert f("central", "central") == SAME_ZONE_MINUTES
    assert f("north-seafront", "south-seafront") == travel(
        "north-seafront", "south-seafront"
    )
