"""Shared fixtures. Real schedule for integration-ish tests; tiny hand-built
schedules for unit tests so behaviour is obvious and independent of the data."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from festers.schedule import Event, Festival, Schedule, Venue, load_schedule


@pytest.fixture(scope="session")
def real_schedule() -> Schedule:
    return load_schedule()


def _utc(y, mo, d, h, mi):
    return datetime(y, mo, d, h, mi, tzinfo=timezone.utc)


@pytest.fixture
def tiny_schedule() -> Schedule:
    """Two zones, a couple of venues, a handful of events incl. a null-end point
    set and a two-instance group - enough to exercise every primitive."""
    festival = Festival(
        id="test",
        name="Test Fest",
        dates=["2026-06-26"],
        timezone="Europe/London",
        utc_offset_during_festival="+01:00",
    )
    venues = [
        Venue(code="A1", name="Alpha Hall", zone="central"),
        Venue(code="B1", name="Beta Beach", zone="south-seafront"),
    ]
    events = [
        Event(id="e1", name="Early Set", venue="A1", type="gig",
              start_utc=_utc(2026, 6, 26, 18, 0), end_utc=_utc(2026, 6, 26, 19, 0)),
        Event(id="e2", name="Clashing Set", venue="A1", type="gig",
              start_utc=_utc(2026, 6, 26, 18, 30), end_utc=_utc(2026, 6, 26, 19, 30)),
        Event(id="e3", name="Point Set (no end)", venue="B1", type="gig",
              start_utc=_utc(2026, 6, 26, 20, 0), end_utc=None),
        Event(id="e4", name="Reel One", venue="A1", type="film", collection="reels",
              start_utc=_utc(2026, 6, 26, 12, 0), end_utc=_utc(2026, 6, 26, 13, 0)),
        Event(id="e5", name="Reel Two", venue="A1", type="film", collection="reels",
              start_utc=_utc(2026, 6, 26, 15, 0), end_utc=_utc(2026, 6, 26, 16, 0)),
    ]
    return Schedule(festival=festival, venues=venues, events=events)
