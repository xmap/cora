"""Domain events emitted by the Assembly aggregate, plus the discriminated union.

Mirrors the Mount event-module shape (see `aggregates/mount/events.py`):
event classes as frozen dataclasses, discriminated union,
`event_type_name`, `to_payload`, `from_stored` with per-arm
KeyError / TypeError / AttributeError wrapping into tagged
ValueError per `project_from_stored_wrap_convention`.

Event catalog (3, scaffold-only):
  - `AssemblyDefined`     (genesis; carries the canonical structural
                           fields + content_hash + drawing + version)
  - `AssemblyVersioned`   (new revision snapshot on the same stream;
                           append-only mirroring CalibrationRevision)
  - `AssemblyDeprecated`  (terminal lifecycle)

`AssemblyInstantiated` is a fourth event in the design memo but
lives on a separate `assembly_instantiation` stream and ships with
the `instantiate_assembly` slice. Keeping it out of this scaffold
module keeps the discriminated union focused on the main-stream
events that the Assembly evolver folds.

## Payload conventions for Assembly

`status` is NOT carried in the payload: the event TYPE encodes the
state change (`AssemblyDefined -> Defined`, `AssemblyVersioned ->
Versioned`, `AssemblyDeprecated -> Deprecated`). Same precedent as
Mount / Frame / Asset / Family.

`content_hash` IS carried in `AssemblyDefined` and `AssemblyVersioned`
payloads (the hash is computed at write time and embedded for
audit-self-containment). `content_hash` is absent from
`AssemblyDeprecated` because deprecation does not change content
identity; the prior hash stays the structural fingerprint.

`required_slots` and `required_wires` serialize as sorted lists of
dicts / 4-tuples; deserialization reconstructs frozensets via the
VO constructors (which re-run __post_init__ validation, catching
on-disk corruption at load time).

`drawing` is carried optionally on `AssemblyDefined` and
`AssemblyVersioned` (the drawing may itself be re-attested at
version time). Placement and Drawing payload codecs are imported
from the shared `_placement` / `_drawing` modules to honor the
codec-helper-duplication anti-hook flagged in
`project_mount_frame_design` Watch items.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.equipment.aggregates._drawing import (
    Drawing,
    drawing_from_payload,
    drawing_to_payload,
)
from cora.equipment.aggregates._placement import (
    placement_from_payload,
    placement_to_payload,
)
from cora.equipment.aggregates.assembly.state import (
    AssemblyName,
    SlotCardinality,
    SlotName,
    TemplateSlot,
    TemplateWire,
)
from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent


def _template_slot_to_payload(slot: TemplateSlot) -> dict[str, Any]:
    return {
        "slot_name": slot.slot_name.value,
        "required_family_ids": sorted(str(f) for f in slot.required_family_ids),
        "cardinality": slot.cardinality.value,
        "default_settings": slot.default_settings,
        "default_placement": (
            placement_to_payload(slot.default_placement)
            if slot.default_placement is not None
            else None
        ),
    }


def _template_slot_from_payload(payload: dict[str, Any]) -> TemplateSlot:
    raw_placement = payload.get("default_placement")
    return TemplateSlot(
        slot_name=SlotName(payload["slot_name"]),
        required_family_ids=frozenset(UUID(f) for f in payload["required_family_ids"]),
        cardinality=SlotCardinality(payload["cardinality"]),
        default_settings=payload.get("default_settings"),
        default_placement=(
            placement_from_payload(raw_placement) if raw_placement is not None else None
        ),
    )


def _template_wire_to_payload(wire: TemplateWire) -> dict[str, Any]:
    return {
        "source_slot_name": wire.source_slot_name,
        "source_port_name": wire.source_port_name,
        "target_slot_name": wire.target_slot_name,
        "target_port_name": wire.target_port_name,
    }


def _template_wire_from_payload(payload: dict[str, Any]) -> TemplateWire:
    return TemplateWire(
        source_slot_name=payload["source_slot_name"],
        source_port_name=payload["source_port_name"],
        target_slot_name=payload["target_slot_name"],
        target_port_name=payload["target_port_name"],
    )


@dataclass(frozen=True)
class AssemblyDefined:
    """A new Assembly was defined.

    Genesis event. Carries the full canonical structural subset
    (name, presents_as_family_id, required_slots, required_wires,
    parameter_overrides_schema) plus the computed content_hash and
    the operator-curatorial fields (drawing, version).

    Status is implicit (`Defined`); the evolver sets it from the
    event type.
    """

    assembly_id: UUID
    name: AssemblyName
    presents_as_family_id: UUID
    required_slots: frozenset[TemplateSlot]
    required_wires: frozenset[TemplateWire]
    parameter_overrides_schema: dict[str, Any] | None
    drawing: Drawing | None
    version: str | None
    content_hash: str
    occurred_at: datetime


@dataclass(frozen=True)
class AssemblyVersioned:
    """A new revision snapshot of the Assembly was published.

    Replace-on-version: the payload carries the FULL canonical
    structural subset (not a diff), the recomputed content_hash, and
    the new version label. Multiple AssemblyVersioned events on the
    same stream are permitted; each is a fresh snapshot under the
    same aggregate id.

    Re-attestation with identical structural payload (same
    content_hash) is allowed: it surfaces a refreshed version label
    or drawing while pinning that no structural change happened.
    """

    assembly_id: UUID
    name: AssemblyName
    presents_as_family_id: UUID
    required_slots: frozenset[TemplateSlot]
    required_wires: frozenset[TemplateWire]
    parameter_overrides_schema: dict[str, Any] | None
    drawing: Drawing | None
    version: str | None
    content_hash: str
    previous_content_hash: str | None
    occurred_at: datetime


@dataclass(frozen=True)
class AssemblyDeprecated:
    """The Assembly was retired from active use.

    Terminal lifecycle transition. Subsequent `instantiate_assembly`
    calls reject. New revisions must fork via `define_assembly` with
    a fresh id.

    `reason` is operator-supplied free text (audit-log breadcrumb).
    """

    assembly_id: UUID
    reason: str
    occurred_at: datetime


AssemblyEvent = AssemblyDefined | AssemblyVersioned | AssemblyDeprecated


def event_type_name(event: AssemblyEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: AssemblyEvent) -> dict[str, Any]:
    """Serialize an Assembly event to a JSON-friendly dict for jsonb storage."""
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
            occurred_at=occurred_at,
        ):
            return {
                "assembly_id": str(assembly_id),
                "name": name.value,
                "presents_as_family_id": str(presents_as_family_id),
                "required_slots": sorted(
                    (_template_slot_to_payload(s) for s in required_slots),
                    key=lambda d: d["slot_name"],
                ),
                "required_wires": sorted(
                    (_template_wire_to_payload(w) for w in required_wires),
                    key=lambda d: (
                        d["source_slot_name"],
                        d["source_port_name"],
                        d["target_slot_name"],
                        d["target_port_name"],
                    ),
                ),
                "parameter_overrides_schema": parameter_overrides_schema,
                "drawing": (drawing_to_payload(drawing) if drawing is not None else None),
                "version": version,
                "content_hash": content_hash,
                "occurred_at": occurred_at.isoformat(),
            }
        case AssemblyVersioned(
            assembly_id=assembly_id,
            name=name,
            presents_as_family_id=presents_as_family_id,
            required_slots=required_slots,
            required_wires=required_wires,
            parameter_overrides_schema=parameter_overrides_schema,
            drawing=drawing,
            version=version,
            content_hash=content_hash,
            previous_content_hash=previous_content_hash,
            occurred_at=occurred_at,
        ):
            return {
                "assembly_id": str(assembly_id),
                "name": name.value,
                "presents_as_family_id": str(presents_as_family_id),
                "required_slots": sorted(
                    (_template_slot_to_payload(s) for s in required_slots),
                    key=lambda d: d["slot_name"],
                ),
                "required_wires": sorted(
                    (_template_wire_to_payload(w) for w in required_wires),
                    key=lambda d: (
                        d["source_slot_name"],
                        d["source_port_name"],
                        d["target_slot_name"],
                        d["target_port_name"],
                    ),
                ),
                "parameter_overrides_schema": parameter_overrides_schema,
                "drawing": (drawing_to_payload(drawing) if drawing is not None else None),
                "version": version,
                "content_hash": content_hash,
                "previous_content_hash": previous_content_hash,
                "occurred_at": occurred_at.isoformat(),
            }
        case AssemblyDeprecated(
            assembly_id=assembly_id,
            reason=reason,
            occurred_at=occurred_at,
        ):
            return {
                "assembly_id": str(assembly_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> AssemblyEvent:
    """Rebuild an Assembly event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.
    Per-arm `(KeyError, TypeError, AttributeError)` wrap into tagged
    ValueError per `project_from_stored_wrap_convention`.
    """
    payload = stored.payload
    match stored.event_type:
        case "AssemblyDefined":

            def _build_defined() -> AssemblyDefined:
                raw_drawing = payload.get("drawing")
                return AssemblyDefined(
                    assembly_id=UUID(payload["assembly_id"]),
                    name=AssemblyName(payload["name"]),
                    presents_as_family_id=UUID(payload["presents_as_family_id"]),
                    required_slots=frozenset(
                        _template_slot_from_payload(s) for s in payload["required_slots"]
                    ),
                    required_wires=frozenset(
                        _template_wire_from_payload(w) for w in payload["required_wires"]
                    ),
                    parameter_overrides_schema=payload.get("parameter_overrides_schema"),
                    drawing=(
                        drawing_from_payload(raw_drawing) if raw_drawing is not None else None
                    ),
                    version=payload.get("version"),
                    content_hash=payload["content_hash"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )

            return deserialize_or_raise("AssemblyDefined", _build_defined)
        case "AssemblyVersioned":

            def _build_versioned() -> AssemblyVersioned:
                raw_drawing = payload.get("drawing")
                return AssemblyVersioned(
                    assembly_id=UUID(payload["assembly_id"]),
                    name=AssemblyName(payload["name"]),
                    presents_as_family_id=UUID(payload["presents_as_family_id"]),
                    required_slots=frozenset(
                        _template_slot_from_payload(s) for s in payload["required_slots"]
                    ),
                    required_wires=frozenset(
                        _template_wire_from_payload(w) for w in payload["required_wires"]
                    ),
                    parameter_overrides_schema=payload.get("parameter_overrides_schema"),
                    drawing=(
                        drawing_from_payload(raw_drawing) if raw_drawing is not None else None
                    ),
                    version=payload.get("version"),
                    content_hash=payload["content_hash"],
                    previous_content_hash=payload.get("previous_content_hash"),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )

            return deserialize_or_raise("AssemblyVersioned", _build_versioned)
        case "AssemblyDeprecated":
            return deserialize_or_raise(
                "AssemblyDeprecated",
                lambda: AssemblyDeprecated(
                    assembly_id=UUID(payload["assembly_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case _:
            msg = f"Unknown AssemblyEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "AssemblyDefined",
    "AssemblyDeprecated",
    "AssemblyEvent",
    "AssemblyVersioned",
    "event_type_name",
    "from_stored",
    "to_payload",
]
