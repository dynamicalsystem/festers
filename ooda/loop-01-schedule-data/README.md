# loop-01: festival schedule as structured data

Status: **in review** - transcription complete, verification pending.

## Observe

The Black Lights timetable is published only as an image-only 9-page PDF
(`TBL-MAP-WEBSITE-001-02.pdf`): a cover, a venue map/legend, three day-schedule
pages, and program notes. No text layer, so it cannot be parsed - it has to be
read and transcribed.

## Orient

Everything downstream (travel model, optimiser, UI) depends on trustworthy
schedule data. This is the foundational dependency, so it is the first loop.
Re-reading the image PDF is expensive, so capture once, carefully, and verify.

Decisions taken:
- Store both UTC (canonical, per house rule) and local clock time. UTC-canonical
  confirmed by Simon (2026-06-24) - see resolved decision in `docs/design.md`;
  `*_local` is display-only and consumers must not trust the device timezone.
- Point performances have no published end time; `end_utc` left null rather than
  guessed. A default set length will be a parameter of the optimiser, not data.

## Decide

Produce `data/schedule.json` (machine) + `docs/schedule-source.md` (faithful
human transcript) + `docs/venues.md` (legend/geography). Generation done by a
script so UTC conversion and midnight rollover are mechanical, not hand-typed.

## Act

- [x] Decode all 9 PDF pages to images and read them.
- [x] Transcribe venues (15) and all events (104) to `data/schedule.json`.
- [x] Write the human transcript and venue notes.
- [x] Handle after-midnight window rollovers in UTC conversion.
- [ ] **Verify** `schedule.json` against the source PDF end to end.
- [ ] Resolve or confirm the data-quality flags (see below).

## Outcomes

1. A downstream loop (travel/optimiser) can consume the schedule without ever
   touching the PDF again.
2. Times in the data are correct to the minute in both local and UTC.

## Tests

- [ ] Every event in `docs/schedule-source.md` appears in `schedule.json` and
      vice versa (count + spot-check by day/venue).
- [ ] For a sample across all three days, `start_local` re-derived from
      `start_utc` at +01:00 matches the printed PDF time.
- [ ] All midnight-crossing windows (e.g. 23:59-04:00) have `end_utc` on the
      following calendar day. (Checked once during generation; re-confirm.)
- [ ] `verified` flags flip to true only after a human has checked against source.

## Data-quality flags to resolve

- Record fair (Sun): grid 11:00-20:00 vs notes 12:00-20:00.
- Micro-pub (Sun): grid 14:00-17:00 vs notes window 12:00-19:00.
- Austin Philemon (Fri) 19:15 sits before the 20:00 ballroom window.
- "The Transfinite Daynder" (Sun MFRT session) - title uncertain from the image.
- MDX (Sun, Derham) has no printed start time.

## Notes

- Source PDF cached at the session tool-results path; re-fetchable from the
  festival site if needed.
- Render pipeline used: PyMuPDF at 4x to PNG (Ghostscript/poppler absent on this
  Mac; `sips` only does page 1). Kept in scratchpad, not committed.
