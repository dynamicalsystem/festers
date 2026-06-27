# Schedule reconciliation — PDF ↔ transcript ↔ schedule.json

**Method.** Read all 9 pages of `sources/TBL-MAP-WEBSITE-001-02.pdf` (image-only,
rendered at 5× and split top/bottom for legibility) end-to-end: the venue legend
(p2), the three day-grids (p3–5), and the four program-note pages (p6–9) which
carry the session-level detail. Cross-checked every one of the 104 events in
`data/schedule.json` against both the grid and the notes.

**Headline.** The bulk gig listings (Bootleg Social, Olympia Hall, Derham, the
club nights, the closing-ceremony floors) reconcile **cleanly** — names, times and
order all match. The errors cluster in exactly two places: (1) the curated
art-strand detail that came from the **notes** pages (MFRT sessions, films), where
the transcription mis-assigned several titles, and (2) **grid-vs-notes time
conflicts** that are genuine source ambiguities, not our mistakes. Plus the
structural finding we expected: the `window` rows are venue *headings*, confirmed
by the source, and should not be events.

The original transcription is `verified: false` for good reason — but it's ~90%
right; the issues below are specific and fixable.

---

## 1. Transcription errors — FIX (data is wrong vs the PDF)

| id | field | current | correct (per source) | evidence |
|----|-------|---------|----------------------|----------|
| **e026** | name | "Why Is There Something Rather Than Nothing?" | **"Cubulating The Void"** | p6: "Why Is There…" is the Saturday *day-theme*; the 12:00 session is "Cubulating The Void" |
| **e073** | name | "The Void" | **"Psychic Friendships (How & Why)"** | p6: Sunday 12:00 session; "The Void" was a mis-fragment |
| **e074** | name | "The Transfinite Daynder" *(flagged)* | **"The Transfinite Dayrider"** | p6: resolves the uncertain-title flag |
| **e068** | time | 13:00 | **19:00** | p8: notes say 19:00; and Histoire(s) (10:00 + 4h26m) runs to 14:26, so 13:00 is physically impossible in the same room |
| **e076** | start | 14:00 | **12:00** | p5 grid *and* p8 notes both start 12:00; loop-01 misread the grid as 14:00 |
| **e101** | time | 00:20 | **00:30** | p5: DJ Deathdef listed at 00.30 |
| **e054** | name | "Crown" | **"Croww" (?)** | p4: reads "CROWW" — low confidence, please eyeball |

Note: e068's title already embeds the runtime ("1h 34m"), so this one is
self-checking.

## 2. Source ambiguities — NEED YOUR RULING (the grid and notes disagree)

These are real inconsistencies *in the PDF*, so they can't be "fixed" — pick which
the data should follow.

| thing | grid (p3–5) | notes (p6–9) | our data | 
|-------|-------------|--------------|----------|
| **Record fair** (e071, Sun, WG Atrium) | 11:00–20:00 | 12:00–20:00 | 11:00 (grid) |
| **Micro-pub** (e076, Sun, Albert Pub) | 12:00–**17:00** | 12:00–**19:00** | 14:00–17:00 |
| **Sun Houndshill / MFRT** (e072) | 12:00–**21:00** | 11:00–21:00 | 12:00–**20:00** |
| **Speed & Strike "Man…Will"** (e068) | 13:00 | 19:00 | see §1 — 19:00 wins on duration logic |

My recommendation: **follow the notes** where they're more specific (they carry
the durations and the per-session detail), except keep the fair at the grid's
11:00 unless you know it opened at noon. Your call on each.

## 3. Missing from the data

| what | where | why missed |
|------|-------|-----------|
| **Manchester Soda — Sunday** | Info Hub, 11:00–18:00 | p8 notes: Soda runs "Saturday **& Sunday**"; we only have Saturday (e029). Add it → `soda` becomes a 2-day **repeat**. |
| **MDX** | WG Derham, Sun | p5: "(soundtracking)", no start time — dropped because timeless |
| **Conor Thomas** | Pleasure Beach FLR1, Sun | p5: "(soundtracking)", no start time — dropped because timeless |

The two "soundtracking" acts are *intentionally* absent under the current model
(no start time). Under the new model they'd be ambient/all-night entries on their
session — worth representing rather than dropping.

## 4. Structural — the `window` rows are headings, not events

The source confirms it: every venue is printed as a **heading with a bracketed
open-span**, then its acts beneath. So these 13 rows are room-open spans, not
attendable things — **delete**; the open-span is emergent from the acts (pivot
venue × time):

