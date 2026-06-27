from __future__ import annotations

from datetime import timedelta

from festers.params import Interval, OptimiserParams, event_interval


def test_event_interval_uses_real_end(tiny_schedule):
    iv = event_interval(tiny_schedule.event("e1"), OptimiserParams())
    assert iv.minutes == 60


def test_event_interval_applies_default_for_null_end(tiny_schedule):
    p = OptimiserParams(default_set_minutes=45)
    iv = event_interval(tiny_schedule.event("e3"), p)  # e3 has no end_utc
    assert iv.minutes == 45


def test_overlap_true_for_clashing(tiny_schedule):
    p = OptimiserParams()
    a = event_interval(tiny_schedule.event("e1"), p)  # 18:00-19:00
    b = event_interval(tiny_schedule.event("e2"), p)  # 18:30-19:30
    assert a.overlaps(b)
    assert b.overlaps(a)  # symmetric


def test_no_overlap_for_disjoint(tiny_schedule):
    p = OptimiserParams()
    a = event_interval(tiny_schedule.event("e4"), p)  # 12:00-13:00
    b = event_interval(tiny_schedule.event("e5"), p)  # 15:00-16:00
    assert not a.overlaps(b)


def test_touching_is_not_overlap(tiny_schedule):
    p = OptimiserParams()
    a = event_interval(tiny_schedule.event("e4"), p)  # ends 13:00
    # an interval starting exactly at 13:00 does not clash with one ending 13:00
    b = event_interval(tiny_schedule.event("e5"), p)
    later = Interval(start=a.end, end=a.end + timedelta(hours=1))
    assert not a.overlaps(later)


def test_gap_turns_a_tight_pass_into_a_clash(tiny_schedule):
    p = OptimiserParams()
    a = event_interval(tiny_schedule.event("e4"), p)  # 12:00-13:00
    later = Interval(start=a.end + timedelta(minutes=10), end=a.end + timedelta(minutes=70))
    assert not a.overlaps(later)                       # 10 min gap, no travel
    assert a.overlaps(later, gap=timedelta(minutes=15))  # needs 15 min to travel
