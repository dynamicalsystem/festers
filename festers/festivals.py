"""The festival registry - discovers and holds every festival's schedule.

A festival is self-contained data: a ``data/festivals/<id>/schedule.json`` (its
venues + travel matrix + events). The registry globs that directory at startup,
loads and validates each schedule (fail fast on a bad or duplicate one), and
keys them by ``festival.id`` so the web layer can route to one by id. Adding a
festival is dropping a new ``<id>/schedule.json`` here - no code change.

The base directory is overridable via ``FESTERS_FESTIVALS_DIR`` (same pattern as
``FESTERS_PLANS_DIR``/``FESTERS_AUTH_DIR``) so tests can point at a tmp dir.
"""

from __future__ import annotations

import os
from pathlib import Path

from festers.schedule import Schedule, load_schedule

DEFAULT_FESTIVALS_DIR = Path(__file__).resolve().parent.parent / "data" / "festivals"


def festivals_dir() -> Path:
    # Read at call time so create_app()/load_registry() pick up a test-set env var.
    return Path(os.environ.get("FESTERS_FESTIVALS_DIR", str(DEFAULT_FESTIVALS_DIR)))


class FestivalRegistry:
    """An immutable id -> Schedule map with a stable display ordering."""

    def __init__(self, schedules: dict[str, Schedule]):
        self._by_id = dict(schedules)

    def get(self, festival_id: str | None) -> Schedule | None:
        if festival_id is None:
            return None
        return self._by_id.get(festival_id)

    def all(self) -> list[Schedule]:
        """Every festival, earliest first (then by id) - the index ordering."""
        return sorted(
            self._by_id.values(),
            key=lambda s: (s.festival.dates[0] if s.festival.dates else "", s.festival.id),
        )

    def ids(self) -> list[str]:
        return [s.festival.id for s in self.all()]

    def __len__(self) -> int:
        return len(self._by_id)

    def __contains__(self, festival_id: str) -> bool:
        return festival_id in self._by_id


def load_registry(base_dir: str | Path | None = None) -> FestivalRegistry:
    """Load every ``<base_dir>/<id>/schedule.json`` into a registry.

    Raises on a malformed schedule, a duplicate festival id, or an empty
    directory (a deploy with no festivals is a misconfiguration, surfaced early)."""
    base = Path(base_dir) if base_dir is not None else festivals_dir()
    schedules: dict[str, Schedule] = {}
    for path in sorted(base.glob("*/schedule.json")):
        schedule = load_schedule(path)
        fid = schedule.festival.id
        if fid in schedules:
            raise ValueError(f"duplicate festival id {fid!r} (from {path})")
        schedules[fid] = schedule
    if not schedules:
        raise ValueError(f"no festivals found under {base}")
    return FestivalRegistry(schedules)
