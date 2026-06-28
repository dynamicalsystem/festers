"""Contract A behaviour + a verification pass over the real schedule.json.

This doubles as part of loop-01's outstanding 'verify the data' test: counts and
structural invariants over the committed schedule.
"""

from __future__ import annotations

from datetime import timezone

import pytest
from pydantic import ValidationError

from festers.schedule import Event, Schedule, load_schedule


def test_real_schedule_loads_and_counts(real_schedule: Schedule):
    assert real_schedule.festival.name == "The Black Lights"
    assert len(real_schedule.venues) == 15
    assert len(real_schedule.events) == 91


def test_real_schedule_all_times_are_utc(real_schedule: Schedule):
    for e in real_schedule.events:
        assert e.start_utc.tzinfo == timezone.utc
        if e.end_utc is not None:
            assert e.end_utc.tzinfo == timezone.utc


def test_real_schedule_every_event_venue_exists(real_schedule: Schedule):
    codes = {v.code for v in real_schedule.venues}
    for e in real_schedule.events:
        assert e.venue in codes, f"{e.id} references unknown venue {e.venue}"


def test_real_schedule_ids_unique(real_schedule: Schedule):
    ids = [e.id for e in real_schedule.events]
    assert len(ids) == len(set(ids))


def test_real_schedule_end_after_start_when_present(real_schedule: Schedule):
    for e in real_schedule.events:
        if e.end_utc is not None:
            assert e.end_utc > e.start_utc, f"{e.id} ends before it starts"


def test_room_is_optional_and_defaults_none():
    e = Event(id="x", name="ok", venue="A1", type="gig",
              start_utc="2026-06-26T19:00:00+01:00")
    assert e.room is None


def test_real_schedule_rooms_distinguish_within_a_venue(real_schedule: Schedule):
    # The whole point: two Winter Gardens events in different rooms must be
    # tellable apart. Kali Malone is in the Opera House; Crown is in Olympia Hall.
    by_id = {e.id: e for e in real_schedule.events}
    assert by_id["e051"].venue == by_id["e054"].venue == "WG"
    assert by_id["e051"].room == "Opera House"
    assert by_id["e054"].room == "Olympia Hall"
    assert by_id["e051"].room != by_id["e054"].room


def test_real_schedule_room_is_absent_where_the_venue_has_one_space(real_schedule: Schedule):
    # Single-room venues carry no room; the field stays optional.
    assert real_schedule.event("e003").room is None  # North Pier


def test_real_schedule_pleasure_beach_name_prefix_hack_is_gone(real_schedule: Schedule):
    # Rooms used to be smuggled into the event name as a "[FLR..]" prefix.
    # That hack must be retired in favour of the room field.
    for e in real_schedule.events:
        assert not e.name.startswith("[FLR"), f"{e.id} still prefixes its name"
    pb = [e for e in real_schedule.events if e.venue == "PB"]
    assert pb and all(e.room for e in pb), "every Pleasure Beach event needs its floor"


def test_indexes(tiny_schedule: Schedule):
    assert tiny_schedule.event("e1").name == "Early Set"
    assert tiny_schedule.venue("A1").name == "Alpha Hall"
    assert tiny_schedule.zone_of("B1") == "south-seafront"
    assert tiny_schedule.zone_of_event(tiny_schedule.event("e3")) == "south-seafront"
    assert {e.id for e in tiny_schedule.events_in_collection("reels")} == {"e4", "e5"}
    assert tiny_schedule.zones == {"central", "south-seafront"}


def test_naive_datetime_rejected():
    with pytest.raises(ValidationError):
        Event(id="x", name="bad", venue="A1", type="gig",
              start_utc="2026-06-26T18:00:00")  # no offset -> naive -> rejected


def test_offset_normalised_to_utc():
    # +01:00 local should be stored as UTC.
    e = Event(id="x", name="ok", venue="A1", type="gig",
              start_utc="2026-06-26T19:00:00+01:00")
    assert e.start_utc.tzinfo == timezone.utc
    assert e.start_utc.hour == 18
