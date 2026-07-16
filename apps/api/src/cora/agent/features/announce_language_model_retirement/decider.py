"""Pure decider for the `AnnounceLanguageModelRetirement` command.

Source set is `{Approved}` only: the announcement is meaningful only
for an entry the facility currently serves (a Defined entry the
vendor retires simply never gets approved; a terminal entry is past
caring). Strict-not-idempotent: re-announcing from
`RetirementAnnounced` raises `LanguageModelCannotAnnounceRetirementError`.

## Validation

  - State must not be None -> `LanguageModelNotFoundError`
  - Current status must be `Approved` ->
    `LanguageModelCannotAnnounceRetirementError`
  - `reason` REQUIRED; wrapped via `LanguageModelReason(...)`;
    1-500 chars after trim -> `InvalidLanguageModelReasonError`.

`effective_at` passes through unvalidated: a vendor cutoff in the
past is legitimate input (the operator may record an announcement
after the fact).
"""

from datetime import datetime

from cora.agent.aggregates.language_model import (
    LanguageModel,
    LanguageModelCannotAnnounceRetirementError,
    LanguageModelNotFoundError,
    LanguageModelReason,
    LanguageModelRetirementAnnounced,
    LanguageModelStatus,
)
from cora.agent.features.announce_language_model_retirement.command import (
    AnnounceLanguageModelRetirement,
)

_ANNOUNCEABLE_STATUSES: tuple[LanguageModelStatus, ...] = (LanguageModelStatus.APPROVED,)


def decide(
    state: LanguageModel | None,
    command: AnnounceLanguageModelRetirement,
    *,
    now: datetime,
) -> list[LanguageModelRetirementAnnounced]:
    """Decide the events produced by announcing a LanguageModel's retirement.

    Invariants:
      - State must not be None -> LanguageModelNotFoundError
      - Current status must be Approved
        -> LanguageModelCannotAnnounceRetirementError
      - Reason must be valid -> InvalidLanguageModelReasonError
        (via LanguageModelReason VO)
    """
    if state is None:
        raise LanguageModelNotFoundError(command.language_model_id)
    if state.status not in _ANNOUNCEABLE_STATUSES:
        raise LanguageModelCannotAnnounceRetirementError(state.id, state.status)

    reason = LanguageModelReason(command.reason)

    return [
        LanguageModelRetirementAnnounced(
            language_model_id=state.id,
            reason=reason.value,
            effective_at=command.effective_at,
            occurred_at=now,
        )
    ]
