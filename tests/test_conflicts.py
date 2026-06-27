"""Loop-03 - pure conflict-detection tests.

Built on the tiny_schedule fixture (conftest.py) so the expected clashes are
obvious by hand. The seam test injects a travel callable to prove the same
function upgrades to travel-feasibility (loop-06) without an interface change.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from festers.conflicts import Conflict, find_conflicts
from festers.params import OptimiserParams
from festers.wants import Want, Wants


@pytest.fixture
def params() -> OptimiserParams:
    return OptimiserParams()


def _wants(*refs_kinds) -> Wants:
    """(ref, kind) pairs -> a Wants object."""
    return Wants(
        plan_name="t",
        wants=[Want(ref=r, kind=k) for r, k in refs_kinds],
    )


def test_two_overlapping_wanted_events_are_a_conflict(tiny_schedule, params):
    # e1 18:00-19:00 and e2 18:30-19:30 overlap.
    wants = _wants(("e1", "event"), ("e2", "event"))
    conflicts = find_conflicts(tiny_schedule, wants, params)
    assert len(conflicts) == 1
    c = conflicts[0]
    assert {c.a.id, c.b.id} == {"e1", "e2"}


def test_two_non_overlapping_wanted_events_are_not_reported(tiny_schedule, params):
    # e1 18:00-19:00 and e4 12:00-13:00 do not overlap.
    wants = _wants(("e1", "event"), ("e4", "event"))
    assert find_conflicts(tiny_schedule, wants, params) == []


def test_unwanted_events_are_ignored(tiny_schedule, params):
    # e1 and e2 overlap but only e1 is wanted -> no conflict.
    wants = _wants(("e1", "event"))
    assert find_conflicts(tiny_schedule, wants, params) == []


def test_group_want_not_flagged_against_itself(tiny_schedule, params):
    # group "reels" = e4 (12:00-13:00) + e5 (15:00-16:00): two instances of one
    # want, do not overlap and must never be reported as a self-clash.
    wants = _wants(("collection:reels", "collection"))
    assert find_conflicts(tiny_schedule, wants, params) == []


def test_group_instance_conflicts_with_other_event(tiny_schedule, params):
    # e1 18:00-19:00 wanted as event; a group whose instance overlaps it.
    # reels instances are at 12:00 and 15:00 - neither overlaps e1, so still 0.
    wants = _wants(("e1", "event"), ("collection:reels", "collection"))
    assert find_conflicts(tiny_schedule, wants, params) == []


def test_pair_reported_once_not_twice(tiny_schedule, params):
    wants = _wants(("e1", "event"), ("e2", "event"))
    conflicts = find_conflicts(tiny_schedule, wants, params)
    pairs = [frozenset((c.a.id, c.b.id)) for c in conflicts]
    assert len(pairs) == len(set(pairs)) == 1


def test_point_set_with_null_end_uses_assumed_duration(tiny_schedule, params):
    # e3 is a point set at 20:00 with null end -> assumed 50 min -> 20:00-20:50.
    # Add a fixed event overlapping that assumed window.
    sched = tiny_schedule.model_copy(deep=True)
    from festers.schedule import Event
    from datetime import datetime, timezone

    sched.events.append(
        Event(
            id="e6",
            name="Overlaps the point set",
            venue="B1",
            type="gig",
            start_utc=datetime(2026, 6, 26, 20, 30, tzinfo=timezone.utc),
            end_utc=datetime(2026, 6, 26, 21, 30, tzinfo=timezone.utc),
        )
    )
    # rebuild index cache by reconstructing
    sched = sched.model_validate(sched.model_dump())
    wants = _wants(("e3", "event"), ("e6", "event"))
    conflicts = find_conflicts(sched, wants, params)
    assert len(conflicts) == 1
    assert {conflicts[0].a.id, conflicts[0].b.id} == {"e3", "e6"}


def test_travel_seam_turns_a_clean_pair_into_a_conflict(tiny_schedule, params):
    # e1 ends 19:00, e3 (point set) starts 20:00 -> 60 min gap, fine on pure time.
    wants = _wants(("e1", "event"), ("e3", "event"))
    assert find_conflicts(tiny_schedule, wants, params) == []

    # Inject a huge travel time between their zones -> now infeasible.
    def big_travel(zone_a: str, zone_b: str) -> float:
        return 120.0  # minutes; far exceeds the 60-min gap

    conflicts = find_conflicts(tiny_schedule, wants, params, travel=big_travel)
    assert len(conflicts) == 1
    assert {conflicts[0].a.id, conflicts[0].b.id} == {"e1", "e3"}


def test_travel_same_zone_small_gap_stays_clean(tiny_schedule, params):
    # e1 (A1, central) ends 19:00; e2 (A1, central) starts 18:30 -> overlap anyway.
    # Use e4 (A1 12:00-13:00) and e1 (A1 18:00) - same zone, hours apart, even a
    # modest travel time must not create a false conflict.
    wants = _wants(("e4", "event"), ("e1", "event"))

    def small_travel(zone_a: str, zone_b: str) -> float:
        return 5.0

    assert find_conflicts(tiny_schedule, wants, params, travel=small_travel) == []


def test_conflict_carries_day_for_grouping(tiny_schedule, params):
    wants = _wants(("e1", "event"), ("e2", "event"))
    c = find_conflicts(tiny_schedule, wants, params)[0]
    # day is a stable string label usable to group the view.
    assert isinstance(c.day, str) and c.day


def test_conflict_dataclass_fields(tiny_schedule, params):
    wants = _wants(("e1", "event"), ("e2", "event"))
    c = find_conflicts(tiny_schedule, wants, params)[0]
    assert isinstance(c, Conflict)
    assert hasattr(c, "a") and hasattr(c, "b")


def test_session_day_splits_a_straddling_calendar_date(real_schedule):
    """Regression: a calendar date can hold two sessions. 2026-06-27 carries both
    Friday-night spillover (01:30) and Saturday daytime (11:00); session_day must
    split them by clock time, not fold the whole date to one night."""
    from festers.conflicts import session_day

    by = {e.id: session_day(e) for e in real_schedule.events}
    assert by["e025"] == "2026-06-27"  # Saturday studio (11:00) -> Saturday
    assert by["e001"] == "2026-06-26"  # Friday studio -> Friday (not same as e025)
    assert by["e012"] == "2026-06-26"  # Fri-night 01:30 (date 06-27) -> Friday
    assert by["e101"] == "2026-06-28"  # Sun-night 00:30 (date 06-29) -> Sunday
    assert set(by.values()) == {"2026-06-26", "2026-06-27", "2026-06-28"}
