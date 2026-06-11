"""Evolver: replay events to reconstruct Role state.

3A ships ONE event type (`RoleDefined`); the evolver collapses to a
single genesis arm. When Lock 14 versioning lands, the evolver gains
`RoleAffordancesUpdated` / `RoleSignalsUpdated` arms with widening-only
semantics (the future arms preserve fields the new event does not
restate, mirroring Family's `settings_schema` preservation across
versioned events).

Transition events applied to empty state raise ValueError via
`require_state`.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.equipment.aggregates._value_types import RoleId
from cora.equipment.aggregates.role.events import RoleDefined, RoleEvent
from cora.equipment.aggregates.role.state import Role, RoleName


def evolve(state: Role | None, event: RoleEvent) -> Role:
    """Apply one event to the current state."""
    match event:
        case RoleDefined(
            role_id=role_id,
            name=name,
            docstring=docstring,
            required_affordances=required_affordances,
            optional_affordances=optional_affordances,
            produces=produces,
            consumes=consumes,
        ):
            _ = state  # Genesis event; prior state ignored
            return Role(
                id=RoleId(role_id),
                name=RoleName(name),
                docstring=docstring,
                required_affordances=required_affordances,
                optional_affordances=optional_affordances,
                produces=produces,
                consumes=consumes,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[RoleEvent]) -> Role | None:
    """Replay a stream of events from the empty initial state."""
    state: Role | None = None
    for event in events:
        state = evolve(state, event)
    return state
