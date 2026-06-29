"""Magic-link account/token core (no email stored, one plan per email)."""

from __future__ import annotations

import pytest

from festers.accounts import (
    TokenStore,
    is_valid_email,
    is_valid_phone,
    magic_link,
    normalize_email,
    normalize_phone,
    plan_id_for,
)


@pytest.mark.parametrize("raw,norm", [
    ("+44 7700 900123", "+447700900123"),
    ("+44-7700-900123", "+447700900123"),
    ("00447700900123", "+447700900123"),
])
def test_phone_normalisation(raw, norm):
    assert normalize_phone(raw) == norm


@pytest.mark.parametrize("good", ["+447700900123", "+15551234567"])
def test_phone_validation_accepts(good):
    assert is_valid_phone(good)


@pytest.mark.parametrize("bad", ["07700900123", "+0123", "notaphone", "+4407700900123" * 2])
def test_phone_validation_rejects(bad):
    assert not is_valid_phone(bad)


def test_same_normalised_handle_same_plan_id(monkeypatch):
    monkeypatch.setenv("FESTERS_SECRET", "test-secret")
    # caller normalises (here via normalize_email) -> one plan per (festival, handle)
    a = plan_id_for(normalize_email("Simon@Horrobin.net"), "blacklight")
    b = plan_id_for(normalize_email("  simon@horrobin.net "), "blacklight")
    assert a == b
    assert len(a) == 64 and all(c in "0123456789abcdef" for c in a)


def test_festival_scopes_the_plan_id(monkeypatch):
    monkeypatch.setenv("FESTERS_SECRET", "k")
    h = "+447700900123"
    assert plan_id_for(h, "blacklight") != plan_id_for(h, "otherfest")


def test_plan_id_is_not_the_handle_and_depends_on_secret(monkeypatch):
    monkeypatch.setenv("FESTERS_SECRET", "secret-one")
    one = plan_id_for("a@b.com", "blacklight")
    monkeypatch.setenv("FESTERS_SECRET", "secret-two")
    two = plan_id_for("a@b.com", "blacklight")
    assert "a@b.com" not in one
    assert one != two  # fingerprint is keyed by the server secret


def test_different_handles_differ(monkeypatch):
    monkeypatch.setenv("FESTERS_SECRET", "k")
    assert plan_id_for("x@y.com", "f") != plan_id_for("z@y.com", "f")


@pytest.mark.parametrize("good", ["a@b.com", "simon.horrobin@example.co.uk"])
def test_email_validation_accepts(good):
    assert is_valid_email(good)


@pytest.mark.parametrize("bad", ["", "nope", "a@b", "a b@c.com", "@b.com"])
def test_email_validation_rejects(bad):
    assert not is_valid_email(bad)


def test_mint_resolve_verify_roundtrip(tmp_path):
    store = TokenStore(tmp_path)
    pid = "plan123"
    token = store.mint(pid, "blacklight")
    assert store.resolve(token) == pid
    assert store.festival_of(token) == "blacklight"  # token carries its festival
    assert store.is_verified(token) is False
    assert store.verify(token) == pid
    assert store.is_verified(token) is True


def test_mint_rotates_old_tokens_for_same_plan(tmp_path):
    store = TokenStore(tmp_path)
    pid = "planX"
    t1 = store.mint(pid, "blacklight")
    t2 = store.mint(pid, "blacklight")  # rotation: t1 should die
    assert t1 != t2
    assert store.resolve(t1) is None
    assert store.resolve(t2) == pid


def test_mint_does_not_touch_other_plans(tmp_path):
    store = TokenStore(tmp_path)
    ta = store.mint("planA", "blacklight")
    tb = store.mint("planB", "blacklight")
    store.mint("planA", "blacklight")  # rotating A must not drop B
    assert store.resolve(tb) == "planB"


def test_resolve_unknown_token_is_none(tmp_path):
    assert TokenStore(tmp_path).resolve("nope") is None
    assert TokenStore(tmp_path).festival_of("nope") is None


def test_magic_link_format():
    assert magic_link("https://x.example/", "abc") == "https://x.example/p/abc"
