"""Delivering the magic link over a pluggable channel.

The app depends only on the :class:`Notifier` protocol - one method, ``send`` -
so a new channel is one small class and a config switch; nothing else changes.
Channels share nothing but the protocol:

- :class:`ConsoleNotifier` - dev default, logs the link. No setup, used in tests.
- :class:`SignalSender`    - POST to a signal-cli-rest-api instance (on-brand).
- :class:`EmailSender`     - SMTP+STARTTLS (e.g. Gmail app password).

Future channels (WhatsApp, Telegram, …) slot in the same way. Note the *handle*
differs per channel (Signal/WhatsApp identify by phone number, email by address);
that choice lives with the routes, not here.
"""

from __future__ import annotations

import json
import logging
import os
import smtplib
import ssl
import urllib.request
from email.message import EmailMessage
from typing import Protocol

log = logging.getLogger("festers.notify")

_SUBJECT = "Your festers link"


class Notifier(Protocol):
    def send(self, recipient: str, message: str) -> None: ...


class ConsoleNotifier:
    """Dev/default: log the message instead of delivering it. The link is printed
    so you can click it straight from the logs. Never touches the network."""

    def send(self, recipient: str, message: str) -> None:
        log.warning("NOTIFY (console, not sent) to=%s", recipient)
        print(f"\n--- magic link ({recipient}) ---\n{message}\n---\n")


def _http_post_json(url: str, payload: dict, timeout: int = 15) -> None:
    """POST JSON with the stdlib (no HTTP-client dependency). Raises on error."""
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (trusted local URL)
        if resp.status >= 300:
            raise RuntimeError(f"notify POST {url} -> {resp.status}")


class SignalSender:
    """Send via signal-cli-rest-api (``POST /v2/send``). ``sender`` is the bot's
    registered E.164 number; ``recipient`` may be a number or a username."""

    def __init__(self, base_url: str, sender: str):
        self._url = base_url.rstrip("/") + "/v2/send"
        self._sender = sender

    def send(self, recipient: str, message: str) -> None:
        _http_post_json(self._url, {
            "message": message,
            "number": self._sender,
            "recipients": [recipient],
        })


class EmailSender:
    """Real email over SMTP+STARTTLS."""

    def __init__(self, host: str, port: int, username: str, password: str, sender: str):
        self._host, self._port = host, port
        self._username, self._password = username, password
        self._sender = sender

    def send(self, recipient: str, message: str) -> None:
        msg = EmailMessage()
        msg["From"] = self._sender
        msg["To"] = recipient
        msg["Subject"] = _SUBJECT
        msg.set_content(message)
        with smtplib.SMTP(self._host, self._port, timeout=15) as s:
            s.starttls(context=ssl.create_default_context())
            s.login(self._username, self._password)
            s.send_message(msg)


def make_notifier() -> Notifier:
    """Pick the channel from ``FESTERS_NOTIFIER`` (signal | smtp | console)."""
    kind = os.environ.get("FESTERS_NOTIFIER", "console").lower()
    if kind == "signal":
        return SignalSender(
            base_url=os.environ["FESTERS_SIGNAL_URL"],
            sender=os.environ["FESTERS_SIGNAL_FROM"],  # E.164, e.g. +447700900123
        )
    if kind in ("smtp", "email"):
        user = os.environ["FESTERS_SMTP_USER"]
        return EmailSender(
            host=os.environ["FESTERS_SMTP_HOST"],
            port=int(os.environ.get("FESTERS_SMTP_PORT", "587")),
            username=user,
            password=os.environ["FESTERS_SMTP_PASS"],
            sender=os.environ.get("FESTERS_SMTP_FROM", user),
        )
    return ConsoleNotifier()
