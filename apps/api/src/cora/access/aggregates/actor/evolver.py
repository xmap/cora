"""Evolver: replay events to reconstruct Actor state.

`evolve(state, event) -> state` applies a single event to the current
state. `fold(events) -> state | None` is the convenience that walks an
event list from the empty initial state, used by the application handler
after loading a stream from the EventStore.

Both functions are pure and total: every (state, event) pair has a
single deterministic result. The terminal `assert_never` case forces
pyright (and the runtime) to error if a new event type is added to
`ActorEvent` without a matching match arm here, so the evolver can
never silently return None for an unhandled event.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.access.aggregates.actor.events import (
    ActorDeactivated,
    ActorEvent,
    ActorProfileForgotten,
    ActorReactivated,
    ActorRegistered,
)
from cora.access.aggregates.actor.state import Actor


def evolve(state: Actor | None, event: ActorEvent) -> Actor:
    """Apply one event to the current state."""
    # `pragma: no mutate` silences mutmut's `operator_match`, which removes
    # one case clause at a time. The two reachable-case removals get killed
    # by tests anyway; the unreachable `case _:` removal is the equivalent
    # mutant we want to silence. mutmut's pragma is per-line + per-CST-node
    # start_line, and the operator_match mutation is rooted on the `match`
    # statement itself — so the pragma lives here, not on individual cases.
    match event:  # pragma: no mutate
        case ActorRegistered(actor_id=actor_id, kind=kind):
            # `active` defaults to True on `Actor` — omit the explicit
            # kwarg so mutmut can't generate a redundancy mutation. The
            # ActorDeactivated branch below passes `active=False`
            # explicitly (NOT the default).
            return Actor(id=actor_id, kind=kind)
        case ActorDeactivated():
            # Corruption guard: ActorDeactivated never appears before
            # ActorRegistered in a well-formed stream. Block is
            # unreachable in well-formed streams; both `no cover` (skip
            # coverage) and `no mutate` (skip mutation) on each statement.
            if state is None:  # pragma: no cover  # pragma: no mutate
                msg = "ActorDeactivated cannot be applied to empty state"  # pragma: no cover  # pragma: no mutate  # noqa: E501
                raise ValueError(msg)  # pragma: no cover  # pragma: no mutate
            return Actor(id=state.id, active=False, kind=state.kind)
        case ActorReactivated():
            # Corruption guard mirrors ActorDeactivated: unreachable in a
            # well-formed stream, where registration always precedes any
            # availability flip.
            if state is None:  # pragma: no cover  # pragma: no mutate
                msg = "ActorReactivated cannot be applied to empty state"  # pragma: no cover  # pragma: no mutate  # noqa: E501
                raise ValueError(msg)  # pragma: no cover  # pragma: no mutate
            return Actor(id=state.id, active=True, kind=state.kind)
        case ActorProfileForgotten():
            # PII erasure event: aggregate state is unchanged. The
            # event records the audit fact ("operator scrubbed this
            # actor's profile row on this date"); the actual side-
            # table mutation lives in the handler's same-transaction
            # `ProfileStore.scrub_and_delete` call. Corruption guard
            # mirrors ActorDeactivated.
            if state is None:  # pragma: no cover  # pragma: no mutate
                msg = "ActorProfileForgotten cannot be applied to empty state"  # pragma: no cover  # pragma: no mutate  # noqa: E501
                raise ValueError(msg)  # pragma: no cover  # pragma: no mutate
            return state
        case _:  # pragma: no cover  # pragma: no mutate
            # Exhaustiveness guard (LibCST attaches leading comments to the
            # next node, so the `# pragma: no mutate` only takes effect if
            # the `case _:` line is the FIRST line of the case clause —
            # keep this comment INSIDE the body, not above the case).
            assert_never(event)  # pragma: no cover  # pragma: no mutate


def fold(events: Sequence[ActorEvent]) -> Actor | None:
    """Replay a stream of events from the empty initial state.

    `Sequence` (covariant) rather than `list` (invariant) so callers can
    pass `list[ActorRegistered]` (a single-variant subtype) without an
    explicit cast -- matters in tests that build small homogeneous lists.
    """
    state: Actor | None = None
    for event in events:
        state = evolve(state, event)
    return state
