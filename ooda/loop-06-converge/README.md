# loop-06: converge - optimiser behind an endpoint, picker shows the plan

Status: **shipped**. The meeting point of Track A (service/picker/conflicts) and
Track B (travel model/optimiser).

## Observe

Both tracks shipped independently against the frozen contracts. The optimiser is
a pure library with no web surface; the conflict view was built travel-blind with
a seam for travel. Nothing yet joins them so a user can see an actual plan.

## Orient

Convergence is small by design because the seams were built ahead of time:
- loop-03 left `find_conflicts(..., travel=None)` with travel folded into the
  same overlap primitive via a `gap`. Wiring Contract C is a one-line change.
- loop-05's `plan(schedule, wants, travel, params)` already takes travel as a
  plain callable, so `festers.travel.travel` drops straight in.

## Decide

In the FastAPI app: pass Contract C into the conflict helpers (flip the view to
travel-aware) and add `GET /plan/{name}/optimise` that runs the optimiser and
renders the attendance plan - attended (by day), dropped-with-reason, and forced
either/or choices - resolved to human titles. The web layer stays thin: a single
`_plan_view` shaping function over the pure `Plan`.

## Act

- [x] Wire `travel` into `find_conflicts` calls; flip the conflict view to
      travel-aware (`travel_aware=True`).
- [x] `GET /plan/{name}/optimise` endpoint + `plan.html` view.
- [x] `_plan_view` shaper: Plan -> template data (titles, reasons, choices).
- [x] Nav link to the plan from every plan page.
- [x] Tests: optimise endpoint renders for empty and clashing plans and explains
      a drop; conflict view no longer says travel is unmodelled. Live uvicorn
      smoke test of browse -> toggle -> optimise -> conflicts.

## Outcomes

1. A user builds a wishlist on their phone and sees a feasible, travel-aware
   attendance plan with the reasoning behind every drop and forced choice.

## Tests

- [x] `/plan/{name}/optimise` returns 200 and renders the plan for an empty and a
      populated plan.
- [x] A plan with two clashing fixed events attends the higher-weight one and
      shows the other dropped with a visible reason.
- [x] The conflict view is travel-aware (Contract C wired).

## Left for follow-up (see NIGHT-LOG.md)

- Validate the optimiser's 3h window heuristic and earliest-feasible window
  placement against real data.
- A JSON `/api/plan/{name}` surface (currently HTML only).
- Live deploy + phone-reachability test on the Oracle box (loop-02 tail).
