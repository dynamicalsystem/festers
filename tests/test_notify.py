"""Pluggable notifier channels."""

from __future__ import annotations

import pytest

import festers.notify as notify
from festers.notify import (
    ConsoleNotifier,
    EmailSender,
    SignalSender,
    make_notifier,
)


def test_console_notifier_prints(capsys):
    ConsoleNotifier().send("+447700900123", "click https://x/p/abc")
    out = capsys.readouterr().out
    assert "+447700900123" in out and "https://x/p/abc" in out


def test_signal_sender_posts_v2_send_payload(monkeypatch):
    captured = {}

    def fake_post(url, payload, timeout=15):
        captured["url"] = url
        captured["payload"] = payload

    monkeypatch.setattr(notify, "_http_post_json", fake_post)
    SignalSender("http://localhost:8010/", "+447700900123").send("+447900111222", "hello")

    assert captured["url"] == "http://localhost:8010/v2/send"
    assert captured["payload"] == {
        "message": "hello",
        "number": "+447700900123",       # bot sends FROM its registered number
        "recipients": ["+447900111222"],
    }


def test_make_notifier_defaults_to_console(monkeypatch):
    monkeypatch.delenv("FESTERS_NOTIFIER", raising=False)
    assert isinstance(make_notifier(), ConsoleNotifier)


def test_make_notifier_selects_signal(monkeypatch):
    monkeypatch.setenv("FESTERS_NOTIFIER", "signal")
    monkeypatch.setenv("FESTERS_SIGNAL_URL", "http://localhost:8010")
    monkeypatch.setenv("FESTERS_SIGNAL_FROM", "+447700900123")
    n = make_notifier()
    assert isinstance(n, SignalSender)


def test_make_notifier_selects_smtp(monkeypatch):
    monkeypatch.setenv("FESTERS_NOTIFIER", "smtp")
    monkeypatch.setenv("FESTERS_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("FESTERS_SMTP_USER", "bot@example.com")
    monkeypatch.setenv("FESTERS_SMTP_PASS", "secret")
    assert isinstance(make_notifier(), EmailSender)
