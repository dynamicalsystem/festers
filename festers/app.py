"""Loop-02/03 - the FastAPI service: browse, pick (persist wants), see conflicts.

Thin web layer over the frozen contracts. All real logic lives in pure,
separately-tested functions (``schedule``, ``wants``, ``conflicts``, ``params``);
handlers just marshal HTTP <-> those. The schedule is loaded and validated once
at app construction (fail fast on a bad file).

Plans base dir is injectable via the ``FESTERS_PLANS_DIR`` env var so tests
write into a tmp dir instead of ``data/plans`` (read at create_app time).
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from festers.accounts import (
    TokenStore,
    is_valid_phone,
    magic_link,
    normalize_phone,
    plan_id_for,
)
from festers.conflicts import find_conflicts, session_day
from festers.festivals import FestivalRegistry, load_registry
from festers.notify import Notifier, make_notifier
from festers.optimiser import plan as build_plan
from festers.params import OptimiserParams
from festers.schedule import Event, Schedule
from festers.travel import make_travel
from festers.wants import Want, Wants, load_wants, save_wants

log = logging.getLogger("festers.app")

# Human-readable labels for each drop reason (loop-06 plan view).
_DROP_LABELS = {
    "clash": "time clash",
    "travel": "can't get there in time",
    "unresolved": "no matching event",
    "shortfall": "fewer instances available than wanted",
}

_HERE = Path(__file__).resolve().parent
_TEMPLATES_DIR = _HERE / "templates"
_STATIC_DIR = _HERE / "static"

def _day_label(date_str: str) -> str:
    """Weekday name for a ``YYYY-MM-DD`` session day, e.g. "Saturday".

    Derived generically so any festival's dates get labels for free (no hardcoded
    per-festival map). Events are already folded onto the right session day by
    ``session_day``; this just names it. Falls back to the raw string if it is not
    a parseable date."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%A")
    except ValueError:
        return date_str


def _plans_dir() -> Path:
    # Read at call time so create_app() picks up a test-set env var.
    return Path(os.environ.get("FESTERS_PLANS_DIR", str(_HERE.parent / "data" / "plans")))


def _auth_dir() -> Path:
    return Path(os.environ.get("FESTERS_AUTH_DIR", str(_HERE.parent / "data" / "auth")))


def _base_url() -> str:
    # Used to build the magic link; set to the public URL at deploy.
    return os.environ.get("FESTERS_BASE_URL", "http://localhost:8000")


_REQUEST_COOLDOWN_SECONDS = 30  # per-IP throttle on /request-link


def _fmt_time(ev: Event) -> str:
    """Display string from the LOCAL clock fields only (never the device clock).

    ``start_local``/``end_local`` are the schedule's pre-rendered +01:00 strings.
    Falls back to nothing rather than computing from UTC in the wrong tz.
    """
    start = ev.start_local or ""
    if ev.end_local:
        return f"{start}–{ev.end_local}"
    return start


def _build_days(schedule: Schedule, wanted_refs: set[str]) -> list[dict]:
    """Schedule grouped by festival session day -> venue -> events, chronological.

    Day grouping is by ``session_day`` (clock-time based), so after-midnight
    spillover sits under the night it belongs to and every event shows across
    exactly three day sections.
    """
    # day -> venue_code -> list[Event]
    by_day: dict[str, dict[str, list[Event]]] = {}
    for ev in schedule.events:
        day = session_day(ev)
        by_day.setdefault(day, {}).setdefault(ev.venue, []).append(ev)

    days = []
    for day in sorted(by_day):
        venues = []
        for code in sorted(by_day[day], key=lambda c: schedule.venue(c).name):
            evs = sorted(by_day[day][code], key=lambda e: (e.start_utc, e.id))
            venues.append(
                {
                    "name": schedule.venue(code).name,
                    "zone": schedule.venue(code).zone,
                    "maps_url": schedule.venue(code).maps_url,
                    "events": [
                        {
                            "id": e.id,
                            "title": e.name,
                            "time": _fmt_time(e),
                            "room": e.room,
                            "collection": e.collection,
                        }
                        for e in evs
                    ],
                }
            )
        days.append({"date": day, "label": _day_label(day), "venues": venues})
    return days


def _travel_for_schedule(schedule: Schedule):
    """Adapt Contract C to the (event-zone, event-zone) callable the conflict
    detector and optimiser expect: they pass zone strings straight through.

    The travel matrix now lives in the festival's own data, so this builds the
    callable from the given schedule rather than a global matrix."""
    return make_travel(schedule)


