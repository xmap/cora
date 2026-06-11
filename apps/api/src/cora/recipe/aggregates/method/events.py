"""Domain events emitted by the Method aggregate, plus the discriminated union.

Mirrors the locked event-module shape: event classes, discriminated
union, `event_type_name`, `to_payload`, `from_stored`. The
persistence-envelope construction (`NewEvent`) lives at
`cora.infrastructure.event_envelope.to_new_event`.

`MethodDefined` is the genesis; `MethodVersioned` and
`MethodDeprecated` cover the `Defined → Versioned → Deprecated`
lifecycle. MethodVersioned carries an operator-supplied
`version_tag` (free-text label like "v2" or "2026-Q3"; precedent:
AssetRelocated.reason and FamilyVersioned). MethodDeprecated
carries no extra fields. Mirrors Family's transition shape from
the Equipment BC.

## Payload conventions

`needed_family_ids` is stored as `tuple[UUID, ...]` here (events carry
primitives per CONTRIBUTING.md; tuples JSON-serialize cleanly and are
immutable so the fold step can't accidentally alias a mutable list
into state). The evolver converts to `frozenset` when folding into
Method state. The values are sorted by string form in `to_payload` so
the same logical family set serializes deterministically — important
for hash-based idempotency and any future content-addressed lookup.
Same precedent as Trust's PolicyDefined.

Status is NOT carried in event payloads — the event type itself
encodes the state change (for example, `MethodVersioned ->
status=VERSIONED`). The evolver hardcodes the mapping per match
arm. Same precedent as `FamilyDefined → DEFINED` /
`SubjectMounted → MOUNTED`.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent


@dataclass(frozen=True)
class MethodDefined:
    """A new abstract technique-class recipe was defined.

    Status is implicit (`Defined`) — the evolver sets it.

    `needed_family_ids` carries the Family ids the Method
    requires; eventual-consistency stance, no cross-aggregate
    verification.

    `needed_supplies` (additive evolution) carries Supply
    KIND strings the Method requires, NOT Supply instance ids.
    Older events without the field fold via `payload.get("needed_supplies", ())`. The
    values are sorted by string form in `to_payload` for persistence
    determinism (matches needed_family_ids). Default empty tuple.

    `needed_assembly_ids` (additive evolution) carries Assembly UUIDs
    the Method requires (Equipment BC cross-aggregate ref). Empty
    means "no specific composition blueprint required, just N Assets
    of the needed_family_ids Families." Older events without the
    field fold via `payload.get("needed_assembly_ids", ())`. Values are
    sorted by string form in `to_payload` for persistence determinism
    (matches needed_family_ids). Default empty tuple.
    """

    method_id: UUID
    name: str
    needed_family_ids: tuple[UUID, ...]
    occurred_at: datetime
    needed_supplies: tuple[str, ...] = ()
    # additive evolution: capability_id points to the
    # universal Capability template this Method realizes. Defaults
    # None for older events without the field (additive-state pattern); current decider
    # rejects None at define_method time per Pattern P.
    capability_id: UUID | None = None
    # additive evolution: needed_assembly_ids declares the Method's
    # cross-BC dependency on Equipment Assemblies (composition
    # blueprints). Defaults empty for additive-state forward-compat.
    needed_assembly_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True)
class MethodVersioned:
    """A method's definition was revised; a new version label was issued.

    Multi-source transition: `Defined | Versioned -> Versioned`. The
    evolver sets status=VERSIONED and updates state.version to the
    new tag. The decider's source-state guard enforces that
    Deprecated methods can't be re-versioned.

    `version_tag` is operator-supplied free text (1-50 chars,
    validated at API boundary AND in the decider). Could be semver
    ("v2.1.0"), date-stamped ("2026-Q3"), or anything else
    institution-specific. Not a VO; same precedent as
    AssetRelocated.reason and FamilyVersioned.

    `content_hash` is the SHA-256 of the canonical body bytes for this
    Method revision's content subset (`name + parameters_schema +
    capability_id + needed_family_ids + needed_supplies +
    needed_assembly_ids`), captured by the decider per the
    non-determinism principle. 64-char lowercase
    hex. The same content emitted twice (re-attestation) produces the
    same hash, which is the intended equivalence-detection semantic
    (Bazel input/output split pattern). Pre-rollout legacy events
    have no payload field; `from_stored` returns None there, matching
    Method state's `content_hash: str | None` shape per
    [[project_content_addressed_identity_design]] pre-rollout fold.
    The dataclass default of None exists only for legacy-event
    reconstruction; current deciders always supply a concrete hash.
    """

    method_id: UUID
    version_tag: str
    occurred_at: datetime
    content_hash: str | None = None


@dataclass(frozen=True)
class MethodDeprecated:
    """A method was marked as no longer recommended for new Plans.

    Multi-source transition: `Defined | Versioned -> Deprecated`. The
    evolver sets status=DEPRECATED; `version` is preserved (the
    historical label of when the method was last revised before being
    deprecated remains visible).

    Existing Plans / Practices that reference this Method are NOT
    automatically invalidated. Deprecation is advisory at the BC
    layer; future Plan-side enrichment may surface a warning at
    bind-time when referencing a deprecated Method.
    """

    method_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class MethodParametersSchemaUpdated:
    """The Method's parameter-shape contract was updated.

    `parameters_schema` is the new JSON Schema (Draft 2020-12,
    constrained subset) replacing whatever was on state. None clears
    the contract (Method declares no parameter shape; downstream Plans
    and Runs accept any dict). Schema-changes do NOT auto-revalidate
    pre-existing Plans / Runs; existing Plans preserve historical
    validity (locked, mirrors Family.settings_schema posture).

    Validator (`parameters_validation.validate_parameters_schema`)
    runs at decide time so persisted payloads are always well-formed.
    Mirrors `FamilySettingsSchemaUpdated` shape from Equipment BC.

    Status is NOT carried — schema updates are orthogonal to lifecycle
    (Defined / Versioned / Deprecated all permit schema updates).
    """

    method_id: UUID
    parameters_schema: dict[str, Any] | None
    occurred_at: datetime


@dataclass(frozen=True)
class MethodRequiredRoleAdded:
    """A positional role slot was declared on the Method.

    Part of the positional role-tagging workstream (IEC 81346
    Function aspect). Strict-not-idempotent: a duplicate role_name
    surfaces as `MethodRoleNameAlreadyDeclaredError` rather than
    silently no-opping. Restricted to Methods in `Defined` status.

    ## Additive evolution (Layer 3 sub-slice 3D)

    `role_kind` is the additive field landing in 3D per memo Lock 5:
    the global Role contract this slot targets (federation-portable
    path). KEPT alongside the slice-1 `family_id` field for the XOR
    invariant; exactly one is set per instance. Defaults to None
    here so streams predating 3D rebuild as family_id-only
    RoleRequirements without needing payload backfill.

    `required_ports` is stored as a `tuple[dict[str, Any], ...]` in
    the payload (each dict = {port_name, direction, signal_type})
    for JSON-friendly persistence; the evolver converts to
    `frozenset[PortRequirement]` when folding into state. Sorted by
    `(port_name, direction)` for deterministic payload bytes.
    """

    method_id: UUID
    role_name: str
    family_id: UUID | None
    required_ports: tuple[dict[str, Any], ...]
    optional: bool
    occurred_at: datetime
    role_kind: UUID | None = None


@dataclass(frozen=True)
class MethodRequiredRoleRemoved:
    """A positional role slot was removed from the Method.

    Mirror of `MethodRequiredRoleAdded`. Strict-not-idempotent:
    removing a role_name not present surfaces as
    `MethodRoleNameNotFoundError`. Same lifecycle restriction
    (Defined-only). Payload carries only the `role_name` (the
    structural identity of the role within the Method scope); the
    full `RoleRequirement` is reconstructed by removing the matching
    entry from state during folding.
    """

    method_id: UUID
    role_name: str
    occurred_at: datetime


# Discriminated union of every event the Method aggregate emits.
MethodEvent = (
    MethodDefined
    | MethodVersioned
    | MethodDeprecated
    | MethodParametersSchemaUpdated
    | MethodRequiredRoleAdded
    | MethodRequiredRoleRemoved
)


def event_type_name(event: MethodEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: MethodEvent) -> dict[str, Any]:
    """Serialize a Method event to a JSON-friendly dict for jsonb storage.

    `needed_family_ids` is sorted by UUID string form so the
    persisted payload is deterministic — same logical family
    set, same payload bytes, same idempotency hash. Same precedent
    as Trust's PolicyDefined.
    """
    match event:
        case MethodDefined(
            method_id=method_id,
            name=name,
            needed_family_ids=needed_family_ids,
            needed_supplies=needed_supplies,
            capability_id=capability_id,
            needed_assembly_ids=needed_assembly_ids,
            occurred_at=occurred_at,
        ):
            return {
                "method_id": str(method_id),
                "name": name,
                "needed_family_ids": sorted(str(c) for c in needed_family_ids),
                # additive: kind strings sorted lexically for
                # deterministic payload bytes (matches needed_family_ids
                # convention; same idempotency-hash story).
                "needed_supplies": sorted(needed_supplies),
                # additive: capability_id is None on older events
                # without the field; the from_stored fallback to None
                # preserves legacy stream replay.
                "capability_id": (str(capability_id) if capability_id is not None else None),
                # additive: Assembly UUIDs sorted lexically by string
                # form (matches needed_family_ids convention).
                "needed_assembly_ids": sorted(str(a) for a in needed_assembly_ids),
                "occurred_at": occurred_at.isoformat(),
            }
        case MethodVersioned(
            method_id=method_id,
            version_tag=version_tag,
            occurred_at=occurred_at,
            content_hash=content_hash,
        ):
            payload: dict[str, Any] = {
                "method_id": str(method_id),
                "version_tag": version_tag,
                "occurred_at": occurred_at.isoformat(),
            }
            if content_hash is not None:
                payload["content_hash"] = content_hash
            return payload
        case MethodDeprecated(method_id=method_id, occurred_at=occurred_at):
            return {
                "method_id": str(method_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case MethodParametersSchemaUpdated(
            method_id=method_id,
            parameters_schema=parameters_schema,
            occurred_at=occurred_at,
        ):
            return {
                "method_id": str(method_id),
                "parameters_schema": parameters_schema,
                "occurred_at": occurred_at.isoformat(),
            }
        case MethodRequiredRoleAdded(
            method_id=method_id,
            role_name=role_name,
            family_id=family_id,
            required_ports=required_ports,
            optional=optional,
            occurred_at=occurred_at,
            role_kind=role_kind,
        ):
            # required_ports comes in already as tuple[dict, ...] from
            # the decider; sort by (port_name, direction) for byte-
            # stable persistence regardless of insertion order.
            #
            # role_kind + family_id are XOR-bound on the VO; both
            # rendered as str-or-null per the additive-evolution
            # convention (sparse legacy payloads round-trip cleanly
            # via from_stored's payload.get with default None).
            payload: dict[str, Any] = {
                "method_id": str(method_id),
                "role_name": role_name,
                "family_id": str(family_id) if family_id is not None else None,
                "required_ports": sorted(
                    required_ports,
                    key=lambda p: (p["port_name"], p["direction"]),
                ),
                "optional": optional,
                "occurred_at": occurred_at.isoformat(),
            }
            # Conditional render: role_kind only appears in the
            # payload when non-None. Preserves legacy payload byte
            # stability for streams predating 3D (no spurious
            # `"role_kind": null` key in the on-disk bytes).
            if role_kind is not None:
                payload["role_kind"] = str(role_kind)
            return payload
        case MethodRequiredRoleRemoved(
            method_id=method_id,
            role_name=role_name,
            occurred_at=occurred_at,
        ):
            return {
                "method_id": str(method_id),
                "role_name": role_name,
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> MethodEvent:
    """Rebuild a Method event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.
    """
    payload = stored.payload
    match stored.event_type:
        case "MethodDefined":

            def _build_method_defined() -> MethodDefined:
                capability_raw = payload.get("capability_id")
                return MethodDefined(
                    method_id=UUID(payload["method_id"]),
                    name=payload["name"],
                    needed_family_ids=tuple(UUID(c) for c in payload["needed_family_ids"]),
                    # forward-compat: older MethodDefined
                    # payloads have no needed_supplies key; default to empty
                    # tuple. Additive-evolution pattern.
                    needed_supplies=tuple(payload.get("needed_supplies", ())),
                    # forward-compat: older MethodDefined payloads
                    # have no capability_id key; default to None. Currently
                    # the decider enforces non-None at write time.
                    capability_id=(UUID(capability_raw) if capability_raw is not None else None),
                    # forward-compat: older MethodDefined payloads
                    # have no needed_assembly_ids key; default to empty tuple.
                    # Additive-evolution pattern.
                    needed_assembly_ids=tuple(
                        UUID(a) for a in payload.get("needed_assembly_ids", ())
                    ),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )

            return deserialize_or_raise("MethodDefined", _build_method_defined)
        case "MethodVersioned":
            return deserialize_or_raise(
                "MethodVersioned",
                lambda: MethodVersioned(
                    method_id=UUID(payload["method_id"]),
                    version_tag=payload["version_tag"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    # forward-compat: pre-rollout MethodVersioned payloads
                    # have no content_hash; default to None. Additive-
                    # evolution pattern per [[project_content_addressed
                    # _identity_design]] watch item on pre-rollout fold.
                    content_hash=payload.get("content_hash"),
                ),
            )
        case "MethodDeprecated":
            return deserialize_or_raise(
                "MethodDeprecated",
                lambda: MethodDeprecated(
                    method_id=UUID(payload["method_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "MethodParametersSchemaUpdated":
            return deserialize_or_raise(
                "MethodParametersSchemaUpdated",
                lambda: MethodParametersSchemaUpdated(
                    method_id=UUID(payload["method_id"]),
                    parameters_schema=payload["parameters_schema"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "MethodRequiredRoleAdded":

            def _build_method_required_role_added() -> MethodRequiredRoleAdded:
                # Both fields are XOR-bound on the VO but the payload
                # may legitimately carry either: legacy (pre-3D)
                # payloads have family_id only; 3D-era role_kind
                # payloads have role_kind only. Defaults via .get
                # preserve round-trip.
                raw_family = payload.get("family_id")
                raw_role_kind = payload.get("role_kind")
                return MethodRequiredRoleAdded(
                    method_id=UUID(payload["method_id"]),
                    role_name=payload["role_name"],
                    family_id=UUID(raw_family) if raw_family is not None else None,
                    required_ports=tuple(payload.get("required_ports", ())),
                    optional=bool(payload.get("optional", False)),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    role_kind=UUID(raw_role_kind) if raw_role_kind is not None else None,
                )

            return deserialize_or_raise(
                "MethodRequiredRoleAdded",
                _build_method_required_role_added,
                extra=(ValueError,),
            )
        case "MethodRequiredRoleRemoved":
            return deserialize_or_raise(
                "MethodRequiredRoleRemoved",
                lambda: MethodRequiredRoleRemoved(
                    method_id=UUID(payload["method_id"]),
                    role_name=payload["role_name"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case _:
            msg = f"Unknown MethodEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "MethodDefined",
    "MethodDeprecated",
    "MethodEvent",
    "MethodParametersSchemaUpdated",
    "MethodRequiredRoleAdded",
    "MethodRequiredRoleRemoved",
    "MethodVersioned",
    "event_type_name",
    "from_stored",
    "to_payload",
]
