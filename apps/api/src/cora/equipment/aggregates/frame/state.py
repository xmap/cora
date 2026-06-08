"""Frame aggregate state, status enum, and domain errors.

`Frame` is a named coordinate system. The first frames in any
deployment are the beamline centerlines (e.g., APS 2-BM's standard
1.35 mrad centerline, plus the alternate 5.1 mrad and 5.23 mrad
centerlines that engage when the mirror is in use). Mount placements
(and other Frame placements) reference a `parent_frame_id: UUID` field
that points at a Frame's `id`.

Frames form a tree: every Frame has a `parent_id` that is
either `None` (root frame, e.g., the storage-ring centerline as
defined by the facility) or points at another Frame. Cycles are
defensively rejected at register time (depth-bounded BFS, max depth
16); since there is no `reparent_frame` slice in v1, cycles can only
arise from manual data manipulation, but the defensive check stays
to catch that case loudly.

## Root frames versus child frames

The invariant is "both together, or both None":
  - Root frame: `parent_id is None` AND
    `placement is None`.
  - Child frame: both non-None, and the embedded
    `Placement.parent_frame_id` field MUST equal the Frame's own
    `parent_id` (the Placement points at the same parent that
    the Frame declares).

The decider enforces this invariant; `InvalidFrameRootError` carries
the offending combination for diagnostics.

## Lifecycle

`FrameStatus` is `Active | Decommissioned`, matching Supply's
lifecycle-terminal pattern (deregister_supply design). No operational
sub-states (no `Available`/`Degraded` analog for Frames): a frame
either exists in the coordinate hierarchy or it does not; runtime
"misalignment" is a property of the installed Asset, not of the slot
or frame.

Transitions:
  - `register_frame`            -> Active (genesis)
  - `decommission_frame`        -> Decommissioned (terminal; guarded
                                   by FrameInUseError if any active
                                   Mount.placement.parent_frame_id or
                                   active child Frame.parent_id
                                   references this frame)

`update_frame_placement` does NOT change status; it updates
`placement` and is a no-op when the new placement
equals the current one (idempotent contract via
`make_asset_update_handler`).

## Bounded-name VO

`FrameName` is the umpteenth trimmed-bounded-name VO; uses the
shared `validate_bounded_text` helper. The cap is 200 chars to
match `AssetName`; frame names tend to be much shorter
(`centerline_1p35_mrad`) but the cap protects the projection table
column without forcing a tighter discipline on operators.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from cora.equipment.aggregates._placement import Placement
from cora.shared.bounded_text import bounded_name

FRAME_NAME_MAX_LENGTH = 200


class FrameStatus(StrEnum):
    """The Frame's lifecycle state.

    Binary: a frame is either in service (`Active`) or removed
    (`Decommissioned`). No operational sub-states; runtime alignment
    drift lives on the installed Asset's `Asset.condition`, not on
    the frame.
    """

    ACTIVE = "Active"
    DECOMMISSIONED = "Decommissioned"


class InvalidFrameNameError(ValueError):
    """The supplied frame name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Frame name must be 1-{FRAME_NAME_MAX_LENGTH} chars after trimming (got: {value!r})"
        )
        self.value = value


class InvalidFrameRootError(ValueError):
    """A Frame's root-vs-child invariant was violated at register time.

    The invariant is "both fields together, or both None":
      - Root frame: `parent_id is None` AND
        `placement is None`.
      - Child frame: both non-None, and the embedded
        `Placement.parent_frame_id` MUST equal the Frame's own
        `parent_id`.

    Three failure modes folded into one error:
      1. `parent_id` is None but `placement`
         is not (or vice versa).
      2. Both are non-None but `placement.parent_frame_id` does not
         equal `parent_id`.

    `reason` identifies which case fired for diagnostics.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid Frame root configuration: {reason}")
        self.reason = reason


class FrameAlreadyExistsError(Exception):
    """Attempted to register a frame whose stream already has events."""

    def __init__(self, frame_id: UUID) -> None:
        super().__init__(f"Frame {frame_id} already exists")
        self.frame_id = frame_id


class FrameNotFoundError(Exception):
    """Attempted an operation on a frame whose stream has no events."""

    def __init__(self, frame_id: UUID) -> None:
        super().__init__(f"Frame {frame_id} not found")
        self.frame_id = frame_id


class FrameCannotUpdateError(Exception):
    """Attempted to update a frame under disqualifying conditions.

    Two failure modes folded into one error (mirrors
    `AssetCannotRelocateError` reason-bearing shape):
      - Frame is in `Decommissioned` status (re-issuing a placement
        update on a retired frame raises; operators must register a
        fresh frame instead).
      - Frame is a root frame (its `placement` is
        None by invariant; updating would create a placement on a
        root frame, violating the root-vs-child invariant).

    `reason` identifies which case fired for diagnostics; surfaces in
    the route's 409 body.
    """

    def __init__(self, frame_id: UUID, reason: str) -> None:
        super().__init__(f"Frame {frame_id} cannot be updated: {reason}")
        self.frame_id = frame_id
        self.reason = reason


class FrameCannotDecommissionError(Exception):
    """Attempted to decommission a frame under disqualifying conditions.

    Failure mode at the decider layer (no-active-consumers check
    runs separately via `FrameInUseError` at the handler layer):
      - Frame is already in `Decommissioned` status (re-decommissioning
        is NOT idempotent at the domain layer; the second call raises).

    `reason` identifies the case for diagnostics. The handler may
    wrap with idempotency at the application layer if needed by the
    caller's contract, but the domain itself rejects double-
    decommission.
    """

    def __init__(self, frame_id: UUID, reason: str) -> None:
        super().__init__(f"Frame {frame_id} cannot be decommissioned: {reason}")
        self.frame_id = frame_id
        self.reason = reason


class FrameInUseError(Exception):
    """Attempted to decommission a frame still referenced by active consumers.

    A frame is "in use" when any of the following hold:
      - Some active Mount's `Placement.parent_frame_id` points at this
        frame (lands once the Mount aggregate exists).
      - Some active child Frame's `parent_id` points at this
        frame.

    The handler loads consumers via the `frame_consumers` projection
    before calling the decider. `consumer_ids` lists the offending
    references for diagnostics; the route surfaces a 409.
    """

    def __init__(self, frame_id: UUID, consumer_ids: tuple[UUID, ...]) -> None:
        super().__init__(
            f"Frame {frame_id} cannot be decommissioned: still referenced by "
            f"{len(consumer_ids)} active consumer(s) ({list(consumer_ids)!r})"
        )
        self.frame_id = frame_id
        self.consumer_ids = consumer_ids


class InvalidFrameRevisionError(ValueError):
    """A FrameRevisionLink VO failed its within-VO invariant.

    The link carries a predecessor frame id plus a transform expressing
    where this frame's origin sits relative to the predecessor's. The
    transform's `parent_frame_id` field MUST equal `predecessor_frame_id`
    so the transform unambiguously names which frame it transforms
    from. Mirrors `Placement.__post_init__`'s within-VO validation
    precedent (finiteness, non-negative tolerance).

    Cross-Frame invariants (self-supersession, predecessor existence)
    live in the decider, not here.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid FrameRevisionLink: {reason}")
        self.reason = reason


