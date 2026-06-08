"""Domain events emitted by the Caution aggregate, plus the discriminated union.

Mirrors the locked event-module shape: event classes, discriminated
union, `event_type_name`, `to_payload`, `from_stored`, plus the
polymorphic-target serialize/deserialize helpers.

Three events shipped at BC genesis:

  - `CautionRegistered`  -- genesis (Active); also written as the child
                            genesis on supersession (with parent_id set)
  - `CautionSuperseded`  -- transition on the PARENT stream (Active -> Superseded)
  - `CautionRetired`     -- transition (Active -> Retired); single-stream

`target` travels in the genesis payload as a JSON-friendly dict with a
`"kind"` discriminator (`Asset` or `Procedure`) plus the target's id
field. The aggregate carries the typed `CautionTarget` VO; the
serialise / deserialise helpers bridge typed <-> wire.

`tags` travels in the genesis payload as a sorted `list[str]` (sorted
for deterministic payload bytes), reconstructed into
`frozenset[CautionTag]` by the evolver.

`expires_at` is `datetime | None`; ISO-8601 string in the payload or
`None`.

`authored_by` lives on both the genesis payload (denorm convenience
for projection queries) and the `StoredEvent.principal_id` envelope
(at register time they are equal; at supersede/retire time the
envelope-only convention applies, mirroring 11a-c-1 precedent).

`parent_id` is `None` on top-level registers; set to the
parent's UUID on supersede-child genesis events. Travels in payload.

## Public `serialize_target` / `deserialize_target` helpers

No leading underscore: sanctioned cross-slice helpers consumed by
both the `register_caution` decider (to build payload from typed
CautionTarget) and the evolver (to rebuild typed CautionTarget from
payload). Public-within-the-BC; importing slices reference them
directly. Same convention as Safety's `serialize_binding` /
`deserialize_binding` (events.py public helpers).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.caution.aggregates.caution.state import (
    AssetTarget,
    CautionTarget,
    ProcedureTarget,
)
from cora.infrastructure.event_payload import deserialize_or_raise, deserialize_vo_or_raise
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identity import ActorId

# ---------------------------------------------------------------------------
# CautionTarget serialize / deserialize (public cross-slice helpers)
# ---------------------------------------------------------------------------


def serialize_target(target: CautionTarget) -> dict[str, Any]:
    """Encode a typed CautionTarget to a JSON-friendly dict.

    The dict carries a `"kind"` discriminator plus the target-specific
    id field. Mirrors Safety's `serialize_binding` shape:

      AssetTarget(asset_id=X)        -> {"kind": "Asset",     "id": str(X)}
      ProcedureTarget(procedure_id=Y) -> {"kind": "Procedure", "id": str(Y)}
    """
    match target:
        case AssetTarget(asset_id=asset_id):
            return {"kind": "Asset", "id": str(asset_id)}
        case ProcedureTarget(procedure_id=procedure_id):
            return {"kind": "Procedure", "id": str(procedure_id)}
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(target)


def deserialize_target(payload: dict[str, Any]) -> CautionTarget:
    """Decode a JSON-friendly dict to a typed CautionTarget.

    Dispatches on `payload["kind"]`; raises ValueError on any
    discriminator-or-inner-field violation so a contaminated event
    payload fails loud (KeyError + TypeError wrapped to ValueError so
    callers don't see leaked low-level exceptions). Mirrors Safety's
    `deserialize_binding` defensive shape.
    """

    def _build() -> CautionTarget:
        kind = payload["kind"]
        match kind:
            case "Asset":
                return AssetTarget(asset_id=UUID(payload["id"]))
            case "Procedure":
                return ProcedureTarget(procedure_id=UUID(payload["id"]))
            case _:
                msg = f"Unknown CautionTarget kind: {kind!r}"
                raise ValueError(msg)

    return deserialize_vo_or_raise("CautionTarget", _build)


# ---------------------------------------------------------------------------
# Event classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CautionRegistered:
    """A new caution was registered (or a supersession child was created).

    Initial status implicitly `Active` (event type IS the state-change
    indicator; the genesis evolver hardcodes the mapping). The same
    event class is reused for the supersession child: in that case
    `parent_id` is set to the parent's UUID; for top-level
    registers it is `None`.

    `target` is the typed VO inside the dataclass; `to_payload`
    serialises it via `serialize_target`.

    `tags` is `frozenset[str]` here (already-validated tag strings;
    payload-friendly). The evolver reconstructs `frozenset[CautionTag]`
    via the VO constructor (which re-trims and re-length-checks, but
    that's harmless on already-validated input).

    `authored_by` lives on the payload for denorm convenience; the
    envelope's `principal_id` carries the same value at register time
    (and may differ at supersede-child time if the supersede actor
    is not the original author, which is allowed).
    """

    caution_id: UUID
    target: CautionTarget
    category: str
    severity: str
    text: str
    workaround: str
    tags: frozenset[str]
    authored_by: ActorId
    expires_at: datetime | None
    propagate_to_children: bool
    parent_id: UUID | None
    occurred_at: datetime


@dataclass(frozen=True)
class CautionSuperseded:
    """An Active caution was superseded by a newer one.

    Written to the PARENT caution's stream. Sets `status=Superseded`
    and `superseded_by_caution_id=<child>`. Cross-aggregate atomic
    with the child's genesis `CautionRegistered` via
    `EventStore.append_streams`; mirrors 11a-c-2 `amend_clearance`.

    The superseding actor's id lives ONLY on the envelope
    (`StoredEvent.principal_id`) per 11a-c-1 precedent; no actor
    field on the payload.
    """

    caution_id: UUID
    superseded_by_caution_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class CautionRetired:
    """An Active caution was retired (terminal-good).

    Single-stream transition. `reason` is a closed StrEnum value
    (`Resolved` / `NoLongerApplies` / `WrongTarget`); travels as its
    string value in the payload.

    The retiring actor's id lives ONLY on the envelope.
    """

    caution_id: UUID
    reason: str
    occurred_at: datetime


# Discriminated union of every event the Caution aggregate emits.
CautionEvent = CautionRegistered | CautionSuperseded | CautionRetired


def event_type_name(event: CautionEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: CautionEvent) -> dict[str, Any]:
    """Serialise a Caution event to a JSON-friendly dict for jsonb storage.

    Primitives only: UUIDs become strings, datetimes become ISO-8601
    strings, the typed `CautionTarget` becomes `{kind, id}` via
    `serialize_target`, and `tags` becomes a sorted list (deterministic
    bytes for byte-for-byte idempotency replay).
    """
    match event:
        case CautionRegistered(
            caution_id=caution_id,
            target=target,
            category=category,
            severity=severity,
            text=text,
            workaround=workaround,
            tags=tags,
            authored_by=authored_by,
            expires_at=expires_at,
            propagate_to_children=propagate_to_children,
            parent_id=parent_id,
            occurred_at=occurred_at,
        ):
            return {
                "caution_id": str(caution_id),
                "target": serialize_target(target),
                "category": category,
                "severity": severity,
                "text": text,
                "workaround": workaround,
                "tags": sorted(tags),
                "authored_by": str(authored_by),
                "expires_at": expires_at.isoformat() if expires_at is not None else None,
                "propagate_to_children": propagate_to_children,
                "parent_id": (str(parent_id) if parent_id is not None else None),
                "occurred_at": occurred_at.isoformat(),
            }
        case CautionSuperseded(
            caution_id=caution_id,
            superseded_by_caution_id=superseded_by_caution_id,
            occurred_at=occurred_at,
        ):
            return {
                "caution_id": str(caution_id),
                "superseded_by_caution_id": str(superseded_by_caution_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case CautionRetired(
            caution_id=caution_id,
            reason=reason,
            occurred_at=occurred_at,
        ):
            return {
                "caution_id": str(caution_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> CautionEvent:
    """Rebuild a Caution event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.

    Each arm delegates to `deserialize_or_raise`, which catches
    KeyError / TypeError / AttributeError and re-raises as ValueError
    tagged with the event-type name; mirrors Safety's
    `deserialize_binding` defensive shape (the outer
    `deserialize_target` already does this for the polymorphic target
    subfield, but the arm-level wrap catches every other malformed
    field too).

    Nullable / defaulted fields (`expires_at`, `parent_id`,
    `propagate_to_children`) use `payload.get(...)` so future migrations
    that add new nullable fields remain forward-compat at replay time.
    """
    payload = stored.payload
    match stored.event_type:
        case "CautionRegistered":

            def _build_registered() -> CautionRegistered:
                expires_at_raw = payload.get("expires_at")
                parent_id_raw = payload.get("parent_id")
                return CautionRegistered(
                    caution_id=UUID(payload["caution_id"]),
                    target=deserialize_target(payload["target"]),
                    category=payload["category"],
                    severity=payload["severity"],
                    text=payload["text"],
                    workaround=payload["workaround"],
                    tags=frozenset(payload["tags"]),
                    authored_by=ActorId(UUID(payload["authored_by"])),
                    expires_at=(
                        datetime.fromisoformat(expires_at_raw)
                        if expires_at_raw is not None
                        else None
                    ),
                    propagate_to_children=payload.get("propagate_to_children", False),
                    parent_id=(UUID(parent_id_raw) if parent_id_raw is not None else None),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )

            return deserialize_or_raise("CautionRegistered", _build_registered)
        case "CautionSuperseded":
            return deserialize_or_raise(
                "CautionSuperseded",
                lambda: CautionSuperseded(
                    caution_id=UUID(payload["caution_id"]),
                    superseded_by_caution_id=UUID(payload["superseded_by_caution_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "CautionRetired":
            return deserialize_or_raise(
                "CautionRetired",
                lambda: CautionRetired(
                    caution_id=UUID(payload["caution_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case _:
            msg = f"Unknown CautionEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "CautionEvent",
    "CautionRegistered",
    "CautionRetired",
    "CautionSuperseded",
    "deserialize_target",
    "event_type_name",
    "from_stored",
    "serialize_target",
    "to_payload",
]
