"""festers - attendance planner for The Black Lights festival.

Public surface is intentionally small and organised around the frozen contracts
in ``docs/contracts.md``:

- :mod:`festers.schedule` - Contract A (the schedule as data).
- :mod:`festers.wants`    - Contract B (what the user wants to attend).
- :mod:`festers.params`   - shared time primitives + optimiser tunables.

Time discipline (decided 2026-06-24): ``start_utc``/``end_utc`` are canonical and
all arithmetic happens in UTC. The ``*_local`` strings are display-only.
"""
