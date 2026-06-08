"""Mount aggregate state, status enum, slot-code VO, and domain errors.

A `Mount` is the named slot in the beamline at which a single
specimen Asset sits at a time. The slot persists across installs
(SAP's "the slot outlives the device installed in it" lesson per
project_mount_frame_design.md); operators install / uninstall
Assets into the slot, and the Mount carries the slot's identity,
position (Placement against a Frame), and currently-installed
specimen.

## Identity

`id` is the opaque UUID (CORA's standard internal id), used for
event-store stream keying and cross-aggregate references.
`slot_code` is the external alias (e.g., APS 2-BM's `02-BM-A-K-01`
RSS tag); operators talk in slot codes, the system talks in UUIDs.
Slot-code uniqueness is a projection-precondition concern at register
time (not enforced at the DB level here), enabling a future
multi-facility deployment where slot codes are facility-scoped.

## Composition (parent_id)

`parent_id` is the immediate parent in the slot hierarchy
(an Assembly slot containing Device slots, ISA-88-derived). It is
NOT the coordinate-frame parent: coordinate framing lives entirely
on `Placement.parent_frame_id`, which references a Frame, not another
Mount. The two parent axes are deliberately separate (a Mount may
live in an Assembly that itself lives in a different Frame from the
Mount).

## Placement

`placement` is required for every Mount (no "root mount" carve-out
analogous to root Frames; every slot has a position). Refers to a
Frame via `placement.parent_frame_id`. Per the design memo, eventual-
consistency: the decider does NOT verify the Frame exists at write
time (matches Asset.parent_id eventual-consistency stance).

## Drawing

`drawing` is the optional engineering reference (ICMS document for
the slot itself: which assembly drawing shows where this slot lives
in the beamline). Distinct from the Asset's `drawing` (the
build-to drawing for the specimen) per the design memo's
anti-hook: do NOT collapse Mount.drawing and Asset.drawing.

## Currently-installed Asset

`installed_asset_id: AssetId | None` is the single source of truth
for "what's installed where" per the design memo. None means the
slot is vacant (post-uninstall, pre-install, or freshly registered).
The bidirectional back-lookup (asset_id -> mount_id) lives in the
`asset_location` projection; the Asset aggregate does NOT carry
`installed_at` per the anti-hook.

## Lifecycle

`MountStatus` is `Active | Decommissioned`, matching Supply's
lifecycle-terminal pattern. No operational sub-states (slots are
either in service or gone; runtime conditions like "misaligned"
live on the installed Asset's condition, not on the slot per the
Frame design rationale).

Transitions:
  - register_mount      -> Active (genesis)
  - decommission_mount  -> Decommissioned (terminal; guarded by
                           MountHasInstalledAsset if a specimen is
                           still installed AND by MountHasActiveChildren
                           if any child Mount is still Active)

`update_mount_placement`, `install_asset`, `uninstall_asset` do NOT
change status; they mutate the Placement / `installed_asset_id`
fields respectively. `update_mount_placement` is no-op-on-equal via the
make_mount_update_handler factory; `install_asset` is strict-not-
idempotent (re-installing into an occupied slot raises
MountAlreadyOccupied per the design's no-implicit-eviction anti-
hook); `uninstall_asset` likewise raises MountIsEmpty when there is
nothing to uninstall.

## Bounded VO

`SlotCode` is a trimmed-bounded-text VO via validate_bounded_text;
200 chars to match other CORA name VOs. Slot codes tend to be much
shorter in practice (`02-BM-A-K-01`).
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from cora.equipment.aggregates._drawing import Drawing
from cora.equipment.aggregates._placement import Placement
from cora.shared.bounded_text import validate_bounded_text

SLOT_CODE_MAX_LENGTH = 200


class MountStatus(StrEnum):
    """The Mount's lifecycle state.

    Binary: a slot is either in service (`Active`) or removed
    (`Decommissioned`). No operational sub-states; runtime alignment
    drift / specimen-condition lives on the installed Asset's
    `Asset.condition`, not on the slot.
    """

    ACTIVE = "Active"
    DECOMMISSIONED = "Decommissioned"


class InvalidSlotCodeError(ValueError):
    """The supplied slot code is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Mount slot_code must be 1-{SLOT_CODE_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class MountAlreadyExistsError(Exception):
    """Attempted to register a mount whose stream already has events."""

    def __init__(self, mount_id: UUID) -> None:
        super().__init__(f"Mount {mount_id} already exists")
        self.mount_id = mount_id


class MountNotFoundError(Exception):
    """Attempted an operation on a mount whose stream has no events."""

    def __init__(self, mount_id: UUID) -> None:
        super().__init__(f"Mount {mount_id} not found")
        self.mount_id = mount_id


class MountHasAssetInstalledError(Exception):
    """Attempted to decommission a mount that still has an installed Asset.

    Decommission requires the slot to be vacant. Operators must
    `uninstall_asset` first (no implicit eviction per the design
    anti-hook). `installed_asset_id` carries the
    offending Asset id for diagnostics.
    """

    def __init__(self, mount_id: UUID, installed_asset_id: UUID) -> None:
        super().__init__(
            f"Mount {mount_id} cannot be decommissioned: Asset "
            f"{installed_asset_id} is still installed; uninstall first"
        )
        self.mount_id = mount_id
        self.installed_asset_id = installed_asset_id


class MountHasFixtureBoundAssetError(Exception):
    """Attempted to uninstall an Asset that is still bound into a Fixture.

    Uninstall requires the installed Asset to carry no Fixture
    back-reference; popping a fixture-bound Asset off its Mount would
    silently strand the Fixture binding. Operators must
    `detach_asset_from_fixture` first (no implicit detach per the
    no-cascade anti-hook; mirrors `MountHasAssetInstalledError` on
    the inverse axis where decommission_asset rejects fixture-bound
    Assets).

    Carries `asset_id` (the installed Asset) and `fixture_id` (the
    Fixture currently binding it) so the operator error response can
    deep-link to detach.
    """

    def __init__(self, mount_id: UUID, asset_id: UUID, fixture_id: UUID) -> None:
        super().__init__(
            f"Mount {mount_id} cannot uninstall: Asset {asset_id} is still "
            f"bound to Fixture {fixture_id}; detach first"
        )
        self.mount_id = mount_id
        self.asset_id = asset_id
        self.fixture_id = fixture_id


class MountHasActiveChildrenError(Exception):
    """Attempted to decommission a mount with active child Mounts.

    No cascade-decommission per the design anti-hook: operators must
    decommission children first. `active_child_mount_ids` lists the
    offending children for diagnostics.
    """

    def __init__(self, mount_id: UUID, active_child_mount_ids: tuple[UUID, ...]) -> None:
        super().__init__(
            f"Mount {mount_id} cannot be decommissioned: "
            f"{len(active_child_mount_ids)} active child mount(s) "
            f"({list(active_child_mount_ids)!r})"
        )
        self.mount_id = mount_id
        self.active_child_mount_ids = active_child_mount_ids


class MountCannotUpdateError(Exception):
    """Attempted to mutate (update_mount_placement / install_asset /
    uninstall_asset) a decommissioned mount.

    Strict semantics: a Decommissioned mount is terminal; no further
    mutations. Operators must register a fresh mount instead. `reason`
    identifies which slice fired for diagnostics.
    """

    def __init__(self, mount_id: UUID, reason: str) -> None:
        super().__init__(f"Mount {mount_id} cannot be mutated: {reason}")
        self.mount_id = mount_id
        self.reason = reason


class MountCannotDecommissionError(Exception):
    """Attempted to decommission an already-decommissioned mount.

    Strict semantics: re-decommissioning is NOT idempotent at the
    domain layer; the second call raises. Mirrors
    FrameCannotDecommissionError.
    """

    def __init__(self, mount_id: UUID, reason: str) -> None:
        super().__init__(f"Mount {mount_id} cannot be decommissioned: {reason}")
        self.mount_id = mount_id
        self.reason = reason


class MountAlreadyOccupiedError(Exception):
    """Attempted to install an Asset into a mount that already holds one.

    No implicit eviction per the design anti-hook: operators must
    `uninstall_asset` first if they want to replace the specimen.
    `installed_asset_id` carries the existing occupant for
    diagnostics; `attempted_asset_id` is the new specimen the caller
    tried to install.
    """

    def __init__(
        self,
        mount_id: UUID,
        installed_asset_id: UUID,
        attempted_asset_id: UUID,
    ) -> None:
        super().__init__(
            f"Mount {mount_id} cannot install Asset {attempted_asset_id}: "
            f"Asset {installed_asset_id} is already installed; uninstall first"
        )
        self.mount_id = mount_id
        self.installed_asset_id = installed_asset_id
        self.attempted_asset_id = attempted_asset_id


class MountIsEmptyError(Exception):
    """Attempted to uninstall an Asset from a mount with no installed Asset.

    Symmetric with MountAlreadyOccupiedError. Operators cannot
    uninstall from a vacant slot.
    """

    def __init__(self, mount_id: UUID) -> None:
        super().__init__(f"Mount {mount_id} cannot uninstall: no Asset is installed")
        self.mount_id = mount_id


class AssetNotFoundForMountError(Exception):
    """Attempted to install an Asset that has no event-store stream.

    Loaded by the install_asset handler via the asset_lookup
    projection precondition BEFORE calling the pure decider. Distinct
    class from `cora.equipment.aggregates.asset.AssetNotFoundError`
    (which fires on Asset's own update-style slices) so the route
    handler can map this precondition-failure with its own HTTP code
    if the contract needs to diverge later. Today both map to 404.
    """

    def __init__(self, asset_id: UUID) -> None:
        super().__init__(f"Cannot install Asset {asset_id}: no Asset stream exists with that id")
        self.asset_id = asset_id


class AssetNotInstallableError(Exception):
    """Attempted to install an Asset whose lifecycle disallows installation.

    Only `Active` Assets can be installed. `Commissioned` Assets are
    pre-service (the operator must activate them first); `Maintenance`
    Assets are pulled for repair; `Decommissioned` Assets are retired
    and must not occupy live equipment slots. Mirrors Subject's
    mount-onto-Active-Asset-only precedent.

    Loaded by the install_asset handler via the asset_status projection
    precondition BEFORE calling the pure decider. `current_lifecycle`
    is the AssetLifecycle value carried on the projection row.
    """

    def __init__(self, asset_id: UUID, current_lifecycle: str) -> None:
        super().__init__(
            f"Cannot install Asset {asset_id}: currently in lifecycle "
            f"{current_lifecycle}, install requires Active"
        )
        self.asset_id = asset_id
        self.current_lifecycle = current_lifecycle


class AssetAlreadyInstalledElsewhereError(Exception):
    """Attempted to install an Asset that is already installed in a
    different Mount.

    Single-source-of-truth invariant: an Asset can occupy AT MOST ONE
    Mount slot at a time. The Mount aggregate's `installed_asset_id`
    is the write-side authority for the slot's occupant; the
    asset_location projection (`asset_id -> mount_id`) is the read-side
    back-lookup. This error fires when the back-lookup says the Asset
    is somewhere else.

    Operators must `uninstall_asset` from the current Mount first if
    they want to relocate.
    """

    def __init__(
        self,
        asset_id: UUID,
        currently_at_mount_id: UUID,
        attempted_mount_id: UUID,
    ) -> None:
        super().__init__(
            f"Asset {asset_id} cannot be installed in Mount "
            f"{attempted_mount_id}: already installed in Mount "
            f"{currently_at_mount_id}; uninstall from the current Mount first"
        )
        self.asset_id = asset_id
        self.currently_at_mount_id = currently_at_mount_id
        self.attempted_mount_id = attempted_mount_id


@dataclass(frozen=True)
class SlotCode:
    """External alias for a mount (e.g., APS 2-BM `02-BM-A-K-01`).

    Trimmed; 1-200 chars. Uniqueness is enforced per-facility-scope
    at the handler layer (via the `mount_slot_code` projection
    precondition), NOT at the VO. Two facilities could legitimately
    share a slot code in different deployments.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=SLOT_CODE_MAX_LENGTH,
            error_class=InvalidSlotCodeError,
        )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class Mount:
    """Aggregate root: a named slot in the beamline.

    `id` is the opaque UUID stream key; `slot_code` is the external
    alias operators use. Slot-code uniqueness is enforced via
    projection precondition at register time, not by the VO.

    `parent_id` is the immediate parent in the slot hierarchy
    tree (Assembly slot containing Device slots). None for top-level
    slots. Distinct axis from `placement.parent_frame_id` (which names
    the coordinate frame, NOT a Mount).

    `placement` is required (every slot has a position). `drawing`
    is optional (the engineering reference for the slot itself).

    `installed_asset_id` is the AssetId of the specimen currently
    in the slot, or None for a vacant slot. Single source of truth
    for "what's installed where"; the asset_location projection
    provides the reverse lookup.

    `status` transitions only `Active -> Decommissioned`. The
    install / uninstall / update_mount_placement slices do NOT change
    status.
    """

    id: UUID
    slot_code: SlotCode
    parent_id: UUID | None
    placement: Placement
    drawing: Drawing | None
    installed_asset_id: UUID | None
    status: MountStatus = MountStatus.ACTIVE
