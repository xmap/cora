"""Domain events emitted by the Asset aggregate, plus the discriminated union.

Mirrors the locked event-module shape: event classes,
discriminated union, `event_type_name`, `to_payload`,
`from_stored`. The persistence-envelope construction (`NewEvent`)
lives at `cora.infrastructure.event_envelope.to_new_event`.

Event catalog: `AssetRegistered` (genesis), the lifecycle transitions
(`AssetActivated`, `AssetDecommissioned`, `AssetMaintenanceEntered`,
`AssetMaintenanceExited`), the hierarchy mutation
(`AssetRelocated` — the first event whose payload carries source
AND target state, `from_parent_id` + `to_parent_id`, since `parent_id`
is mutable and the audit log should record both sides without
forcing readers to walk the prior event), and the incremental
family-set mutations (`AssetFamilyAdded` / `AssetFamilyRemoved`,
each carrying a single `family_id` that the evolver folds into the
`family_ids` frozenset as new techniques are commissioned or retired).

`AssetDecommissioned`'s source set accepts both ACTIVE and
MAINTENANCE so a faulted asset can be retired without first being
restored.

## Payload conventions for Asset

`level` IS carried in the payload (set at registration, never
changes; no `AssetLevelChanged` event in scope). The evolver
reconstructs via `AssetLevel(payload["level"])`.

`parent_id` IS carried in the AssetRegistered payload (sets the
initial value). For mutations, AssetRelocated carries BOTH
`from_parent_id` and `to_parent_id` — the only event in the
codebase to date with source-state in the payload (most
transitions encode the source via the event TYPE; this one needs
explicit source because parent_id is a value with many possible
prior states, not a discrete state-machine state). Serialized as
`str(parent_id)` or `None` (Optional fits naturally into JSON).

`reason` on AssetRelocated is free-text (validated at the API
boundary, not by a domain VO) — operators include why the move
happened (commissioning move, maintenance reorganization,
decommissioning to storage, etc).

`lifecycle` is NOT carried in the payload — the event TYPE
encodes the state change (`AssetRegistered → COMMISSIONED`).
Same precedent as Subject / Family / Actor.

`drawing` on AssetRegistered uses the omit-when-None convention:
the payload key is absent when no Drawing was supplied (rather
than written as JSON null). `from_stored` uses `payload.get(...)`
so legacy events written before the drawing field landed fold
cleanly to `drawing=None`. Mount took the opposite convention
(always-present-with-null) because MountRegistered carried
drawing from genesis; Asset's omit-when-None is the strict
additive-evolution shape and matches the `AssetSettingsUpdated`
precedent (also payload.get-based).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.equipment.aggregates._drawing import Drawing, DrawingSystem
from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent


@dataclass(frozen=True)
class AssetRegistered:
    """A new asset was registered with the facility.

    Lifecycle is implicit (`Commissioned`) — the evolver sets it.
    `parent_id` is optional: only `level=Enterprise` has a null
    parent (the root); other levels enforce non-null at the
    decider per the hierarchy rule.

    `drawing` is an optional Drawing VO captured at registration:
    the engineering build-to spec for the physical specimen. Defaults
    to None so legacy AssetRegistered streams (no drawing in the
    payload) fold cleanly via the additive-payload pattern.

    `model_id` is an optional reference to the Model catalog entry
    this Asset is an instance of (Family -> Model -> Assembly ->
    Asset ladder). Set at registration per the model-binding design
    memo (Lock A); rebind path is decommission + re-register.
    Defaults to None so legacy AssetRegistered streams (no model_id
    in the payload) fold cleanly via the additive-payload pattern;
    `to_payload` uses the omit-when-None convention (key absent
    rather than serialized as JSON null) to mirror the `drawing`
    precedent.
    """

    asset_id: UUID
    name: str
    level: str  # AssetLevel.value; carried as primitive in the payload
    parent_id: UUID | None
    occurred_at: datetime
    drawing: Drawing | None = None
    model_id: UUID | None = None


@dataclass(frozen=True)
class AssetActivated:
    """An asset transitioned into service.

    Lifecycle transition: `Commissioned -> Active`. The evolver
    sets the new lifecycle; no lifecycle field in the payload.
    """

    asset_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class AssetDecommissioned:
    """An asset was retired from service.

    Lifecycle transition: `Commissioned | Active -> Decommissioned`
    (multi-source; widens to include Maintenance). The
    evolver sets the new lifecycle regardless of which source state
    the asset came from; the decider's source-state guard is what
    enforces the multi-source restriction at command time.
    """

    asset_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class AssetMaintenanceEntered:
    """An asset was taken out of service for maintenance.

    Lifecycle transition: `Active -> Maintenance` (single-source).
    The evolver sets the new lifecycle; no lifecycle field in the
    payload (event TYPE encodes the change). Same convention as
    AssetActivated.
    """

    asset_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class AssetMaintenanceExited:
    """An asset was returned to active service after maintenance.

    Lifecycle transition: `Maintenance -> Active` (single-source).
    The evolver sets the new lifecycle; no lifecycle field in the
    payload (event TYPE encodes the change). Mirrors
    `AssetMaintenanceEntered` shape exactly with symmetric
    enter/exit preposition.
    """

    asset_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class AssetFamilyAdded:
    """A Family was added to an asset's family set.

    Single-family event (not bulk-update). Capabilities accumulate
    as operators commission new techniques on the asset; each event
    captures a single addition for clean audit trails ("when did this
    asset gain XRF Mapping?"). The evolver inserts the family_id
    into `state.family_ids` (frozenset semantics → no-op on
    duplicate at the evolver layer; the decider's strict-not-idempotent
    guard is what enforces "must not already be present" at command
    time).

    Eventual-consistency: `family_id` is NOT verified against the
    Family stream. Same precedent as Conduit zone refs (3b),
    Asset parent refs (5b), Method.needed_family_ids (6a).
    """

    asset_id: UUID
    family_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class AssetFamilyRemoved:
    """A Family was removed from an asset's family set.

    Mirror of `AssetFamilyAdded`. Single-family event; the
    evolver removes the family_id from `state.family_ids`. The
    decider's strict-not-idempotent guard enforces "must currently be
    present" at command time.
    """

    asset_id: UUID
    family_id: UUID
    occurred_at: datetime


@dataclass(frozen=True)
class AssetDegraded:
    """An asset's condition transitioned to `Degraded`.

    Condition transition: any condition -> Degraded (target-state
    semantics, mirrors `enter_maintenance`'s lifecycle target). The
    evolver sets the new condition; no condition field in the
    payload (event TYPE encodes the change).

    `reason` is operator-supplied free text (for example "hot pixel detected
    at (12, 42)"); validated 1-500 chars at the API boundary, the
    decider trusts the input. Same precedent as `AssetRelocated.reason`.
    """

    asset_id: UUID
    reason: str
    occurred_at: datetime


@dataclass(frozen=True)
class AssetFaulted:
    """An asset's condition transitioned to `Faulted`.

    Condition transition: any condition -> Faulted. Mirror of
    `AssetDegraded`. Operationally: device is down, requires repair
    before any further use.
    """

    asset_id: UUID
    reason: str
    occurred_at: datetime


@dataclass(frozen=True)
class AssetRestored:
    """An asset's condition transitioned to `Nominal`.

    Condition transition: any condition -> Nominal. Mirror of
    `AssetDegraded`. Operationally: device fully repaired and back
    to normal operating specs. Partial repairs (Faulted -> Degraded)
    use `degrade_asset`, NOT `restore_asset` with a target arg —
    each slice has a fixed target.
    """

    asset_id: UUID
    reason: str
    occurred_at: datetime


@dataclass(frozen=True)
class AssetPortAdded:
    """A typed port was added to an Asset's port set (5h).

    Single-port event (not bulk-add), mirrors `AssetFamilyAdded`.
    Audit value: "when did this Asset gain a `sync_clock` port?"

    `port_name`, `direction`, and `signal_type` are the three
    components of the AssetPort VO; carried as primitives in the
    event payload so the from_stored reconstruction can rebuild the
    VO without reading the state.
    """

    asset_id: UUID
    port_name: str
    direction: str  # PortDirection.value (StrEnum)
    signal_type: str
    occurred_at: datetime


@dataclass(frozen=True)
class AssetPortRemoved:
    """A typed port was removed from an Asset's port set (5h).

    Mirror of `AssetPortAdded`. Carries only `port_name` because
    that is the unique key on Asset.ports — the decider's evolver
    pre-image gives the removed port's full shape if a future reader
    needs it. Symmetric with `AssetFamilyRemoved`.
    """

    asset_id: UUID
    port_name: str
    occurred_at: datetime


@dataclass(frozen=True)
class AssetSettingsUpdated:
    """An asset's settings dict was set / replaced via the
    update_asset_settings slice (5g-c).

    The payload carries the FULL post-merge dict (`settings`), NOT
    the patch (`settings_patch`) that was submitted. Readers
    reconstruct current state without folding back through prior
    events; the audit log answers "what is true at time T", not
    "what changed between T and T-1". Trade-off: payloads are
    slightly larger than carrying the diff, but for typical settings
    dicts (5-30 keys) it's a non-issue.

    The handler validates the post-merge dict against the union of
    currently-assigned Capabilities' settings_schemas BEFORE
    emitting; an event in the stream means validation passed at the
    moment of write. Family schemas changing later does NOT
    auto-revalidate existing settings (locked design; see the 5g-c
    memo).
    """

    asset_id: UUID
    settings: dict[str, Any]
    occurred_at: datetime


@dataclass(frozen=True)
class AssetRelocated:
    """An asset's parent in the hierarchy tree changed.

    Hierarchy mutation: `parent_id: from_parent_id -> to_parent_id`.
    Lifecycle is unchanged. Carries BOTH source and target parent
    in the payload — the audit log should record both sides without
    requiring readers to walk the prior event. `reason` is operator-
    supplied free text (for example "moved from storage to BL2-IBP", "site
    reorganization 2026-Q3").

    Per BC map: `from_parent_id` is the prior parent, `to_parent_id`
    is the new parent. Both non-null for any non-Enterprise asset
    (Enterprise can't relocate per the decider's hierarchy guard).
    """

    asset_id: UUID
    from_parent_id: UUID
    to_parent_id: UUID
    reason: str
    occurred_at: datetime


# Discriminated union of every event the Asset aggregate emits.
# Add new event classes above and extend this alias when new
# slices land.
AssetEvent = (
    AssetRegistered
    | AssetActivated
    | AssetDecommissioned
    | AssetRelocated
    | AssetMaintenanceEntered
    | AssetMaintenanceExited
    | AssetFamilyAdded
    | AssetFamilyRemoved
    | AssetDegraded
    | AssetFaulted
    | AssetRestored
    | AssetSettingsUpdated
    | AssetPortAdded
    | AssetPortRemoved
)


def event_type_name(event: AssetEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: AssetEvent) -> dict[str, Any]:
    """Serialize an Asset event to a JSON-friendly dict for jsonb storage.

    Primitives only: UUIDs become strings, datetimes become ISO-8601
    strings, optional UUIDs become string-or-None.
    """
    match event:
        case AssetRegistered(
            asset_id=asset_id,
            name=name,
            level=level,
            parent_id=parent_id,
            occurred_at=occurred_at,
            drawing=drawing,
            model_id=model_id,
        ):
            payload: dict[str, Any] = {
                "asset_id": str(asset_id),
                "name": name,
                "level": level,
                "parent_id": str(parent_id) if parent_id is not None else None,
                "occurred_at": occurred_at.isoformat(),
            }
            if drawing is not None:
                payload["drawing"] = {
                    "system": drawing.system.value,
                    "number": drawing.number,
                    "revision": drawing.revision,
                }
            if model_id is not None:
                payload["model_id"] = str(model_id)
            return payload
        case AssetActivated(asset_id=asset_id, occurred_at=occurred_at):
            return {
                "asset_id": str(asset_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetDecommissioned(asset_id=asset_id, occurred_at=occurred_at):
            return {
                "asset_id": str(asset_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetRelocated(
            asset_id=asset_id,
            from_parent_id=from_parent_id,
            to_parent_id=to_parent_id,
            reason=reason,
            occurred_at=occurred_at,
        ):
            return {
                "asset_id": str(asset_id),
                "from_parent_id": str(from_parent_id),
                "to_parent_id": str(to_parent_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetMaintenanceEntered(asset_id=asset_id, occurred_at=occurred_at):
            return {
                "asset_id": str(asset_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetMaintenanceExited(asset_id=asset_id, occurred_at=occurred_at):
            return {
                "asset_id": str(asset_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetFamilyAdded(
            asset_id=asset_id,
            family_id=family_id,
            occurred_at=occurred_at,
        ):
            return {
                "asset_id": str(asset_id),
                "family_id": str(family_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetFamilyRemoved(
            asset_id=asset_id,
            family_id=family_id,
            occurred_at=occurred_at,
        ):
            return {
                "asset_id": str(asset_id),
                "family_id": str(family_id),
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetDegraded(asset_id=asset_id, reason=reason, occurred_at=occurred_at):
            return {
                "asset_id": str(asset_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetFaulted(asset_id=asset_id, reason=reason, occurred_at=occurred_at):
            return {
                "asset_id": str(asset_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetRestored(asset_id=asset_id, reason=reason, occurred_at=occurred_at):
            return {
                "asset_id": str(asset_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetSettingsUpdated(asset_id=asset_id, settings=settings, occurred_at=occurred_at):
            return {
                "asset_id": str(asset_id),
                "settings": settings,
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetPortAdded(
            asset_id=asset_id,
            port_name=port_name,
            direction=direction,
            signal_type=signal_type,
            occurred_at=occurred_at,
        ):
            return {
                "asset_id": str(asset_id),
                "port_name": port_name,
                "direction": direction,
                "signal_type": signal_type,
                "occurred_at": occurred_at.isoformat(),
            }
        case AssetPortRemoved(asset_id=asset_id, port_name=port_name, occurred_at=occurred_at):
            return {
                "asset_id": str(asset_id),
                "port_name": port_name,
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> AssetEvent:
    """Rebuild an Asset event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.
    """
    payload = stored.payload
    match stored.event_type:
        case "AssetRegistered":

            def _build_registered() -> AssetRegistered:
                raw_parent = payload["parent_id"]
                raw_drawing = payload.get("drawing")
                drawing = (
                    Drawing(
                        system=DrawingSystem(raw_drawing["system"]),
                        number=raw_drawing["number"],
                        revision=raw_drawing.get("revision"),
                    )
                    if raw_drawing is not None
                    else None
                )
                raw_model_id = payload.get("model_id")
                model_id = UUID(raw_model_id) if raw_model_id is not None else None
                return AssetRegistered(
                    asset_id=UUID(payload["asset_id"]),
                    name=payload["name"],
                    level=payload["level"],
                    parent_id=UUID(raw_parent) if raw_parent is not None else None,
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    drawing=drawing,
                    model_id=model_id,
                )

            return deserialize_or_raise("AssetRegistered", _build_registered)
        case "AssetActivated":
            return deserialize_or_raise(
                "AssetActivated",
                lambda: AssetActivated(
                    asset_id=UUID(payload["asset_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AssetDecommissioned":
            return deserialize_or_raise(
                "AssetDecommissioned",
                lambda: AssetDecommissioned(
                    asset_id=UUID(payload["asset_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AssetRelocated":
            return deserialize_or_raise(
                "AssetRelocated",
                lambda: AssetRelocated(
                    asset_id=UUID(payload["asset_id"]),
                    from_parent_id=UUID(payload["from_parent_id"]),
                    to_parent_id=UUID(payload["to_parent_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AssetMaintenanceEntered":
            return deserialize_or_raise(
                "AssetMaintenanceEntered",
                lambda: AssetMaintenanceEntered(
                    asset_id=UUID(payload["asset_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AssetMaintenanceExited":
            return deserialize_or_raise(
                "AssetMaintenanceExited",
                lambda: AssetMaintenanceExited(
                    asset_id=UUID(payload["asset_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AssetFamilyAdded":
            return deserialize_or_raise(
                "AssetFamilyAdded",
                lambda: AssetFamilyAdded(
                    asset_id=UUID(payload["asset_id"]),
                    family_id=UUID(payload["family_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AssetFamilyRemoved":
            return deserialize_or_raise(
                "AssetFamilyRemoved",
                lambda: AssetFamilyRemoved(
                    asset_id=UUID(payload["asset_id"]),
                    family_id=UUID(payload["family_id"]),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AssetDegraded":
            return deserialize_or_raise(
                "AssetDegraded",
                lambda: AssetDegraded(
                    asset_id=UUID(payload["asset_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AssetFaulted":
            return deserialize_or_raise(
                "AssetFaulted",
                lambda: AssetFaulted(
                    asset_id=UUID(payload["asset_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AssetRestored":
            return deserialize_or_raise(
                "AssetRestored",
                lambda: AssetRestored(
                    asset_id=UUID(payload["asset_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AssetSettingsUpdated":
            return deserialize_or_raise(
                "AssetSettingsUpdated",
                lambda: AssetSettingsUpdated(
                    asset_id=UUID(payload["asset_id"]),
                    settings=payload.get("settings", {}),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AssetPortAdded":
            return deserialize_or_raise(
                "AssetPortAdded",
                lambda: AssetPortAdded(
                    asset_id=UUID(payload["asset_id"]),
                    port_name=payload["port_name"],
                    direction=payload["direction"],
                    signal_type=payload["signal_type"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "AssetPortRemoved":
            return deserialize_or_raise(
                "AssetPortRemoved",
                lambda: AssetPortRemoved(
                    asset_id=UUID(payload["asset_id"]),
                    port_name=payload["port_name"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case _:
            msg = f"Unknown AssetEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "AssetActivated",
    "AssetDecommissioned",
    "AssetDegraded",
    "AssetEvent",
    "AssetFamilyAdded",
    "AssetFamilyRemoved",
    "AssetFaulted",
    "AssetMaintenanceEntered",
    "AssetMaintenanceExited",
    "AssetPortAdded",
    "AssetPortRemoved",
    "AssetRegistered",
    "AssetRelocated",
    "AssetRestored",
    "AssetSettingsUpdated",
    "event_type_name",
    "from_stored",
    "to_payload",
]
