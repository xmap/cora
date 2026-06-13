"""Visit aggregate state, value objects, enums, and domain errors.

`Visit` is the operational-envelope counterpart to Trust's authz-topology
primitives (Conduit / Policy / Surface / Zone). It represents a team's
allocated time on a Surface for a Policy-scoped purpose: the
operational answer to "who is on this beamline today, doing what, until
when." Distinct from Campaign (scientific composition above Run) and
from Policy (stable authz rule); orthogonal axes, composition through
Surface + Run + Subject.

8-state FSM locked per `[[project_visit_aggregate_design]]`:

    Planned    -> Arrived    (operator explicit gesture; presence
                              tracking is separate per V6 lock)
    Arrived    -> InProgress (operator explicit start)
    InProgress <-> OnHold    (pause / resume cycle; OnHold reserved
                              for genuine envelope pauses: beam dump,
                              equipment fault, safety hold, extended
                              user break -- NOT for nested-child
                              commissioning, where parent stays
                              InProgress and control concern lives on
                              `proj_surface_active_visit`)
    InProgress | OnHold -> Completed   (normal terminal)
    Planned | Arrived   -> Cancelled   (pre-work cancel; never started)
    InProgress | OnHold -> Aborted     (work-started-then-stopped + reason)
    any non-terminal    -> Voided      (FHIR `entered-in-error` analog;
                                        "this Visit should never have
                                        existed", e.g. BSS double-sent)

The aggregate is intentionally slim per `[[project_fold_cost_principles]]`
and the thin-shape lock in `[[project_visit_aggregate_research]]`: 6
owned scalar fields plus 2 collections (`presence_entries`,
`external_refs`) plus 1 self-FK (`parent_id`).

## Two-tier period split

`planned_start_at` + `planned_end_at` live on STATE (operator-supplied
at registration; decider reads them for invariants such as
`planned_end_at > now()`). `actual_start_at` + `actual_end_at` live on
PROJECTION per `[[project_template_aggregate_timestamps]]` Path C
(derivable from VisitArrived / VisitStarted / Visit{Completed, Cancelled,
Aborted, Voided} event `occurred_at`).

## Lifecycle-via-explicit-gesture only

Visit lifecycle changes via explicit gesture only -- never auto-derived
from Supply / Asset / Safety / Schedule state. Subscriber may emit an
explicit command in response to those BCs' events, but the command is
audit-trail-visible. Direct application of
`[[project_non_determinism_principle]]` V6 lock.

## Bootstrap stance

Visit commands (`RegisterVisit`, `ArriveVisit`, ..., `VoidVisit`) are NOT
in the System Bootstrap Policy seed. The bootstrap seed stays at
`{DefinePolicy, RegisterActor}`; first real admin Policy grants Visit
commands post-bootstrap. See AuthZ matrix in design memo.

## VisitType closed enum

`VisitType` is a closed StrEnum (`user` / `commissioning` / `maintenance`
/ `calibration` / `staff`) following the `Affordance` precedent. Replaces
the sentinel-value anti-pattern (DMagic `--gup 0`, NICOS demo=0).
Adding a 6th type uses CORA's forward-only migration pattern (drop +
re-add CHECK constraint).

## No `Period` VO

CORA has no `Period` VO today; uses separate `*_at` fields per existing
convention. First rule-of-three on `(start_at, end_at)` pairs would hoist
a `Period` VO; not yet.

## Reason fields carry no PII

Free-text `reason` on Held / Cancelled / Aborted / Voided sits in the
immutable event log forever. Operator UI MUST display a "no PII"
placeholder warning. Cannot be grep-enforced (free-text); enforced by
review + UI affordance. Promote to a `VisitTransitionReason` VO with
structured fields at rule-of-three on PII-leakage incidents.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from cora.shared.identifier import Identifier
from cora.shared.text_bounds import REASON_MAX_LENGTH


class VisitStatus(StrEnum):
    """The Visit's lifecycle state.

    Eight values locked day one per `[[project_visit_aggregate_design]]`.

      - `Planned`    -- registered; not yet arrived; presence collection empty
      - `Arrived`    -- operator declared team on-site (or remote-checked-in);
                        no scans run yet
      - `InProgress` -- work has started (first Run, first take_control, OR
                        explicit start_visit)
      - `OnHold`     -- envelope paused (beam dump / equipment fault / safety
                        hold / extended user break); NOT used for
                        commissioning-during-user (parent stays InProgress)
      - `Completed`  -- normal terminal
      - `Cancelled`  -- pre-work cancel (never reached InProgress)
      - `Aborted`    -- work-started-then-stopped (always with reason)
      - `Voided`     -- FHIR entered-in-error analog: "should never have
                        existed" (BSS double-registration, duplicate, etc.)
    """

    PLANNED = "Planned"
    ARRIVED = "Arrived"
    IN_PROGRESS = "InProgress"
    ON_HOLD = "OnHold"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"
    ABORTED = "Aborted"
    VOIDED = "Voided"


class VisitType(StrEnum):
    """Closed enum classifying the operational nature of a Visit.

    Five values per `[[project_visit_aggregate_design]]`. Replaces the
    sentinel-value anti-pattern (DMagic `--gup 0`, NICOS demo=0).

      - `user`         -- proposal-driven user beamtime
      - `commissioning`-- detector / mechanism commissioning (nested as
                          partOf a parent user Visit per S2 scenario)
      - `maintenance`  -- preventative or corrective maintenance window
      - `calibration`  -- standalone calibration block (CalibrationRevision
                          is the data-side counterpart in Calibration BC)
      - `staff`        -- staff-only work outside a proposal envelope
    """

    USER = "user"
    COMMISSIONING = "commissioning"
    MAINTENANCE = "maintenance"
    CALIBRATION = "calibration"
    STAFF = "staff"


# ---------------------------------------------------------------------------
# Domain validation errors (raised by decider invariants)
# ---------------------------------------------------------------------------


class InvalidVisitPlannedPeriodError(ValueError):
    """`planned_end_at <= planned_start_at` at registration."""

    def __init__(self, planned_start_at: datetime, planned_end_at: datetime) -> None:
        super().__init__(
            f"Visit planned_end_at must be strictly after planned_start_at "
            f"(got start={planned_start_at.isoformat()}, end={planned_end_at.isoformat()})"
        )
        self.planned_start_at = planned_start_at
        self.planned_end_at = planned_end_at


class InvalidVisitReasonError(ValueError):
    """Reason text on hold / cancel / abort / void is empty or too long after trim."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Visit reason must be 1-{REASON_MAX_LENGTH} chars after trimming (got: {value!r})"
        )
        self.value = value


