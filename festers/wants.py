"""Contract B - what the user wants to attend, and its persistence.

This is the ONLY runtime interface shared between the UI track and the optimiser
track, so the shape here is frozen (see ``docs/contracts.md``). Persistence is a
JSON file per ``plan_name`` under a base directory - human-inspectable, no DB.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

DEFAULT_PLANS_DIR = Path(__file__).resolve().parent.parent / "data" / "plans"

# plan_name becomes a filename; constrain it to a safe slug to prevent path
# traversal and collisions. Anything outside this set is rejected, not munged.
_PLAN_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class Want(BaseModel):
    ref: str  # an event id ("e042") or "collection:<key>"
    kind: Literal["event", "collection"]
    weight: int = 1
    count: int = 1  # for collection wants: how many instances to attend


class Wants(BaseModel):
    version: int = 1
    plan_name: str
    wants: list[Want] = Field(default_factory=list)

    def refs(self) -> set[str]:
        return {w.ref for w in self.wants}


def validate_plan_name(plan_name: str) -> str:
    if not _PLAN_NAME_RE.match(plan_name):
        raise ValueError(
            f"invalid plan_name {plan_name!r}: must be lowercase "
            "alphanumeric/_/- and start alphanumeric"
        )
    return plan_name


def wants_path(plan_name: str, base_dir: str | Path = DEFAULT_PLANS_DIR) -> Path:
    return Path(base_dir) / f"{validate_plan_name(plan_name)}.json"


def load_wants(plan_name: str, base_dir: str | Path = DEFAULT_PLANS_DIR) -> Wants:
    """Load a plan's wants, or an empty plan if it does not exist yet."""
    path = wants_path(plan_name, base_dir)
    if not path.exists():
        return Wants(plan_name=plan_name)
    return Wants.model_validate_json(path.read_text(encoding="utf-8"))


def save_wants(wants: Wants, base_dir: str | Path = DEFAULT_PLANS_DIR) -> Path:
    """Persist wants atomically (write-temp-then-rename)."""
    path = wants_path(wants.plan_name, base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(wants.model_dump_json(indent=2), encoding="utf-8")
    tmp.replace(path)
    return path
