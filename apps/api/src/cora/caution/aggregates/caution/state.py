"""Caution aggregate state, VOs, enums, target discriminated union, and domain errors.

`Caution` is an operator-authored tribal-knowledge note attached to
an Asset or a Procedure: the hexapod-stalls-below-0.5mm/s family. It
is distinct from Safety BC's formal regulatory Clearance (audience
separation: operator vocabulary vs ESH-officer vocabulary; lifecycle
weight asymmetry: 3-state lightweight vs 8-state formal FSM).

Per [[project_caution_design]] the 3-state FSM is locked day one:

  Active -> Superseded   (cross-aggregate edit path; parent links to child)
  Active -> Retired      (single-stream terminal with closed reason enum)

The aggregate is intentionally slim: identity + target + category +
severity + bounded-text body + bounded-text workaround + author +
tags + optional expires-at + propagation opt-in + status + supersession
+ retirement metadata. Per-transition audit metadata (timestamps,
actor identity) lives on the event-envelope (`StoredEvent.principal_id`
+ `recorded_at`); the projection denormalises the latest values for
query-time access.

## VO pattern reuse (14th / 15th / 16th bounded-text instances)

`CautionText` and `CautionWorkaround` are 1-2000 char trimmed strings.
`CautionTag` is a 1-50 char trimmed string (one tag per VO; the
aggregate carries `frozenset[CautionTag]`). All three follow the
established `validate_bounded_text` + `object.__setattr__` pattern
from the shared `cora.shared.bounded_text` helper.

## Target discriminated union (day-1: 2 kinds)

`AssetTarget(asset_id)` and `ProcedureTarget(procedure_id)` are the
day-1 lock per [[project_caution_design]]. `RunTarget` rejected
day-1 (Runs are short-lived; caution about one is unactionable);
`SubjectTarget` rejected day-1 (overlaps Subject.hazard field, a
Safety BC watch item). Both can be added additively when triggers
fire (see Watch items in the design memo).

## Severity ladder (ANSI Z535 downshifted)

`CautionSeverity` is the Z535 signal-word ladder downshifted one
notch (`Notice` / `Caution` / `Warning`). NO `Danger` tier because
formal-blocking authority lives in Safety BC Clearance; adding
`Danger` here would either dilute Caution into blocking (defeating
the BC's purpose) or duplicate Clearance functionality.

## Category enum (6 values closed) + free tags

`CautionCategory` is closed at 6 values derived from the synchrotron
+ EHS research corpora ('observed in the wild' lists). Free
`tags: frozenset[CautionTag]` absorbs facility-specific drift
without fragmenting the closed enum (ICAT `ParameterType` + Olog
`level` + `tags` precedent). Day-1 lock is intentionally narrow:
adding categories is cheap (additive StrEnum), pruning is expensive.

## Retire-reason enum (3 values closed)

`CautionRetireReason` mirrors the closed-reason precedent of
`truncate_run` / `truncate_procedure`. Free-form `reason: str`
rejected: operators already pick from a small mental list.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from cora.shared.bounded_text import validate_bounded_text
from cora.shared.identity import ActorId

CAUTION_TEXT_MAX_LENGTH = 2000
CAUTION_WORKAROUND_MAX_LENGTH = 2000
CAUTION_TAG_MAX_LENGTH = 50


class CautionStatus(StrEnum):
    """The Caution's lifecycle state.

    Three values locked day one per [[project_caution_design]]:

      - `Active`     -- currently in force; shows on Asset/Procedure view +
                        future Run.start banner (11b-c)
      - `Superseded` -- replaced by a newer caution; `superseded_by_caution_id`
                        links to the child
      - `Retired`    -- operator marked as resolved / no-longer-applies /
                        wrong-target; closed-reason enum on `retired_reason`

    3-state lifecycle is the corpus convergence for operator-authored
    lightweight artifacts (KEDB minus Resolved, KCS Article minus
    Approval, Cority Observation). Heavy regulated lifecycles
    (CAPA 6-state, MIL-STD-882 7-state) are explicitly rejected per
    Anti-hooks.
    """

    ACTIVE = "Active"
    SUPERSEDED = "Superseded"
    RETIRED = "Retired"


class CautionSeverity(StrEnum):
    """ANSI Z535 signal-word ladder, downshifted one notch.

    No `Danger` tier -- formal lockout / regulated-blocking lives in
    Safety BC Clearance. The downshifted ladder is the explicit
    BC-boundary marker.

      - `Notice`   -- informational FYI; default for asset-quirks ledger
      - `Caution`  -- will not block, may bite; default for operator-discovered issue
      - `Warning`  -- could harm work; reserve for things ESH would care about
                      but hasn't formalised
    """

    NOTICE = "Notice"
    CAUTION = "Caution"
    WARNING = "Warning"


class CautionCategory(StrEnum):
    """Closed controlled vocabulary, day-one lock at 6 values.

    Derived from synchrotron + EHS corpus 'observed in the wild' lists:
    motion + thermal + electrical -> engineering quirks; calibration +
    interlock; procedure. Tags absorb the rest (ICAT `ParameterType` +
    Olog `level` + `tags` precedent). Adding categories is cheap
    (additive StrEnum); pruning is expensive.
    """

    WEAR = "Wear"
    CALIBRATION = "Calibration"
    WIRING = "Wiring"
    OPERATIONAL_WINDOW = "OperationalWindow"
    INTERLOCK_QUIRK = "InterlockQuirk"
    PROCEDURE_GOTCHA = "ProcedureGotcha"


class CautionRetireReason(StrEnum):
    """Closed reason enum for retire_caution slice.

    Three values mirror the `truncate_run` / `truncate_procedure`
    reason precedent. Free-form `reason: str` rejected: forces
    read-side analytics to bucket, and operators already pick from a
    small mental list.
    """

    RESOLVED = "Resolved"
    NO_LONGER_APPLIES = "NoLongerApplies"
    WRONG_TARGET = "WrongTarget"


# ---------------------------------------------------------------------------
# Domain validation errors (raised by VO __post_init__ + deciders)
# ---------------------------------------------------------------------------


class InvalidCautionTextError(ValueError):
    """The supplied caution text is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Caution text must be 1-{CAUTION_TEXT_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class InvalidCautionWorkaroundError(ValueError):
    """The supplied caution workaround is empty, whitespace-only, or too long.

    `workaround` is REQUIRED (corpus's strongest convergence: KEDB,
    MIL-STD-882, OSHA 1910.119, CAPA all mandate it). The whole BC
    reduces to logbook-spam if cautions can be written without a
    'what does the operator DO about it' field.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Caution workaround must be 1-{CAUTION_WORKAROUND_MAX_LENGTH} chars "
            f"after trimming (got: {value!r})"
        )
        self.value = value


class InvalidCautionTagError(ValueError):
    """A supplied tag is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Caution tag must be 1-{CAUTION_TAG_MAX_LENGTH} chars after trimming (got: {value!r})"
        )
        self.value = value


