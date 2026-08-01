"""Domain events emitted by the Plan aggregate, plus the discriminated union.

Mirrors the locked event-module shape: event classes, discriminated
union, `event_type_name`, `to_payload`, `from_stored`. The
persistence-envelope construction (`NewEvent`) lives at
`cora.infrastructure.event_envelope.to_new_event`.

`PlanDefined` is the genesis; `PlanVersioned` and `PlanDeprecated`
cover the `Defined → Versioned → Deprecated` lifecycle, mirroring
Method and Practice. PlanVersioned carries an operator-supplied
`version_tag`; PlanDeprecated carries no extra fields.

## Payload conventions

`practice_id` and entries in `asset_ids` carry as primitive UUIDs
(strings in jsonb). Eventual-consistency stance: existence is NOT
verified at the persistence layer — the handler pre-loads them
before reaching the decider (gate-review Q5).

`asset_ids` serializes as a sorted list of UUID-as-strings (the
state holds a `frozenset[UUID]`; sorting by string form keeps the
persisted bytes deterministic — same logical Asset set, same
payload, same idempotency hash). Same precedent as
`Method.needed_family_ids`.

## Audit snapshots in payload (gate-review Q4)

`PlanDefined` carries three audit-only fields that are NOT folded
into Plan state:

  - `method_id`: the Method ultimately implemented by this Plan
    (resolved from `practice.method_id` at handler-load time).
    Captured in the event so audit replay doesn't need to traverse
    Practice → Method (capture-don't-recompute principle).
  - `method_needed_family_ids_snapshot`: the Method's
    `needed_family_ids` AT BIND TIME. Pinned so the audit trail
    reproduces what was checked even if Method later evolves.
  - `asset_family_ids_snapshot`: each bound Asset's `family_ids`
    AT BIND TIME. Same audit pinning rationale.

Both snapshots serialize as primitive forms (sorted UUID lists /
sorted-key dicts of sorted UUID lists) for deterministic hashing.
The evolver does NOT read these snapshots — they're audit-only
data living in the payload, not state.

Status is NOT carried in event payloads — the event type itself
encodes the state change. The evolver hardcodes the mapping per
match arm. Same precedent as PracticeDefined / MethodDefined /
FamilyDefined / SubjectMounted / ActorDeactivated.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent


@dataclass(frozen=True)
class PlanDefined:
    """A new Plan was defined: Practice + Asset binding established.

    Status is implicit (`Defined`) — the evolver sets it.

    `practice_id` and `asset_ids` are eventual-consistency refs.
    `method_id` and the two snapshots are audit-only data captured
    at bind time (see module docstring).
    """

    plan_id: UUID
    name: str
    practice_id: UUID
    asset_ids: tuple[UUID, ...]
    method_id: UUID
    method_needed_family_ids_snapshot: tuple[UUID, ...]
    asset_families_snapshot: dict[UUID, tuple[UUID, ...]]
    occurred_at: datetime


@dataclass(frozen=True)
class PlanVersioned:
    """A plan's binding was revised; a new version label was issued.

    Multi-source transition: `Defined | Versioned -> Versioned`. The
    evolver sets status=VERSIONED and updates state.version to the
    new tag. The decider's source-state guard enforces that
    Deprecated plans can't be re-versioned.

    `version_tag` is operator-supplied free text (1-50 chars,
    validated at API boundary AND in the decider). Same precedent
    as PracticeVersioned / MethodVersioned / FamilyVersioned.

    `content_hash` is the SHA-256 of the canonical body bytes for
    this Plan revision's content subset (`name + method_id +
    practice_id + asset_ids + default_parameters + wires`), captured
    by the decider per the non-determinism principle. 64-char
    lowercase hex. The same content emitted twice (re-attestation)
    produces the same hash, which is the intended equivalence-
    detection semantic (Bazel input/output split pattern). Pre-
    rollout legacy events have no payload field; `from_stored`
    returns None there, matching Plan state's `content_hash: str |
    None` shape per [[project_content_addressed_identity_design]]
    pre-rollout fold. The dataclass default of None exists only for
    legacy-event reconstruction; current deciders always supply a
    concrete hash.
    """

    plan_id: UUID
    version_tag: str
    occurred_at: datetime
    content_hash: str | None = None


@dataclass(frozen=True)
class PlanDeprecated:
    """A plan was marked as no longer recommended for new Runs.

    Multi-source transition: `Defined | Versioned -> Deprecated`. The
    evolver sets status=DEPRECATED; `version` is preserved (the
    historical label of when the plan was last revised before
    deprecation remains visible).

    Existing Runs that reference this Plan are NOT automatically
    invalidated. Deprecation is advisory at the BC layer; future
    Run-side enrichment may surface a warning at start-time when
    referencing a deprecated Plan (or Run-start may reject — that's
    a Run-side decision).
    """

    plan_id: UUID
    reason: str
    occurred_at: datetime


@dataclass(frozen=True)
class PlanWireAdded:
    """A typed Wire was added to a Plan's wire set.

    Single-wire event (not bulk-add); mirrors `AssetPortAdded` shape
    from Asset.ports. Audit value: "when did this Plan gain the connection
    from pandabox.trigger_out → camera.trigger_in?"

    The four port-reference fields together form the Wire's
    identity (no separate `wire_id`). Carried as primitives in the
    event payload so `from_stored` can rebuild the `Wire` VO without
    importing state.

    Status is NOT carried — wiring updates are orthogonal to
    lifecycle (Defined / Versioned / Deprecated all permit wiring
    updates; mirrors the default-parameters stance and
    PortAdded's lifecycle independence at the Asset side).
    """

    plan_id: UUID
    source_asset_id: UUID
    source_port_name: str
    target_asset_id: UUID
    target_port_name: str
    occurred_at: datetime


@dataclass(frozen=True)
class PlanWireRemoved:
    """A typed Wire was removed from a Plan's wire set.

    Mirror of `PlanWireAdded`. Carries all 4 endpoint components
    because the Wire's identity IS the 4-tuple (no shorter unique
    key). Symmetric with `AssetPortRemoved` from Asset.ports.
    """

    plan_id: UUID
    source_asset_id: UUID
    source_port_name: str
    target_asset_id: UUID
    target_port_name: str
    occurred_at: datetime


@dataclass(frozen=True)
class PlanDefaultParametersUpdated:
    """The Plan's parameter defaults were updated.

    `default_parameters` is the POST-merge dict (RFC 7396 PATCH
    applied at the slice layer; the event payload carries the
    resolved snapshot, not the patch — same self-contained-audit-log
    precedent as `AssetSettingsUpdated`).

    Validation runs at the decider against the owning Method's
    `parameters_schema` (loaded by the handler before reaching the
    decider, then handed in via the slice's MethodSchemaContext).
    Strict when Method.parameters_schema is None: non-empty defaults
    are rejected.

    Status is NOT carried — defaults updates are orthogonal to
    lifecycle (Defined / Versioned / Deprecated all permit defaults
    updates; mirrors the Method-side stance).
    """

    plan_id: UUID
    default_parameters: dict[str, Any]
    occurred_at: datetime


@dataclass(frozen=True)
class PlanRoleBound:
    """A positional role slot was bound to a specific Asset on a Plan.

    Plan-side closure for the positional role-tagging workstream.
    Strict-not-idempotent: a duplicate role_name surfaces as
    `PlanRoleAlreadyBoundError`. Restricted to Plans in `Defined`
    status; mirrors `PlanWireAdded`'s shape with the role identity
    carried as a primitive string so `from_stored` can rebuild the
    RoleBinding VO without importing state.

    Status is NOT carried because the lifecycle restriction is enforced
    at the decider, not derived from this event type.
    """

    plan_id: UUID
    role_name: str
    asset_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class PlanRoleUnbound:
    """A positional role slot was unbound from a Plan.

    Mirror of `PlanRoleBound`. Strict-not-idempotent. The payload
    carries only `role_name` (the structural identity of the binding
    within the Plan); the asset_id is reconstructable from prior
    state at fold time but not strictly needed for the unbind
    semantics.
    """

    plan_id: UUID
    role_name: str
    occurred_at: datetime


# Discriminated union of every event the Plan aggregate emits.
PlanEvent = (
    PlanDefined
    | PlanVersioned
    | PlanDeprecated
    | PlanDefaultParametersUpdated
    | PlanWireAdded
    | PlanWireRemoved
    | PlanRoleBound
    | PlanRoleUnbound
)


def event_type_name(event: PlanEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def _serialize_asset_families_snapshot(
    snapshot: dict[UUID, tuple[UUID, ...]],
) -> dict[str, list[str]]:
    """Serialize the bind-time asset-families snapshot deterministically.

    jsonb stores object keys as strings; the dict key sort order
    matters for idempotency-key hashing (same logical snapshot
    must produce identical bytes). Outer keys sorted by UUID string
    form; inner lists sorted by UUID string form.
    """
    return {
        str(asset_id): sorted(str(c) for c in families)
        for asset_id, families in sorted(snapshot.items(), key=lambda kv: str(kv[0]))
    }


def _deserialize_asset_families_snapshot(
    payload: dict[str, list[str]],
) -> dict[UUID, tuple[UUID, ...]]:
    """Inverse of `_serialize_asset_families_snapshot`."""
    return {UUID(asset_id): tuple(UUID(c) for c in caps) for asset_id, caps in payload.items()}


def to_payload(event: PlanEvent) -> dict[str, Any]:
    """Serialize a Plan event to a JSON-friendly dict for jsonb storage.

    Primitives only: UUIDs become strings, datetimes become ISO-8601
    strings, frozensets/dicts become deterministically-ordered lists
    and string-keyed dicts.
    """
    match event:
        case PlanDefined(
            plan_id=plan_id,
            name=name,
            practice_id=practice_id,
            asset_ids=asset_ids,
            method_id=method_id,
            method_needed_family_ids_snapshot=needs_snapshot,
            asset_families_snapshot=asset_caps_snapshot,
            occurred_at=occurred_at,
        ):
            return {
                "plan_id": str(plan_id),
                "name": name,
                "practice_id": str(practice_id),
                # asset_ids deterministic for idempotency hashing.
                "asset_ids": sorted(str(a) for a in asset_ids),
                "method_id": str(method_id),
                "method_needed_family_ids_snapshot": sorted(str(c) for c in needs_snapshot),
                "asset_families_snapshot": _serialize_asset_families_snapshot(asset_caps_snapshot),
                "occurred_at": occurred_at.isoformat(),
            }
        case PlanVersioned(
            plan_id=plan_id,
            version_tag=version_tag,
            occurred_at=occurred_at,
            content_hash=content_hash,
        ):
            payload: dict[str, Any] = {
                "plan_id": str(plan_id),
                "version_tag": version_tag,
                "occurred_at": occurred_at.isoformat(),
            }
            if content_hash is not None:
                payload["content_hash"] = content_hash
            return payload
        case PlanDeprecated(
            plan_id=plan_id,
            reason=reason,
            occurred_at=occurred_at,
        ):
            return {
                "plan_id": str(plan_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case PlanDefaultParametersUpdated(
            plan_id=plan_id,
            default_parameters=default_parameters,
            occurred_at=occurred_at,
        ):
            return {
                "plan_id": str(plan_id),
                "default_parameters": default_parameters,
                "occurred_at": occurred_at.isoformat(),
            }
        case PlanWireAdded(
            plan_id=plan_id,
            source_asset_id=source_asset_id,
            source_port_name=source_port_name,
            target_asset_id=target_asset_id,
            target_port_name=target_port_name,
            occurred_at=occurred_at,
        ):
            return {
                "plan_id": str(plan_id),
                "source_asset_id": str(source_asset_id),
                "source_port_name": source_port_name,
                "target_asset_id": str(target_asset_id),
                "target_port_name": target_port_name,
                "occurred_at": occurred_at.isoformat(),
            }
        case PlanWireRemoved(
            plan_id=plan_id,
            source_asset_id=source_asset_id,
            source_port_name=source_port_name,
            target_asset_id=target_asset_id,
            target_port_name=target_port_name,
            occurred_at=occurred_at,
        ):
            return {
                "plan_id": str(plan_id),
                "source_asset_id": str(source_asset_id),
                "source_port_name": source_port_name,
                "target_asset_id": str(target_asset_id),
                "target_port_name": target_port_name,
                "occurred_at": occurred_at.isoformat(),
            }
        case PlanRoleBound(
            plan_id=plan_id,
            role_name=role_name,
            asset_id=asset_id,
            occurred_at=occurred_at,
        ):
            return {
                "plan_id": str(plan_id),
                "role_name": role_name,
                "asset_id": str(asset_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case PlanRoleUnbound(
            plan_id=plan_id,
            role_name=role_name,
            occurred_at=occurred_at,
        ):
            return {
                "plan_id": str(plan_id),
                "role_name": role_name,
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> PlanEvent:
    """Rebuild a Plan event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.
    """
    payload = stored.payload
    match stored.event_type:
        case "PlanDefined":

            def _build_plan_defined() -> PlanDefined:
                # dual-key fallback: legacy PlanDefined payloads carry
                # `method_needed_capabilities_snapshot` and
                # `asset_capabilities_snapshot`; current payloads carry the
                # `*_families_snapshot` equivalents. Read the new key first,
                # fall back to the legacy key. Stays forever per Marten/Axon
                # rename pattern.
                needed_snap = payload.get(
                    "method_needed_family_ids_snapshot",
                    payload.get("method_needed_capabilities_snapshot", []),
                )
                asset_snap = payload.get(
                    "asset_families_snapshot",
                    payload.get("asset_capabilities_snapshot", {}),
                )
                return PlanDefined(
                    plan_id=UUID(payload["plan_id"]),
                    name=payload["name"],
                    practice_id=UUID(payload["practice_id"]),
                    asset_ids=tuple(UUID(a) for a in payload["asset_ids"]),
                    method_id=UUID(payload["method_id"]),
                    method_needed_family_ids_snapshot=tuple(UUID(c) for c in needed_snap),
                    asset_families_snapshot=_deserialize_asset_families_snapshot(asset_snap),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )

            return deserialize_or_raise("PlanDefined", _build_plan_defined)
        case "PlanVersioned":
            return deserialize_or_raise(
                "PlanVersioned",
                lambda: PlanVersioned(
                    plan_id=UUID(payload["plan_id"]),
                    version_tag=payload["version_tag"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    # forward-compat: pre-rollout PlanVersioned payloads
                    # have no content_hash; default to None. Additive-
                    # evolution pattern per [[project_content_addressed
                    # _identity_design]] watch item on pre-rollout fold.
                    content_hash=payload.get("content_hash"),
                ),
            )
        case "PlanDeprecated":
            return deserialize_or_raise(
                "PlanDeprecated",
                lambda: PlanDeprecated(
                    plan_id=UUID(payload["plan_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "PlanDefaultParametersUpdated":
            return deserialize_or_raise(
                "PlanDefaultParametersUpdated",
                lambda: PlanDefaultParametersUpdated(
                    plan_id=UUID(payload["plan_id"]),
                    default_parameters=payload["default_parameters"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "PlanWireAdded":
            return deserialize_or_raise(
                "PlanWireAdded",
                lambda: PlanWireAdded(
                    plan_id=UUID(payload["plan_id"]),
                    source_asset_id=UUID(payload["source_asset_id"]),
                    source_port_name=payload["source_port_name"],
                    target_asset_id=UUID(payload["target_asset_id"]),
                    target_port_name=payload["target_port_name"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "PlanWireRemoved":
            return deserialize_or_raise(
                "PlanWireRemoved",
                lambda: PlanWireRemoved(
                    plan_id=UUID(payload["plan_id"]),
                    source_asset_id=UUID(payload["source_asset_id"]),
                    source_port_name=payload["source_port_name"],
                    target_asset_id=UUID(payload["target_asset_id"]),
                    target_port_name=payload["target_port_name"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "PlanRoleBound":
            return deserialize_or_raise(
                "PlanRoleBound",
                lambda: PlanRoleBound(
                    plan_id=UUID(payload["plan_id"]),
                    role_name=payload["role_name"],
                    asset_id=UUID(payload["asset_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "PlanRoleUnbound":
            return deserialize_or_raise(
                "PlanRoleUnbound",
                lambda: PlanRoleUnbound(
                    plan_id=UUID(payload["plan_id"]),
                    role_name=payload["role_name"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case _:
            msg = f"Unknown PlanEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "PlanDefaultParametersUpdated",
    "PlanDefined",
    "PlanDeprecated",
    "PlanEvent",
    "PlanRoleBound",
    "PlanRoleUnbound",
    "PlanVersioned",
    "PlanWireAdded",
    "PlanWireRemoved",
    "event_type_name",
    "from_stored",
    "to_payload",
]
