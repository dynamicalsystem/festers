"""The festival registry: discovery, validation, ordering, lookup.

Registries are built from tiny on-disk fixtures written into a tmp dir so the
behaviour is independent of the real data; one test also loads the real
data/festivals tree to prove blacklight is discoverable as shipped.
"""

from __future__ import annotations

import json

import pytest

from festers.festivals import FestivalRegistry, load_registry


def _schedule_doc(fid: str, name: str, first_date: str) -> dict:
    """A minimal-but-valid schedule document for festival ``fid``."""
    return {
        "festival": {
            "id": fid,
            "name": name,
            "dates": [first_date],
            "timezone": "Europe/London",
            "utc_offset_during_festival": "+01:00",
        },
        "venues": [{"code": "A", "name": "Hall A", "zone": "central"}],
        "events": [],
        "travel": {"same_zone_minutes": 5, "pairs": []},
    }


def _write_festival(base, fid, name, first_date) -> None:
    d = base / fid
    d.mkdir(parents=True)
    (d / "schedule.json").write_text(
        json.dumps(_schedule_doc(fid, name, first_date)), encoding="utf-8"
    )


def test_discovers_and_keys_by_id(tmp_path):
    _write_festival(tmp_path, "alpha", "Alpha Fest", "2026-07-01")
    _write_festival(tmp_path, "beta", "Beta Fest", "2026-08-01")
    reg = load_registry(tmp_path)
    assert len(reg) == 2
    assert reg.get("alpha").festival.name == "Alpha Fest"
    assert reg.get("beta").festival.name == "Beta Fest"
    assert reg.get("missing") is None
    assert reg.get(None) is None


def test_all_is_ordered_by_first_date(tmp_path):
    _write_festival(tmp_path, "later", "Later", "2026-09-01")
    _write_festival(tmp_path, "earlier", "Earlier", "2026-06-01")
    reg = load_registry(tmp_path)
    assert reg.ids() == ["earlier", "later"]


def test_empty_dir_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        load_registry(tmp_path)


def test_duplicate_id_is_rejected(tmp_path):
    # Two dirs whose schedules declare the same festival id.
    _write_festival(tmp_path, "dir-one", "Dup", "2026-06-01")
    _write_festival(tmp_path, "dir-two", "Dup", "2026-06-01")
    # both declare id from _schedule_doc = their dir name, so make them collide:
    (tmp_path / "dir-two" / "schedule.json").write_text(
        json.dumps(_schedule_doc("dir-one", "Dup", "2026-06-01")), encoding="utf-8"
    )
    with pytest.raises(ValueError):
        load_registry(tmp_path)


def test_malformed_schedule_is_rejected(tmp_path):
    d = tmp_path / "broken"
    d.mkdir()
    (d / "schedule.json").write_text("{ not valid json", encoding="utf-8")
    with pytest.raises(Exception):
        load_registry(tmp_path)


def test_env_var_overrides_base_dir(tmp_path, monkeypatch):
    _write_festival(tmp_path, "alpha", "Alpha", "2026-07-01")
    monkeypatch.setenv("FESTERS_FESTIVALS_DIR", str(tmp_path))
    reg = load_registry()  # no arg -> reads the env var
    assert reg.ids() == ["alpha"]


def test_real_data_tree_contains_blacklight():
    reg = load_registry()  # the shipped data/festivals tree
    assert "blacklight" in reg
    assert reg.get("blacklight").festival.name == "The Black Lights"
