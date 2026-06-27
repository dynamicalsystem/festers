# festers

A small personal scheduler for **The Black Lights** festival (Blackpool,
26-28 June 2026): a music/film/art festival with many overlapping, repeated
events across ~15 venues.

You tell it which events you want to see. It builds an attendance plan that:

- minimises **conflict** (you cannot be in two places at once),
- minimises **travel** (venue-to-venue movement and missed opening windows),
- minimises **misses** (wanted events that do not fit),
- and **surfaces the choices** you have to make (where two wants collide, or a
  repeated event lets you pick a different instance).

Designed to run on our Oracle Cloud server.

## Status

Scaffold + first data capture. Today is 2026-06-24; the festival is this
coming weekend, so this is time-boxed.

- [x] Festival schedule transcribed from the source PDF into `data/schedule.json`
      (104 events, 15 venues) - **unverified**, see loop-01.
- [ ] Verify the transcription against the source.
- [ ] Define the optimisation model and pick / reject a stack.
- [ ] Build the picker + optimiser.

The stack is deliberately undecided (see `docs/design.md`).

## Layout

```
data/      structured festival data (schedule.json is the source of truth)
docs/      problem statement, data model, venue + travel notes
ooda/      OODA loops; each loop is a folder with a README (outcomes + tests)
```

## Source data

The festival timetable is published only as an image-only PDF
(`TBL-MAP-WEBSITE-001-02.pdf`). It has been transcribed by hand into
`data/schedule.json`. Times are stored as UTC instants (`start_utc`/`end_utc`,
canonical per house rule) plus the local wall-clock (`start_local`) for humans.
During the festival Blackpool is on BST (UTC+01:00).

A faithful human-readable transcript of the three day-schedules lives in
`docs/schedule-source.md`, and the venue legend in `docs/venues.md`.