def _conflict_days(schedule: Schedule, wants: Wants, params: OptimiserParams) -> list[dict]:
    """Conflicts grouped by session day for the view (pure -> view shape).

    loop-06: now travel-aware - a pair that overlaps only once walking time is
    added is surfaced too. The seam was built in loop-03; here we pass Contract C.
    """
    conflicts = find_conflicts(schedule, wants, params, travel=_travel_for_schedule(schedule))
    by_day: dict[str, list] = {}
    for c in conflicts:
        by_day.setdefault(c.day, []).append(c)
    days = []
    for day in sorted(by_day):
        rows = [
            {
                "a_id": c.a.id,
                "a_title": c.a.name,
                "a_time": _fmt_time(c.a),
                "b_id": c.b.id,
                "b_title": c.b.name,
                "b_time": _fmt_time(c.b),
                "overlap_minutes": int(round(c.overlap_minutes)) if c.overlap_minutes else 0,
            }
            for c in by_day[day]
        ]
        days.append({"date": day, "label": _day_label(day), "conflicts": rows})
    return days


def _build_collections(schedule: Schedule, wanted_refs: set[str]) -> list[dict]:
    """Cross-cutting 'repeated experiences' view: each collection of >1 instance.

    A collection is SUBSTITUTABLE only when all its instances share one name (a
    true repeat, e.g. Ivan Seal's identical drop-in on Sat and Sun) - those get a
    'want any one' collection want and the optimiser picks the session. Collections
    of distinct names are a SERIES (a film programme, a ceremony's line-up); we
    surface them so you can see the cluster, but you pick instances individually.
    The repeat-vs-series split is data-driven (name identity), not hardcoded.
    """
    groups = []
    for coll in schedule.collections:
        instances = sorted(schedule.events_in_collection(coll.key),
                           key=lambda e: e.start_utc)
        if len(instances) < 2:
            continue  # a lone event is not a 'repeated experience'
        substitutable = len({e.name for e in instances}) == 1
        ref = f"collection:{coll.key}"
        groups.append(
            {
                "key": coll.key,
                "label": coll.name,
                "ref": ref,
                "venue": schedule.venue(instances[0].venue).name,
                "substitutable": substitutable,
                "wanted": ref in wanted_refs,
                "instances": [
                    {
                        "id": e.id,
                        "day": _day_label(session_day(e)),
                        "time": _fmt_time(e),
                        "title": e.name,
                        "wanted": e.id in wanted_refs,
                    }
                    for e in instances
                ],
            }
        )
    groups.sort(key=lambda g: g["label"].lower())
    return groups


def _title_for(schedule: Schedule, event_id: str) -> str:
    try:
        return schedule.event(event_id).name
    except KeyError:
        return event_id


def _plan_view(schedule: Schedule, result) -> dict:
    """Shape an optimiser Plan into template data: attended grouped by session
    day, dropped-with-reason, and forced either/or choices - all resolved to
    human titles. Keeps the optimiser pure and the web layer thin."""
    by_day: dict[str, list[dict]] = {}
    for att in sorted(result.attended, key=lambda a: a.interval.start):
        day = session_day(att.event)
        by_day.setdefault(day, []).append(
            {
                "id": att.event.id,
                "title": att.event.name,
                "time": _fmt_time(att.event),
                "venue": schedule.venue(att.event.venue).name,
                "room": att.event.room,
                "weight": att.want.weight,
            }
        )
    attended_days = [
        {"date": d, "label": _day_label(d), "events": by_day[d]}
        for d in sorted(by_day)
    ]

    dropped = [
        {
            "ref": d.want.ref,
            "title": _title_for(schedule, d.want.ref),
            "reason": _DROP_LABELS.get(d.reason.value, d.reason.value),
            "detail": d.detail,
            "lost_to": [_title_for(schedule, eid) for eid in d.conflicts_with],
        }
        for d in result.dropped
    ]

    forced = [
        {
            "options": [
                {"id": eid, "title": _title_for(schedule, eid),
                 "chosen": eid in fc.chosen}
                for eid in fc.event_ids
            ],
            "note": fc.note,
        }
        for fc in result.forced_choices
    ]

    return {
        "attended_days": attended_days,
        "attended_count": len(result.attended),
        "dropped": dropped,
        "forced": forced,
        "total_weight": result.total_weight,
    }


