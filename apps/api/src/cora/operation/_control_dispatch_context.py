"""Per-dispatch `correlation_id` propagation for ControlPort adapters.

The Conductor walks per-step dispatch through `ControlPort.write` /
`ControlPort.read`. Each PseudoAxis resolution fans into a sequence
of constituent setpoints that all share one upstream `correlation_id`;
the adapters need that id on every emitted `controlport.dispatch`
structured-log event so an operator can trace one virtual-axis command
end-to-end across the constituent writes.

Why a `ContextVar` instead of a kwarg on `ControlPort.write`:

  - Signature stability. The `ControlPort` Protocol is shared across
    four adapters (`InMemoryControlPort`, `CaprotoControlPort`,
    `EpicsCaControlPort`, `EpicsPvaControlPort`) and is consumed by
    action bodies, the Conductor, and the future Plan executor.
    Adding a correlation_id parameter would touch every adapter +
    every caller, including third-party-shaped substrate libraries
    (aioca / p4p / caproto) whose interfaces the adapter mirrors.
  - Survives `await` boundaries. Python's `contextvars` are
    asyncio-aware: a value set in one coroutine remains visible to
    every coroutine it awaits, including third-party library callbacks
    that resume inside the same task. The Conductor sets the id
    before `await self._control_port.write(...)`, the adapter reads
    it once inside the await, no plumbing in between.
  - Loose coupling. Adapters never import the Conductor; they read
    the id from this module's contextvar. The Conductor never imports
    adapter internals; it just sets the contextvar before dispatch.
    The seam is one shared module that knows about neither side.

`with_dispatch_correlation_id(cid)` is the public entrance: a context
manager that sets the contextvar on enter + resets to the prior token
on exit so nested or concurrent walkers cannot leak state across each
other. `get_dispatch_correlation_id()` returns `None` outside any
active scope; adapters log `correlation_id=None` rather than raising,
keeping the dispatch path resilient to non-conducted call sites
(e.g., direct test invocations of an adapter).
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator
    from uuid import UUID


_dispatch_correlation_id: ContextVar[UUID | None] = ContextVar(
    "cora_control_dispatch_correlation_id",
    default=None,
)
"""Module-level `ContextVar` carrying the correlation id of the
in-flight Conductor dispatch. Default `None` so callers that read
without an active scope receive a clean sentinel instead of raising
`LookupError`."""


def get_dispatch_correlation_id() -> UUID | None:
    """Return the active dispatch correlation id, or `None` outside a scope."""
    return _dispatch_correlation_id.get()


def set_dispatch_correlation_id(correlation_id: UUID | None) -> Token[UUID | None]:
    """Install `correlation_id` for the current asyncio task scope.

    Returns the `Token` so the caller can later `reset` to the prior
    value. Prefer the `with_dispatch_correlation_id` context manager
    for the standard set + reset lifecycle; this primitive exists for
    call sites that cannot use the manager syntax (e.g., a hand-rolled
    try / finally inside a generator).
    """
    return _dispatch_correlation_id.set(correlation_id)


def reset_dispatch_correlation_id(token: Token[UUID | None]) -> None:
    """Restore the dispatch correlation id to its pre-`set` value."""
    _dispatch_correlation_id.reset(token)


@contextmanager
def with_dispatch_correlation_id(correlation_id: UUID | None) -> Generator[None]:
    """Bind `correlation_id` to the dispatch contextvar for the block body.

    Sets the contextvar on `__enter__`, resets it to the prior value
    on `__exit__` (even on exception). Per-task isolation comes from
    `ContextVar` semantics; concurrent Conductor walks on different
    asyncio tasks each see their own value with no cross-talk.
    """
    token = _dispatch_correlation_id.set(correlation_id)
    try:
        yield
    finally:
        _dispatch_correlation_id.reset(token)


__all__ = [
    "get_dispatch_correlation_id",
    "reset_dispatch_correlation_id",
    "set_dispatch_correlation_id",
    "with_dispatch_correlation_id",
]
