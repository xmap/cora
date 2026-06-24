"""Shared shape for the L2 edge runtimes (Conductor, Reckoner).

An L2 edge runtime conducts an aggregate to a terminal across a substrate
port: the `Conductor` drives a Procedure FSM over `ControlPort`, the
`Reckoner` drives a Run FSM over `ComputePort`. They are siblings with a
deliberately mirrored shape (best-effort abort, the observed
`ActuationKind` threaded onto the terminal, a result that reports success
plus the observed kind), but their inner work and FSMs genuinely diverge.

This module captures only what they TRULY share, not a forced engine:
- `ConductOutcome`, the terminal-outcome contract their result types
  structurally satisfy (the slice-6 merge collapses to one engine that
  still yields a `ConductOutcome`);
- `abort_orphan_on_cancel`, the cancel-orphan-abort control flow both
  wrap their inner await in.

Collapsing the two into one engine is the deferred slice-6 merge's job,
not this module's. See [[project_reckoner_dissolution_stage0_design]].
"""

from __future__ import annotations

import asyncio
import contextlib
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable


@runtime_checkable
class ConductOutcome(Protocol):
    """The terminal outcome shape every edge-runtime conduct produces.

    `succeeded` is the canonical pass/fail bit; `actuation_kind` is the
    kind the runtime observed for the episode. The result types carry it
    as an `ActuationKind` (a `StrEnum`); the runtime also snapshots it as
    a raw string onto the terminal event. It is typed `str | None` here
    (the StrEnum is assignable to `str`) so this module stays
    substrate-agnostic and below the BCs. `ConductorResult` and
    `ReckonerResult` structurally satisfy it.
    """

    @property
    def succeeded(self) -> bool: ...

    @property
    def actuation_kind(self) -> str | None: ...


@asynccontextmanager
async def abort_orphan_on_cancel(
    abort: Callable[[], Awaitable[object]],
) -> AsyncGenerator[None]:
    """Best-effort abort an in-flight aggregate if the conduct is cancelled.

    A conduct task cancelled mid-flight (the caller cancelled it, or the
    loop is shutting down) leaves its aggregate non-terminal in `Running`.
    Letting the cancellation propagate untouched orphans the FSM; this
    transitions it to its abort terminal best-effort (a failing abort is
    suppressed so signals / shutdown still behave), then re-raises so the
    caller's task still sees the cancellation. Shared by the L2 edge
    runtimes (Conductor, Reckoner); the observed kind is unrecoverable on
    cancellation, so callers record None on the abort.
    """
    try:
        yield
    except asyncio.CancelledError:
        with contextlib.suppress(Exception):
            await abort()
        raise


__all__ = ["ConductOutcome", "abort_orphan_on_cancel"]
