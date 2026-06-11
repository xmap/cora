"""Domain events emitted by the Role aggregate.

3A ships ONE event: `RoleDefined`. Update events
(`RoleAffordancesUpdated`, `RoleSignalsUpdated`) are deferred per
[[project-role-aggregate-design]] Q1 user pick (2026-06-10) until the
Lock 14 SiLA-2 FQN-terminal-major versioning trigger fires. Shipping
updates at 3A would lock the SHAPE of versioning before the trigger.

The `RoleDefined` payload carries the full Role contract (name,
docstring, required_affordances, optional_affordances, produces,
consumes). Status is implicit (`Defined`) -- since no FSM ships at 3A
there is no status field anywhere.

`from_stored` uses the project-wide `deserialize_or_raise` pattern so
malformed payloads surface as `Malformed RoleDefined` rather than
KeyError / TypeError.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.equipment.aggregates.family.affordance import Affordance
from cora.equipment.aggregates.role._signal_type import SignalType
from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent


@dataclass(frozen=True)
class RoleDefined:
    """A new global Role contract was defined.

    Genesis event for the Role stream. `required_affordances` and
    `optional_affordances` are disjoint (`RoleAffordanceOverlapError`
    fires at the decider if not). `produces` and `consumes` are open
    SignalType vocabularies (normalized + length-bounded at the
    decider). `docstring` is operator-facing prose.
    """

    role_id: UUID
    name: str
    docstring: str
    occurred_at: datetime
    required_affordances: frozenset[Affordance] = field(default_factory=frozenset[Affordance])
    optional_affordances: frozenset[Affordance] = field(default_factory=frozenset[Affordance])
    produces: frozenset[SignalType] = field(default_factory=frozenset[SignalType])
    consumes: frozenset[SignalType] = field(default_factory=frozenset[SignalType])


# Discriminated union of every event the Role aggregate emits.
# Single-arm today; ready for sibling expansion when 3A's deferred
# update slices land.
RoleEvent = RoleDefined


def event_type_name(event: RoleEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: RoleEvent) -> dict[str, Any]:
    """Serialize a Role event to a JSON-friendly dict for jsonb storage."""
    match event:
        case RoleDefined(
            role_id=role_id,
            name=name,
            docstring=docstring,
            occurred_at=occurred_at,
            required_affordances=required_affordances,
            optional_affordances=optional_affordances,
            produces=produces,
            consumes=consumes,
        ):
            return {
                "role_id": str(role_id),
                "name": name,
                "docstring": docstring,
                "occurred_at": occurred_at.isoformat(),
                # Sorted for deterministic payload serialization
                "required_affordances": sorted(a.value for a in required_affordances),
                "optional_affordances": sorted(a.value for a in optional_affordances),
                "produces": sorted(str(s) for s in produces),
                "consumes": sorted(str(s) for s in consumes),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def _load_affordances(payload: dict[str, Any], key: str) -> frozenset[Affordance]:
    """Load an Affordance set from a payload list field.

    Tolerates: missing key (default empty), empty list, or list of
    valid Affordance enum value strings. Unknown values raise a
    defensive `ValueError` via the StrEnum constructor.
    """
    raw = payload.get(key, [])
    return frozenset(Affordance(v) for v in raw)


def _load_signal_types(payload: dict[str, Any], key: str) -> frozenset[SignalType]:
    """Load a SignalType set from a payload list field.

    Open vocabulary at 3A: any string is accepted at load time. The
    decider does the trim + bound check before emit; the from_stored
    path trusts the payload was validated at write time.
    """
    raw = payload.get(key, [])
    return frozenset(SignalType(s) for s in raw)


def from_stored(stored: StoredEvent) -> RoleEvent:
    """Rebuild a Role event from a StoredEvent loaded from the event store."""
    payload = stored.payload
    match stored.event_type:
        case "RoleDefined":
            return deserialize_or_raise(
                "RoleDefined",
                lambda: RoleDefined(
                    role_id=UUID(payload["role_id"]),
                    name=payload["name"],
                    docstring=payload["docstring"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    required_affordances=_load_affordances(payload, "required_affordances"),
                    optional_affordances=_load_affordances(payload, "optional_affordances"),
                    produces=_load_signal_types(payload, "produces"),
                    consumes=_load_signal_types(payload, "consumes"),
                ),
                # Absorb ValueError from defensive Affordance / UUID /
                # datetime parsers so unknown values surface as
                # "Malformed RoleDefined" rather than leaking through.
                extra=(ValueError,),
            )
        case _:
            msg = f"Unknown RoleEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "RoleDefined",
    "RoleEvent",
    "event_type_name",
    "from_stored",
    "to_payload",
]
