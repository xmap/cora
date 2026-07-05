"""Evolver: replay events to reconstruct Policy state.

Mirror of the Zone / Conduit evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `PolicyEvent` without a matching match arm.

Folds the `list[UUID]` / `list[str]` from event payloads into
`frozenset[UUID]` / `frozenset[str]` on the Policy state — set
semantics matter for `evaluate`'s O(1) membership checks.
"""

from collections.abc import Sequence
from dataclasses import replace
from typing import assert_never

from cora.trust.aggregates.policy.events import (
    PolicyDefined,
    PolicyEvent,
    PolicyGrantRevoked,
)
from cora.trust.aggregates.policy.state import Policy, PolicyName


def evolve(state: Policy | None, event: PolicyEvent) -> Policy:
    """Apply one event to the current state."""
    match event:
        case PolicyDefined(
            policy_id=policy_id,
            name=name,
            conduit_id=conduit_id,
            permitted_principal_ids=permitted_principal_ids,
            permitted_commands=permitted_commands,
            surface_id=surface_id,
        ):
            _ = state  # PolicyDefined is the genesis event; prior state ignored
            return Policy(
                id=policy_id,
                name=PolicyName(name),
                conduit_id=conduit_id,
                permitted_principal_ids=frozenset(permitted_principal_ids),
                permitted_commands=frozenset(permitted_commands),
                surface_id=surface_id,
            )
        case PolicyGrantRevoked(principal_id=principal_id):
            assert state is not None, "PolicyGrantRevoked requires prior state"
            return replace(
                state,
                permitted_principal_ids=state.permitted_principal_ids - {principal_id},
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[PolicyEvent]) -> Policy | None:
    """Replay a stream of events from the empty initial state."""
    state: Policy | None = None
    for event in events:
        state = evolve(state, event)
    return state
