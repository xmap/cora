"""Evolver: replay events to reconstruct Assembly state.

Status mapping per event type:
  - `AssemblyDefined`     -> DEFINED (genesis)
  - `AssemblyVersioned`   -> VERSIONED (re-attestation allowed;
                             multiple versions on one stream)
  - `AssemblyDeprecated`  -> DEPRECATED (terminal)

The status mapping is hardcoded per match arm; the event type IS
the status-change indicator (no status field in event payloads).
Same precedent as Mount / Frame / Asset / Family.

`AssemblyVersioned` REPLACES the structural fields (slots / wires /
parameter_overrides_schema / drawing / version / content_hash) with
the new snapshot's values. The previous-snapshot fingerprint is
carried on the event itself as `previous_content_hash` for audit;
the evolver does not retain prior snapshots in state (the event
stream IS the revision history).

**Critical invariant**: every transition arm MUST construct the
full Assembly dataclass; partial construction relies on dataclass
defaults that would silently zero out unchanged fields. `id` and
`presents_as_family_id` are immutable across the lifecycle.

Transition events applied to empty state raise ValueError: they
can never appear before `AssemblyDefined` in a well-formed stream.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.equipment.aggregates.assembly.events import (
    AssemblyDefined,
    AssemblyDeprecated,
    AssemblyEvent,
    AssemblyVersioned,
)
from cora.equipment.aggregates.assembly.state import Assembly, AssemblyStatus
from cora.infrastructure.evolver import require_state


def evolve(state: Assembly | None, event: AssemblyEvent) -> Assembly:
    """Apply one event to the current state."""
    match event:
        case AssemblyDefined(
            assembly_id=assembly_id,
            name=name,
            presents_as_family_id=presents_as_family_id,
            required_slots=required_slots,
            required_wires=required_wires,
            parameter_overrides_schema=parameter_overrides_schema,
            drawing=drawing,
            version=version,
            content_hash=content_hash,
        ):
            _ = state  # AssemblyDefined is genesis; prior state ignored
            return Assembly(
                id=assembly_id,
                name=name,
                presents_as_family_id=presents_as_family_id,
                required_slots=required_slots,
                required_wires=required_wires,
                parameter_overrides_schema=parameter_overrides_schema,
                drawing=drawing,
                status=AssemblyStatus.DEFINED,
                version=version,
                content_hash=content_hash,
            )
        case AssemblyVersioned(
            name=name,
            presents_as_family_id=presents_as_family_id,
            required_slots=required_slots,
            required_wires=required_wires,
            parameter_overrides_schema=parameter_overrides_schema,
            drawing=drawing,
            version=version,
            content_hash=content_hash,
        ):
            prior = require_state(state, "AssemblyVersioned")
            return Assembly(
                id=prior.id,
                name=name,
                presents_as_family_id=presents_as_family_id,
                required_slots=required_slots,
                required_wires=required_wires,
                parameter_overrides_schema=parameter_overrides_schema,
                drawing=drawing,
                status=AssemblyStatus.VERSIONED,
                version=version,
                content_hash=content_hash,
            )
        case AssemblyDeprecated():
            prior = require_state(state, "AssemblyDeprecated")
            return Assembly(
                id=prior.id,
                name=prior.name,
                presents_as_family_id=prior.presents_as_family_id,
                required_slots=prior.required_slots,
                required_wires=prior.required_wires,
                parameter_overrides_schema=prior.parameter_overrides_schema,
                drawing=prior.drawing,
                status=AssemblyStatus.DEPRECATED,
                version=prior.version,
                content_hash=prior.content_hash,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[AssemblyEvent]) -> Assembly | None:
    """Replay a stream of events from the empty initial state."""
    state: Assembly | None = None
    for event in events:
        state = evolve(state, event)
    return state
