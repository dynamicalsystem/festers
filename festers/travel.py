"""Contract C - the zone-to-zone travel model, sourced from festival data.

Each festival owns its travel matrix in its schedule (``Schedule.travel``, a
:class:`~festers.schedule.TravelModel`): a hand-built **symmetric** matrix of
walking/tram minutes between that festival's zones. This module adapts that data
into the pure ``(zoneA, zoneB) -> int`` callable the optimiser and conflict view
consume, so neither depends on a global matrix and every festival carries its own
calibration. The matrix's completeness (every venue-zone pair covered) is enforced
at load time by ``Schedule``; an uncovered pair raises ``KeyError`` here rather
than silently defaulting.

Calibration rationale for The Black Lights lives in ``docs/travel.md``: a dense
central cluster (a few minutes between any two), with North Pier and the Pleasure
Beach as the two outliers that dominate travel cost.
"""

from __future__ import annotations

from typing import Callable

from festers.schedule import Schedule


def make_travel(schedule: Schedule) -> Callable[[str, str], int]:
    """This festival's travel matrix as a pure ``(zoneA, zoneB) -> int`` callable.

    Closes over ``schedule.travel``; same-zone -> the festival's default,
    uncovered distinct pair -> ``KeyError`` (a data gap, surfaced not defaulted).
    The optimiser takes a callable so it never depends on this module directly -
    a test can pass any stub of the same shape.
    """
    return schedule.travel.minutes


def travel_between_venues(schedule: Schedule, code_a: str, code_b: str) -> int:
    """Convenience: travel minutes between two venues, by their zones."""
    return schedule.travel.minutes(schedule.zone_of(code_a), schedule.zone_of(code_b))