# ---------------------------------------------------------------------------
# Presence value object + mode enum
# ---------------------------------------------------------------------------


class PresenceMode(StrEnum):
    """How a participant is present at the Visit.

    Two values closed day-one per `[[project_visit_aggregate_design]]`:

      - `physical`  -- on-site (badge-in at the beamline)
      - `remote`    -- remote-checked-in (e.g., PI driving via API from
                       another time zone while the on-site postdoc runs
                       the bench; S3 scenario)
    """

    PHYSICAL = "physical"
    REMOTE = "remote"


@dataclass(frozen=True)
class PresenceEntry:
    """One actor's presence record on a Visit.

    Fully-immutable frozen dataclass with default `__hash__`/`__eq__` over
    ALL FOUR fields (per Identifier / Wire / AssetPort precedent). When
    `VisitCheckedOut` flips `check_out_at` from None to a timestamp, the
    evolver removes the open entry and inserts a NEW entry with the same
    `(actor_id, mode, check_in_at)` plus the populated `check_out_at` --
    the frozen-replace pattern. Old and new entries are distinct frozenset
    members because the hash differs on the 4th field.

    Composite uniqueness on `(actor_id, check_in_at)` is enforced by the
    decider (iterate `state.presence_entries` for an open entry before
    accepting a new check-in), not by the frozenset itself. The frozenset
    naturally dedups full 4-tuple duplicates (e.g., replay of the same
    VisitCheckedIn event after a closed entry already exists).

    Same actor may check in / out multiple times in one Visit (multi-shift
    presence: shift 1 closed, shift 2 open, both retained on state).
    """

    actor_id: UUID
    mode: PresenceMode
    check_in_at: datetime
    check_out_at: datetime | None = None


