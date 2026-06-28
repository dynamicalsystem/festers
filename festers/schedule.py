"""Contract A - the festival schedule as trustworthy structured data.

Loads ``data/schedule.json`` into validated models. ``start_utc``/``end_utc`` are
canonical UTC (the house rule, reaffirmed 2026-06-24); naive datetimes are
rejected so the discipline cannot silently rot. ``end_utc`` is ``None`` for point
sets with no published duration - consumers apply an assumed length via
:func:`festers.params.event_interval`.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import cached_property
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, field_validator

DEFAULT_SCHEDULE_PATH = Path(__file__).resolve().parent.parent / "data" / "schedule.json"


def _ensure_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Reject naive datetimes; normalise aware ones to UTC.

    Encodes the UTC-canonical house rule in the type system: anything that
    reaches a model carries an explicit offset, and we store it as ``Z`` UTC.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware (UTC canonical)")
    return value.astimezone(timezone.utc)


class Festival(BaseModel):
    id: str  # stable slug, e.g. "blacklight"; namespaces plan ids per festival
    name: str
    subtitle: Optional[str] = None
    location: Optional[str] = None
    dates: list[str]
    timezone: str
    utc_offset_during_festival: str
    source: Optional[str] = None
    transcribed: Optional[str] = None
    verified: bool = False
    notes: Optional[str] = None


class Venue(BaseModel):
    code: str
    name: str
    zone: str  # coarse travel bucket (drives the travel model)
    address: Optional[str] = None
    maps_url: Optional[str] = None  # Apple Maps link for tap-to-navigate


class Collection(BaseModel):
    """A festival strand a set of events belong to (a programme or a repeat)."""

    key: str
    name: str


class Event(BaseModel):
    id: str
    name: str
    venue: str  # venue code
    room: Optional[str] = None  # space within the venue (e.g. "Opera House"); not all venues have rooms
    type: str  # gig | film | exhibition | talk | workshop
    collection: Optional[str] = None  # key into collections[]
    start_utc: datetime
    end_utc: Optional[datetime] = None  # real span for exhibitions/films; null for point events
    start_local: Optional[str] = None
    end_local: Optional[str] = None
    local_date: Optional[str] = None
    verified: bool = False
    notes: Optional[str] = None

    _utc = field_validator("start_utc", "end_utc")(_ensure_utc)


class Schedule(BaseModel):
    festival: Festival
    venues: list[Venue]
    events: list[Event]
    collections: list[Collection] = []

    # --- indexes (built once, O(1) lookups) ---
    @cached_property
    def _venue_by_code(self) -> dict[str, Venue]:
        return {v.code: v for v in self.venues}

    @cached_property
    def _event_by_id(self) -> dict[str, Event]:
        return {e.id: e for e in self.events}

    @cached_property
    def _events_by_collection(self) -> dict[str, list[Event]]:
        out: dict[str, list[Event]] = {}
        for e in self.events:
            if e.collection is not None:
                out.setdefault(e.collection, []).append(e)
        return out

    @cached_property
    def _collection_by_key(self) -> dict[str, Collection]:
        return {c.key: c for c in self.collections}

    def venue(self, code: str) -> Venue:
        return self._venue_by_code[code]

    def event(self, event_id: str) -> Event:
        return self._event_by_id[event_id]

    def zone_of(self, venue_code: str) -> str:
        return self._venue_by_code[venue_code].zone

    def zone_of_event(self, event: Event) -> str:
        return self.zone_of(event.venue)

    def events_in_collection(self, collection: str) -> list[Event]:
        return list(self._events_by_collection.get(collection, []))

    def collection_name(self, key: str) -> str:
        c = self._collection_by_key.get(key)
        return c.name if c else key

    @cached_property
    def zones(self) -> set[str]:
        return {v.zone for v in self.venues}


def load_schedule(path: str | Path = DEFAULT_SCHEDULE_PATH) -> Schedule:
    """Load and validate the schedule JSON. Raises on a malformed file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return Schedule.model_validate(data)
