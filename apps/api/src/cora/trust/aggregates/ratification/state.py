"""Ratification aggregate state, value objects, enum, and domain errors.

`Ratification` is the consequence gate's aggregate: the record that a
consequential action is awaiting, or has received, a second independent
principal's co-signature before it may proceed. It is the "must a second
principal co-sign?" member of the governance-gate family, the deontic
co-action counterpart to Trust's permission gate (Policy / Authorize).

Where it sits
-------------
A Ratification is requested for a target action (a command against a run or
other aggregate) whose declared consequence class requires co-signature. The
pending action is parked in the shared reversible hold; a second, independent
principal grants or denies the ratification; a grant releases the hold and lets
the action proceed. This aggregate owns only the co-signature lifecycle; the
consequence-class declaration and the decider gate that consults it are the
wiring increment (see the implementation plan), and the hold reuse is the
shipped kill-switch. This increment lands the aggregate DORMANT: nothing gates
on it yet, so it changes no existing behavior.

3-state FSM
-----------

    Requested -> Granted    (a different, independent principal co-signs)
    Requested -> Denied     (a different, independent principal refuses; + reason)

`Requested` is genesis; `Granted` and `Denied` are terminal. There is no
re-open: a denied action's requester issues a fresh request if warranted, the
same strict-not-idempotent stance the sibling FSM aggregates take.

Kind-blindness (consequence-gate invariant)
-------------------------------------------
The co-signature requirement attaches to the action's consequence, never to the
actor's kind: a human running a first-of-a-kind irreversible action is held for
co-signature identically to an agent. `requested_by` and the granting/denying
principal are bare identifiers; no decider in this aggregate reads actor kind.

Independence
------------
The grant/deny principal must differ from `requested_by`: a principal cannot
ratify its own pending action. This is the four-eyes property the gate exists to
provide, enforced in the grant/deny deciders and pinned by a unit test.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from cora.shared.text_bounds import REASON_MAX_LENGTH


class RatificationStatus(StrEnum):
    """The Ratification's lifecycle state.

    Three values, locked day one:

      - `Requested` -- genesis; a co-signature is required and not yet given.
                       The target action is parked in the shared reversible hold.
      - `Granted`   -- a different, independent principal co-signed; terminal.
                       The hold on the target action may be released.
      - `Denied`    -- a different, independent principal refused; terminal.
                       The target action stays held (+ operator-supplied reason).
    """

    REQUESTED = "Requested"
    GRANTED = "Granted"
    DENIED = "Denied"


# ---------------------------------------------------------------------------
# Domain validation + transition-guard errors (raised by decider invariants)
# ---------------------------------------------------------------------------


class RatificationAlreadyExistsError(Exception):
    """A ratification with the requested id already exists (genesis collision)."""

    def __init__(self, ratification_id: UUID) -> None:
        super().__init__(f"Ratification {ratification_id} already exists")
        self.ratification_id = ratification_id


class RatificationNotFoundError(Exception):
    """No ratification exists for the given id (transition on an empty stream)."""

    def __init__(self, ratification_id: UUID) -> None:
        super().__init__(f"Ratification {ratification_id} not found")
        self.ratification_id = ratification_id


class RatificationCannotGrantError(Exception):
    """Grant attempted from a non-`Requested` status (already terminal)."""

    def __init__(self, ratification_id: UUID, current_status: RatificationStatus) -> None:
        super().__init__(
            f"Ratification {ratification_id} cannot be granted: currently "
            f"{current_status.value} (grant requires Requested)"
        )
        self.ratification_id = ratification_id
        self.current_status = current_status


class RatificationCannotDenyError(Exception):
    """Deny attempted from a non-`Requested` status (already terminal)."""

    def __init__(self, ratification_id: UUID, current_status: RatificationStatus) -> None:
        super().__init__(
            f"Ratification {ratification_id} cannot be denied: currently "
            f"{current_status.value} (deny requires Requested)"
        )
        self.ratification_id = ratification_id
        self.current_status = current_status


class RatificationRequesterCannotSelfRatifyError(Exception):
    """The grant/deny principal is the same as the requester (independence breach).

    The consequence gate requires a DIFFERENT, INDEPENDENT second principal. A
    principal cannot ratify its own pending action; this is the four-eyes
    invariant. Kind-blind: the check compares bare principal identifiers and
    never reads actor kind.
    """

    def __init__(self, ratification_id: UUID, principal_id: UUID) -> None:
        super().__init__(
            f"Ratification {ratification_id} cannot be co-signed by its requester "
            f"{principal_id}: an independent second principal is required"
        )
        self.ratification_id = ratification_id
        self.principal_id = principal_id


class InvalidConsequenceClassError(ValueError):
    """`consequence_class` is empty or too long after trim."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"consequence_class must be 1-{CONSEQUENCE_CLASS_MAX_LENGTH} chars "
            f"after trimming (got: {value!r})"
        )
        self.value = value


class InvalidRatificationReasonError(ValueError):
    """Reason text on deny is empty or too long after trim."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Ratification reason must be 1-{REASON_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


CONSEQUENCE_CLASS_MAX_LENGTH = 100
"""Max length of a `consequence_class` label, after trim.

A consequence class is a short bare-string label (e.g. `first_of_kind`,
`irreversible`) a capability declares for an action. Bare-str now, following
the Supply.kind / Procedure.kind precedent; graduates to a closed StrEnum when
the vocabulary stabilizes.
"""


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Ratification:
    """A co-signature record for a consequential target action.

    Slim by design: the aggregate owns the co-signature lifecycle and a
    reference to the target action it gates, nothing more. The target's own
    state (its hold) lives on the target aggregate; this record only tracks
    whether the required second signature is pending, given, or refused.

    Fields:
      - `id`                 -- the Ratification stream id.
      - `target_action_id`         -- opaque identifier of the action being gated
                                (e.g. the run id whose consequential command is
                                held). Not existence-checked here per the
                                cross-BC eventual-consistency stance.
      - `command_name`       -- the canonical name of the gated command.
      - `consequence_class`  -- the declared class that triggered the requirement.
      - `requested_by`       -- bare principal id of the requester (the actor
                                whose action is held). Independence is checked
                                against this on grant/deny.
      - `status`             -- lifecycle state.
      - `last_reason`        -- operator-supplied reason on deny (None otherwise).
    """

    id: UUID
    target_action_id: UUID
    command_name: str
    consequence_class: str
    requested_by: UUID
    status: RatificationStatus
    last_reason: str | None
