"""Service + picker + conflict view via the magic-link flow.

A captured FakeNotifier stands in for Signal/email; tmp dirs for plans and the
token store (injected via env) keep tests isolated. No phone number is stored;
identity is the HMAC fingerprint, access is the messaged token.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from festers.accounts import TokenStore, plan_id_for
from festers.wants import Wants, load_wants, save_wants

PHONE = "+447000000000"


class FakeNotifier:
    def __init__(self):
        self.sent: list[tuple[str, str]] = []

    def send(self, recipient: str, message: str) -> None:
        self.sent.append((recipient, message))


@pytest.fixture
def env(tmp_path, monkeypatch):
    (tmp_path / "plans").mkdir()
    (tmp_path / "auth").mkdir()
    monkeypatch.setenv("FESTERS_PLANS_DIR", str(tmp_path / "plans"))
    monkeypatch.setenv("FESTERS_AUTH_DIR", str(tmp_path / "auth"))
    monkeypatch.setenv("FESTERS_SECRET", "test-secret")
    return tmp_path


@pytest.fixture
def notifier():
    return FakeNotifier()


@pytest.fixture
def client(env, notifier):
    from festers.app import create_app

    return TestClient(create_app(notifier=notifier))


@pytest.fixture
def plan_id():
    return plan_id_for(PHONE, "blacklight")


@pytest.fixture
def token(env):
    """A live token for PHONE's plan (as if the link had been requested)."""
    return TokenStore(env / "auth").mint(plan_id_for(PHONE, "blacklight"))


# --------------------------------------------------------------------------- #
# Public surface (no auth)
# --------------------------------------------------------------------------- #


def test_schedule_json_endpoint(client):
    body = client.get("/api/schedule").json()
    assert len(body["events"]) == 91
    assert len(body["venues"]) == 15


def test_public_browse_lists_all_events_without_checkboxes(client):
    from festers.schedule import load_schedule

    html = client.get("/").text
    missing = [e.id for e in load_schedule().events if e.id not in html]
    assert missing == []
    assert 'type="checkbox"' not in html  # can't edit without a link


def test_browse_shows_room_within_a_venue(client):
    # So you know which Winter Gardens room to walk into, not just the building.
    html = client.get("/").text
    assert "Opera House" in html
    assert "Olympia Hall" in html
    assert "[FLR" not in html  # the old name-prefix hack is gone


def test_optimise_plan_shows_the_room(client, token):
    # Want a roomed event; the plan must name the room next to the venue.
    client.post(f"/p/{token}/toggle", data={"ref": "e051", "kind": "event"})  # Kali Malone, Opera House
    html = client.get(f"/p/{token}/optimise").text
    assert "Opera House" in html


def test_browse_shows_three_festival_days(client):
    html = client.get("/").text
    for label in ("2026-06-26", "2026-06-27", "2026-06-28"):
        assert label in html
    assert "2026-06-29" not in html  # folded onto Sunday


# --------------------------------------------------------------------------- #
# Magic-link request
# --------------------------------------------------------------------------- #


def test_request_link_sends_a_link_and_mints_a_token(client, notifier, env):
    resp = client.post("/request-link", data={"phone": PHONE})
    assert resp.status_code == 200
    assert "check your messages" in resp.text.lower()
    assert len(notifier.sent) == 1
    recipient, message = notifier.sent[0]
    assert recipient == PHONE
    m = re.search(r"/p/([0-9a-f]+)", message)
    assert m, "message should contain a /p/<token> link"
    assert TokenStore(env / "auth").resolve(m.group(1)) == plan_id_for(PHONE, "blacklight")


def test_request_link_rejects_a_bad_number(client, notifier):
    resp = client.post("/request-link", data={"phone": "not-a-phone"})
    assert resp.status_code == 400
    assert notifier.sent == []


def test_request_link_is_rate_limited_per_ip(client, notifier):
    first = client.post("/request-link", data={"phone": PHONE})
    second = client.post("/request-link", data={"phone": "+447111222333"})
    assert first.status_code == 200
    assert second.status_code == 429
    assert len(notifier.sent) == 1  # the throttled one never sent


def test_request_link_does_not_reveal_validity(client, notifier):
    r = client.post("/request-link", data={"phone": "+15551234567"})
    assert "if that number" in r.text.lower()


# --------------------------------------------------------------------------- #
# Token-gated editor
# --------------------------------------------------------------------------- #


def test_editor_opens_with_a_valid_token(client, token):
    html = client.get(f"/p/{token}").text
    assert 'type="checkbox"' in html
    assert "your plan" in html.lower()


def test_invalid_token_shows_link_invalid_404(client):
    resp = client.get("/p/deadbeef")
    assert resp.status_code == 404
    assert "isn't valid" in resp.text


def test_toggle_persists_for_the_token_plan(client, token, env, plan_id):
    client.post(f"/p/{token}/toggle", data={"ref": "e042", "kind": "event"})
    assert "e042" in load_wants(plan_id, base_dir=env / "plans").refs()


def test_toggle_fetch_returns_204(client, token):
    resp = client.post(
        f"/p/{token}/toggle",
        data={"ref": "e042", "kind": "event"},
        headers={"X-Requested-With": "fetch"},
        follow_redirects=False,
    )
    assert resp.status_code == 204


def test_toggle_nojs_redirects_back_to_the_plan(client, token):
    resp = client.post(
        f"/p/{token}/toggle?next=/p/{token}",
        data={"ref": "e042", "kind": "event"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/p/{token}"


def test_toggle_on_an_invalid_token_404s(client):
    resp = client.post("/p/nope/toggle", data={"ref": "e042", "kind": "event"})
    assert resp.status_code == 404


def test_toggle_unknown_ref_rejected(client, token):
    resp = client.post(f"/p/{token}/toggle", data={"ref": "e999", "kind": "event"})
    assert resp.status_code == 400


def test_repeats_panel_distinguishes_repeat_from_series(client, token):
    html = client.get(f"/p/{token}").text
    assert "Repeated experiences" in html
    assert 'value="collection:ivanseal"' in html   # repeat -> 'want any one'
    assert 'value="collection:reels"' not in html   # series -> picked individually


def test_collection_toggle_persists(client, token, env, plan_id):
    client.post(
        f"/p/{token}/toggle",
        data={"ref": "collection:ivanseal", "kind": "collection"},
        headers={"X-Requested-With": "fetch"},
    )
    w = load_wants(plan_id, base_dir=env / "plans")
    assert any(x.ref == "collection:ivanseal" and x.kind == "collection" for x in w.wants)


# --------------------------------------------------------------------------- #
# Conflict + optimise views (token-gated)
# --------------------------------------------------------------------------- #


def test_conflicts_view_is_travel_aware(client, token):
    html = client.get(f"/p/{token}/conflicts").text
    assert "travel not yet modelled" not in html


def test_optimise_view_renders(client, token):
    resp = client.get(f"/p/{token}/optimise")
    assert resp.status_code == 200
    assert "optimised plan" in resp.text.lower()


def test_gated_views_404_on_bad_token(client):
    assert client.get("/p/x/conflicts").status_code == 404
    assert client.get("/p/x/optimise").status_code == 404
