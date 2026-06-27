"""loop-06 - convergence: the optimiser behind the (token-gated) endpoint, and
the conflict view upgraded to travel-aware. End-to-end through the real app."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from festers.accounts import TokenStore, plan_id_for
from festers.params import OptimiserParams, event_interval
from festers.schedule import load_schedule
from festers.wants import Want, Wants, save_wants

PHONE = "+447000000000"


@pytest.fixture
def env(tmp_path, monkeypatch):
    (tmp_path / "plans").mkdir()
    (tmp_path / "auth").mkdir()
    monkeypatch.setenv("FESTERS_PLANS_DIR", str(tmp_path / "plans"))
    monkeypatch.setenv("FESTERS_AUTH_DIR", str(tmp_path / "auth"))
    monkeypatch.setenv("FESTERS_SECRET", "test-secret")
    return tmp_path


@pytest.fixture
def client(env):
    from festers.app import create_app

    return TestClient(create_app())


@pytest.fixture
def token(env):
    return TokenStore(env / "auth").mint(plan_id_for(PHONE, "blacklight"))


def _two_overlapping_event_ids():
    """A genuinely clashing pair of FIXED events (not drop-in exhibitions, which
    the optimiser places as short flexible visits). Derived, not hardcoded."""
    sch = load_schedule()
    params = OptimiserParams()
    fixed = [
        e for e in sorted(sch.events, key=lambda e: e.start_utc)
        if e.type != "exhibition" and event_interval(e, params).minutes <= 180
    ]
    for i, a in enumerate(fixed):
        ia = event_interval(a, params)
        for b in fixed[i + 1:]:
            ib = event_interval(b, params)
            if ib.start >= ia.end:
                break
            if ia.overlaps(ib):
                return a.id, b.id
    raise AssertionError("expected an overlapping pair of fixed events")


def test_optimise_empty_plan_renders(client, token):
    r = client.get(f"/p/{token}/optimise")
    assert r.status_code == 200
    assert "optimised plan" in r.text.lower()


def test_optimise_resolves_a_clash_and_explains(client, token, env):
    a_id, b_id = _two_overlapping_event_ids()
    save_wants(
        Wants(plan_name=plan_id_for(PHONE, "blacklight"), wants=[
            Want(ref=a_id, kind="event", weight=5),
            Want(ref=b_id, kind="event", weight=1),
        ]),
        base_dir=env / "plans",
    )
    r = client.get(f"/p/{token}/optimise")
    assert r.status_code == 200
    assert "Dropped" in r.text
    assert ("time clash" in r.text) or ("can&#39;t get there in time" in r.text) \
        or ("can't get there in time" in r.text)


def test_conflicts_view_is_travel_aware(client, token):
    r = client.get(f"/p/{token}/conflicts")
    assert r.status_code == 200
    assert "travel not yet modelled" not in r.text
    assert "loop-04" not in r.text
