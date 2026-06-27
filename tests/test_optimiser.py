"""Tests for the optimiser core (loop-05).

All fixtures are hand-built (NOT the real schedule) so each behaviour is obvious
and independent of the data. The point of the optimiser is EXPLAINABILITY, so the
tests assert on the reasons attached to drops and on the surfaced forced choices,
not just on the attended set.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from festers.params import OptimiserParams
from festers.schedule import Event, Festival, Schedule, Venue
from festers.wants import Want, Wants
from festers.optimiser import DropReason, plan


def _utc(h, mi, d=26):
    return datetime(2026, 6, d, h, mi, tzinfo=timezone.utc)


def _sched(venues, events):
    festival = Festival(
        id="opt",
        name="Opt Fest",
        dates=["2026-06-26"],
        timezone="Europe/London",
        utc_offset_during_festival="+01:00",
    )
    return Schedule(festival=festival, venues=venues, events=events)


# A zero/flat travel stub: makes overlap tests about TIME only, no travel noise.
def _no_travel(_a, _b):
    return 0


# A travel stub keyed on zone names used in the travel fixtures below.
def _zone_travel(table, default=0):
    def f(a, b):
        if a == b:
            return default
        return table[frozenset({a, b})]

    return f


# --------------------------------------------------------------------------
# 1. Two hard-overlapping wants -> exactly one attended, other dropped+reason,
#    trade-off surfaced.
# --------------------------------------------------------------------------

def test_hard_overlap_keeps_one_drops_other_with_reason():
    venues = [Venue(code="A1", name="Alpha", zone="central")]
    events = [
        Event(id="e1", name="Set One", venue="A1", type="gig",
              start_utc=_utc(18, 0), end_utc=_utc(19, 0)),
        Event(id="e2", name="Set Two", venue="A1", type="gig",
              start_utc=_utc(18, 30), end_utc=_utc(19, 30)),
    ]
    schedule = _sched(venues, events)
    wants = Wants(plan_name="t", wants=[
        Want(ref="e1", kind="event", weight=3),
        Want(ref="e2", kind="event", weight=1),
    ])

    result = plan(schedule, wants, _no_travel, OptimiserParams())

    attended_ids = [a.event.id for a in result.attended]
    assert attended_ids == ["e1"]  # higher weight wins
    assert len(result.dropped) == 1
    drop = result.dropped[0]
    assert drop.want.ref == "e2"
    assert drop.reason == DropReason.CLASH
    # the trade-off names the winner so the user can override
    assert "e1" in drop.conflicts_with
    # forced choice surfaced as an either/or group
    assert any({"e1", "e2"} <= set(fc.event_ids) for fc in result.forced_choices)


# --------------------------------------------------------------------------
# 2. Higher-weight want preferred under forced choice (independent of order).
# --------------------------------------------------------------------------

def test_higher_weight_preferred_regardless_of_input_order():
    venues = [Venue(code="A1", name="Alpha", zone="central")]
    events = [
        Event(id="e1", name="Low", venue="A1", type="gig",
              start_utc=_utc(18, 0), end_utc=_utc(19, 0)),
        Event(id="e2", name="High", venue="A1", type="gig",
              start_utc=_utc(18, 30), end_utc=_utc(19, 30)),
    ]
    schedule = _sched(venues, events)
    # low-weight listed first; high-weight should still win
    wants = Wants(plan_name="t", wants=[
        Want(ref="e1", kind="event", weight=1),
        Want(ref="e2", kind="event", weight=5),
    ])
    result = plan(schedule, wants, _no_travel, OptimiserParams())
    assert [a.event.id for a in result.attended] == ["e2"]


# --------------------------------------------------------------------------
# 3. Grouped want with one feasible instance picks that instance.
# --------------------------------------------------------------------------

def test_group_want_picks_the_only_feasible_instance():
    venues = [Venue(code="A1", name="Alpha", zone="central")]
    events = [
        # a fixed high-weight event blocks reel-one's slot
        Event(id="block", name="Blocker", venue="A1", type="gig",
              start_utc=_utc(12, 0), end_utc=_utc(13, 0)),
        Event(id="r1", name="Reel One", venue="A1", type="film", collection="reels",
              start_utc=_utc(12, 0), end_utc=_utc(13, 0)),
        Event(id="r2", name="Reel Two", venue="A1", type="film", collection="reels",
              start_utc=_utc(15, 0), end_utc=_utc(16, 0)),
    ]
    schedule = _sched(venues, events)
    wants = Wants(plan_name="t", wants=[
        Want(ref="block", kind="event", weight=10),
        Want(ref="collection:reels", kind="collection", weight=2, count=1),
    ])
    result = plan(schedule, wants, _no_travel, OptimiserParams())
    attended_ids = {a.event.id for a in result.attended}
    assert "block" in attended_ids
    # only r2 is feasible (r1 clashes the blocker), so the group resolves to r2
    assert "r2" in attended_ids
    assert "r1" not in attended_ids


def test_group_want_with_single_instance_is_attended():
    venues = [Venue(code="A1", name="Alpha", zone="central")]
    events = [
        Event(id="g1", name="Solo", venue="A1", type="film", collection="solo",
              start_utc=_utc(12, 0), end_utc=_utc(13, 0)),
    ]
    schedule = _sched(venues, events)
    wants = Wants(plan_name="t", wants=[
        Want(ref="collection:solo", kind="collection", weight=2, count=1),
    ])
    result = plan(schedule, wants, _no_travel, OptimiserParams())
    assert [a.event.id for a in result.attended] == ["g1"]


# --------------------------------------------------------------------------
# 4. Travel feasibility: a gap large enough is scheduled; too small cites travel.
# --------------------------------------------------------------------------

def test_pair_feasible_only_with_enough_travel_gap_is_scheduled():
    venues = [
        Venue(code="A1", name="Alpha", zone="central"),
        Venue(code="B1", name="Beta", zone="south-seafront"),
    ]
    # 30-minute gap between end of e1 and start of e2; travel is 20 -> feasible.
    events = [
        Event(id="e1", name="Central Set", venue="A1", type="gig",
              start_utc=_utc(18, 0), end_utc=_utc(19, 0)),
        Event(id="e2", name="Beach Set", venue="B1", type="gig",
              start_utc=_utc(19, 30), end_utc=_utc(20, 30)),
    ]
    schedule = _sched(venues, events)
    travel = _zone_travel({frozenset({"central", "south-seafront"}): 20})
    wants = Wants(plan_name="t", wants=[
        Want(ref="e1", kind="event", weight=1),
        Want(ref="e2", kind="event", weight=1),
    ])
    result = plan(schedule, wants, travel, OptimiserParams())
    assert {a.event.id for a in result.attended} == {"e1", "e2"}
    assert result.dropped == []


def test_pair_infeasible_by_travel_is_dropped_citing_travel():
    venues = [
        Venue(code="A1", name="Alpha", zone="central"),
        Venue(code="B1", name="Beta", zone="south-seafront"),
    ]
    # only a 10-minute clock gap, but travel is 40 -> cannot make the second.
    events = [
        Event(id="e1", name="Central Set", venue="A1", type="gig",
              start_utc=_utc(18, 0), end_utc=_utc(19, 0)),
        Event(id="e2", name="Beach Set", venue="B1", type="gig",
              start_utc=_utc(19, 10), end_utc=_utc(20, 10)),
    ]
    schedule = _sched(venues, events)
    travel = _zone_travel({frozenset({"central", "south-seafront"}): 40})
    wants = Wants(plan_name="t", wants=[
        Want(ref="e1", kind="event", weight=3),  # keep the higher-weight one
        Want(ref="e2", kind="event", weight=1),
    ])
    result = plan(schedule, wants, travel, OptimiserParams())
    assert [a.event.id for a in result.attended] == ["e1"]
    assert len(result.dropped) == 1
    drop = result.dropped[0]
    assert drop.want.ref == "e2"
    assert drop.reason == DropReason.TRAVEL
    assert "e1" in drop.conflicts_with


# --------------------------------------------------------------------------
# 5. Invariant: no two attended events overlap once travel is included.
# --------------------------------------------------------------------------

def test_no_attended_pair_overlaps_with_travel_included():
    venues = [
        Venue(code="A1", name="Alpha", zone="central"),
        Venue(code="B1", name="Beta", zone="south-seafront"),
        Venue(code="C1", name="Gamma", zone="north-seafront"),
    ]
    events = [
        Event(id="e1", name="One", venue="A1", type="gig",
              start_utc=_utc(10, 0), end_utc=_utc(11, 0)),
        Event(id="e2", name="Two", venue="B1", type="gig",
              start_utc=_utc(11, 30), end_utc=_utc(12, 30)),
        Event(id="e3", name="Three", venue="C1", type="gig",
              start_utc=_utc(13, 0), end_utc=_utc(14, 0)),
        Event(id="e4", name="Four overlaps e1", venue="A1", type="gig",
              start_utc=_utc(10, 30), end_utc=_utc(11, 30)),
    ]
    schedule = _sched(venues, events)
    table = {
        frozenset({"central", "south-seafront"}): 25,
        frozenset({"south-seafront", "north-seafront"}): 40,
        frozenset({"central", "north-seafront"}): 18,
    }
    travel = _zone_travel(table)
    wants = Wants(plan_name="t", wants=[
        Want(ref="e1", kind="event", weight=1),
        Want(ref="e2", kind="event", weight=1),
        Want(ref="e3", kind="event", weight=1),
        Want(ref="e4", kind="event", weight=1),
    ])
    result = plan(schedule, wants, travel, OptimiserParams())

    # check the invariant directly on whatever the optimiser returned
    att = result.attended
    for i in range(len(att)):
        for j in range(i + 1, len(att)):
            a, b = att[i], att[j]
            t = travel(
                schedule.zone_of_event(a.event),
                schedule.zone_of_event(b.event),
            )
            # order by start
            from datetime import timedelta
            first, second = sorted((a, b), key=lambda x: x.interval.start)
            assert second.interval.start >= first.interval.end + timedelta(minutes=t), \
                "attended events must respect travel gap (and not overlap)"


# --------------------------------------------------------------------------
# 6. A non-wanted event never sneaks into the plan.
# --------------------------------------------------------------------------

def test_only_wanted_events_are_attended():
    venues = [Venue(code="A1", name="Alpha", zone="central")]
    events = [
        Event(id="e1", name="Wanted", venue="A1", type="gig",
              start_utc=_utc(18, 0), end_utc=_utc(19, 0)),
        Event(id="e2", name="Not wanted", venue="A1", type="gig",
              start_utc=_utc(20, 0), end_utc=_utc(21, 0)),
    ]
    schedule = _sched(venues, events)
    wants = Wants(plan_name="t", wants=[Want(ref="e1", kind="event", weight=1)])
    result = plan(schedule, wants, _no_travel, OptimiserParams())
    assert [a.event.id for a in result.attended] == ["e1"]


# --------------------------------------------------------------------------
# 7. Point set with null end uses default_set_minutes for clash reasoning.
# --------------------------------------------------------------------------

def test_point_set_uses_default_minutes_for_clash():
    venues = [Venue(code="A1", name="Alpha", zone="central")]
    events = [
        # null end -> 50 min default => occupies 20:00-20:50
        Event(id="e1", name="Point", venue="A1", type="gig",
              start_utc=_utc(20, 0), end_utc=None),
        # starts inside the assumed 50-min run -> clashes
        Event(id="e2", name="Overlaps assumed run", venue="A1", type="gig",
              start_utc=_utc(20, 30), end_utc=_utc(21, 30)),
    ]
    schedule = _sched(venues, events)
    wants = Wants(plan_name="t", wants=[
        Want(ref="e1", kind="event", weight=2),
        Want(ref="e2", kind="event", weight=1),
    ])
    result = plan(schedule, wants, _no_travel, OptimiserParams())
    assert [a.event.id for a in result.attended] == ["e1"]
    assert result.dropped[0].reason == DropReason.CLASH


# --------------------------------------------------------------------------
# 8. Unresolvable want (ref points nowhere) is dropped with a clear reason.
# --------------------------------------------------------------------------

def test_unknown_ref_is_dropped_unresolved():
    venues = [Venue(code="A1", name="Alpha", zone="central")]
    events = [Event(id="e1", name="X", venue="A1", type="gig",
                    start_utc=_utc(18, 0), end_utc=_utc(19, 0))]
    schedule = _sched(venues, events)
    wants = Wants(plan_name="t", wants=[
        Want(ref="e1", kind="event", weight=1),
        Want(ref="nope", kind="event", weight=1),
        Want(ref="collection:ghost", kind="collection", weight=1),
    ])
    result = plan(schedule, wants, _no_travel, OptimiserParams())
    assert [a.event.id for a in result.attended] == ["e1"]
    dropped_refs = {d.want.ref: d.reason for d in result.dropped}
    assert dropped_refs["nope"] == DropReason.UNRESOLVED
    assert dropped_refs["collection:ghost"] == DropReason.UNRESOLVED


# --------------------------------------------------------------------------
# 9. count>1 group want attends multiple instances when feasible.
# --------------------------------------------------------------------------

def test_group_count_two_attends_two_instances():
    venues = [Venue(code="A1", name="Alpha", zone="central")]
    events = [
        Event(id="r1", name="R1", venue="A1", type="film", collection="reels",
              start_utc=_utc(12, 0), end_utc=_utc(13, 0)),
        Event(id="r2", name="R2", venue="A1", type="film", collection="reels",
              start_utc=_utc(14, 0), end_utc=_utc(15, 0)),
        Event(id="r3", name="R3", venue="A1", type="film", collection="reels",
              start_utc=_utc(16, 0), end_utc=_utc(17, 0)),
    ]
    schedule = _sched(venues, events)
    wants = Wants(plan_name="t", wants=[
        Want(ref="collection:reels", kind="collection", weight=2, count=2),
    ])
    result = plan(schedule, wants, _no_travel, OptimiserParams())
    assert len(result.attended) == 2


def test_group_count_two_but_only_one_feasible_reports_shortfall():
    venues = [Venue(code="A1", name="Alpha", zone="central")]
    events = [
        Event(id="r1", name="R1", venue="A1", type="film", collection="reels",
              start_utc=_utc(12, 0), end_utc=_utc(13, 0)),
        Event(id="r2", name="R2", venue="A1", type="film", collection="reels",
              start_utc=_utc(12, 30), end_utc=_utc(13, 30)),  # clashes r1
    ]
    schedule = _sched(venues, events)
    wants = Wants(plan_name="t", wants=[
        Want(ref="collection:reels", kind="collection", weight=2, count=2),
    ])
    result = plan(schedule, wants, _no_travel, OptimiserParams())
    # one instance attended, want reported as a partial drop (shortfall)
    assert len(result.attended) == 1
    assert any(d.want.ref == "collection:reels" for d in result.dropped)


# --------------------------------------------------------------------------
# Scaling: many mutually-compatible wants must not blow up. The exact search is
# O(2^n) without bounding; the branch-and-bound weight bound must tame the
# all-compatible case (every event sequential in one zone) to near-linear.
# --------------------------------------------------------------------------

def test_many_compatible_wants_solve_fast_and_attend_all():
    import time
    from datetime import timedelta

    venues = [Venue(code="A1", name="Alpha", zone="central")]
    n = 40
    base = datetime(2026, 6, 26, 9, 0, tzinfo=timezone.utc)
    events = []
    for i in range(n):
        s = base + timedelta(hours=2 * i)  # 2h apart -> never overlap, all compatible
        events.append(Event(id=f"e{i}", name=f"Set {i}", venue="A1", type="gig",
                            start_utc=s, end_utc=s + timedelta(minutes=45)))
    schedule = _sched(venues, events)
    wants = Wants(plan_name="big",
                  wants=[Want(ref=f"e{i}", kind="event") for i in range(n)])

    t = time.time()
    result = plan(schedule, wants, _no_travel, OptimiserParams())
    dt = time.time() - t

    assert len(result.attended) == n        # all are compatible -> all attended
    assert result.dropped == []
    assert dt < 1.0, f"optimiser too slow on {n} compatible wants: {dt:.2f}s"
