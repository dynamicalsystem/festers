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

from itertools import combinations

from pydantic import BaseModel, field_validator, model_validator

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


class TravelPair(BaseModel):
    """Walking/tram minutes between two DISTINCT zones (an unordered pair)."""

    zones: tuple[str, str]
    minutes: int


class TravelModel(BaseModel):
    """A festival's hand-built zone-to-zone travel matrix (Contract C as data).

    Symmetric by construction: pairs are stored once and looked up by an
    unordered ``frozenset`` key, so the matrix cannot rot into an asymmetric one.
    Same-zone hops use ``same_zone_minutes`` (a small positive default - you still
    walk between venues in a zone), never zero-by-accident.
    """

    same_zone_minutes: int
    pairs: list[TravelPair]

    @cached_property
    def _by_pair(self) -> dict[frozenset[str], int]:
        return {frozenset(p.zones): p.minutes for p in self.pairs}

    def minutes(self, zone_a: str, zone_b: str) -> int:
        """Minutes between two zones. Symmetric; same-zone -> the default.

        Raises ``KeyError`` for an uncovered distinct pair (a data gap worth
        surfacing, not silently defaulting)."""
        if zone_a == zone_b:
            return self.same_zone_minutes
        return self._by_pair[frozenset({zone_a, zone_b})]


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
    travel: TravelModel

    @model_validator(mode="after")
    def _travel_covers_every_zone_pair(self) -> "Schedule":
        """Fail fast if the travel matrix is missing any pair of venue zones.

        The optimiser and conflict view treat an uncovered pair as a hard error
        (``KeyError``); catching it at load time keeps a half-specified festival
        from ever reaching them."""
        covered = self.travel._by_pair
        missing = [
            sorted(pair)
            for pair in (frozenset(p) for p in combinations(self.zones, 2))
            if pair not in covered
        ]
        if missing:
            raise ValueError(
                f"travel matrix missing zone pairs: {missing} "
                f"(zones in use: {sorted(self.zones)})"
            )
        return self

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
