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
    from cora.infrastructure.schema_version import SchemaPosture

DatabaseStatus = Literal["ok", "unreachable", "saturated", "closing", "skipped", "error"]
"""What the probe learned about Postgres. `skipped` means this
deployment has no pool at all (the in-memory kernel), so there is
nothing to report rather than nothing wrong."""

LlmReach = Literal["off", "live"]
"""Whether this deployment calls an external language model.

`live` means both the switch (`llm_enabled`) and the credential
(`anthropic_api_key`) are present, so the LLM-backed subscribers are
registered and will call out on every terminal Run. `off` means no
external model is called through this seam.

Named `llm`, NOT `egress`, and the distinction is the honest part. This
reports ONE outbound path. It is not a claim that nothing leaves the
deployment: `HttpRangeChecksumAdapter` is wired unconditionally for
http/https Distributions (`cora.data.wire`), so CORA can make outbound
requests with the LLM entirely off. Calling this field `egress` would
promise a perimeter this code does not enforce, which is exactly the
overclaim `derive_actuation` is careful to avoid on its own axis.
"""

ActuationReach = Literal["inert", "reachable"]
"""Whether this deployment can drive a physical effect on the beamline.

`inert` = both actuation paths are shut: CORA may observe but cannot
move hardware. `reachable` = at least one path is open.

This is a REPORT, not a gate. It reads the settings the real gates
already use (`ControlPort` write switch, `ComputePort` substrate) and
summarises them so a skeptical controls engineer can VERIFY the
observe-only claim in one call instead of trusting it. It decides
nothing and refuses nothing; the gates do that. Making it a pure report
is deliberate: a report that is wrong is a bug someone files, whereas a
gate that can be talked into the wrong answer moves a motor. See
`derive_actuation`.
"""

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


def derive_actuation(settings: Settings) -> ActuationReach:
    """Summarise whether either actuation path can drive hardware.

    Two paths reach a beamline, and this reports `inert` only when BOTH
    are shut:

      - the ControlPort write path: `control_writes_enabled` (a caput
        that moves a motor);
      - the ComputePort exec path: a compute job whose argv could itself
        be `caput ...`, reaching a control system without touching the
        ControlPort. Only `compute_substrate == "in_memory"` is provably
        unable to spawn anything, so any OTHER substrate reads as
        reachable.

    The compute test is written as an ALLOWLIST (`== "in_memory"`), not a
    denylist (`!= "local_process"`), on purpose: a future `globus` or
    `slurm` substrate is not-in_memory and so reads reachable by default,
    rather than slipping through a denylist the day its literal is added.

    ## Fail closed in the REPORTING direction

    When the answer is uncertain, this returns `reachable`, never
    `inert`. That deliberately INVERTS the `getattr(..., None)` idiom the
    Conductor's `_ActuationObserver` uses (whose absent case fails OPEN),
    because the pessimistic answer sits on the other side here: a false
    `reachable` is an alarm someone investigates and files as a bug; a
    false `inert` is a facility discovering CORA moved their stage after
    being told it could not. Only the first is survivable.

    ## What this deliberately does NOT read

    `cora_allow_raw_conduct` is excluded. It is read per-request, not at
    the composition root, and it is inert while `compute_substrate` is
    `in_memory` (a raw argv handed to the in-memory port spawns nothing).
    It is logged at boot beside this summary (see `main`) so an operator
    can still see it, but it does not move this value.

    `ActuationKind` (the Conductor's Physical/Simulated/Hybrid stamp)
    also cannot witness this posture and is not consulted: it tracks
    whether a route is a SIMULATOR, not whether it is WRITABLE, so an
    observe-only conduct over a non-simulated route still derives
    Physical. Simulated-ness and write-reachability are orthogonal axes
    that merely share the "actuation" lexeme.

    ## Scope

    This is the ACTUATION axis only (moving hardware). The EGRESS axis
    (sending data out, e.g. the LLM seam) and the SPEND axis are separate
    promises with their own switches; when they gain reported summaries
    they slot in beside this one rather than widening its meaning.
    """
    control_can_write = settings.control_writes_enabled
    compute_can_spawn = settings.compute_substrate != "in_memory"
    if control_can_write or compute_can_spawn:
        return "reachable"
    return "inert"


def derive_llm(settings: Settings) -> LlmReach:
    """Report whether an external language model gets called.

    `live` requires BOTH the switch and the credential, mirroring
    `build_llm`'s two guards, so this answers the question an operator
    actually has ("is CORA phoning out and spending?") rather than
    restating one flag. A deployment that sets `llm_enabled` and forgets
    the key reads `off`, which is the truth: nothing is called.

    Like `derive_actuation` this is a REPORT, not a gate. It decides
    nothing; `build_llm` is the thing that refuses. And it is scoped to
    the LLM seam alone, not to egress in general (see `LlmReach`).
    """
    return "live" if settings.llm_enabled and settings.anthropic_api_key is not None else "off"


def readiness_body(
    database: DatabaseStatus,
    settings: Settings,
    schema: SchemaPosture = "matched",
) -> dict[str, str]:
    """Render the probe result. Fixed vocabulary, no free text.

    `app_env` is here because `test` builds an in-memory kernel with no
    persistence; a green probe over a store that loses every Run on
    restart is worth making visible to whoever reads this. `actuation`
    is here because the pilot's whole value is that management, who will
    never hold credentials, can curl the observe-only claim: a green
    probe on a process that could move a beamline clears that same bar,
    for a stronger reason.

    Deliberately absent: the database URL, the driver's error text, and
    the names of projections, bounded contexts, or route prefixes. This
    endpoint is unauthenticated, and none of that helps a probe while all
    of it describes the deployment to anyone who can reach it. `actuation`
    is a scalar for exactly this reason: it says inert-or-reachable, not
    WHICH prefixes are writable. The logs carry the detail.

    `schema` reports whether this process booted against the schema it
    expects, and `degraded` deliberately does NOT make the status
    `not_ready`. A degraded process serves reads correctly, which is the
    entire reason it was allowed to start; reporting it unready would
    have an orchestrator pull it from rotation and so remove the access
    the override existed to grant. That is the same self-locking shape
    the projection-health note above rejects. It is visible, and it is
    not traffic-shaping.
    """
    return {
        "status": "ready" if database in ("ok", "skipped") else "not_ready",
        "database": database,
        "app_env": settings.app_env,
        "actuation": derive_actuation(settings),
        "llm": derive_llm(settings),
        "schema": schema,
    }


__all__ = [
    "ActuationReach",
    "DatabaseStatus",
    "LlmReach",
    "derive_actuation",
    "derive_llm",
    "probe_database",
    "readiness_body",
]
