# venues

Fifteen venues from the festival map (page 1 of the source PDF). Codes are our
own short codes used in `data/schedule.json` (the PDF uses slightly different
glyphs, e.g. a tower icon for Blackpool Tower and `+`-prefixed crosses for
churches/landmarks).

| code | venue                        | rough zone        | address (FY postcode) |
|------|------------------------------|-------------------|------------------------|
| NP   | North Pier                   | north seafront    | North Promenade, FY1 1NE *(landmark)* |
| GG   | Grundy Art Gallery           | central           | Queen Street, FY1 1PX *(landmark)* |
| CC   | Blackpool Catholic Club      | central-east      | **30 Queen Street, FY1 1PU** |
| BH   | Bad Habitz                   | central-east      | **94 Talbot Road, FY1 1LR** |
| AV   | The Avenue                   | central-east      | **Ma Kelly's Station, 67 Talbot Road, FY1 2AA** |
| BS   | Bootleg Social               | central-east      | **32–36 Topping Street, FY1 3AQ** |
| BT   | Blackpool Tower              | central seafront  | Promenade, FY1 4BJ *(landmark)* |
| WG   | Winter Gardens               | central           | 97 Church Street, FY1 1HL *(landmark)* |
| IN   | Info Hub (Houndshill)        | central           | inside Houndshill (use HS) |
| HS   | Houndshill Shopping Centre   | central           | Victoria Street, FY1 4HU *(landmark)* |
| GT   | The Grand Theatre            | central           | 33 Church Street, FY1 1HT *(landmark)* |
| RC   | The Regent Cinema            | central           | **181–189 Church Street, FY1 3NY** |
| SC   | Blackpool Spiritualist Church| central-south     | **71 Albert Road, FY1 4PW** |
| AH   | The Albert Hotel             | central-south     | **117 Albert Road, FY1 4PW** |
| PB   | The Pleasure Beach           | south seafront    | 525 Ocean Boulevard, FY4 1EZ *(landmark)* |

**Bold** addresses were web-sourced (June 2026) for the venues whose names don't
geocode cleanly; *(landmark)* addresses are the well-known sites (name-search
resolves, address listed for completeness). Each venue will carry a `maps_url`
(`https://maps.apple.com/?q=<address>`) so people can tap through to navigate.

## Rooms within a venue

Some venues are a single building with several performance spaces, and the source
PDF lists which room each event is in. Getting to the right building but the wrong
room is a real way to miss something, so the room rides on each **event** as an
optional `room` field (see Contract A) - not as a venue sub-structure. Venues with
rooms in the data:

- **Winter Gardens (WG)** - Opera House, Olympia Hall, Olympia Hall Balcony,
  Derham Lounge, Atrium.
- **Blackpool Tower (BT)** - Ballroom (early) and 5th Floor (late).
- **The Pleasure Beach (PB)** - FLR 1 / Paradise, FLR 2 / Horseshoe,
  FLR 3 / The White Tower (the closing ceremony runs across all three).
- **The Grand Theatre (GT)** - Studio. **The Albert Hotel (AH)** - Pub.

Single-room venues simply omit the field. Rooms are a display/wayfinding cue; they
do not affect travel (no walking between rooms of one building).

## Geography (from the map, approximate)

The map is a single promenade axis running north-south along the seafront:

- **North Pier (NP)** sits at the north end, a short way up the promenade on
  its own spur.
- The dense **central cluster** is everything around the Winter Gardens /
  Blackpool Tower / Houndshill: WG, IN, HS, GT, RC, BT, plus GG, CC, BH, AV, BS
  just to the east, and SC, AH just to the south. Most of the festival is here
  and these are all within a few minutes' walk of each other.
- **The Pleasure Beach (PB)** is far south, at the bottom of the axis - this is
  the one venue that is a real journey (tram down the promenade). The closing
  ceremony is here on Sunday night.

## Travel notes (TODO - not yet quantified)

The optimiser needs venue-to-venue travel times. We do not have these yet.
Options, cheapest first:

1. Hand-assign a small zone-to-zone walking-minutes matrix (central cluster
   ~0-8 min walk; NP and PB are the outliers). Good enough for a first cut and
   needs no dependencies.
2. Geocode venues and compute walking distances (adds a dependency / API).

Recommend (1) for the first build. Captured as a task in loop-01 / the design.
