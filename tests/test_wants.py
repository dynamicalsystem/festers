from __future__ import annotations

import pytest

from festers.wants import (
    Want,
    Wants,
    load_wants,
    save_wants,
    validate_plan_name,
    wants_path,
)


def test_roundtrip_persistence(tmp_path):
    w = Wants(
        plan_name="simon",
        wants=[
            Want(ref="e042", kind="event", weight=3),
            Want(ref="collection:reels", kind="collection", weight=2, count=1),
        ],
    )
    save_wants(w, base_dir=tmp_path)
    loaded = load_wants("simon", base_dir=tmp_path)
    assert loaded == w
    assert loaded.refs() == {"e042", "collection:reels"}


def test_missing_plan_returns_empty(tmp_path):
    w = load_wants("nobody", base_dir=tmp_path)
    assert w.plan_name == "nobody"
    assert w.wants == []


def test_defaults():
    w = Want(ref="e1", kind="event")
    assert w.weight == 1 and w.count == 1


@pytest.mark.parametrize("bad", ["../etc/passwd", "Simon", "a/b", "", "x" * 65, "-leading"])
def test_plan_name_rejects_unsafe(bad):
    with pytest.raises(ValueError):
        validate_plan_name(bad)


@pytest.mark.parametrize("good", ["simon", "plan-1", "a", "team_b2"])
def test_plan_name_accepts_safe(good):
    assert validate_plan_name(good) == good


def test_wants_path_within_base(tmp_path):
    assert wants_path("simon", tmp_path) == tmp_path / "simon.json"
