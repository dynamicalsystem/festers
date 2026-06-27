"""Loop-03 - pure conflict detection over a wishlist (Contract B).

Reports every clashing PAIR among WANTED events. Built entirely on the shared
time primitives (``event_interval`` + ``Interval.overlaps``) so it cannot drift
from the optimiser on overlap semantics (DRY).

Travel seam (the loop-06 upgrade path, built now, defaulted off): pass a
``travel`` callable ``(zoneA, zoneB) -> minutes`` and its result is fed as the
``gap`` to ``Interval.overlaps`` - i.e. "can the user physically get from A to
B in time?". With ``travel=None`` it is pure time overlap. No interface change is
needed when loop-04's Contract C lands; the conflict view just starts passing it.

# ASSUMPTION (documented per loop-03 brief): window-type / point-set wants use
# their conservative FULL interval from ``event_interval`` (point sets -> assumed
# ``default_set_minutes``; windows -> their whole span). A coarse clash check
# prefers false-positives (flag a possible clash) over silently missing one; the
# optimiser does the finer flexible-placement reasoning.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta, timezone
from typing import Callable, Optional

from festers.params import Interval, OptimiserParams, event_interval
from festers.schedule import Event, Schedule
from festers.wants import Wants

# A travel cost function: minutes to get between two zones. Optional so the view
# ships (pure time overlap) before the travel model (Contract C) exists.
TravelFn = Callable[[str, str], float]


@dataclass(frozen=True)
class Conflict:
    """One clashing pair of wanted events, with a day label for grouping."""

    a: Event
    b: Event
    day: str  # festival session day label (see ``session_day``)
    overlap_minutes: float  # by how much they collide on pure time (>=0)


_FESTIVAL_TZ = timezone(timedelta(hours=1))  # fixed +01:00 for the whole event
# A festival "day" runs from late morning through the early hours of the NEXT
# calendar date. So an event before this clock hour belongs to the PREVIOUS
# night's session. (Can't fold by ``local_date`` alone: e.g. 2026-06-27 holds
# both Friday-night spillover at 01:30 AND Saturday daytime at 11:00.)
_SESSION_CUTOFF_HOUR = 6


def session_day(event: Event) -> str:
    """The festival 'night' an event belongs to, as a stable label string.

    Derived from the canonical ``start_utc`` (converted to the festival's fixed
    +01:00), assigning anything before ``_SESSION_CUTOFF_HOUR`` to the previous
    day's session. This correctly splits a calendar date that straddles two
    nights; the result is used only for the human day grouping.
    """
    local = event.start_utc.astimezone(_FESTIVAL_TZ)
    day = local.date()
    if local.hour < _SESSION_CUTOFF_HOUR:
        day -= timedelta(days=1)
    return day.isoformat()


def _wanted_events(schedule: Schedule, wants: Wants) -> list[Event]:
    """Resolve a wishlist to concrete event instances.

    - ``event`` wants -> the single event.
    - ``group`` wants -> every instance in the group (``events_in_group``).

    De-duplicated by event id so a refs overlap (event also covered by a group)
    cannot fabricate a self-clash. Order is stable for deterministic output.
    """
    seen: set[str] = set()
    out: list[Event] = []
    for want in wants.wants:
        if want.kind == "collection":
            key = want.ref[len("collection:"):] if want.ref.startswith("collection:") else want.ref
            instances = schedule.events_in_collection(key)
        else:
            try:
                instances = [schedule.event(want.ref)]
            except KeyError:
                # A want pointing at an unknown id is ignored here, not fatal;
                # the picker validates refs at write time.
                instances = []
        for ev in instances:
            if ev.id not in seen:
                seen.add(ev.id)
                out.append(ev)
    return out


def find_conflicts(
    schedule: Schedule,
    wants: Wants,
    params: OptimiserParams,
    travel: Optional[TravelFn] = None,
) -> list[Conflict]:
    """Every clashing pair among the wanted events.

    Two distinct events clash when their intervals (with an optional travel
    ``gap``) overlap. Each unordered pair is reported at most once; an event is
    never compared with itself. Sorted by start time then by partner start time
    for a stable, day-ordered view.
    """
    events = _wanted_events(schedule, wants)
    # Stable chronological order so the earlier event is ``a`` and output is
    # deterministic.
    events.sort(key=lambda e: (e.start_utc, e.id))

    intervals: dict[str, Interval] = {e.id: event_interval(e, params) for e in events}

    conflicts: list[Conflict] = []
    for i, a in enumerate(events):
        ia = intervals[a.id]
        for b in events[i + 1 :]:
            ib = intervals[b.id]
            gap = timedelta(0)
            if travel is not None:
                minutes = travel(schedule.zone_of(a.venue), schedule.zone_of(b.venue))
                gap = timedelta(minutes=minutes)
            if ia.overlaps(ib, gap=gap):
                conflicts.append(
                    Conflict(
                        a=a,
                        b=b,
                        day=session_day(a),
                        overlap_minutes=_overlap_minutes(ia, ib),
                    )
                )
    return conflicts


def _overlap_minutes(a: Interval, b: Interval) -> float:
    """Pure-time overlap in minutes (0 if they only clash via a travel gap)."""
    start = max(a.start, b.start)
    end = min(a.end, b.end)
    seconds = (end - start).total_seconds()
    return max(0.0, seconds / 60.0)
