"""The deadline tests pass to `drain_projections`, sized for the run's parallelism.

`drain_projections` is production code (`cora.api.main` drains at startup,
`pilot_seed` after seeding), so it cannot know or care whether it is running
under pytest-xdist. The knowledge that a test run has N workers competing for
one machine belongs here, in the test tree.

## Why a fixed number was wrong

Every integration and contract test passed a hardcoded `deadline_seconds=2.0`,
tighter than the library's own 5.0 default. Serially that is generous. Under
`-n 4` it is not, and the suite produced a handful of failures per run, in a
different place each time, none reproducible in isolation. That reads as
flakiness and was diagnosed as such twice before someone read the exception:

    ProjectionDrainTimeoutError: did not catch up within 2.0s
        heads:     {asset_summary: 14, method_summary: 17, plan_summary: 19, ...}
        bookmarks: {all zero}

Bookmarks at zero after two seconds is a starved worker, not slow work.

## The measurement

787 drains instrumented with the deadline removed, under `-n 4` on a 10-core
machine (2026-08-02):

    median  0.03s      p90 0.83s      p99 4.60s      p99.9 5.97s
    exceeded 2.0s:  35 / 787  (4.4%)
    exceeded 5.0s:   6 / 787  (0.8%)

A drain is a 30ms operation with a six-second tail. The tail is the whole
problem: at ~151 call sites per full run, a 4.4% miss rate predicts 6-7
failures, and runs produced 5, 8, 2 and 0. Note that the library's 5.0s
default would still miss 0.8% of the time, so simply dropping the explicit
argument would have left the suite flaky at roughly one failure per run.

## The scaling

Serial keeps 2.0s: it is 66x the median and still fails fast on a genuine
hang, which is what the tight bound was for. Under xdist the budget scales
with worker count and then doubles, because contention is not purely linear
(N workers also means N Postgres containers plus their own IO):

    workers      1        2        4        8
    deadline   2.0s     8.0s    16.0s    32.0s

At the 4-worker configuration this repo pins, 16s is 2.7x the worst drain
observed across 787 samples. It stays clear of the 60s per-test timeout in
`pyproject.toml`, so a genuine hang still fails the test rather than the
deadline. Widen the factor rather than the base if the tail grows: the base
is what protects serial runs from hanging.
"""

from __future__ import annotations

import os
from typing import Final

# Serial budget. 66x the measured median drain; unchanged from what every call
# site hardcoded before, so serial behaviour is identical.
_SERIAL_DEADLINE_S: Final[float] = 2.0

# Headroom beyond linear worker scaling. Contention adds more than a
# proportional share because each worker also runs its own Postgres container.
_CONTENTION_FACTOR: Final[float] = 2.0


def _worker_count() -> int:
    """Workers in this run. 1 when not under xdist.

    pytest-xdist sets `PYTEST_XDIST_WORKER_COUNT` in every worker process.
    Absent or unparseable means a serial run, which is also what a plain
    `pytest` invocation gives.
    """
    raw = os.environ.get("PYTEST_XDIST_WORKER_COUNT")
    if raw is None:
        return 1
    try:
        return max(1, int(raw))
    except ValueError:
        return 1


def drain_deadline_s() -> float:
    """Deadline to pass to `drain_projections`, sized for this run.

    Use at every test call site instead of a literal, so the suite's
    parallelism is accounted for in one place:

        await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())
    """
    workers = _worker_count()
    if workers <= 1:
        return _SERIAL_DEADLINE_S
    return _SERIAL_DEADLINE_S * workers * _CONTENTION_FACTOR


__all__ = ["drain_deadline_s"]
