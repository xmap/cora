"""Evolver: replay events to reconstruct Family state.

Status mapping per event type:
  - `FamilyDefined`    -> DEFINED   (genesis; version=None)
  - `FamilyVersioned`  -> VERSIONED (version=event.version_tag;
                                     multi-source: Defined | Versioned)
  - `FamilyDeprecated` -> DEPRECATED (version preserved;
                                      multi-source: Defined | Versioned)

The mapping is hardcoded per match arm — the event type IS the
state-change indicator (no status field in event payloads).

Legacy `Family*` event-type-name strings in the event store are
upcast to `Family*` dataclasses by `events.from_stored` at load time
(per Marten/Axon dual-match pattern). The evolver only sees the new
dataclass shapes.

Transition events applied to empty state raise ValueError.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.equipment.aggregates._value_types import RoleId
from cora.equipment.aggregates.family.events import (
    FamilyDefined,
    FamilyDeprecated,
    FamilyEvent,
    FamilyPresentsAsAdded,
    FamilyPresentsAsRemoved,
    FamilySettingsSchemaUpdated,
    FamilyVersioned,
)
from cora.equipment.aggregates.family.state import (
    Family,
    FamilyName,
    FamilyStatus,
)
from cora.infrastructure.evolver import require_state


def evolve(state: Family | None, event: FamilyEvent) -> Family:
    """Apply one event to the current state."""
    match event:
        case FamilyDefined(family_id=family_id, name=name, affordances=affordances):
            _ = state  # FamilyDefined is the genesis event; prior state ignored
            return Family(
                id=family_id,
                name=FamilyName(name),
                status=FamilyStatus.DEFINED,
                affordances=affordances,
            )
        case FamilyVersioned(version_tag=version_tag, affordances=affordances):
            prior = require_state(state, "FamilyVersioned")
            return Family(
                id=prior.id,
                name=prior.name,
                status=FamilyStatus.VERSIONED,
                version=version_tag,
                # Affordance set REPLACES (5j semantics: a new version
                # IS a new declaration). Matches Method/Plan/Practice
                # replace-on-version precedent.
                affordances=affordances,
                settings_schema=prior.settings_schema,
                # presents_as PRESERVED across version: a new
                # affordance declaration does not implicitly revoke
                # role advertisements (orthogonal-axis; matches
                # settings_schema precedent). Operators who want to
                # withdraw a role on version do so explicitly via
                # `remove_family_presents_as`.
                presents_as=prior.presents_as,
            )
        case FamilyDeprecated():
            prior = require_state(state, "FamilyDeprecated")
            return Family(
                id=prior.id,
                name=prior.name,
                status=FamilyStatus.DEPRECATED,
                version=prior.version,
                # Affordances PRESERVED across deprecation; the
                # historical declaration stays visible for audit.
                affordances=prior.affordances,
                settings_schema=prior.settings_schema,
                # presents_as PRESERVED across deprecation: audit
                # trail of what role contracts this Family advertised.
                presents_as=prior.presents_as,
            )
        case FamilySettingsSchemaUpdated(settings_schema=settings_schema):
            prior = require_state(state, "FamilySettingsSchemaUpdated")
            return Family(
                id=prior.id,
                name=prior.name,
                status=prior.status,
                version=prior.version,
                # Affordances PRESERVED across schema updates; settings
                # schema and affordance set evolve independently.
                # Shallow-copy settings_schema so payload mutation can't alias state (B1).
                affordances=prior.affordances,
                settings_schema=(dict(settings_schema) if settings_schema is not None else None),
                presents_as=prior.presents_as,
            )
        case FamilyPresentsAsAdded(role_id=role_id):
            prior = require_state(state, "FamilyPresentsAsAdded")
            return Family(
                id=prior.id,
                name=prior.name,
                status=prior.status,
                version=prior.version,
                affordances=prior.affordances,
                settings_schema=prior.settings_schema,
                presents_as=prior.presents_as | {RoleId(role_id)},
            )
        case FamilyPresentsAsRemoved(role_id=role_id):
            prior = require_state(state, "FamilyPresentsAsRemoved")
            return Family(
                id=prior.id,
                name=prior.name,
                status=prior.status,
                version=prior.version,
                affordances=prior.affordances,
                settings_schema=prior.settings_schema,
                presents_as=prior.presents_as - {RoleId(role_id)},
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[FamilyEvent]) -> Family | None:
    """Replay a stream of events from the empty initial state."""
    state: Family | None = None
    for event in events:
        state = evolve(state, event)
    return state