class InvalidCautionExpiresAtError(ValueError):
    """The supplied expires_at is not strictly in the future (relative to occurred_at).

    Past-dated cautions can never warn anyone, so the decider refuses
    them. Validated at register and at supersede (where the child
    inherits the same constraint).
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidCautionSupersedeTargetError(ValueError):
    """Child caution's target does not match the parent's target.

    Supersession preserves target; retargeting confuses lineage and
    breaks the read-side 'active cautions on Asset X' query (which
    needs target-stability across supersession chains). Operators
    who want a different target start a new caution.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


# ---------------------------------------------------------------------------
# Aggregate-level guard errors (genesis collision / not-found / cannot-transition)
# ---------------------------------------------------------------------------


class CautionAlreadyExistsError(Exception):
    """Attempted to register a caution whose stream already has events.

    Per [[project_genesis_error_classes]] this class stays un-hoisted:
    per-BC isinstance routing in the BC's exception handler outweighs
    the ~80 LOC saved by hoisting to a generic `AggregateAlreadyExists`
    error.
    """

    def __init__(self, caution_id: UUID) -> None:
        super().__init__(f"Caution {caution_id} already exists")
        self.caution_id = caution_id


class CautionNotFoundError(Exception):
    """Attempted an operation on a caution whose stream has no events."""

    def __init__(self, caution_id: UUID) -> None:
        super().__init__(f"Caution {caution_id} not found")
        self.caution_id = caution_id


class CautionCannotSupersedeError(Exception):
    """Attempted `supersede_caution` from a disqualifying status.

    Single-source guard: source set is `{Active}` only. Cannot supersede
    a Retired or already-Superseded caution; start a new one instead.
    Mirrors `ClearanceCannotAmendError` shape.
    """

    def __init__(self, caution_id: UUID, current_status: "CautionStatus") -> None:
        super().__init__(
            f"Caution {caution_id} cannot be superseded: currently in status "
            f"{current_status.value}, supersede_caution requires "
            f"{CautionStatus.ACTIVE.value}"
        )
        self.caution_id = caution_id
        self.current_status = current_status


class CautionCannotRetireError(Exception):
    """Attempted `retire_caution` from a disqualifying status.

    Single-source guard: source set is `{Active}` only. Cannot retire
    a Superseded caution (it's already terminal via a different path)
    and cannot re-retire an already-Retired one (strict-not-idempotent).
    """

    def __init__(self, caution_id: UUID, current_status: "CautionStatus") -> None:
        super().__init__(
            f"Caution {caution_id} cannot be retired: currently in status "
            f"{current_status.value}, retire_caution requires "
            f"{CautionStatus.ACTIVE.value}"
        )
        self.caution_id = caution_id
        self.current_status = current_status


