"""loop-05 - the optimiser core (pure library, no I/O, no web).

Turns a wishlist (:class:`~festers.wants.Wants`) into a feasible attendance
:class:`Plan`: the ordered events to attend, every dropped want WITH A REASON, and
the forced either/or choices surfaced for the user. Explainability is the whole
point - the optimiser must always be able to say *why* something was dropped.

Problem shape (see ``docs/design.md``): weighted interval selection with travel
constraints. For chosen attendances A then B in time order the schedule must
satisfy ``start(B) >= end(A) + travel(zone_A, zone_B)``.

ALGORITHM CHOICE (and why a clean DP does not apply)
----------------------------------------------------
Classic weighted-interval scheduling is an O(n log n) DP: sort by end time, and
for each interval binary-search the latest non-overlapping predecessor. That
relies on "compatible predecessor" being a property of *one* interval. Here
compatibility between A and B depends on ``travel(zone_A, zone_B)`` - i.e. on
WHICH venue you came from - so the predecessor relation is pairwise, not a clean
binary search, and the 1-D DP breaks (see the comment by :func:`_search`).

A correct DP would carry the last attended event in the state (O(n^2) states),
but collection ``count`` caps and the forced-choice bookkeeping make a recursive
exact search clearer. At this scale (a user picks ~10-30 wants; after expanding
collection instances, a few dozen candidate attendances) an exhaustive
branch-and-bound over candidates sorted by start time is provably optimal and
fast, and - crucially - it lets us reconstruct the exact reason each candidate
lost. Correctness and explainability over cleverness. No solver dependency: a
hand-written exact search does this tiny problem well, exactly as loop-05 asked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from typing import Callable, Optional

from festers.params import Interval, OptimiserParams, event_interval
from festers.schedule import Event, Schedule
from festers.wants import Want, Wants

Travel = Callable[[str, str], int]  # (zoneA, zoneB) -> minutes

# Drop-in flexibility is now DATA-DRIVEN: an event of type "exhibition" is a
# come-anytime span, so we place a short visit_minutes visit inside it rather than
# blocking its whole length. (This replaced an earlier duration heuristic once the
# schedule was reconciled and `type` made faithful - see docs/reconciliation.md.)
# Placement policy: earliest feasible start inside the span.
EXHIBITION = "exhibition"


class DropReason(str, Enum):
    """Why a want did not (fully) make the plan. str-Enum so it serialises."""

    CLASH = "clash"  # lost a time clash to a higher-value attendance
    TRAVEL = "travel"  # could not be reached in time given travel
    UNRESOLVED = "unresolved"  # ref points at no event / empty collection
    SHORTFALL = "shortfall"  # collection want: fewer instances feasible than count


@dataclass(frozen=True)
class Attendance:
    """A concrete decision to attend ``event`` over ``interval`` (its placed
    visit, which for an exhibition is a short slice inside the span)."""

    event: Event
    interval: Interval
    want: Want  # the want this attendance satisfies (for weight/provenance)


@dataclass
class Dropped:
    """A want (or part of one) that did not make the plan, with the reason."""

    want: Want
    reason: DropReason
    detail: str = ""
    # event ids this want lost out to (for CLASH/TRAVEL) - lets the UI offer an
    # override ("attend e2 instead of e1?").
    conflicts_with: tuple[str, ...] = ()


@dataclass
class ForcedChoice:
    """An either/or the optimiser had to resolve: a set of mutually exclusive
    wanted events of which at most some can be attended. Surfaced so the user can
    override the optimiser's pick."""

    event_ids: tuple[str, ...]
    chosen: tuple[str, ...]
    note: str = ""


@dataclass
class Plan:
    attended: list[Attendance] = field(default_factory=list)
    dropped: list[Dropped] = field(default_factory=list)
    forced_choices: list[ForcedChoice] = field(default_factory=list)
    total_weight: int = 0


# --------------------------------------------------------------------------
# Candidate expansion: a want -> the concrete attendances that could satisfy it.
# --------------------------------------------------------------------------

