"""Contract C - the zone-to-zone travel model (loop-04).

A hand-built **symmetric** matrix of walking/tram minutes between the six zones
of the festival map. No routing API, no dependency: at this scale (six zones, a
weekend) a calibrated hand matrix gets the conflict/travel trade-offs right and
is trivially testable. The optimiser and the conflict view both consume
:func:`travel` as a pure ``(zoneA, zoneB) -> int`` callable.

Calibration is documented per cell in ``docs/travel.md``. The short version:
Blackpool's venues sit on one north-south promenade axis. Everything from the
Winter Gardens / Tower / Houndshill outward is a dense central cluster (a few
minutes between any two). North Pier sits north on its own spur and the Pleasure
Beach is far south - a genuine tram ride. Travel cost is dominated by those two
outliers, exactly as ``docs/design.md`` says.
"""

from __future__ import annotations

from typing import Callable

from festers.schedule import Schedule

# The six zones, ORDERED roughly north -> south along the promenade axis. The
# ordering is documentation, not logic (the matrix is explicit), but it makes the
# calibration legible: distance grows with separation along this axis.
ZONES: frozenset[str] = frozenset(
    {
        "north-seafront",  # North Pier - northern spur, the northern outlier
        "central",  # Winter Gardens / Houndshill core
        "central-east",  # clubs just inland of the core
        "central-seafront",  # Blackpool Tower, on the front by the core
        "central-south",  # church / hotel just south of the core
        "south-seafront",  # The Pleasure Beach - the far-south outlier
    }
)

# ASSUMPTION: within a single zone you still walk between venues, so same-zone is
# a small positive default, never zero. 5 min is a generous "across one venue
# precinct" walk.
SAME_ZONE_MINUTES: int = 5

# Symmetric zone-to-zone walking/tram minutes between DISTINCT zones. Stored once
# per unordered pair (frozenset key) so symmetry is structural - it cannot rot
# into an asymmetric matrix. Same-zone is handled by SAME_ZONE_MINUTES, not here.
#
# Calibration rationale lives in docs/travel.md; summary per cell:
#   central <-> central-east/seafront/south : 5-8 min, all inside the core cluster.
#   north-seafront (NP) <-> central core     : ~18 min, a real walk up the prom.
#   south-seafront (PB) <-> central core     : ~22 min, a tram ride down the prom.
#   north-seafront <-> south-seafront        : ~40 min, the two opposite ends.
_DISTINCT_PAIR_MINUTES: dict[frozenset[str], int] = {
    # --- central cluster internal hops (cheap) ---
    frozenset({"central", "central-east"}): 6,
    frozenset({"central", "central-seafront"}): 5,
    frozenset({"central", "central-south"}): 7,
    frozenset({"central-east", "central-seafront"}): 8,
    frozenset({"central-east", "central-south"}): 8,
    frozenset({"central-seafront", "central-south"}): 8,
    # --- north-seafront (North Pier) into the cluster ---
    frozenset({"north-seafront", "central"}): 18,
    frozenset({"north-seafront", "central-east"}): 20,
    frozenset({"north-seafront", "central-seafront"}): 16,  # both on the front
    frozenset({"north-seafront", "central-south"}): 22,
    # --- south-seafront (Pleasure Beach) into the cluster ---
    frozenset({"south-seafront", "central"}): 22,
    frozenset({"south-seafront", "central-east"}): 24,
    frozenset({"south-seafront", "central-seafront"}): 20,  # both on the front
    frozenset({"south-seafront", "central-south"}): 18,  # PB is just south
    # --- the two outliers to each other: the full length of the promenade ---
    frozenset({"north-seafront", "south-seafront"}): 40,
}


def travel(zone_a: str, zone_b: str) -> int:
    """Walking/tram minutes between two zones. Symmetric; same-zone -> default.

    Raises ``KeyError`` for an unknown zone (a wiring bug worth surfacing, not
    silently defaulting).
    """
    if zone_a not in ZONES:
        raise KeyError(zone_a)
    if zone_b not in ZONES:
        raise KeyError(zone_b)
    if zone_a == zone_b:
        return SAME_ZONE_MINUTES
    return _DISTINCT_PAIR_MINUTES[frozenset({zone_a, zone_b})]


def travel_between_venues(schedule: Schedule, code_a: str, code_b: str) -> int:
    """Convenience: travel minutes between two venues, by their zones."""
    return travel(schedule.zone_of(code_a), schedule.zone_of(code_b))


def travel_callable() -> Callable[[str, str], int]:
    """The travel function as a plain ``(zoneA, zoneB) -> int`` callable.

    The optimiser takes a callable so it never depends on this module directly;
    a test can pass any stub of the same shape.
    """
    return travel
