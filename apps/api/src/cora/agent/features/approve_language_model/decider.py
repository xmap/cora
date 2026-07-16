"""Pure decider for the `ApproveLanguageModel` command.

Single-source transition: `Defined -> Approved`. Strict-not-idempotent.

## Validation

  - State must not be None -> `LanguageModelNotFoundError`
  - Current status must be `Defined` -> `LanguageModelCannotApproveError`
"""

from datetime import datetime

from cora.agent.aggregates.language_model import (
    LanguageModel,
    LanguageModelApproved,
    LanguageModelCannotApproveError,
    LanguageModelNotFoundError,
    LanguageModelStatus,
)
from cora.agent.features.approve_language_model.command import ApproveLanguageModel

_APPROVABLE_STATUSES: tuple[LanguageModelStatus, ...] = (LanguageModelStatus.DEFINED,)


def decide(
    state: LanguageModel | None,
    command: ApproveLanguageModel,
    *,
    now: datetime,
) -> list[LanguageModelApproved]:
    """Decide the events produced by approving a Defined LanguageModel.

    Invariants:
      - State must not be None -> LanguageModelNotFoundError
      - Current status must be Defined -> LanguageModelCannotApproveError
    """
    if state is None:
        raise LanguageModelNotFoundError(command.language_model_id)
    if state.status not in _APPROVABLE_STATUSES:
        raise LanguageModelCannotApproveError(state.id, state.status)

    return [
        LanguageModelApproved(
            language_model_id=state.id,
            occurred_at=now,
        )
    ]
