"""Evolver: replay events to reconstruct Capability state.

Status mapping per event type:
  - `CapabilityDefined`    -> DEFINED   (genesis; version=None)
  - `CapabilityVersioned`  -> VERSIONED (version=event.version_tag;
                                         declarative contract REPLACES
                                         wholesale)
  - `CapabilityDeprecated` -> DEPRECATED (declarative contract PRESERVED
                                          for audit; replaced_by_capability_id
                                          captured if supplied)

The mapping is hardcoded per match arm — the event type IS the
state-change indicator (no status field in event payloads). Same
precedent as `FamilyVersioned`.

## Replace vs preserve on each arm

- CapabilityVersioned REPLACES required_affordances, executor_shapes,
  description, parameters_schema with the new event's values (a new
  version IS a new declaration).
- CapabilityDeprecated PRESERVES all declarative fields and ADDS the
  replaced_by_capability_id pointer. Operators reading a deprecated
  Capability still see what it declared (audit-critical).

Transition events applied to empty state raise ValueError via
`require_state` — they can never appear before `CapabilityDefined`
in a well-formed stream.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.infrastructure.evolver import require_state
from cora.recipe.aggregates.capability.events import (
    CapabilityDefined,
    CapabilityDeprecated,
    CapabilityEvent,
    CapabilitySuggestedRolesUpdated,
    CapabilityVersioned,
)
from cora.recipe.aggregates.capability.state import (
    Capability,
    CapabilityCode,
    CapabilityName,
    CapabilityStatus,
)


def evolve(state: Capability | None, event: CapabilityEvent) -> Capability:
    """Apply one event to the current state."""
    match event:
        case CapabilityDefined(
            capability_id=capability_id,
            code=code,
            name=name,
            description=description,
            required_affordances=required_affordances,
            executor_shapes=executor_shapes,
            parameters_schema=parameters_schema,
        ):
            _ = state  # genesis event; prior state ignored
            # Shallow-copy parameters_schema so payload mutation can't alias state (B1).
            return Capability(
                id=capability_id,
                code=CapabilityCode(code),
                name=CapabilityName(name),
                status=CapabilityStatus.DEFINED,
                description=description,
                required_affordances=required_affordances,
                executor_shapes=executor_shapes,
                parameters_schema=(
                    dict(parameters_schema) if parameters_schema is not None else None
                ),
            )
        case CapabilityVersioned(
            version_tag=version_tag,
            description=description,
            required_affordances=required_affordances,
            executor_shapes=executor_shapes,
            parameters_schema=parameters_schema,
        ):
            prior = require_state(state, "CapabilityVersioned")
            # Shallow-copy parameters_schema so payload mutation can't alias state (B1).
            return Capability(
                id=prior.id,
                code=prior.code,
                name=prior.name,
                status=CapabilityStatus.VERSIONED,
                version=version_tag,
                # Declarative contract REPLACES wholesale (a new
                # version IS a new declaration per Pattern P).
                description=description,
                required_affordances=required_affordances,
                executor_shapes=executor_shapes,
                parameters_schema=(
                    dict(parameters_schema) if parameters_schema is not None else None
                ),
                replaced_by_capability_id=prior.replaced_by_capability_id,
                # suggested_role_ids PRESERVED across version: orthogonal-
                # axis editorial set per memo Lock 10 (3E). Operators
                # who want to clear the set on version do so explicitly
                # via update_capability_suggested_roles with an empty
                # frozenset.
                suggested_role_ids=prior.suggested_role_ids,
            )
        case CapabilityDeprecated(replaced_by_capability_id=replaced_by_capability_id):
            prior = require_state(state, "CapabilityDeprecated")
            return Capability(
                id=prior.id,
                code=prior.code,
                name=prior.name,
                status=CapabilityStatus.DEPRECATED,
                version=prior.version,
                # Declarative contract PRESERVED across deprecation; the
                # historical declaration stays visible for audit.
                description=prior.description,
                required_affordances=prior.required_affordances,
                executor_shapes=prior.executor_shapes,
                parameters_schema=prior.parameters_schema,
                # Set the replaced_by pointer (None if not supplied).
                replaced_by_capability_id=replaced_by_capability_id,
                # suggested_role_ids PRESERVED across deprecation: audit
                # trail of what the editorial mapping said at retire
                # time.
                suggested_role_ids=prior.suggested_role_ids,
            )
        case CapabilitySuggestedRolesUpdated(suggested_role_ids=suggested_role_ids):
            prior = require_state(state, "CapabilitySuggestedRolesUpdated")
            return Capability(
                id=prior.id,
                code=prior.code,
                name=prior.name,
                status=prior.status,
                version=prior.version,
                description=prior.description,
                required_affordances=prior.required_affordances,
                executor_shapes=prior.executor_shapes,
                parameters_schema=prior.parameters_schema,
                replaced_by_capability_id=prior.replaced_by_capability_id,
                # Wholesale-replace per Pattern P (set-edit semantic).
                suggested_role_ids=suggested_role_ids,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[CapabilityEvent]) -> Capability | None:
    """Replay a stream of events from the empty initial state."""
    state: Capability | None = None
    for event in events:
        state = evolve(state, event)
    return state
