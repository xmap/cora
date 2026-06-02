"""Domain events emitted by the Mount aggregate, plus the discriminated union.

Mirrors the Frame event-module shape (see `aggregates/frame/events.py`):
event classes as frozen dataclasses, discriminated union,
`event_type_name`, `to_payload`, `from_stored` with per-arm
KeyError / TypeError / AttributeError wrapping into tagged
ValueError per `project_from_stored_wrap_convention`.

Event catalog (5):
  - `MountRegistered`     (genesis)
  - `MountDecommissioned` (terminal lifecycle)
  - `MountPlacementUpdated`    (placement mutation; no-op on equal at the
                           decider via make_mount_update_handler)
  - `MountAssetInstalled`      (single-stream-write + projection-precondition;
                           carries optional `previously_installed_asset_id`
                           for the swap-within-cycle audit shape)
  - `MountAssetUninstalled`    (no precondition; symmetric with install)

## Payload conventions for Mount

`status` is NOT carried in the payload: the event TYPE encodes the
state change (`MountRegistered -> Active`,
`MountDecommissioned -> Decommissioned`). Same precedent as Asset /
Frame / Subject.

`parent_mount_id` IS carried in the `MountRegistered` payload as
`UUID | None`. Top-level slots serialize None.

`placement` and `drawing` IS carried in `MountRegistered` (initial
values). `placement.parent_frame_id` references a Frame; not validated
at write time (eventual consistency per the design memo).

`previously_installed_asset_id?` on `MountAssetInstalled` is populated
ONLY when the slot was just vacated and a new specimen replaces it
within the same operational cycle (audit-self-contained per the
design memo's note inspired by Supply's `from_status` shape).
Shape-divergent: Supply's `from_status` is always populated;
Mount's first-install genuinely has no prior asset, so the field is
Optional.

`reason` on `MountDecommissioned` / `MountAssetUninstalled` is operator-
supplied free text (1-500 chars validated at the API boundary).
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
    Placement,
    placement_from_payload,
    placement_to_payload,
)
from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent

# Codec helpers (placement_to/from_payload, drawing_to/from_payload) are
# imported above from the shared VO modules per the codec-helper-
# duplication anti-hook in project_mount_frame_design Watch items.


@dataclass(frozen=True)
class MountRegistered:
    """A new mount was registered.

    Status is implicit (`Active`); the evolver sets it.
    `parent_mount_id` is optional (None for top-level slots).
    `placement` is required; `drawing` is optional.
    `installed_asset_id` is implicitly None at registration; the
    install_asset slice transitions a vacant slot to occupied.
    """

    mount_id: UUID
    slot_code: str
    parent_mount_id: UUID | None
    placement: Placement
    drawing: Drawing | None
    occurred_at: datetime


@dataclass(frozen=True)
class MountDecommissioned:
    """A mount was retired from the beamline.

    Terminal lifecycle transition: `Active -> Decommissioned`.
    Strict semantics: re-decommissioning raises
    MountCannotDecommissionError. The handler's projection
    preconditions (MountHasInstalledAsset, MountHasActiveChildren)
    are what guard against orphaning specimens / children; this
    event being in the stream means no live consumer remained at
    write time.

    `reason` is operator-supplied free text.
    """

    mount_id: UUID
    reason: str
    occurred_at: datetime


@dataclass(frozen=True)
class MountPlacementUpdated:
    """A mount's placement was updated.

    Used for both nominal-from-drawing initial corrections and re-
    survey updates. When `survey` is present, the payload carries
    survey provenance (instrument id, technician id, residual);
    when absent, the update is operator-asserted without measurement
    provenance.

    No-op at the decider when `new_placement == current_placement`
    (idempotent contract via make_mount_update_handler); an event
    in the stream means the placement actually changed.
    """

    mount_id: UUID
    new_placement: Placement
    survey: dict[str, Any] | None
    occurred_at: datetime


@dataclass(frozen=True)
class MountAssetInstalled:
    """An Asset was installed into a Mount's slot.

    `previously_installed_asset_id` is populated ONLY when the slot
    was just vacated and a new specimen replaces it within the same
    operational cycle; None for first-install (audit-self-contained,
    inspired by Supply's `from_status` shape but shape-divergent
    since first-install has no prior asset).

    The asset_location projection subscribes to this + MountAssetUninstalled
    to maintain the reverse lookup (asset_id -> mount_id).
    """

    mount_id: UUID
    asset_id: UUID
    previously_installed_asset_id: UUID | None
    occurred_at: datetime


@dataclass(frozen=True)
class MountAssetUninstalled:
    """An Asset was uninstalled from a Mount's slot.

    The Asset record persists (the specimen still exists in CORA's
    registry; it's just not in this slot). Mount.installed_asset_id
    returns to None; the asset_location projection drops the
    (asset_id -> mount_id) row.

    `reason` is operator-supplied free text.
    """

    mount_id: UUID
    asset_id: UUID
    reason: str
    occurred_at: datetime


MountEvent = (
    MountRegistered
    | MountDecommissioned
    | MountPlacementUpdated
    | MountAssetInstalled
    | MountAssetUninstalled
)


def event_type_name(event: MountEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: MountEvent) -> dict[str, Any]:
    """Serialize a Mount event to a JSON-friendly dict for jsonb storage."""
    match event:
        case MountRegistered(
            mount_id=mount_id,
            slot_code=slot_code,
            parent_mount_id=parent_mount_id,
            placement=placement,
            drawing=drawing,
            occurred_at=occurred_at,
        ):
            return {
                "mount_id": str(mount_id),
                "slot_code": slot_code,
                "parent_mount_id": (str(parent_mount_id) if parent_mount_id is not None else None),
                "placement": placement_to_payload(placement),
                "drawing": (drawing_to_payload(drawing) if drawing is not None else None),
                "occurred_at": occurred_at.isoformat(),
            }
        case MountDecommissioned(
            mount_id=mount_id,
            reason=reason,
            occurred_at=occurred_at,
        ):
            return {
                "mount_id": str(mount_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case MountPlacementUpdated(
            mount_id=mount_id,
            new_placement=new_placement,
            survey=survey,
            occurred_at=occurred_at,
        ):
            return {
                "mount_id": str(mount_id),
                "new_placement": placement_to_payload(new_placement),
                "survey": survey,
                "occurred_at": occurred_at.isoformat(),
            }
        case MountAssetInstalled(
            mount_id=mount_id,
            asset_id=asset_id,
            previously_installed_asset_id=prior,
            occurred_at=occurred_at,
        ):
            return {
                "mount_id": str(mount_id),
                "asset_id": str(asset_id),
                "previously_installed_asset_id": (str(prior) if prior is not None else None),
                "occurred_at": occurred_at.isoformat(),
            }
        case MountAssetUninstalled(
            mount_id=mount_id,
            asset_id=asset_id,
            reason=reason,
            occurred_at=occurred_at,
        ):
            return {
                "mount_id": str(mount_id),
                "asset_id": str(asset_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> MountEvent:
    """Rebuild a Mount event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.
    Per-arm `(KeyError, TypeError, AttributeError)` wrap into tagged
    ValueError per `project_from_stored_wrap_convention`.
    """
    payload = stored.payload
    match stored.event_type:
        case "MountRegistered":

            def _build_registered() -> MountRegistered:
                raw_parent = payload["parent_mount_id"]
                raw_drawing = payload["drawing"]
                return MountRegistered(
                    mount_id=UUID(payload["mount_id"]),
                    slot_code=payload["slot_code"],
                    parent_mount_id=UUID(raw_parent) if raw_parent is not None else None,
                    placement=placement_from_payload(payload["placement"]),
                    drawing=(
                        drawing_from_payload(raw_drawing) if raw_drawing is not None else None
                    ),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )

            return deserialize_or_raise("MountRegistered", _build_registered)
        case "MountDecommissioned":
            return deserialize_or_raise(
                "MountDecommissioned",
                lambda: MountDecommissioned(
                    mount_id=UUID(payload["mount_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "MountPlacementUpdated":
            return deserialize_or_raise(
                "MountPlacementUpdated",
                lambda: MountPlacementUpdated(
                    mount_id=UUID(payload["mount_id"]),
                    new_placement=placement_from_payload(payload["new_placement"]),
                    survey=payload.get("survey"),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case "MountAssetInstalled":

            def _build_installed() -> MountAssetInstalled:
                raw_prior = payload.get("previously_installed_asset_id")
                return MountAssetInstalled(
                    mount_id=UUID(payload["mount_id"]),
                    asset_id=UUID(payload["asset_id"]),
                    previously_installed_asset_id=(
                        UUID(raw_prior) if raw_prior is not None else None
                    ),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )

            return deserialize_or_raise("MountAssetInstalled", _build_installed)
        case "MountAssetUninstalled":
            return deserialize_or_raise(
                "MountAssetUninstalled",
                lambda: MountAssetUninstalled(
                    mount_id=UUID(payload["mount_id"]),
                    asset_id=UUID(payload["asset_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                ),
            )
        case _:
            msg = f"Unknown MountEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "MountAssetInstalled",
    "MountAssetUninstalled",
    "MountDecommissioned",
    "MountEvent",
    "MountPlacementUpdated",
    "MountRegistered",
    "event_type_name",
    "from_stored",
    "to_payload",
]
