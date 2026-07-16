"""Allocation aggregate state, VOs, enum, and domain errors.

`Allocation` is the spending envelope a holder receives and spends:
v1's holder is the deployment's own beamline (one CORA instance, one
beamline at the pilot), with an optional `campaign_id` reference that
binds the award window to a Campaign's lifecycle. Design lock:
[[project_allocation_design]].

Balance is never stored: it folds from the same inference ledger every
other spend tier sums, so this aggregate carries only the envelope's
declared shape (ceiling, note, window timestamps) and its FSM.

Per [[project_lifecycle_status_naming]] the FSM is a single axis,
`AllocationStatus`:

  Granted -> Active -> Sealed
  {Granted, Active} -> Voided

`Granted` is the award's dormant phase (granted at approval, dormant
until work starts); `Active` opens the spend window (`activated_at`);
`Sealed` closes the books with a final-spend snapshot
(`spent_usd_at_seal`), the normal terminal; `Voided` is the operator
withdrawing a mistaken grant, terminal without a spend snapshot. The
two terminals stay distinct because they answer different audit
questions (did this envelope's books close, or did the award never
stand?).

## Window

The allocation's own lifecycle IS the award window: `activated_at`
opens it and `sealed_at` closes it. No calendar arithmetic lives here;
the calendar case stays the per-agent caps' territory.

## Ceiling

`ceiling_usd` is USD-only at v1 (facility-unit accounting waits for
the first in-house GPU pool). It must be finite and strictly positive:
a zero or negative ceiling would make every envelope check refuse
unconditionally, and a non-finite one would never refuse, so both are
construction-time errors rather than representable states.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from math import isfinite
from uuid import UUID

from cora.shared.bounded_text import bounded_name, validate_bounded_text
from cora.shared.identity import ActorId
from cora.shared.text_bounds import REASON_MAX_LENGTH

ALLOCATION_NOTE_MAX_LENGTH = 200


class AllocationStatus(StrEnum):
    """The allocation envelope's lifecycle state.

    - `Granted` -- awarded but dormant; the spend window has not
                   opened and the envelope check does not arm.
    - `Active`  -- the spend window is open (`activated_at`); the
                   gate stack refuses spend that would breach
                   `ceiling_usd`.
    - `Sealed`  -- books closed with a final-spend snapshot
                   (`spent_usd_at_seal`). Terminal.
    - `Voided`  -- the operator withdrew a mistaken grant; no spend
                   snapshot because the award never stood. Terminal.
    """

    GRANTED = "Granted"
    ACTIVE = "Active"
    SEALED = "Sealed"
    VOIDED = "Voided"


# ---------------------------------------------------------------------------
# Domain validation errors (raised by VO __post_init__ + deciders)
# ---------------------------------------------------------------------------


class InvalidAllocationCeilingError(ValueError):
    """The supplied ceiling is not a finite, strictly positive USD amount.

    Zero and negative ceilings would refuse all spend unconditionally;
    NaN and infinity would never refuse. Both poison the envelope
    check, so they fail at the decider rather than folding into state.
    """

    def __init__(self, value: float) -> None:
        super().__init__(
            f"Allocation ceiling must be a finite USD amount greater than 0 (got {value!r})"
        )
        self.value = value


class InvalidAllocationNoteError(ValueError):
    """The supplied note is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Allocation note must be 1-{ALLOCATION_NOTE_MAX_LENGTH} chars "
            f"after trimming (got: {value!r})"
        )
        self.value = value


