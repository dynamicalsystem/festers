"""Email -> magic-link -> token access, storing no email addresses.

The user's email is NEVER persisted. A plan's id is a one-way HMAC fingerprint of
the (normalised) email, recomputed on each request - so the same email always maps
to the same plan ("one plan per email") without us holding the address. We persist
only ``token -> {plan_id, verified, created_at}``.

Each access request ROTATES the link: any existing tokens for that plan are
dropped and a fresh single-use-ish token is minted, so only the latest emailed
link is live. Possession of a token (delivered only by email) is the credential;
clicking it flips ``verified`` true (records that the inbox was reachable).

The HMAC key comes from ``FESTERS_SECRET``. In production it MUST be set to a
strong random value - otherwise plan ids are forgeable and email fingerprints are
brute-forceable. A loud dev default is used when unset.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("festers.accounts")

DEFAULT_AUTH_DIR = Path(__file__).resolve().parent.parent / "data" / "auth"

_DEV_SECRET = "dev-insecure-secret-change-me"
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\+[1-9]\d{6,14}$")  # E.164


def _secret() -> bytes:
    s = os.environ.get("FESTERS_SECRET")
    if not s:
        log.warning("FESTERS_SECRET not set - using an insecure dev default")
        s = _DEV_SECRET
    return s.encode()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email.strip()))


def normalize_phone(phone: str) -> str:
    """Best-effort E.164: strip spaces/dashes/parens; '00' prefix -> '+'."""
    p = re.sub(r"[\s\-()]", "", phone.strip())
    if p.startswith("00"):
        p = "+" + p[2:]
    return p


def is_valid_phone(phone: str) -> bool:
    return bool(_PHONE_RE.match(normalize_phone(phone)))


def plan_id_for(handle: str, festival_id: str) -> str:
    """One-way fingerprint of (festival, handle) -> the plan's stable id.

    Festival-scoped so the same person has a separate plan per festival (more
    festivals are coming). The caller normalises the handle first
    (:func:`normalize_phone` / :func:`normalize_email`) - phone and email
    normalise differently, so this stays handle-agnostic. Not reversible to the
    handle without ``FESTERS_SECRET``. The NUL separator keeps the two parts
    unambiguous (neither a festival slug nor a handle can contain it)."""
    key = f"{festival_id}\x00{handle.strip()}".encode()
    return hmac.new(_secret(), key, hashlib.sha256).hexdigest()


class TokenStore:
    """A tiny JSON-file store of ``token -> {plan_id, verified, created_at}``."""

    def __init__(self, base_dir: str | Path = DEFAULT_AUTH_DIR):
        self.base_dir = Path(base_dir)
        self.path = self.base_dir / "tokens.json"

    def _load(self) -> dict[str, dict]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, data: dict[str, dict]) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def mint(self, plan_id: str, festival_id: str) -> str:
        """Rotate: drop any existing tokens for this plan, mint and store a new
        one, and return it. So only the latest emailed link stays live.

        The token record carries its ``festival_id`` so the plan editor can map a
        token straight to its festival (the plan URL stays ``/p/<token>``, with no
        festival in the path)."""
        data = self._load()
        data = {t: rec for t, rec in data.items() if rec.get("plan_id") != plan_id}
        token = uuid.uuid4().hex
        data[token] = {
            "plan_id": plan_id,
            "festival_id": festival_id,
            "verified": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save(data)
        return token

    def resolve(self, token: str) -> str | None:
        """The plan id a token grants access to, or None if unknown."""
        rec = self._load().get(token)
        return rec["plan_id"] if rec else None

    def festival_of(self, token: str) -> str | None:
        """The festival id a token belongs to, or None if unknown/legacy.

        Tokens minted before festivals were namespaced have no ``festival_id``;
        they resolve to None and the editor treats the link as expired (re-mint)."""
        rec = self._load().get(token)
        return rec.get("festival_id") if rec else None

    def verify(self, token: str) -> str | None:
        """Mark a token verified (the link was clicked) and return its plan id."""
        data = self._load()
        rec = data.get(token)
        if not rec:
            return None
        if not rec.get("verified"):
            rec["verified"] = True
            self._save(data)
        return rec["plan_id"]

    def is_verified(self, token: str) -> bool:
        rec = self._load().get(token)
        return bool(rec and rec.get("verified"))


def magic_link(base_url: str, token: str) -> str:
    return f"{base_url.rstrip('/')}/p/{token}"