`e002, e005, e010, e014, e018, e032, e036, e038, e050, e053, e060, e077, e089`

Two headings double as collection names worth keeping: **e005** = the *Opening
Ceremony* (its acts e006–e009), **e097** = the *Closing Ceremony* (floors
e098–e104). Drop the heading row, attach the name as the acts' `collection`.

The **8 real drop-ins** keep their span and become `type: exhibition`:
`e001, e023, e025, e029(+Sun), e070, e071, e072, e076`. (`e066` "New Habitz Bad
World" is a *named club night* with no sub-acts → a single `gig`, not an
exhibition.)

## 5. Enrichments the source unlocks

- **Film end-times** (durations are in the notes/titles): Histoire(s) 10:00→14:26
  (4h26m); Man…Will 19:00→20:34 (1h34m); A Woman Kills 20:45→21:55 (1h10m). The
  Reels films give years but no runtimes.
- **Collection/work names** now available: Soda "Agentic Anxiety" (artists AUDINT,
  Christopher Gladwin, Lois Macdonald & Adam Cain, Michael England); the fair's
  work is **"Morphologies"** under *Bound × Impiety Hour*; Jack Sheen's piece is
  **"And Here To There"**; MFRT day-themes (*"Why Is There Something Rather Than
  Nothing?"* Sat, *"The Unordered Equivariant"* Sun).
- **Venue detail**: MFRT is at **Unit 65**, Houndshill. The Ivan Seal × Caretaker
  talk (e024) is at the Albert Hotel **Micro-pub**, Sat 16:30.
- **Addresses are NOT in the PDF** — the legend (p2) has names + a relative map
  only. The `address` attribute needs an external source (or we keep `zone`).

## 6. Original loop-01 DQ flags — resolved

| flag | verdict |
|------|---------|
| Record fair grid vs notes time | **Real source ambiguity** (11:00 vs 12:00) — §2, your call |
| Micro-pub grid vs notes | loop-01 misread grid as 14:00; truth is grid 12:00–17:00, notes 12:00–19:00 — §1 + §2 |
| Austin Philemon 19:15 before the 20:00 window | **Faithful** — the PDF really lists 19:15. Not an error. |
| "Transfinite Daynder" title uncertain | **Resolved → "The Transfinite Dayrider"** (§1) |
| MDX (Sun) no start time | **Faithful** — printed "(soundtracking)", no time (§3) |

---

## 7. Proposed Contract A reschema (for sign-off)

This is a frozen-interface change, so it's deliberate. The model is yours:
**event = {name, venue, time, type, collection}**.

```jsonc
// event
{
  "id": "e007",
  "name": "You Were There, Weren't You?",     // split from title
  "venue": "BT",                               // key into venues[]
  "type": "gig",                               // gig|film|exhibition|talk|workshop
  "collection": "the-caretaker",               // nullable; key into collections[]
  "start_utc": "2026-06-26T19:00:00Z",
  "end_utc": null,                             // real span ONLY for exhibitions/films
  "start_local": "20:00", "local_date": "2026-06-26",
  "verified": true
}
// venue: { code, name, address?, zone }       // address pending a source; zone kept for travel
// collection: { key, name, kind: "repeat" | "programme" }   // kind DERIVED, not authored
```

Changes from today:
- **Delete** the 13 heading `window` rows (§4); room-open spans become emergent.
- **`type`** → `gig | film | exhibition | talk | workshop` ( `set`→gig, `fair`→
  exhibition, `ceremony`→gig+collection, `window`→ gone / exhibition).
- **Split** `title` into `name` + `collection` (the `Collection: Name` colon).
- **`collection`** promoted to a first-class list with display names; `kind`
  (repeat vs programme) is *derived* from name-identity, not stored.
- **Drop-in = `type: exhibition`** with a true start–end span; no duration
  heuristic, retiring the optimiser's 3h guess and the picker's substitutable
  guess (both become data-driven).

### Decisions needed from you
1. **Each §2 ambiguity** — grid or notes? (my rec: notes, except fair = 11:00).
2. **`address`** — source them separately, or keep `zone` as the location attr?
3. **`type` vocabulary** — is `gig | film | exhibition | talk | workshop` the full
   set, or do you want others (e.g. `ceremony`, `dj`, `performance`)?
4. **The two soundtracking acts** (MDX, Conor Thomas) — represent as timeless
   ambient entries, or leave out?
