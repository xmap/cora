"""Readiness probe: can this process serve a correct request right now.

`/health` (main.py) is the LIVENESS probe and answers a different
question: is the process alive. It checks nothing, deliberately. This
module backs `/readyz`, which reports whether the one dependency that
can change after a successful boot is still there.

## Why Postgres is the only check

Boot is aggressively fail-fast, so readiness must not restate it.
`app = create_app()` runs at import, and every configuration gate
(trust policy, authenticated-principal, IdP posture, signing posture)
raises there, before uvicorn binds a socket. The bootstrap policy, the
seeded Surfaces, and the pool itself are established at lifespan start,
and a failed lifespan exits the process. So if anything is alive to
answer `/readyz`, every one of those already passed. Re-checking them
would report a state that cannot exist.

Postgres is different. The pool is created once at lifespan start and
there is no retry or reconnect logic anywhere, so an outage AFTER boot
leaves a live process that fails every request. That is the gap a
readiness probe exists to close, and it is the whole of it.

Projection health is deliberately NOT gated on. A wedged projection is
a global condition: it would take every replica out of rotation at
once, including the pod hosting the in-band repair tool
(`agent/features/dismiss_event_in_reaction`, whose playbook is "page,
dismiss-event with reason, debug tomorrow"). Removing the repair tool
from the Service to signal that the repair tool is needed is a
self-locking outage. Projection lag belongs in a metric with an alert
on it, not in a traffic-routing signal.

## Why this is a pure function

`tests/conftest.py` forces `APP_ENV=test` process-wide, and that env
builds the in-memory kernel with `pool=None`. So a probe exercised only
through the app can reach nothing but the skipped branch: the DB path,
the status mapping, and the bounded-acquire property would all ship
unexecuted. Taking the pool as an argument lets the unit tier drive
every branch with fakes.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Literal

import asyncpg

if TYPE_CHECKING:
    from cora.infrastructure.config import Settings

DatabaseStatus = Literal["ok", "unreachable", "saturated", "closing", "skipped", "error"]
"""What the probe learned about Postgres. `skipped` means this
deployment has no pool at all (the in-memory kernel), so there is
nothing to report rather than nothing wrong."""

# Total wall budget for the probe, and the slice of it the acquire may
# take. Both are load-bearing and neither is redundant:
#
#   - `pool.acquire(timeout=)` bounds the WAIT FOR A CONNECTION. Without
#     it the probe waits forever on a saturated pool: `Pool.fetchval(q,
#     timeout=T)` calls `self.acquire()` with NO timeout and forwards T
#     only to the query, so the `timeout=` that looks like it bounds the
#     call does not bound the part that hangs.
#   - The outer `asyncio.timeout` bounds EVERYTHING ELSE, including
#     asyncpg's 60s connect default, which CORA never overrides and
#     which a probe can trigger because min_size=1 leaves connections
#     2..10 to be established lazily.
#
# The budget is generous on purpose. The probe is a victim of pool
# exhaustion, never a cause (one connection for ~1ms per period against
# max_size=10), so a tight budget only converts "busy" into "removed
# from rotation" and makes an overload spiral worse. Do not shrink these
# to "fail fast".
#
# INVARIANT: this budget must stay UNDER the orchestrator's own probe
# timeout (see docs/stack/deployment.md). If the orchestrator gives up
# first, its client disconnect, not our timeout, ends the request, and
# /readyz degrades from a diagnostic endpoint into a hang detector: the
# `saturated` body that is the entire point never gets written.
_PROBE_BUDGET_S = 1.5
_ACQUIRE_BUDGET_S = 1.0


async def probe_database(pool: asyncpg.Pool | None) -> DatabaseStatus:
    """Report whether Postgres can serve a trivial query right now.

    Never raises. Every failure is a status the caller renders, because
    a probe that raises turns a dependency outage into a 500 that reads
    like an application bug.
    """
    if pool is None:
        return "skipped"
    try:
        async with (
            asyncio.timeout(_PROBE_BUDGET_S),
            pool.acquire(timeout=_ACQUIRE_BUDGET_S) as conn,
        ):
            await conn.fetchval("SELECT 1")
    except TimeoutError:
        # asyncio.TimeoutError IS the builtin on 3.13, so this arm
        # covers both the outer budget and the acquire timeout.
        return "saturated"
    except asyncpg.InterfaceError:
        # Raised as "pool is closing" during graceful shutdown. NOT a
        # PostgresError subclass, so a narrower tuple would miss it.
        return "closing"
    except OSError:
        return "unreachable"
    except Exception:
        # Residual on purpose. Anything not enumerated above is still a
        # reason we cannot serve, and letting it escape would 500 the
        # probe. CancelledError is BaseException on 3.13, so real
        # cancellation still propagates.
        return "error"
    else:
        return "ok"


def readiness_body(database: DatabaseStatus, settings: Settings) -> dict[str, str]:
    """Render the probe result. Fixed vocabulary, no free text.

    `app_env` is here because `test` builds an in-memory kernel with no
    persistence; a green probe over a store that loses every Run on
    restart is worth making visible to whoever reads this.

    Deliberately absent: the database URL, the driver's error text, and
    the names of projections or bounded contexts. This endpoint is
    unauthenticated, and none of that helps a probe while all of it
    describes the deployment to anyone who can reach it. The logs carry
    the detail.
    """
    return {
        "status": "ready" if database in ("ok", "skipped") else "not_ready",
        "database": database,
        "app_env": settings.app_env,
    }


__all__ = ["DatabaseStatus", "probe_database", "readiness_body"]
