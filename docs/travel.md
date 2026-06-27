# travel model (Contract C)

A hand-built **symmetric** zone-to-zone walking/tram minutes matrix
(`festers/travel.py`). No routing API and no dependency: six zones over a
weekend deadline make a calibrated hand matrix the right tool. The optimiser and
the conflict view consume `travel(zoneA, zoneB) -> int` as a pure callable.

## Geography (from `docs/venues.md` and the festival map)

Blackpool's venues sit on a single **north-south promenade axis**. Listing the
zones north -> south:

| order | zone               | anchor venue(s)              | character                         |
|-------|--------------------|------------------------------|-----------------------------------|
| 1     | `north-seafront`   | North Pier (NP)              | northern spur, an outlier         |
| 2     | `central`          | Winter Gardens, Houndshill   | the dense core                    |
| 2     | `central-seafront` | Blackpool Tower (BT)         | on the front, by the core         |
| 2     | `central-east`     | clubs (CC, BH, AV, BS)       | just inland of the core           |
| 2     | `central-south`    | church (SC), Albert Hotel    | just south of the core            |
| 3     | `south-seafront`   | The Pleasure Beach (PB)      | far south, a real tram ride       |

The four `central-*` zones are the cluster: a few minutes between any two. Travel
cost is dominated by the two outliers (NP, PB), exactly as `docs/design.md` says.

## Calibration, per cell

`SAME_ZONE_MINUTES = 5`. **ASSUMPTION:** even within one zone you walk between
venues, so same-zone is a small positive default, never zero. 5 min is a generous
"across one precinct" walk.

Distinct-zone cells (symmetric; stored once per unordered pair):

| pair                                   | min | rationale                                                            |
|----------------------------------------|-----|----------------------------------------------------------------------|
| central ↔ central-seafront             | 5   | Winter Gardens to the Tower is a couple of streets on the front.     |
| central ↔ central-east                 | 6   | core to the inland clubs, a short walk.                              |
| central ↔ central-south                | 7   | core to the church/Albert, slightly further south.                   |
| central-east ↔ central-seafront        | 8   | across the core from inland to the front.                            |
| central-east ↔ central-south           | 8   | across the core, inland to south.                                    |
| central-seafront ↔ central-south       | 8   | along the front then inland-south.                                   |
| north-seafront ↔ central               | 18  | North Pier down the prom into the core - a real walk.                |
| north-seafront ↔ central-seafront      | 16  | both on the seafront, so the most direct of the NP hops.             |
| north-seafront ↔ central-east          | 20  | NP plus the inland leg.                                              |
| north-seafront ↔ central-south         | 22  | NP to the far (south) side of the core.                              |
| south-seafront ↔ central-south         | 18  | PB is just south of central-south - the cheapest PB hop.             |
| south-seafront ↔ central-seafront      | 20  | both on the front; tram down the prom.                              |
| south-seafront ↔ central               | 22  | PB into the core, a tram ride (design.md: "a real journey").         |
| south-seafront ↔ central-east          | 24  | PB plus the inland leg - the most expensive PB hop.                  |
| **north-seafront ↔ south-seafront**    | 40  | the two opposite ends of the promenade; the single worst trip.       |

### Calibration principles (so the cells are not arbitrary)

1. **Same-zone < cluster hops < outlier hops < end-to-end.** Tests assert this
   ordering, not the exact numbers, so re-tuning a cell will not break the suite
   unless it crosses a tier boundary.
2. **Outliers materially larger.** Every NP/PB-into-cluster cell exceeds the
   largest cluster-internal hop (8). PB-into-core is >= 15 (design.md calls it "a
   real journey / tram").
3. **Seafront-to-seafront is cheaper than crossing inland.** Both NP and PB are
   on the front, so their `*-seafront` cells are the cheapest of their hops and
   their `central-east` (inland) cells the dearest.
4. **The cluster is deliberately flat (5-8 min).** Do not over-fit it; the map
   resolution does not justify finer distinctions there (design.md: "do not
   over-fit the cluster").

## API

- `travel(zoneA, zoneB) -> int` - symmetric; same-zone -> `SAME_ZONE_MINUTES`;
  unknown zone -> `KeyError` (a wiring bug worth surfacing, not silently 0).
- `travel_between_venues(schedule, codeA, codeB) -> int` - resolves venue codes
  to zones then calls `travel`.
- `travel_callable() -> Callable[[str, str], int]` - the function as a plain
  callable for the optimiser to take as a parameter (so it never imports this
  module directly; tests can pass any stub of the same shape).
- `ZONES` - the matrix's zone set; tested to equal `schedule.zones` exactly so a
  new zone in the data fails loudly instead of `KeyError`-ing at runtime.
