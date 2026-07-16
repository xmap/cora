"""Pure decider for the `RetireLanguageModel` command.

Source set is `{Approved, RetirementAnnounced}`: providers remove
models both with and without notice, so retirement is reachable
directly from Approved (the unannounced case keeps its honesty; the
at-risk-results projection simply had no warning window).
Strict-not-idempotent: re-retiring a Retired entry raises
`LanguageModelCannotRetireError`.

## Validation

  - State must not be None -> `LanguageModelNotFoundError`
  - Current status must be `Approved` or `RetirementAnnounced` ->
    `LanguageModelCannotRetireError`
  - `reason` wrapped via `LanguageModelReason(...)` when not None;
    1-500 chars after trim -> `InvalidLanguageModelReasonError`.
    None is allowed (unannounced removal with no vendor statement).
"""

from datetime import datetime

from cora.agent.aggregates.language_model import (
    LanguageModel,
    LanguageModelCannotRetireError,
    LanguageModelNotFoundError,
    LanguageModelReason,
    LanguageModelRetired,
    LanguageModelStatus,
)
from cora.agent.features.retire_language_model.command import RetireLanguageModel

_RETIRABLE_STATUSES: tuple[LanguageModelStatus, ...] = (
    LanguageModelStatus.APPROVED,
    LanguageModelStatus.RETIREMENT_ANNOUNCED,
)


def decide(
    state: LanguageModel | None,
    command: RetireLanguageModel,
    *,
    now: datetime,
) -> list[LanguageModelRetired]:
    """Decide the events produced by retiring a LanguageModel.

    Invariants:
      - State must not be None -> LanguageModelNotFoundError
      - Current status must be Approved or RetirementAnnounced
        -> LanguageModelCannotRetireError
      - Reason (when set) must be valid
        -> InvalidLanguageModelReasonError (via LanguageModelReason VO)
    """
    if state is None:
        raise LanguageModelNotFoundError(command.language_model_id)
    if state.status not in _RETIRABLE_STATUSES:
        raise LanguageModelCannotRetireError(state.id, state.status)

    reason: LanguageModelReason | None = None
    if command.reason is not None:
        reason = LanguageModelReason(command.reason)

    return [
        LanguageModelRetired(
            language_model_id=state.id,
            reason=reason.value if reason is not None else None,
            occurred_at=now,
        )
    ]
