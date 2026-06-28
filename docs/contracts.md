# contracts

The interfaces that let loops proceed independently. **Changing any of these is
a boundary change - stop and have a conversation before doing it** (per our SDLC
rule on not moving interfaces unilaterally). Each is small on purpose.

## Contract A - schedule (`data/schedule.json`)

Source of truth for what is on. Produced by loop-01; reconciled to **schema 2**
against the source PDF (see `docs/reconciliation.md`). Frozen shape:

- `festival`: `id` (stable slug, e.g. `festers` - namespaces per-festival plan
  ids), name, dates, `timezone`, `utc_offset_during_festival`, `schema`, flags.
- `venues[]`: `{ code, name, zone, address, maps_url }`. `zone` drives the travel
  model; `maps_url` is an Apple Maps link for tap-to-navigate.
- `collections[]`: `{ key, name }` - a festival strand (a programme or a repeat).
- `events[]`: each event (his flat model: name/venue/time/type/collection)
  - `id` - stable string id (`e001`...). The unit a want can point at.
  - `name`, `venue` (code), `collection` (nullable key into `collections[]`).
  - `room` - **optional** space within the venue (e.g. `"Opera House"`,
    `"Olympia Hall"`). Free text, nullable; absent for single-room venues. A
    display/wayfinding cue only - it does not affect travel or conflict logic
    (same venue means no travel between rooms).
  - `type` - one of `gig | film | exhibition | talk | workshop`. **`exhibition`**
    is a come-anytime drop-in: its `end_utc` is a real span, and consumers place a
    short visit inside it rather than blocking the whole span.
  - `start_utc` / `end_utc` - ISO-8601 UTC (`...Z`), canonical. `end_utc` is
    **null** for point events (no published duration); a real span for
    exhibitions/films.
  - `start_local` / `end_local` / `local_date` - human display only.
  - `verified` (bool), `notes`.

Consumers must treat `start_utc`/`end_utc` as canonical and tolerate null
`end_utc` (apply an assumed duration - see optimiser params).

`collection` semantics: events sharing a non-null `collection` are one strand.
Within a collection, instances with the **same `name`** are a *repeat* (the
identical thing again - a want can target the collection and let the optimiser
pick which instance); instances with **distinct names** are a *series/programme*
(picked individually). This repeat-vs-series split is derived, not stored.

## Contract B - wants

What the user wants to attend. Persisted by the service; consumed by conflict
view and optimiser. Shape:

```json
{
  "version": 1,
  "plan_name": "simon",
  "wants": [
    { "ref": "e042",             "kind": "event",      "weight": 3 },
    { "ref": "collection:reels", "kind": "collection", "weight": 2, "count": 1 }
  ]
}
```

- `ref` - an event `id`, or `collection:<key>` for a collection want.
- `kind` - `event` | `collection`.
- `weight` - integer priority, higher = wanted more. Default 1.
- `count` - for `collection` wants, how many instances to attend. Default 1.

This is the ONLY thing the UI track and the optimiser track share at runtime.
Pin it now; both tracks code against it.

## Contract C - travel

A pure function `travel(zoneA, zoneB) -> minutes` backed by a small symmetric
zone-to-zone matrix (zones come from Contract A's venues). Produced by loop-04,
consumed by conflict view (feasibility) and optimiser. Same-zone defaults to a
small in-cluster walk; North Pier and Pleasure Beach are the costly outliers.

## Optimiser parameters (config, not a contract)

Not interfaces between loops - just tunables the optimiser owns:

- `default_set_minutes` - assumed length of a point set with null `end_utc`.
- `visit_minutes` - assumed length of a drop-in visit inside a window.
- relative penalties for travel and for missing a wanted event.