class VisitAlreadyCheckedInError(Exception):
    """Attempted to check in an actor who already has an open presence entry."""

    def __init__(self, visit_id: UUID, actor_id: UUID) -> None:
        super().__init__(
            f"Visit {visit_id}: actor {actor_id} is already checked in "
            f"(open presence entry exists; check out first)"
        )
        self.visit_id = visit_id
        self.actor_id = actor_id


class VisitActorNotCheckedInError(Exception):
    """Attempted to check out an actor who is not currently checked in."""

    def __init__(self, visit_id: UUID, actor_id: UUID) -> None:
        super().__init__(
            f"Visit {visit_id}: actor {actor_id} is not currently checked in "
            f"(no open presence entry)"
        )
        self.visit_id = visit_id
        self.actor_id = actor_id


# ---------------------------------------------------------------------------
# Aggregate-level guard errors (genesis collision / not-found / cannot-transition)
# ---------------------------------------------------------------------------


class VisitAlreadyExistsError(Exception):
    """Attempted to register a visit whose stream already has events.

    Per `[[project_genesis_error_classes]]` this class stays un-hoisted:
    per-BC isinstance routing in the BC's exception handler outweighs the
    ~80 LOC saved by hoisting.
    """

    def __init__(self, visit_id: UUID) -> None:
        super().__init__(f"Visit {visit_id} already exists")
        self.visit_id = visit_id


class VisitNotFoundError(Exception):
    """Attempted an operation on a visit whose stream has no events."""

    def __init__(self, visit_id: UUID) -> None:
        super().__init__(f"Visit {visit_id} not found")
        self.visit_id = visit_id


def _format_visit_cannot_message(
    visit_id: UUID,
    verb: str,
    current_status: VisitStatus,
    permitted_sources: tuple[VisitStatus, ...],
) -> str:
    permitted_str = " | ".join(s.value for s in permitted_sources)
    return (
        f"Visit {visit_id} cannot {verb}: currently in status "
        f"{current_status.value}, requires one of {permitted_str}"
    )


class VisitCannotArriveError(Exception):
    """arrive_visit guard failed: status is not in the permitted source set."""

    def __init__(
        self,
        visit_id: UUID,
        current_status: VisitStatus,
        permitted_sources: tuple[VisitStatus, ...],
    ) -> None:
        super().__init__(
            _format_visit_cannot_message(visit_id, "arrive", current_status, permitted_sources)
        )
        self.visit_id = visit_id
        self.current_status = current_status
        self.permitted_sources = permitted_sources


class VisitCannotStartError(Exception):
    """start_visit guard failed: status is not in the permitted source set."""

    def __init__(
        self,
        visit_id: UUID,
        current_status: VisitStatus,
        permitted_sources: tuple[VisitStatus, ...],
    ) -> None:
        super().__init__(
            _format_visit_cannot_message(visit_id, "start", current_status, permitted_sources)
        )
        self.visit_id = visit_id
        self.current_status = current_status
        self.permitted_sources = permitted_sources


class VisitCannotHoldError(Exception):
    """hold_visit guard failed: status is not in the permitted source set."""

    def __init__(
        self,
        visit_id: UUID,
        current_status: VisitStatus,
        permitted_sources: tuple[VisitStatus, ...],
    ) -> None:
        super().__init__(
            _format_visit_cannot_message(visit_id, "hold", current_status, permitted_sources)
        )
        self.visit_id = visit_id
        self.current_status = current_status
        self.permitted_sources = permitted_sources


class VisitCannotResumeError(Exception):
    """resume_visit guard failed: status is not in the permitted source set."""

    def __init__(
        self,
        visit_id: UUID,
        current_status: VisitStatus,
        permitted_sources: tuple[VisitStatus, ...],
    ) -> None:
        super().__init__(
            _format_visit_cannot_message(visit_id, "resume", current_status, permitted_sources)
        )
        self.visit_id = visit_id
        self.current_status = current_status
        self.permitted_sources = permitted_sources


