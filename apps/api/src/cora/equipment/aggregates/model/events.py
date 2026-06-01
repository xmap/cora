"""Domain events emitted by the Model aggregate, plus the discriminated union.

Event types: `ModelDefined`, `ModelVersioned`, `ModelDeprecated`,
`ModelFamilyAdded`, `ModelFamilyRemoved`. Status is NOT carried in
event payloads; the event type itself encodes the state change. The
evolver hardcodes the mapping per match arm.

Targeted-mutation pattern: `ModelFamilyAdded` and `ModelFamilyRemoved`
carry a single `family_id` change rather than the whole
`declared_families` set. The operational pattern at a beamline is
"vendor shipped firmware update, one extra Family declared" rather
than wholesale re-author; targeted mutation preserves the operator
intent signal. `ModelVersioned` accepts the wholesale replacement
when a revision genuinely re-authors the catalog entry.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.equipment.aggregates.model.state import (
    Manufacturer,
    ManufacturerIdentifier,
    ManufacturerIdentifierType,
    ManufacturerName,
)
from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent


@dataclass(frozen=True)
class ModelDefined:
    """A new vendor-catalog entry was defined.

    Status is implicit (`Defined`); the evolver sets it. `version_tag`
    is the optional initial revision label (e.g., `rev-A`); `None`
    means no initial label and `Model.version` stays `None` until the
    first `version_model` call.
    """

    model_id: UUID
    name: str
    manufacturer: Manufacturer
    part_number: str
    declared_families: frozenset[UUID]
    occurred_at: datetime
    version_tag: str | None = None


@dataclass(frozen=True)
class ModelVersioned:
    """A model's catalog entry was revised; a new version label was issued.

    Multi-source transition: `Defined | Versioned -> Versioned`.
    REPLACES `name`, `manufacturer`, `part_number`, `declared_families`,
    and `version_tag` wholesale (a new version IS a new declaration).
    Matches Family/Method/Plan/Practice replace-on-version precedent.
    """

    model_id: UUID
    name: str
    manufacturer: Manufacturer
    part_number: str
    declared_families: frozenset[UUID]
    version_tag: str
    occurred_at: datetime


@dataclass(frozen=True)
class ModelDeprecated:
    """A model was marked as no longer recommended for new Assets.

    Multi-source transition: `Defined | Versioned -> Deprecated`.
    Existing Assets with `model_id` pointing at this Model continue
    to function; deprecation is an authoring signal, not a runtime
    gate.
    """

    model_id: UUID
    reason: str
    occurred_at: datetime


@dataclass(frozen=True)
class ModelFamilyAdded:
    """A family was added to the model's `declared_families` set.

    Targeted-mutation event. Strict-not-idempotent: re-adding a
    present family raises `ModelFamilyAlreadyPresentError`. Allowed
    from `Defined | Versioned`; rejected from `Deprecated`.
    """

    model_id: UUID
    family_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class ModelFamilyRemoved:
    """A family was removed from the model's `declared_families` set.

    Targeted-mutation event. Strict-not-idempotent: removing an
    absent family raises `ModelFamilyNotPresentError`. Allowed from
    `Defined | Versioned`; rejected from `Deprecated`. Does NOT
    cascade through existing Assets bound to this Model.
    """

    model_id: UUID
    family_id: UUID
    occurred_at: datetime


# Discriminated union of every event the Model aggregate emits.
ModelEvent = ModelDefined | ModelVersioned | ModelDeprecated | ModelFamilyAdded | ModelFamilyRemoved


def event_type_name(event: ModelEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def _manufacturer_to_payload(manufacturer: Manufacturer) -> dict[str, Any]:
    """Serialize a Manufacturer VO to a JSON-friendly dict.

    `identifier` and `identifier_type` are omitted when both are None
    (the optional pair drops together per the VO's pairing invariant).
    """
    payload: dict[str, Any] = {"name": manufacturer.name.value}
    if manufacturer.identifier is not None and manufacturer.identifier_type is not None:
        payload["identifier"] = manufacturer.identifier.value
        payload["identifier_type"] = manufacturer.identifier_type.value
    return payload


def to_payload(event: ModelEvent) -> dict[str, Any]:
    """Serialize a Model event to a JSON-friendly dict for jsonb storage."""
    match event:
        case ModelDefined(
            model_id=model_id,
            name=name,
            manufacturer=manufacturer,
            part_number=part_number,
            declared_families=declared_families,
            occurred_at=occurred_at,
            version_tag=version_tag,
        ):
            payload: dict[str, Any] = {
                "model_id": str(model_id),
                "name": name,
                "manufacturer": _manufacturer_to_payload(manufacturer),
                "part_number": part_number,
                # Sorted for deterministic payload serialization.
                "declared_families": sorted(str(family_id) for family_id in declared_families),
                "occurred_at": occurred_at.isoformat(),
            }
            if version_tag is not None:
                payload["version_tag"] = version_tag
            return payload
        case ModelVersioned(
            model_id=model_id,
            name=name,
            manufacturer=manufacturer,
            part_number=part_number,
            declared_families=declared_families,
            version_tag=version_tag,
            occurred_at=occurred_at,
        ):
            return {
                "model_id": str(model_id),
                "name": name,
                "manufacturer": _manufacturer_to_payload(manufacturer),
                "part_number": part_number,
                "declared_families": sorted(str(family_id) for family_id in declared_families),
                "version_tag": version_tag,
                "occurred_at": occurred_at.isoformat(),
            }
        case ModelDeprecated(model_id=model_id, reason=reason, occurred_at=occurred_at):
            return {
                "model_id": str(model_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case ModelFamilyAdded(model_id=model_id, family_id=family_id, occurred_at=occurred_at):
            return {
                "model_id": str(model_id),
                "family_id": str(family_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case ModelFamilyRemoved(model_id=model_id, family_id=family_id, occurred_at=occurred_at):
            return {
                "model_id": str(model_id),
                "family_id": str(family_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def _manufacturer_from_payload(payload: dict[str, Any]) -> Manufacturer:
    """Load a Manufacturer VO from a payload's `manufacturer` sub-dict.

    Tolerates: missing `identifier` and `identifier_type` keys (both
    must be absent together or present together per the VO's pairing
    invariant). Unknown `identifier_type` values raise via the
    StrEnum constructor, same fail-loud stance as the top-level
    `from_stored` dispatch on unknown event types.
    """
    name = ManufacturerName(payload["name"])
    raw_identifier = payload.get("identifier")
    raw_identifier_type = payload.get("identifier_type")
    identifier = ManufacturerIdentifier(raw_identifier) if raw_identifier is not None else None
    identifier_type = (
        ManufacturerIdentifierType(raw_identifier_type) if raw_identifier_type is not None else None
    )
    return Manufacturer(name=name, identifier=identifier, identifier_type=identifier_type)


def _declared_families_from_payload(payload: dict[str, Any]) -> frozenset[UUID]:
    """Load the declared_families frozenset from a payload list field."""
    raw = payload.get("declared_families", [])
    return frozenset(UUID(family_id) for family_id in raw)


def from_stored(stored: StoredEvent) -> ModelEvent:
    """Rebuild a Model event from a StoredEvent loaded from the event store."""
    payload = stored.payload
    match stored.event_type:
        case "ModelDefined":
            return deserialize_or_raise(
                "ModelDefined",
                lambda: ModelDefined(
                    model_id=UUID(payload["model_id"]),
                    name=payload["name"],
                    manufacturer=_manufacturer_from_payload(payload["manufacturer"]),
                    part_number=payload["part_number"],
                    declared_families=_declared_families_from_payload(payload),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    version_tag=payload.get("version_tag"),
                ),
            )
        case "ModelVersioned":
            return deserialize_or_raise(
                "ModelVersioned",
                lambda: ModelVersioned(
                    model_id=UUID(payload["model_id"]),
                    name=payload["name"],
                    manufacturer=_manufacturer_from_payload(payload["manufacturer"]),
                    part_number=payload["part_number"],
                    declared_families=_declared_families_from_payload(payload),
                    version_tag=payload["version_tag"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "ModelDeprecated":
            return deserialize_or_raise(
                "ModelDeprecated",
                lambda: ModelDeprecated(
                    model_id=UUID(payload["model_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "ModelFamilyAdded":
            return deserialize_or_raise(
                "ModelFamilyAdded",
                lambda: ModelFamilyAdded(
                    model_id=UUID(payload["model_id"]),
                    family_id=UUID(payload["family_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "ModelFamilyRemoved":
            return deserialize_or_raise(
                "ModelFamilyRemoved",
                lambda: ModelFamilyRemoved(
                    model_id=UUID(payload["model_id"]),
                    family_id=UUID(payload["family_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case _:
            msg = f"Unknown ModelEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "ModelDefined",
    "ModelDeprecated",
    "ModelEvent",
    "ModelFamilyAdded",
    "ModelFamilyRemoved",
    "ModelVersioned",
    "event_type_name",
    "from_stored",
    "to_payload",
]
