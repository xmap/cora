"""Domain events emitted by the Family aggregate, plus the discriminated union.

Event types: `FamilyDefined`, `FamilyVersioned`, `FamilyDeprecated`,
`FamilySettingsSchemaUpdated`. Status is NOT carried in event
payloads -- the event type itself encodes the state change. The
evolver hardcodes the mapping per match arm.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.equipment.aggregates.family.affordance import Affordance
from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent


@dataclass(frozen=True)
class FamilyDefined:
    """A new device-class family was defined.

    Status is implicit (`Defined`) -- the evolver sets it. `affordances`
    is the closed-enum set of device-level primitives this Family
    supports (required at define_family time; empty frozenset valid).
    Defaults to empty frozenset for evolver-level robustness with
    payloads that don't carry the field (additive-state pattern; see
    [[project-capability-research]]).
    """

    family_id: UUID
    name: str
    occurred_at: datetime
    affordances: frozenset[Affordance] = field(default_factory=frozenset[Affordance])


@dataclass(frozen=True)
class FamilyVersioned:
    """A family's definition was revised; a new version label was issued.

    Multi-source transition: `Defined | Versioned -> Versioned`.
    `version_tag` is operator-supplied free text (1-50 chars).
    `affordances` is the REPLACEMENT affordance set declared at this
    version (a new version IS a new declaration). Defaults to empty
    frozenset for evolver-level robustness with sparse payloads
    (additive-state pattern).
    """

    family_id: UUID
    version_tag: str
    occurred_at: datetime
    affordances: frozenset[Affordance] = field(default_factory=frozenset[Affordance])


@dataclass(frozen=True)
class FamilyDeprecated:
    """A family was marked as no longer recommended for new Methods.

    Multi-source transition: `Defined | Versioned -> Deprecated`.
    Existing Methods that reference this Family are NOT automatically
    invalidated. Deprecation is advisory.
    """

    family_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class FamilySettingsSchemaUpdated:
    """The Family's `settings_schema` was set, replaced, or cleared.

    Carries the FULL replacement schema. Independent of the
    Defined/Versioned/Deprecated lifecycle: schema can be updated in
    any non-terminal state. The validator runs at decider time, so
    this event ALWAYS carries a valid schema or None.
    """

    family_id: UUID
    settings_schema: dict[str, Any] | None
    occurred_at: datetime


@dataclass(frozen=True)
class FamilyPresentsAsAdded:
    """The Family advertised an additional global Role contract.

    Additive on `presents_as`. Strict-not-idempotent: re-adding the
    same `role_id` surfaces `FamilyRolePresentsAsAlreadyError` at the
    decider. The decider also enforces that the Family's current
    `affordances` is a superset of the Role's `required_affordances`
    (handler-side `RoleLookup`); failure surfaces
    `FamilyCannotPresentAsError`.
    """

    family_id: UUID
    role_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class FamilyPresentsAsRemoved:
    """The Family withdrew a previously-advertised global Role contract.

    Removes one `role_id` from `presents_as`. Strict-not-idempotent:
    removing a Role the Family does not advertise surfaces
    `FamilyRolePresentsAsNotPresentError`. The decider does NOT
    consult `RoleLookup` (a Role that no longer resolves may still
    have been previously advertised; the operator can still withdraw
    it cleanly).
    """

    family_id: UUID
    role_id: UUID
    occurred_at: datetime


# Discriminated union of every event the Family aggregate emits.
FamilyEvent = (
    FamilyDefined
    | FamilyVersioned
    | FamilyDeprecated
    | FamilySettingsSchemaUpdated
    | FamilyPresentsAsAdded
    | FamilyPresentsAsRemoved
)


def event_type_name(event: FamilyEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: FamilyEvent) -> dict[str, Any]:
    """Serialize a Family event to a JSON-friendly dict for jsonb storage."""
    match event:
        case FamilyDefined(
            family_id=family_id,
            name=name,
            occurred_at=occurred_at,
            affordances=affordances,
        ):
            return {
                "family_id": str(family_id),
                "name": name,
                "occurred_at": occurred_at.isoformat(),
                # Sorted for deterministic payload serialization
                "affordances": sorted(a.value for a in affordances),
            }
        case FamilyVersioned(
            family_id=family_id,
            version_tag=version_tag,
            occurred_at=occurred_at,
            affordances=affordances,
        ):
            return {
                "family_id": str(family_id),
                "version_tag": version_tag,
                "occurred_at": occurred_at.isoformat(),
                "affordances": sorted(a.value for a in affordances),
            }
        case FamilyDeprecated(family_id=family_id, occurred_at=occurred_at):
            return {
                "family_id": str(family_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case FamilySettingsSchemaUpdated(
            family_id=family_id,
            settings_schema=settings_schema,
            occurred_at=occurred_at,
        ):
            return {
                "family_id": str(family_id),
                "settings_schema": settings_schema,
                "occurred_at": occurred_at.isoformat(),
            }
        case FamilyPresentsAsAdded(family_id=family_id, role_id=role_id, occurred_at=occurred_at):
            return {
                "family_id": str(family_id),
                "role_id": str(role_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case FamilyPresentsAsRemoved(family_id=family_id, role_id=role_id, occurred_at=occurred_at):
            return {
                "family_id": str(family_id),
                "role_id": str(role_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def _load_affordances(payload: dict[str, Any]) -> frozenset[Affordance]:
    """Load the affordance set from a payload's `affordances` list field.

    Tolerates: missing key (default empty), empty list, or list of
    valid Affordance enum value strings. Unknown values raise a
    defensive `ValueError` via the StrEnum constructor, same fail-loud
    stance as the `from_stored` top-level dispatch on unknown event
    types.
    """
    raw = payload.get("affordances", [])
    return frozenset(Affordance(v) for v in raw)


def from_stored(stored: StoredEvent) -> FamilyEvent:
    """Rebuild a Family event from a StoredEvent loaded from the event store."""
    payload = stored.payload
    match stored.event_type:
        case "FamilyDefined":
            return deserialize_or_raise(
                "FamilyDefined",
                lambda: FamilyDefined(
                    family_id=UUID(payload["family_id"]),
                    name=payload["name"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    affordances=_load_affordances(payload),
                ),
            )
        case "FamilyVersioned":
            return deserialize_or_raise(
                "FamilyVersioned",
                lambda: FamilyVersioned(
                    family_id=UUID(payload["family_id"]),
                    version_tag=payload["version_tag"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    affordances=_load_affordances(payload),
                ),
            )
        case "FamilyDeprecated":
            return deserialize_or_raise(
                "FamilyDeprecated",
                lambda: FamilyDeprecated(
                    family_id=UUID(payload["family_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "FamilySettingsSchemaUpdated":
            return deserialize_or_raise(
                "FamilySettingsSchemaUpdated",
                lambda: FamilySettingsSchemaUpdated(
                    family_id=UUID(payload["family_id"]),
                    settings_schema=payload.get("settings_schema"),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "FamilyPresentsAsAdded":
            return deserialize_or_raise(
                "FamilyPresentsAsAdded",
                lambda: FamilyPresentsAsAdded(
                    family_id=UUID(payload["family_id"]),
                    role_id=UUID(payload["role_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
                extra=(ValueError,),
            )
        case "FamilyPresentsAsRemoved":
            return deserialize_or_raise(
                "FamilyPresentsAsRemoved",
                lambda: FamilyPresentsAsRemoved(
                    family_id=UUID(payload["family_id"]),
                    role_id=UUID(payload["role_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
                extra=(ValueError,),
            )
        case _:
            msg = f"Unknown FamilyEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "FamilyDefined",
    "FamilyDeprecated",
    "FamilyEvent",
    "FamilyPresentsAsAdded",
    "FamilyPresentsAsRemoved",
    "FamilySettingsSchemaUpdated",
    "FamilyVersioned",
    "event_type_name",
    "from_stored",
    "to_payload",
]