# ---------------------------------------------------------------------------
# Bounded-text value objects (14th, 15th, 16th instances of the pattern)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CautionText:
    """Free-form caution body. Trimmed; 1-2000 chars.

    Fourteenth occurrence of the trimmed-bounded-text VO pattern. Uses
    the shared `validate_bounded_text` helper.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=CAUTION_TEXT_MAX_LENGTH,
            error_class=InvalidCautionTextError,
        )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class CautionWorkaround:
    """The 'what to DO about it' field. Trimmed; 1-2000 chars. REQUIRED.

    Fifteenth occurrence of the trimmed-bounded-text VO pattern. The
    corpus's strongest convergence: KEDB, MIL-STD-882, OSHA 1910.119,
    CAPA all REQUIRE this field. The whole BC reduces to logbook-spam
    if cautions can be written without it.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=CAUTION_WORKAROUND_MAX_LENGTH,
            error_class=InvalidCautionWorkaroundError,
        )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class CautionTag:
    """One free-form tag. Trimmed; 1-50 chars per tag.

    Sixteenth occurrence of the trimmed-bounded-text VO pattern. The
    aggregate carries `frozenset[CautionTag]`; an empty set is allowed
    (the closed `category` enum carries the discriminator weight).
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=CAUTION_TAG_MAX_LENGTH,
            error_class=InvalidCautionTagError,
        )
        object.__setattr__(self, "value", trimmed)


# ---------------------------------------------------------------------------
# CautionTarget: day-1 2-arm discriminated union (Asset / Procedure)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AssetTarget:
    """Caution attached to an Asset (equipment quirk).

    Maximo HAZARDS / PI AF / ICAT / EPICS precedent: operators look
    at Asset when planning, so an Asset-attached caution surfaces at
    the right decision time.
    """

    asset_id: UUID


@dataclass(frozen=True)
class ProcedureTarget:
    """Caution attached to a Procedure (procedure-gotcha quirk).

    Synchrotron corpus's `procedure-gotcha` category proves operators
    reach for procedure-attached cautions ('this calibration must run
    after thermal-soak finishes'; 'do NOT skip the encoder home').
    """

    procedure_id: UUID


type CautionTarget = AssetTarget | ProcedureTarget
"""Day-1 lock: 2 kinds (Asset / Procedure).

`RunTarget` rejected day-1 (Runs are short-lived; caution about one is
unactionable). `SubjectTarget` rejected day-1 (overlaps Subject.hazard
field, Safety BC watch item #3). Both can be added additively when
triggers fire (see [[project_caution_design]] Watch items).
"""


# ---------------------------------------------------------------------------
# Caution aggregate state
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Caution:
    """Aggregate root: an operator-authored tribal-knowledge note.

    Slim aggregate per [[project_fold_cost_principles]]: identity +
    target + classification + body + author + status + supersession +
    retirement metadata.

    Identity is a stable opaque `id: UUID`. No `external_id` field
    today: cautions are internal operational artifacts; no facility-
    minted regulatory ID exists for them (distinguishes from Clearance
    which has `external_id` for facility IDs like 'ESAF-12345'). If a
    future trigger demands external linkage (LIMS-issued note ID,
    vendor recommendation ID), it lands as additive
    `external_id: str | None`.

    `parent_id` is set on a superseding child (links to the
    superseded parent). `superseded_by_caution_id` is set on the
    superseded parent (links to the child). The two pointers together
    form the supersession lineage chain; both come from
    `CautionSuperseded` (on the parent) + `CautionRegistered` with
    `parent_id` set (on the child genesis), written atomically
    via `EventStore.append_streams` mirroring `amend_clearance`.

    `propagate_to_children` is an explicit opt-in for Asset-hierarchy
    inheritance (AVEVA AF template-inheritance anti-pattern guard;
    EHS corpus). Default `False`. When True (today: hint-only;
    11b-b projection walks Asset.parent_id downward at query time).

    `authored_by`: genesis author identity, inherited unchanged
    through CautionSuperseded and CautionRetired; the superseding /
    retiring actor lives on the envelope (`StoredEvent.principal_id`)
    per Path C.
    """

    id: UUID
    target: CautionTarget
    category: CautionCategory
    severity: CautionSeverity
    text: CautionText
    workaround: CautionWorkaround
    authored_by: ActorId
    tags: frozenset[CautionTag] = field(default_factory=frozenset[CautionTag])
    expires_at: datetime | None = None
    propagate_to_children: bool = False
    status: CautionStatus = CautionStatus.ACTIVE
    parent_id: UUID | None = None
    superseded_by_caution_id: UUID | None = None
    retired_reason: CautionRetireReason | None = None