class VisitCannotCompleteError(Exception):
    """complete_visit guard failed: status is not in the permitted source set."""

    def __init__(
        self,
        visit_id: UUID,
        current_status: VisitStatus,
        permitted_sources: tuple[VisitStatus, ...],
    ) -> None:
        super().__init__(
            _format_visit_cannot_message(visit_id, "complete", current_status, permitted_sources)
        )
        self.visit_id = visit_id
        self.current_status = current_status
        self.permitted_sources = permitted_sources


class VisitCannotCancelError(Exception):
    """cancel_visit guard failed: status is not in the permitted source set."""

    def __init__(
        self,
        visit_id: UUID,
        current_status: VisitStatus,
        permitted_sources: tuple[VisitStatus, ...],
    ) -> None:
        super().__init__(
            _format_visit_cannot_message(visit_id, "cancel", current_status, permitted_sources)
        )
        self.visit_id = visit_id
        self.current_status = current_status
        self.permitted_sources = permitted_sources


class VisitCannotAbortError(Exception):
    """abort_visit guard failed: status is not in the permitted source set."""

    def __init__(
        self,
        visit_id: UUID,
        current_status: VisitStatus,
        permitted_sources: tuple[VisitStatus, ...],
    ) -> None:
        super().__init__(
            _format_visit_cannot_message(visit_id, "abort", current_status, permitted_sources)
        )
        self.visit_id = visit_id
        self.current_status = current_status
        self.permitted_sources = permitted_sources


class VisitCannotVoidError(Exception):
    """void_visit guard failed: status is not in the permitted source set."""

    def __init__(
        self,
        visit_id: UUID,
        current_status: VisitStatus,
        permitted_sources: tuple[VisitStatus, ...],
    ) -> None:
        super().__init__(
            _format_visit_cannot_message(visit_id, "void", current_status, permitted_sources)
        )
        self.visit_id = visit_id
        self.current_status = current_status
        self.permitted_sources = permitted_sources


class VisitCannotCheckInError(Exception):
    """check_in_visit guard failed: status is not in the permitted source set."""

    def __init__(
        self,
        visit_id: UUID,
        current_status: VisitStatus,
        permitted_sources: tuple[VisitStatus, ...],
    ) -> None:
        super().__init__(
            _format_visit_cannot_message(visit_id, "check in", current_status, permitted_sources)
        )
        self.visit_id = visit_id
        self.current_status = current_status
        self.permitted_sources = permitted_sources


class VisitParentNotFoundError(Exception):
    """register_visit with parent_id set, but parent stream is empty."""

    def __init__(self, visit_id: UUID, parent_id: UUID) -> None:
        super().__init__(
            f"Visit {visit_id}: parent_id={parent_id} references a "
            f"parent visit whose stream has no events"
        )
        self.visit_id = visit_id
        self.parent_id = parent_id


class VisitParentMismatchedSurfaceError(Exception):
    """Child Visit's surface_id differs from its parent's surface_id.

    partOf cohesion lock: nested commissioning Visit (child) must operate
    on the SAME Surface as its parent user Visit. Cross-Surface partOf
    nesting would let a low-privilege operator inherit takeover rights
    on an arbitrary Surface they don't have authz for.
    """

    def __init__(
        self,
        visit_id: UUID,
        child_surface_id: UUID,
        parent_id: UUID,
        parent_surface_id: UUID,
    ) -> None:
        super().__init__(
            f"Visit {visit_id}: surface_id={child_surface_id} does not match parent "
            f"visit {parent_id}'s surface_id={parent_surface_id}; partOf "
            f"nesting requires same-Surface cohesion"
        )
        self.visit_id = visit_id
        self.child_surface_id = child_surface_id
        self.parent_id = parent_id
        self.parent_surface_id = parent_surface_id


class VisitCannotTakeControlError(Exception):
    """take_control_of_surface guard failed.

    Two causes (single class per Visit's `VisitCannot<Verb>Error`
    convention, matching the per-verb lifecycle transition errors
    `VisitCannotArriveError` / `VisitCannotStartError` / etc.):

      - Visit's status is not in {Arrived, InProgress, OnHold}; or
      - Surface already has an active controller AND requesting Visit
        is not a parent_id descendant of the current holder.

    The exception's `reason` discriminator distinguishes the two for
    log search + diagnostic messages.
    """

    def __init__(self, visit_id: UUID, surface_id: UUID, reason: str) -> None:
        super().__init__(f"Visit {visit_id} cannot take control of surface {surface_id}: {reason}")
        self.visit_id = visit_id
        self.surface_id = surface_id
        self.reason = reason


