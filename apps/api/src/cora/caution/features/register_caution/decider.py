"""Pure decider for the `RegisterCaution` command.

Pure function: given the current Caution state (None for a fresh
stream) and a `RegisterCaution` command, returns the events to
append. No I/O, no awaits, no side effects.

`now` and `new_id` are injected by the application handler from the
Clock and IdGenerator ports (the non-determinism principle:
capture, don't recompute).

## Validation

  - State must be None (genesis-only) -> `CautionAlreadyExistsError`
  - `text` wrapped via `CautionText(...)`; 1-2000 chars after trim ->
    `InvalidCautionTextError`
  - `workaround` wrapped via `CautionWorkaround(...)`; 1-2000 chars
    after trim -> `InvalidCautionWorkaroundError`. REQUIRED (corpus's
    strongest convergence; see Anti-hooks in the design memo).
  - Each `tag` wrapped via `CautionTag(...)`; 1-50 chars after trim
    -> `InvalidCautionTagError`. Empty tags-set IS allowed (the closed
    `category` enum carries the discriminator weight).
  - `expires_at <= now` if provided -> `InvalidCautionExpiresAtError`.
    Past-dated cautions can never warn anyone.

Initial status is implicit `Active` (event type IS the state-change
indicator; the genesis evolver hardcodes the mapping). The single
emitted event is `CautionRegistered` with `parent_id=None`
(top-level register; supersession-child genesis is emitted by the
`supersede_caution` decider with `parent_id` set).
"""

from datetime import datetime
from uuid import UUID

from cora.caution.aggregates.caution import (
    Caution,
    CautionAlreadyExistsError,
    CautionRegistered,
    CautionTag,
    CautionText,
    CautionWorkaround,
    ensure_expires_at_future,
)
from cora.caution.features.register_caution.command import RegisterCaution
from cora.shared.identity import ActorId


def decide(
    state: Caution | None,
    command: RegisterCaution,
    *,
    now: datetime,
    new_id: UUID,
    authored_by: ActorId,
) -> list[CautionRegistered]:
    """Decide the events produced by registering a new caution.

    Invariants:
      - State must be None (genesis-only) -> CautionAlreadyExistsError
      - Text must be valid -> InvalidCautionTextError
        (via CautionText VO)
      - Workaround must be valid -> InvalidCautionWorkaroundError
        (via CautionWorkaround VO)
      - Each tag must be valid -> InvalidCautionTagError
        (via CautionTag VO)
      - expires_at (when set) must be strictly future
        -> InvalidCautionExpiresAtError

    `authored_by` is handler-injected from the request envelope's
    `principal_id` (not on the command). At register time author and
    principal are equal by construction; the command surface omits the
    field so callers cannot spoof a different author.
    """
    if state is not None:
        raise CautionAlreadyExistsError(state.id)

    # Validate + trim body via VOs.
    text = CautionText(command.text)
    workaround = CautionWorkaround(command.workaround)
    tags = frozenset(CautionTag(t) for t in command.tags)

    ensure_expires_at_future(command.expires_at, now)

    return [
        CautionRegistered(
            caution_id=new_id,
            target=command.target,
            category=command.category.value,
            severity=command.severity.value,
            text=text.value,
            workaround=workaround.value,
            tags=frozenset(t.value for t in tags),
            authored_by=authored_by,
            expires_at=command.expires_at,
            propagate_to_children=command.propagate_to_children,
            parent_id=None,
            occurred_at=now,
        )
    ]
