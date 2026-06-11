"""Domain events emitted by the Capability aggregate, plus the discriminated union.

New aggregate (no rename history → no dual-match arms). Events:

  - CapabilityDefined (genesis)
  - CapabilityVersioned (declarative replacement at new version)
  - CapabilityDeprecated (terminal state; carries optional
                          replaced_by pointer per LOINC `MAP_TO`)

Status is NOT carried in event payloads — the event type itself
encodes the state change. Same precedent as `FamilyStatus` in
[[project-family-affordance-design]].

## Replacement semantics

Per [[project-capability-aggregate-design]] and the Pattern P lock
in [[project-family-affordance-design]]: a new version IS a new
declaration. CapabilityVersioned carries the FULL declarative
contract (required_affordances, parameters_schema, executor_shapes)
— every field REPLACES the prior value wholesale. No diff/merge
semantics. Matches Method/Plan/Practice/Family replace-on-version
precedent.

## Payload field ordering

Affordances and executor_shapes serialize as sorted lists of enum
string values for deterministic payload comparison. `replaced_by_
capability_id` serializes as string-or-None.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.equipment.aggregates.family import Affordance
from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent
from cora.recipe.aggregates.capability.executor_shape import ExecutorShape


@dataclass(frozen=True)
class CapabilityDefined:
    """A new universal Capability template was defined.

    Status is implicit (`Defined`) — the evolver sets it. All
    declarative fields are present in the genesis payload.
    """

    capability_id: UUID
    code: str
    name: str
    required_affordances: frozenset[Affordance]
    executor_shapes: frozenset[ExecutorShape]
    occurred_at: datetime
    description: str | None = None
    parameters_schema: dict[str, Any] | None = None


@dataclass(frozen=True)
class CapabilityVersioned:
    """A Capability's declarative contract was revised; a new version label was issued.

    Multi-source transition: `Defined | Versioned -> Versioned`. The
    full declarative contract REPLACES wholesale (a new version IS a
    new declaration per Pattern P).
    """

    capability_id: UUID
    version_tag: str
    required_affordances: frozenset[Affordance]
    executor_shapes: frozenset[ExecutorShape]
    occurred_at: datetime
    description: str | None = None
    parameters_schema: dict[str, Any] | None = None


@dataclass(frozen=True)
class CapabilityDeprecated:
    """A Capability was marked as no longer recommended for new bindings.

    Multi-source transition: `Defined | Versioned -> Deprecated`.
    `replaced_by_capability_id` is an optional pointer to a successor
    Capability (LOINC `MAP_TO` precedent); None means deprecated-
    without-replacement. Existing Methods/Procedures that reference
    this Capability are NOT automatically invalidated (advisory at BC
    layer).
    """

    capability_id: UUID
    occurred_at: datetime
    replaced_by_capability_id: UUID | None = None


@dataclass(frozen=True)
class CapabilitySuggestedRolesUpdated:
    """The Capability's `suggested_role_ids` set was authored.

    Wholesale-replace semantic (Pattern P; matches the editorial
    set-edit pattern, NOT the add-pair / remove-pair pattern used
    by Family.presents_as). The payload carries the FULL new set;
    the evolver replaces state.suggested_role_ids wholesale.

    Per memo Lock 10: documentation-only. The handler validates that
    every role_id resolves via `Kernel.role_lookup.lookup` (parallel
    `asyncio.gather` edge-load) so callers see `RoleNotFoundError`
    rather than a satisfaction-side mis-record; no decider gates on
    the set membership itself.

    Restricted to Defined + Versioned status by the decider
    (`CapabilityCannotUpdateSuggestedRolesError`).
    """

    capability_id: UUID
    suggested_role_ids: frozenset[UUID]
    occurred_at: datetime


CapabilityEvent = (
    CapabilityDefined | CapabilityVersioned | CapabilityDeprecated | CapabilitySuggestedRolesUpdated
)


def event_type_name(event: CapabilityEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: CapabilityEvent) -> dict[str, Any]:
    """Serialize a Capability event to a JSON-friendly dict for jsonb storage.

    UUIDs become strings, datetimes ISO-8601, frozensets sorted lists.
    """
    match event:
        case CapabilityDefined(
            capability_id=capability_id,
            code=code,
            name=name,
            required_affordances=required_affordances,
            executor_shapes=executor_shapes,
            description=description,
            parameters_schema=parameters_schema,
            occurred_at=occurred_at,
        ):
            return {
                "capability_id": str(capability_id),
                "code": code,
                "name": name,
                "description": description,
                "required_affordances": sorted(a.value for a in required_affordances),
                "executor_shapes": sorted(s.value for s in executor_shapes),
                "parameters_schema": parameters_schema,
                "occurred_at": occurred_at.isoformat(),
            }
        case CapabilityVersioned(
            capability_id=capability_id,
            version_tag=version_tag,
            required_affordances=required_affordances,
            executor_shapes=executor_shapes,
            description=description,
            parameters_schema=parameters_schema,
            occurred_at=occurred_at,
        ):
            return {
                "capability_id": str(capability_id),
                "version_tag": version_tag,
                "description": description,
                "required_affordances": sorted(a.value for a in required_affordances),
                "executor_shapes": sorted(s.value for s in executor_shapes),
                "parameters_schema": parameters_schema,
                "occurred_at": occurred_at.isoformat(),
            }
        case CapabilityDeprecated(
            capability_id=capability_id,
            replaced_by_capability_id=replaced_by_capability_id,
            occurred_at=occurred_at,
        ):
            return {
                "capability_id": str(capability_id),
                "replaced_by_capability_id": (
                    str(replaced_by_capability_id)
                    if replaced_by_capability_id is not None
                    else None
                ),
                "occurred_at": occurred_at.isoformat(),
            }
        case CapabilitySuggestedRolesUpdated(
            capability_id=capability_id,
            suggested_role_ids=suggested_role_ids,
            occurred_at=occurred_at,
        ):
            return {
                "capability_id": str(capability_id),
                # Sorted UUID strings for deterministic payload bytes
                # (Pattern P set-edit wholesale-replace semantic;
                # mirrors required_affordances + executor_shapes
                # sort convention).
                "suggested_role_ids": sorted(str(r) for r in suggested_role_ids),
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def _load_affordances(payload: dict[str, Any]) -> frozenset[Affordance]:
    """Load required_affordances from payload's list field.

    Tolerates missing key (additive-state default empty), empty list,
    or list of valid Affordance enum value strings. Unknown values
    raise ValueError via the StrEnum constructor (fail-loud).
    """
    raw = payload.get("required_affordances", [])
    return frozenset(Affordance(v) for v in raw)


def _load_executor_shapes(payload: dict[str, Any]) -> frozenset[ExecutorShape]:
    """Load executor_shapes from payload's list field.

    Same fail-loud stance as `_load_affordances`. Note: the evolver
    can fold an empty set here (additive-state default), but the
    decider rejects empty input at write time per Pattern P.
    """
    raw = payload.get("executor_shapes", [])
    return frozenset(ExecutorShape(v) for v in raw)


def from_stored(stored: StoredEvent) -> CapabilityEvent:
    """Rebuild a Capability event from a StoredEvent loaded from the event store.

    Single-match arms, no legacy/dual-match (this aggregate is new,
    not a rename of a prior aggregate).
    """
    payload = stored.payload
    match stored.event_type:
        case "CapabilityDefined":
            return deserialize_or_raise(
                "CapabilityDefined",
                lambda: CapabilityDefined(
                    capability_id=UUID(payload["capability_id"]),
                    code=payload["code"],
                    name=payload["name"],
                    description=payload.get("description"),
                    required_affordances=_load_affordances(payload),
                    executor_shapes=_load_executor_shapes(payload),
                    parameters_schema=payload.get("parameters_schema"),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "CapabilityVersioned":
            return deserialize_or_raise(
                "CapabilityVersioned",
                lambda: CapabilityVersioned(
                    capability_id=UUID(payload["capability_id"]),
                    version_tag=payload["version_tag"],
                    description=payload.get("description"),
                    required_affordances=_load_affordances(payload),
                    executor_shapes=_load_executor_shapes(payload),
                    parameters_schema=payload.get("parameters_schema"),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "CapabilityDeprecated":

            def _build_capability_deprecated() -> CapabilityDeprecated:
                replaced_raw = payload.get("replaced_by_capability_id")
                return CapabilityDeprecated(
                    capability_id=UUID(payload["capability_id"]),
                    replaced_by_capability_id=(
                        UUID(replaced_raw) if replaced_raw is not None else None
                    ),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )

            return deserialize_or_raise("CapabilityDeprecated", _build_capability_deprecated)
        case "CapabilitySuggestedRolesUpdated":

            def _build_capability_suggested_role_ids_updated() -> CapabilitySuggestedRolesUpdated:
                return CapabilitySuggestedRolesUpdated(
                    capability_id=UUID(payload["capability_id"]),
                    suggested_role_ids=frozenset(
                        UUID(s) for s in payload.get("suggested_role_ids", [])
                    ),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )

            return deserialize_or_raise(
                "CapabilitySuggestedRolesUpdated",
                _build_capability_suggested_role_ids_updated,
                extra=(ValueError,),
            )
        case _:
            msg = f"Unknown CapabilityEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "CapabilityDefined",
    "CapabilityDeprecated",
    "CapabilityEvent",
    "CapabilitySuggestedRolesUpdated",
    "CapabilityVersioned",
    "event_type_name",
    "from_stored",
    "to_payload",
]