@dataclass
class _Candidate:
    event: Event
    interval: Interval
    want: Want
    group_key: Optional[str]  # mutual-exclusion group ("want index"): see below


def _placed_interval(event: Event, params: OptimiserParams) -> Interval:
    """The interval this attendance actually occupies.

    Fixed events / point events: their event_interval. Exhibitions (drop-in spans): a
    visit_minutes slice placed at the EARLIEST point of the span (documented
    policy - simple, deterministic, and frees the rest of the day).
    """
    span = event_interval(event, params)
    if event.type == EXHIBITION:
        return Interval(
            start=span.start,
            end=span.start + timedelta(minutes=params.visit_minutes),
        )
    return span


def _expand(
    schedule: Schedule, wants: Wants, params: OptimiserParams
) -> tuple[list[_Candidate], list[Dropped]]:
    """Resolve each want to candidate attendances; collect unresolved drops.

    Each want gets a ``group_key`` so the search knows two candidates are
    alternatives for the SAME want (a collection want's instances are mutually
    exclusive up to its ``count``; an event want has a single candidate).
    """
    candidates: list[_Candidate] = []
    unresolved: list[Dropped] = []

    for idx, want in enumerate(wants.wants):
        key = f"want{idx}"
        if want.kind == "collection":
            coll = want.ref.split("collection:", 1)[-1]
            instances = schedule.events_in_collection(coll)
            if not instances:
                unresolved.append(
                    Dropped(want, DropReason.UNRESOLVED,
                            detail=f"no events in collection {coll!r}")
                )
                continue
            for ev in instances:
                candidates.append(
                    _Candidate(ev, _placed_interval(ev, params), want, key)
                )
        else:  # event want
            try:
                ev = schedule.event(want.ref)
            except KeyError:
                unresolved.append(
                    Dropped(want, DropReason.UNRESOLVED,
                            detail=f"no event with id {want.ref!r}")
                )
                continue
            candidates.append(
                _Candidate(ev, _placed_interval(ev, params), want, key)
            )

    return candidates, unresolved


# --------------------------------------------------------------------------
# Feasibility between two attendances (time + travel).
# --------------------------------------------------------------------------

def _feasible_after(prev: _Candidate, nxt: _Candidate, schedule: Schedule,
                    travel: Travel) -> bool:
    """Can ``nxt`` be attended after ``prev`` given travel? Assumes
    prev.interval.start <= nxt.interval.start."""
    gap = timedelta(minutes=travel(
        schedule.zone_of_event(prev.event),
        schedule.zone_of_event(nxt.event),
    ))
    # nxt is reachable iff it does not overlap prev once travel is folded in.
    return not prev.interval.overlaps(nxt.interval, gap=gap)


# --------------------------------------------------------------------------
# Exact branch-and-bound search.
# --------------------------------------------------------------------------

def _objective(chosen: list[_Candidate], schedule: Schedule, travel: Travel,
               params: OptimiserParams) -> float:
    """Sum of attended want-weights minus a small travel penalty (tie-break
    toward less walking). Higher is better."""
    weight = sum(c.want.weight for c in chosen)
    travel_min = 0
    for a, b in zip(chosen, chosen[1:]):
        travel_min += travel(
            schedule.zone_of_event(a.event),
            schedule.zone_of_event(b.event),
        )
    return weight - params.travel_penalty_per_min * travel_min