class InvalidAllocationReasonError(ValueError):
    """A supplied seal or void reason is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Allocation reason must be 1-{REASON_MAX_LENGTH} chars after trimming (got: {value!r})"
        )
        self.value = value


# ---------------------------------------------------------------------------
# Aggregate-level guard errors (genesis collision / not-found / cannot-transition)
# ---------------------------------------------------------------------------


class AllocationAlreadyExistsError(Exception):
    """Attempted to grant an allocation whose stream already has events.

    Per [[project_genesis_error_classes]] this stays un-hoisted.
    """

    def __init__(self, allocation_id: UUID) -> None:
        super().__init__(f"Allocation {allocation_id} already exists")
        self.allocation_id = allocation_id


class AllocationNotFoundError(Exception):
    """Attempted an operation on an allocation whose stream has no events."""

    def __init__(self, allocation_id: UUID) -> None:
        super().__init__(f"Allocation {allocation_id} not found")
        self.allocation_id = allocation_id


class AllocationCannotActivateError(Exception):
    """Attempted `activate_allocation` from a disqualifying status.

    Source set is `{Granted}` only: activation opens the spend window
    exactly once, and re-activating an Active, Sealed, or Voided
    envelope would silently reset or resurrect the window the seal's
    spend snapshot depends on.
    """

    def __init__(self, allocation_id: UUID, current_status: "AllocationStatus") -> None:
        super().__init__(
            f"Allocation {allocation_id} cannot be activated: currently in status "
            f"{current_status.value}, activate_allocation requires "
            f"{AllocationStatus.GRANTED.value}"
        )
        self.allocation_id = allocation_id
        self.current_status = current_status


class AllocationAlreadyActiveError(Exception):
    """Attempted to activate a second envelope while one is already Active.

    Best-effort single-writer guard on the deployment's one instrument
    envelope: the gates enforce a single Active allocation's ceiling and
    the sealer closes a single Active allocation on CampaignClosed, so a
    second Active envelope would silently reset the spend window (older
    ceiling stops being enforced) and orphan the first (its auto-seal
    would never fire). The active allocation must be sealed or voided
    before another is activated. The check reads the projection, so a
    tight concurrent race is possible and accepted; the invariant is a
    guard, not a lock.
    """

    def __init__(self, allocation_id: UUID, active_allocation_id: UUID) -> None:
        super().__init__(
            f"Allocation {allocation_id} cannot be activated: allocation "
            f"{active_allocation_id} is already Active; seal or void it first"
        )
        self.allocation_id = allocation_id
        self.active_allocation_id = active_allocation_id


class AllocationCannotAmendCeilingError(Exception):
    """Attempted `amend_allocation_ceiling` from a disqualifying status.

    Source set is `{Granted, Active}`: the ceiling is the cost-overrun
    tighten lever and stays amendable while the envelope can still
    spend, but a terminal envelope's books are closed and amending
    them would rewrite audit history.
    """

    def __init__(self, allocation_id: UUID, current_status: "AllocationStatus") -> None:
        super().__init__(
            f"Allocation {allocation_id} cannot amend its ceiling: currently in status "
            f"{current_status.value}, amend_allocation_ceiling requires "
            f"{AllocationStatus.GRANTED.value} or {AllocationStatus.ACTIVE.value}"
        )
        self.allocation_id = allocation_id
        self.current_status = current_status


class AllocationCannotSealError(Exception):
    """Attempted `seal_allocation` from a disqualifying status.

    Source set is `{Active}` only: the seal closes an OPEN spend
    window with a final-spend snapshot. A Granted envelope has no
    window to close (void it instead), and a terminal envelope is
    already closed.
    """

    def __init__(self, allocation_id: UUID, current_status: "AllocationStatus") -> None:
        super().__init__(
            f"Allocation {allocation_id} cannot be sealed: currently in status "
            f"{current_status.value}, seal_allocation requires {AllocationStatus.ACTIVE.value}"
        )
        self.allocation_id = allocation_id
        self.current_status = current_status


class AllocationCannotVoidError(Exception):
    """Attempted `void_allocation` from a disqualifying status.

    Source set is `{Granted, Active}`: voiding withdraws a mistaken
    grant while it still stands. A Sealed envelope's books are closed
    (the seal is the honest record) and a Voided one is already gone;
    re-terminating either would blur which end the audit trail
    records.
    """

    def __init__(self, allocation_id: UUID, current_status: "AllocationStatus") -> None:
        super().__init__(
            f"Allocation {allocation_id} cannot be voided: currently in status "
            f"{current_status.value}, void_allocation requires "
            f"{AllocationStatus.GRANTED.value} or {AllocationStatus.ACTIVE.value}"
        )
        self.allocation_id = allocation_id
        self.current_status = current_status


# ---------------------------------------------------------------------------
# Value objects + ceiling validation
# ---------------------------------------------------------------------------


@bounded_name(
    max_length=ALLOCATION_NOTE_MAX_LENGTH,
    error_class=InvalidAllocationNoteError,
)
@dataclass(frozen=True)
class AllocationNote:
    """Operator-facing name for the envelope. Trimmed; 1-200 chars.

    The note labels the envelope for operators (award cycle, proposal
    block).
    """

    value: str


@dataclass(frozen=True)
class AllocationReason:
    """Operator-sourced reason text. Trimmed; 1-500 chars.

    One VO for both the seal's optional closing note and the void's
    required withdrawal reason, sharing the fleet-wide
    REASON_MAX_LENGTH bound per [[project_reason_max_length]].
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=REASON_MAX_LENGTH,
            error_class=InvalidAllocationReasonError,
        )
        object.__setattr__(self, "value", trimmed)


def validate_allocation_ceiling(value: float) -> None:
    """Reject a ceiling that is not finite and strictly positive.

    Shared by the grant and amend deciders so both entry points to
    `ceiling_usd` enforce one rule; a bare float (not a VO) because
    the ceiling participates in arithmetic at the gate and a wrapper
    would be unwrapped at every comparison site.
    """
    if not isfinite(value) or value <= 0.0:
        raise InvalidAllocationCeilingError(value)


# ---------------------------------------------------------------------------
# Allocation aggregate state
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Allocation:
    """Aggregate root: one spending envelope for the deployment's beamline.

    Slim per [[project_fold_cost_principles]]: identity + declared
    shape + status + window timestamps + closing metadata. The
    `(granted_at, granted_by)` / `(activated_at, activated_by)` /
    `(sealed_at, sealed_by)` pairs are the fold-symmetric fact-act
    records per [[project_fold_symmetry_design]]. `spent_usd_at_seal`
    is the closing-the-books snapshot (None until sealed);
    `end_reason` carries whichever reason ended the envelope (the
    seal's optional note or the void's required reason).
    """

    id: UUID
    ceiling_usd: float
    note: AllocationNote
    campaign_id: UUID | None
    granted_at: datetime
    granted_by: ActorId
    status: AllocationStatus = AllocationStatus.GRANTED
    activated_at: datetime | None = None
    activated_by: ActorId | None = None
    sealed_at: datetime | None = None
    sealed_by: ActorId | None = None
    spent_usd_at_seal: float | None = None
    end_reason: str | None = None