class VisitCannotReleaseControlError(Exception):
    """release_control_of_surface guard failed.

    Two causes (single class per Visit's `VisitCannot<Verb>Error`
    convention, matching `VisitCannotTakeControlError`):

      - Visit's surface_id does not match the command's surface_id; or
      - Visit is not the current holder per the projection snapshot.

    `reason` discriminates the two for log search. The current
    holder's id is captured on the instance (for structured logging)
    but kept OUT of the message text so the 409 response body does
    not leak the holder's identity to callers that lack read
    permission on the Surface.
    """

    def __init__(
        self,
        visit_id: UUID,
        surface_id: UUID,
        reason: str,
        current_holder_id: UUID | None = None,
    ) -> None:
        super().__init__(
            f"Visit {visit_id} cannot release control of surface {surface_id}: {reason}"
        )
        self.visit_id = visit_id
        self.surface_id = surface_id
        self.reason = reason
        self.current_holder_id = current_holder_id


# ---------------------------------------------------------------------------
# Visit aggregate state
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Visit:
    """Aggregate root: a team's operational envelope on a Surface.

    Slim aggregate per `[[project_visit_aggregate_design]]` thin-shape
    lock. Identity is a stable opaque `id: UUID`.

    `policy_id: UUID` is REQUIRED -- the authz envelope the Visit
    operates under. Trust BC's `Authorize` port already gates commands
    by Policy; Visit references the same Policy so a single source of
    truth answers "is this actor allowed to act in this Visit's
    context."

    `surface_id: UUID` is REQUIRED -- Visit is Surface-scoped (NOT
    Policy-scoped). One Policy may have many Visits (S8 multi-instrument
    case). Each Visit binds to exactly one Surface. Invariant enforced
    at register_visit.

    `type: VisitType` is REQUIRED -- closed enum classifying the
    operational nature. Replaces sentinel-value anti-pattern.

    `planned_start_at` + `planned_end_at` live on STATE (operator-
    supplied at registration; decider may read them for invariants).
    Actual periods live on projection per Path C.

    `parent_id: UUID | None` is the self-FK for commissioning-
    during-user nesting. Constraint at register_visit: child Visit must
    reference parent on the SAME Surface (`VisitParentMismatchedSurfaceError`).

    `external_refs: frozenset[Identifier]` is the open-scheme anti-
    corruption ref to upstream-deferred concepts (`proposal` / `btr` /
    `visit` / `cycle`). Reuses cross-BC infrastructure.

    `last_status_reason: str | None` is populated by Held / Cancelled /
    Aborted / Voided events. Carries the audit breadcrumb. Resume
    preserves the prior value.

    `presence_entries: frozenset[PresenceEntry]` tracks
    who actually checked in / out, in which mode (physical | remote),
    and when. The Visit lifecycle FSM operates independently of
    presence per V6 explicit-gesture lock: the operator can drive the
    full FSM without ever calling check_in_visit (and conversely,
    check_in_visit requires Visit.status in {Arrived, InProgress,
    OnHold} -- never auto-transitions Planned -> Arrived).

    No actor field on the aggregate beyond inherited
    `StoredEvent.principal_id` envelope. Audit truth ("who started /
    held / completed / aborted") lives on the event envelope. Presence
    actor_id on PresenceEntry IS aggregate state because the decider
    reads it (the open-entry guard for VisitAlreadyCheckedInError).
    """

    id: UUID
    policy_id: UUID
    surface_id: UUID
    type: VisitType
    planned_start_at: datetime
    planned_end_at: datetime
    parent_id: UUID | None = None
    external_refs: frozenset[Identifier] = field(default_factory=frozenset[Identifier])
    presence_entries: frozenset[PresenceEntry] = field(default_factory=frozenset[PresenceEntry])
    status: VisitStatus = VisitStatus.PLANNED
    last_status_reason: str | None = None