def _search(candidates: list[_Candidate], schedule: Schedule, travel: Travel,
            params: OptimiserParams) -> list[_Candidate]:
    """Return the best feasible subset of candidates (ordered by start).

    Exhaustive DFS over candidates sorted by start time. State carries the LAST
    chosen candidate (so travel feasibility, which is pairwise, is exact) and a
    per-want count of how many instances are already taken (so a collection want never
    exceeds its ``count`` and an event want is taken at most once).

    Why not the textbook O(n log n) WIS DP: that needs a single "latest
    compatible predecessor" per interval, but compatibility here depends on the
    previous VENUE (travel), so predecessors are pairwise. We therefore search
    exactly. n is a few dozen, so this is comfortably fast; correctness first.
    """
    ordered = sorted(candidates, key=lambda c: (c.interval.start, c.interval.end))
    n = len(ordered)

    # Suffix weight sums for the branch-and-bound bound: suffix[i] is the total
    # want-weight of candidates i..n-1. Taking ALL of them is the most weight the
    # subtree at i could add; since the travel penalty only subtracts, this is a
    # valid OPTIMISTIC upper bound on any score reachable from i.
    suffix = [0] * (n + 1)
    for i in range(n - 1, -1, -1):
        suffix[i] = suffix[i + 1] + ordered[i].want.weight

    best: dict = {"score": float("-inf"), "chosen": []}

    # caps: how many of each want we may still take.
    caps: dict[str, int] = {}
    for c in ordered:
        caps[c.group_key] = c.want.count if c.want.kind == "collection" else 1

    def dfs(i: int, chosen: list[_Candidate], taken: dict[str, int],
            weight: int) -> None:
        # Branch-and-bound prune: if even taking every remaining candidate cannot
        # beat the incumbent, abandon this subtree. Strict '<' so equal-weight
        # branches survive to be resolved by the (more-events / less-travel) tie
        # break. The optimum is never pruned: its bound is >= its own score >=
        # best. Because branch 1 (take) runs before branch 2 (skip), DFS reaches a
        # greedy take-all incumbent first, which then prunes the skip-subtrees -
        # taming the all-compatible worst case from O(2^n) to ~O(n).
        if weight + suffix[i] < best["score"]:
            return

        if i == n:
            score = _objective(chosen, schedule, travel, params)
            # tie-break: prefer MORE attended events, then higher score.
            key = (score, len(chosen))
            best_key = (best["score"], len(best["chosen"]))
            if key > best_key:
                best["score"] = score
                best["chosen"] = list(chosen)
            return

        cand = ordered[i]

        # branch 1: take cand, if the want still has headroom and it is reachable
        # from the last chosen attendance.
        if taken.get(cand.group_key, 0) < caps[cand.group_key]:
            prev = chosen[-1] if chosen else None
            if prev is None or _feasible_after(prev, cand, schedule, travel):
                taken[cand.group_key] = taken.get(cand.group_key, 0) + 1
                chosen.append(cand)
                dfs(i + 1, chosen, taken, weight + cand.want.weight)
                chosen.pop()
                taken[cand.group_key] -= 1

        # branch 2: skip cand.
        dfs(i + 1, chosen, taken, weight)

    dfs(0, [], {}, 0)
    return best["chosen"]


# --------------------------------------------------------------------------
# Explanation: reconstruct WHY each non-attended candidate lost.
# --------------------------------------------------------------------------

def _explain_drop(cand: _Candidate, chosen: list[_Candidate],
                  schedule: Schedule, travel: Travel) -> Dropped:
    """Classify why ``cand`` is not in the plan, naming what it lost to.

    Walks the chosen set and finds the attendances that would clash with cand
    (time only -> CLASH; only-with-travel -> TRAVEL). If nothing in the plan
    clashes, the want simply was not selected as part of the optimum (still a
    CLASH against same-want siblings or a dominated alternative)."""
    time_blockers: list[str] = []
    travel_blockers: list[str] = []
    for other in chosen:
        if other.group_key == cand.group_key:
            continue  # a sibling instance of the same want is not a "loss"
        if cand.interval.overlaps(other.interval):
            time_blockers.append(other.event.id)
        else:
            a, b = sorted((cand, other), key=lambda c: c.interval.start)
            if not _feasible_after(a, b, schedule, travel):
                travel_blockers.append(other.event.id)

    if time_blockers:
        return Dropped(cand.want, DropReason.CLASH,
                       detail="time clash with a higher-value attendance",
                       conflicts_with=tuple(time_blockers))
    if travel_blockers:
        return Dropped(cand.want, DropReason.TRAVEL,
                       detail="not reachable in time given travel",
                       conflicts_with=tuple(travel_blockers))
    # No direct blocker among the chosen: it lost to a sibling of the same want
    # (collection with too small a count) or was dominated. Report as CLASH with no
    # external conflict so the UI shows "not selected".
    return Dropped(cand.want, DropReason.CLASH,
                   detail="not selected in the optimal plan")