class FrameCannotSupersedeError(Exception):
    """Attempted to register a frame whose `supersedes` link is rejected
    by decider-layer cross-Frame rules.

    Reason-bearing shape mirrors `FrameCannotUpdateError` /
    `FrameCannotDecommissionError`. v1 fires on one case:
      - Self-supersession: `supersedes.predecessor_frame_id` equals
        the frame's own `frame_id`.

    Predecessor existence is NOT checked here. The codebase follows
    eventual-consistency for cross-Frame references (per the
    Mount.placement.parent_frame_id precedent), so a supersedes pointer
    at a non-existent predecessor frame is data-integrity, not write-
    time rejection.
    """

    def __init__(self, frame_id: UUID, reason: str) -> None:
        super().__init__(f"Frame {frame_id} cannot supersede: {reason}")
        self.frame_id = frame_id
        self.reason = reason


@bounded_name(max_length=FRAME_NAME_MAX_LENGTH, error_class=InvalidFrameNameError)
@dataclass(frozen=True)
class FrameName:
    """Display name for a frame. Trimmed; 1-200 chars.

    Uniqueness is enforced per-parent-scope at the handler layer
    (via the `frame_name_lookup` projection precondition), NOT at
    the VO. Two root frames could legitimately share a name in
    different deployments, so global uniqueness is too strong.
    """

    value: str


@dataclass(frozen=True)
class FrameRevisionLink:
    """Links a Frame to the predecessor it revises.

    The predecessor is an older revision of the same physical
    coordinate system. Concrete example: APSU shifted the storage-ring
    reference origin, so a new `F_2BM_apsu` root frame supersedes
    the prior `F_2BM_pre_apsu` root frame. Both stay as root frames
    (siblings under the facility origin); revision and spatial
    hierarchy are deliberately separated.

    `transform_from_predecessor` is the Placement that maps a
    position expressed in the predecessor's coordinates to this
    frame's coordinates. The transform's `parent_frame_id` field MUST
    equal `predecessor_frame_id`; the within-VO invariant is enforced
    in `__post_init__` (mirror of `Placement.__post_init__`'s
    finiteness/tolerance checks).

    Cross-Frame invariants (self-supersession, predecessor existence)
    are decider/handler concerns, not VO concerns.
    """

    predecessor_frame_id: UUID
    transform_from_predecessor: Placement

    def __post_init__(self) -> None:
        if self.transform_from_predecessor.parent_frame_id != self.predecessor_frame_id:
            raise InvalidFrameRevisionError(
                f"transform.parent_frame_id ({self.transform_from_predecessor.parent_frame_id!s}) "
                f"must equal predecessor_frame_id ({self.predecessor_frame_id!s})"
            )


@dataclass(frozen=True)
class Frame:
    """Aggregate root: a named coordinate frame in the placement tree.

    `parent_id` is the immediate parent in the frame tree.
    `None` only for root frames (the storage-ring centerline at APS,
    for instance). Immutable across this aggregate's lifecycle (no
    `reparent_frame` slice in v1).

    `placement` is the pose of THIS frame's origin
    relative to its parent. `None` for root frames; non-None for
    child frames. The invariant
    `placement.parent_frame_id == parent_id` is enforced at the
    decider.

    `supersedes` marks this frame as a revision of an older frame
    (typically same physical coordinate system, e.g., post-upgrade
    re-survey of an origin). `None` for non-revision frames. Carries
    both the lineage pointer (predecessor_frame_id) and the geometric
    transform between the two coordinate systems. Set at registration
    only; immutable thereafter.

    `status` is `Active` at registration and transitions only to
    `Decommissioned` (terminal). The `update_frame_placement` slice mutates
    `placement` but leaves status and supersedes
    unchanged.
    """

    id: UUID
    name: FrameName
    parent_id: UUID | None
    placement: Placement | None
    supersedes: FrameRevisionLink | None = None
    status: FrameStatus = FrameStatus.ACTIVE