def create_app(
    registry: Optional[FestivalRegistry] = None,
    notifier: Optional[Notifier] = None,
) -> FastAPI:
    """Build the app. Loads + validates every festival once (fail fast).

    Festivals are served under ``/f/<id>/``; the landing ``/`` lists them.
    Identity is a magic link: a phone number is submitted, a link to a rotating
    token is sent over the configured channel, and the token grants edit access
    to that number's plan for that festival. The number is never stored (see
    festers.accounts); the token record carries the festival id, so the plan URL
    stays ``/p/<token>``.
    """
    registry = registry or load_registry()
    notifier = notifier or make_notifier()
    params = OptimiserParams()
    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
    tokens = TokenStore(_auth_dir())
    last_request: dict[str, float] = {}  # per-IP cooldown for /request-link

    app = FastAPI(title="festers", summary="festival attendance picker")
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
    app.state.registry = registry

    def _festival_or_404(festival_id: str) -> Schedule:
        schedule = registry.get(festival_id)
        if schedule is None:
            raise HTTPException(status_code=404, detail="unknown festival")
        return schedule

    def _wants_for(plan_id: str) -> Wants:
        return load_wants(plan_id, base_dir=_plans_dir())

    def _conflict_count(schedule: Schedule, plan_id: str) -> int:
        try:
            return len(find_conflicts(schedule, _wants_for(plan_id), params,
                                      travel=_travel_for_schedule(schedule)))
        except Exception:
            return 0

    def _default_festival_id() -> Optional[str]:
        """The festival a festival-less (legacy) token belongs to.

        Tokens minted before festivals were namespaced carry no ``festival_id``,
        but they can only be from the original single festival. Fall back to
        ``FESTERS_DEFAULT_FESTIVAL`` if set, else the sole/earliest festival, so
        those old magic links keep working (and the picks behind them stay
        reachable - the token record still holds the original plan id)."""
        env = os.environ.get("FESTERS_DEFAULT_FESTIVAL")
        if env:
            return env
        ids = registry.ids()
        return ids[0] if ids else None

    def _plan_ctx(token: str, *, verify: bool = False) -> tuple[str, Schedule]:
        """Resolve a token to its (plan_id, schedule), or 404 if the token is
        unknown or its festival no longer exists. A legacy token without a
        ``festival_id`` falls back to the default festival. ``verify=True`` also
        marks the token verified (the link has been clicked)."""
        plan_id = tokens.verify(token) if verify else tokens.resolve(token)
        festival_id = tokens.festival_of(token) or _default_festival_id()
        schedule = registry.get(festival_id)
        if plan_id is None or schedule is None:
            raise HTTPException(status_code=404, detail="invalid or expired link")
        return plan_id, schedule

    def _browse_context(schedule: Schedule, token: Optional[str],
                        wanted: set[str]) -> dict:
        return {
            "festival": schedule.festival,
            "days": _build_days(schedule, wanted),
            "groups": _build_collections(schedule, wanted),
            "token": token,
            "plan_base": f"/p/{token}" if token else None,
            "wanted_refs": wanted,
        }

    def _landing(request: Request, schedule: Schedule, error: str = "",
                 status: int = 200) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "browse.html",
            {**_browse_context(schedule, None, set()), "error": error},
            status_code=status,
        )

    # ----- public: festival index, per-festival browse + JSON + request form -----
    @app.get("/healthz")
    def healthz() -> JSONResponse:
        # Readiness probe for the deploy health-check: 200 only if the registry
        # actually loaded (create_app fails fast, so reaching here means it did).
        events = sum(len(s.events) for s in registry.all())
        return JSONResponse({"status": "ok", "festivals": len(registry), "events": events})

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"festivals": [s.festival for s in registry.all()]},
        )

    @app.get("/f/{festival_id}/", response_class=HTMLResponse)
    def landing(request: Request, festival_id: str) -> HTMLResponse:
        return _landing(request, _festival_or_404(festival_id))

    @app.get("/f/{festival_id}/api/schedule")
    def api_schedule(festival_id: str) -> JSONResponse:
        return JSONResponse(_festival_or_404(festival_id).model_dump(mode="json"))

    @app.post("/f/{festival_id}/request-link", response_class=HTMLResponse)
    def request_link(request: Request, festival_id: str, phone: str = Form(...)):
        schedule = _festival_or_404(festival_id)
        # Per-IP cooldown so nobody can spam links (incl. to strangers' numbers).
        ip = request.client.host if request.client else "?"
        now = time.monotonic()
        if now - last_request.get(ip, 0.0) < _REQUEST_COOLDOWN_SECONDS:
            return templates.TemplateResponse(
                request, "sent.html",
                {"festival": schedule.festival,
                 "message": "You just asked for a link - check your messages, or try again in a moment."},
                status_code=429,
            )
        if not is_valid_phone(phone):
            return _landing(
                request, schedule,
                error="Enter a phone number in international format, e.g. +447700900123.",
                status=400,
            )
        last_request[ip] = now
        number = normalize_phone(phone)
        token = tokens.mint(plan_id_for(number, festival_id=schedule.festival.id),
                            schedule.festival.id)
        link = magic_link(_base_url(), token)
        try:
            notifier.send(
                number,
                f"Your festers plan link:\n{link}\n\nOpen it on this device and bookmark it.",
            )
        except Exception:  # delivery failure must not leak which numbers exist
            log.exception("notify send failed")
        # Neutral response regardless, so we never reveal whether a number is reachable.
        return templates.TemplateResponse(
            request, "sent.html",
            {"festival": schedule.festival,
             "message": "If that number can receive messages, we've sent a link to build your plan."},
        )

    # ----- token-gated plan editor (the link target; festival is in the token) -----
    @app.get("/p/{token}", response_class=HTMLResponse)
    def plan_editor(request: Request, token: str) -> HTMLResponse:
        try:
            plan_id, schedule = _plan_ctx(token, verify=True)
        except HTTPException:
            return templates.TemplateResponse(
                request, "link_invalid.html", {"festival": None}, status_code=404,
            )
        wanted = _wants_for(plan_id).refs()
        return templates.TemplateResponse(
            request,
            "browse.html",
            {
                **_browse_context(schedule, token, wanted),
                "conflict_count": _conflict_count(schedule, plan_id),
            },
        )

    @app.post("/p/{token}/toggle")
    def toggle(
        request: Request,
        token: str,
        ref: str = Form(...),
        kind: str = Form(...),
        next: str = "",
    ):
        plan_id, schedule = _plan_ctx(token)
        if kind not in ("event", "collection"):
            raise HTTPException(status_code=400, detail="kind must be event or collection")
        _validate_ref(schedule, ref, kind)

        wants = _wants_for(plan_id)
        if ref in {w.ref for w in wants.wants}:
            wants.wants = [w for w in wants.wants if w.ref != ref]  # toggle OFF
        else:
            wants.wants.append(Want(ref=ref, kind=kind))  # toggle ON
        save_wants(wants, base_dir=_plans_dir())

        if request.headers.get("x-requested-with") == "fetch":
            return Response(status_code=204)
        return RedirectResponse(next or f"/p/{token}", status_code=303)

    @app.get("/p/{token}/conflicts", response_class=HTMLResponse)
    def conflicts_view(request: Request, token: str) -> HTMLResponse:
        plan_id, schedule = _plan_ctx(token)
        conflict_days = _conflict_days(schedule, _wants_for(plan_id), params)
        return templates.TemplateResponse(
            request,
            "conflicts.html",
            {
                "festival": schedule.festival,
                "plan_base": f"/p/{token}",
                "conflict_days": conflict_days,
                "conflict_count": sum(len(d["conflicts"]) for d in conflict_days),
                "travel_aware": True,
            },
        )

    @app.get("/p/{token}/optimise", response_class=HTMLResponse)
    def optimise_view(request: Request, token: str) -> HTMLResponse:
        plan_id, schedule = _plan_ctx(token)
        result = build_plan(schedule, _wants_for(plan_id), _travel_for_schedule(schedule), params)
        return templates.TemplateResponse(
            request,
            "plan.html",
            {
                "festival": schedule.festival,
                "plan_base": f"/p/{token}",
                "conflict_count": _conflict_count(schedule, plan_id),
                **_plan_view(schedule, result),
            },
        )

    return app


# --------------------------------------------------------------------------- #
# Validation helpers (raise HTTP 400 on bad input).
# --------------------------------------------------------------------------- #
def _validate_ref(schedule: Schedule, ref: str, kind: str) -> None:
    if kind == "collection":
        key = ref[len("collection:"):] if ref.startswith("collection:") else ref
        if not schedule.events_in_collection(key):
            raise HTTPException(status_code=400, detail=f"unknown collection {key!r}")
        return
    try:
        schedule.event(ref)
    except KeyError:
        raise HTTPException(status_code=400, detail=f"unknown event {ref!r}")


# Module-level app for `uvicorn festers.app:app`.
app = create_app()