def _build_forced_choices(candidates: list[_Candidate],
                          chosen_ids: set[str], schedule: Schedule,
                          travel: Travel) -> list[ForcedChoice]:
    """Surface genuine either/or decisions: pairs of WANTED events that mutually
    exclude (time or travel) where the optimiser had to pick. One ForcedChoice
    per maximal clashing cluster keeps it legible for the UI."""
    # union-find over candidates that pairwise exclude.
    parent: dict[int, int] = {i: i for i in range(len(candidates))}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        parent[find(x)] = find(y)

    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            ci, cj = candidates[i], candidates[j]
            a, b = sorted((ci, cj), key=lambda c: c.interval.start)
            if a.interval.overlaps(b.interval) or not _feasible_after(
                a, b, schedule, travel
            ):
                union(i, j)

    clusters: dict[int, list[_Candidate]] = {}
    for i, c in enumerate(candidates):
        clusters.setdefault(find(i), []).append(c)

    forced: list[ForcedChoice] = []
    for members in clusters.values():
        ids = tuple(sorted({m.event.id for m in members}))
        if len(ids) < 2:
            continue  # no contention, no choice
        chosen = tuple(sorted({m.event.id for m in members
                               if m.event.id in chosen_ids}))
        forced.append(ForcedChoice(
            event_ids=ids, chosen=chosen,
            note="mutually exclusive wanted events (time/travel)",
        ))
    return forced


# --------------------------------------------------------------------------
# Public entry point.
# --------------------------------------------------------------------------

def plan(schedule: Schedule, wants: Wants, travel: Travel,
         params: OptimiserParams) -> Plan:
    """Build the attendance plan for ``wants`` (see module docstring)."""
    candidates, unresolved = _expand(schedule, wants, params)

    chosen = _search(candidates, schedule, travel, params)
    chosen_set = set(id(c) for c in chosen)
    chosen_ids = {c.event.id for c in chosen}

    attended = [
        Attendance(event=c.event, interval=c.interval, want=c.want)
        for c in chosen
    ]

    dropped: list[Dropped] = list(unresolved)

    # per-want accounting: how many candidates each want got, how many landed.
    taken_per_want: dict[str, int] = {}
    for c in chosen:
        taken_per_want[c.group_key] = taken_per_want.get(c.group_key, 0) + 1

    # candidates that did not make the plan -> explained drops.
    seen_event_drop: set[str] = set()
    for c in candidates:
        if id(c) in chosen_set:
            continue
        # a collection sibling whose want already met its count is not a "drop".
        if (c.want.kind == "collection"
                and taken_per_want.get(c.group_key, 0) >= c.want.count):
            continue
        drop = _explain_drop(c, chosen, schedule, travel)
        # avoid duplicate drop rows for the same event id
        if c.event.id in seen_event_drop:
            continue
        seen_event_drop.add(c.event.id)
        dropped.append(drop)

    # collection SHORTFALL: a collection want that landed some but fewer than count.
    by_want: dict[str, Want] = {f"want{i}": w for i, w in enumerate(wants.wants)}
    for key, want in by_want.items():
        if want.kind != "collection":
            continue
        got = taken_per_want.get(key, 0)
        if 0 < got < want.count:
            dropped.append(Dropped(
                want, DropReason.SHORTFALL,
                detail=f"wanted {want.count}, only {got} feasible",
            ))

    forced_choices = _build_forced_choices(
        candidates, chosen_ids, schedule, travel
    )

    total_weight = sum(c.want.weight for c in chosen)
    return Plan(
        attended=attended,
        dropped=dropped,
        forced_choices=forced_choices,
        total_weight=total_weight,
    )
