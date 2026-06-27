"""One-off migration: schedule.json v1 -> v2 (the reconciled, model-clean shape).

Reads the committed v1 file and emits v2 per docs/reconciliation.md:
- event = {name, venue, type, collection} + UTC/local times (his flat model)
- delete the 13 phantom `window` heading rows + the closing-ceremony heading
- recast the 8 real drop-ins as type=exhibition (keep their span)
- type vocab -> gig|film|exhibition|talk|workshop (dj/ceremony/fair folded)
- split `title` -> `name` (+ `collection` from the festival strand)
- apply the 7 transcription fixes + the grid/notes rulings (notes win, fair=11:00)
- add Sunday Manchester Soda; set film end-times from runtimes
- venues gain address + maps_url; everything verified:true

Run: uv run python scripts/migrate_v2.py   (writes data/schedule.json in place)
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "schedule.json"

BST = timezone(timedelta(hours=1))  # festival is fixed +01:00, no DST mid-event


def to_utc(local_date: str, hhmm: str | None, *, end_of=None) -> str | None:
    """UTC ISO string from a festival-local date + 'HH:MM'. For an end time that
    is earlier than its start (crosses midnight), roll the date forward a day."""
    if hhmm is None:
        return None
    y, mo, d = map(int, local_date.split("-"))
    h, m = map(int, hhmm.split(":"))
    base = datetime(y, mo, d, h, m, tzinfo=BST)
    if end_of is not None:
        sh, sm = map(int, end_of.split(":"))
        if (h, m) < (sh, sm):  # e.g. 23:00 -> 05:00
            base += timedelta(days=1)
    return base.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- venue enrichment (addresses from docs/venues.md; web-sourced where bold) ---
ADDR = {
    "NP": "North Promenade, FY1 1NE", "GG": "Queen Street, FY1 1PX",
    "CC": "30 Queen Street, FY1 1PU", "BH": "94 Talbot Road, FY1 1LR",
    "AV": "Ma Kelly's Station, 67 Talbot Road, FY1 2AA",
    "BS": "32-36 Topping Street, FY1 3AQ", "BT": "Promenade, FY1 4BJ",
    "WG": "97 Church Street, FY1 1HL", "IN": "Victoria Street, FY1 4HU",
    "HS": "Victoria Street, FY1 4HU", "GT": "33 Church Street, FY1 1HT",
    "RC": "181-189 Church Street, FY1 3NY", "SC": "71 Albert Road, FY1 4PW",
    "AH": "117 Albert Road, FY1 4PW", "PB": "525 Ocean Boulevard, FY4 1EZ",
}

COLLECTIONS = {
    "mfrt": "Mark Fell & Rian Treanor", "ivanseal": "Ivan Seal",
    "soda": "Manchester Soda", "reels": "Reels From The Abyss",
    "speedstrike": "Speed & Strike's Summer Holiday",
    "opening-ceremony": "Opening Ceremony", "closing-ceremony": "Closing Ceremony",
    "bow-down": "Bow Down",
}

DELETE = {"e002", "e005", "e010", "e014", "e018", "e032", "e036", "e038",
          "e050", "e053", "e060", "e077", "e089", "e097"}  # heading rows
EXHIBITION = {"e001", "e023", "e025", "e029", "e070", "e071", "e072", "e076"}
TYPE_OVERRIDE = {"e066": "gig"}  # named all-night club brand, not a drop-in
TYPE_MAP = {"set": "gig", "ceremony": "gig", "fair": "exhibition",
            "film": "film", "talk": "talk", "workshop": "workshop",
            "window": "exhibition"}
COLLECTION_ASSIGN = {
    "e006": "opening-ceremony", "e007": "opening-ceremony",
    "e008": "opening-ceremony", "e009": "opening-ceremony",
    "e048": "bow-down", "e049": "bow-down",
    "e098": "closing-ceremony", "e099": "closing-ceremony",
    "e100": "closing-ceremony", "e101": "closing-ceremony",
    "e102": "closing-ceremony", "e103": "closing-ceremony",
    "e104": "closing-ceremony",
}
# Final names (collection prefix stripped) for the strand members that don't get
# auto-stripped, plus the corrected MFRT session titles.
NAME_OVERRIDE = {
    "e026": "Cubulating The Void",
    "e027": "Five Key Benefits Of Temporal Involution",
    "e028": "Honey I Shrunk The Ambiguity",
    "e073": "Psychic Friendships (How & Why)",
    "e074": "The Transfinite Dayrider",
    "e075": "Non-Beings Of The Monodromy",
    "e072": "Nothing Is Explained, Everything Is Optional",  # de-conflate Soda
    "e048": "Bow Down",  # two showings of one show -> identical names => a repeat
    "e049": "Bow Down",
}
# (local_date, start_local, end_local) overrides for the time fixes.
TIME_OVERRIDE = {
    "e068": ("2026-06-28", "19:00", "20:34"),  # notes time + 1h34m runtime
    "e067": ("2026-06-28", "10:00", "14:26"),  # +4h26m
    "e069": ("2026-06-28", "20:45", "21:55"),  # +1h10m
    "e076": ("2026-06-28", "12:00", "19:00"),  # micro-pub, notes win
    "e072": ("2026-06-28", "11:00", "21:00"),  # Sun MFRT studio, notes win
    "e101": ("2026-06-29", "00:30", None),     # DJ Deathdef 00:20 -> 00:30
}


def collection_name(coll_key: str | None) -> str | None:
    return coll_key


def strip_prefix(title: str, coll_key: str | None) -> str:
    """If the title is 'Collection: Name', drop the strand prefix to get name."""
    if coll_key and coll_key in COLLECTIONS:
        disp = COLLECTIONS[coll_key]
        if title.startswith(disp + ":"):
            return title[len(disp) + 1:].strip()
    return title


def main() -> None:
    v1 = json.loads(SRC.read_text())
    old = {e["id"]: e for e in v1["events"]}

    # venues
    venues = []
    for v in v1["venues"]:
        addr = ADDR[v["code"]]
        venues.append({
            "code": v["code"], "name": v["name"], "zone": v["zone"],
            "address": addr,
            "maps_url": "https://maps.apple.com/?q=" + quote(f"{addr}, Blackpool, UK"),
        })

    events = []
    for eid, e in old.items():
        if eid in DELETE:
            continue
        coll = COLLECTION_ASSIGN.get(eid, e.get("group"))
        typ = (TYPE_OVERRIDE.get(eid)
               or ("exhibition" if eid in EXHIBITION else TYPE_MAP.get(e["type"], e["type"])))

        local_date, start_local, end_local = (
            TIME_OVERRIDE.get(eid)
            or (e["local_date"], e["start_local"], e.get("end_local"))
        )
        name = NAME_OVERRIDE.get(eid) or strip_prefix(e["title"], coll)

        events.append({
            "id": eid, "name": name, "venue": e["venue"], "type": typ,
            "collection": coll,
            "start_utc": to_utc(local_date, start_local),
            "end_utc": to_utc(local_date, end_local, end_of=start_local),
            "start_local": start_local, "end_local": end_local,
            "local_date": local_date, "verified": True,
            "notes": e.get("notes"),
        })

    # add Sunday Manchester Soda (was missing; notes: Sat & Sun)
    events.append({
        "id": "e105", "name": "Agentic Anxiety", "venue": "IN",
        "type": "exhibition", "collection": "soda",
        "start_utc": to_utc("2026-06-28", "11:00"),
        "end_utc": to_utc("2026-06-28", "18:00", end_of="11:00"),
        "start_local": "11:00", "end_local": "18:00", "local_date": "2026-06-28",
        "verified": True,
        "notes": "Drop-in; runs Saturday and Sunday (p8 notes).",
    })

    events.sort(key=lambda x: (x["start_utc"], x["id"]))

    fest = {"id": "blacklight", **v1["festival"]}
    fest["verified"] = True
    fest["schema"] = 2
    fest["notes"] = ("Reconciled against TBL-MAP-WEBSITE-001-02.pdf (see "
                     "docs/reconciliation.md). UTC canonical; *_local display-only.")

    out = {
        "festival": fest,
        "venues": venues,
        "collections": [{"key": k, "name": n} for k, n in COLLECTIONS.items()],
        "events": events,
    }
    SRC.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {len(events)} events, {len(venues)} venues, "
          f"{len(out['collections'])} collections")


if __name__ == "__main__":
    main()
