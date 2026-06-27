"""Shared time primitives + optimiser tunables.

Both the conflict view (Track A) and the optimiser (Track B) reason about events
as time intervals and ask "do these two clash, allowing for travel?". That logic
lives here once so the two tracks cannot drift apart on it (DRY).

The tunables in :class:`OptimiserParams` are config the optimiser owns, NOT a
cross-loop contract (see ``docs/contracts.md``); change them freely.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from festers.schedule import Event


@dataclass(frozen=True)
class OptimiserParams:
    # Assumed length of a point set whose end_utc is null (design suggested
    # 45-60; 50 is a flagged assumption - tune against real set lengths).
    default_set_minutes: int = 50
    # Assumed length of a drop-in visit inside a window.
    visit_minutes: int = 30
    # Tie-breakers / objective weights for the optimiser (loop-05).
    travel_penalty_per_min: float = 0.01
    miss_penalty: float = 1.0


@dataclass(frozen=True)
class Interval:
    """A half-open [start, end) interval in UTC."""

    start: datetime
    end: datetime

    @property
    def minutes(self) -> float:
        return (self.end - self.start).total_seconds() / 60.0

    def overlaps(self, other: "Interval", gap: timedelta = timedelta(0)) -> bool:
        """True if the two intervals cannot both be attended.

        ``gap`` is the minimum required separation between them - pass the travel
        time between the two venues to fold travel-feasibility into the same
        primitive. With ``gap=0`` this is plain time overlap (touching is OK).
        """
        return self.start < other.end + gap and other.start < self.end + gap


def event_interval(event: Event, params: OptimiserParams) -> Interval:
    """The concrete UTC interval an event occupies for clash/travel reasoning.

    - Films / fixed events with a published end: their real [start, end).
    - Point events (``end_utc is None``, e.g. a gig): start + ``default_set_minutes``.
    - Exhibitions (a multi-hour drop-in span) return their FULL span. Flexible
      placement of a short ``visit_minutes`` visit inside that span is a consumer
      concern (the optimiser); for a coarse clash check the full span is the
      conservative interval.
    """
    start = event.start_utc
    if event.end_utc is not None:
        end = event.end_utc
    else:
        end = start + timedelta(minutes=params.default_set_minutes)
    return Interval(start=start, end=end)
