"""Pure decider for the `DeprecateLanguageModel` command.

Source set is `{Defined, Approved, RetirementAnnounced}`: the
facility can withdraw at any pre-terminal point, but a Retired or
Deprecated entry is already terminal and re-terminating it would blur
which end the audit trail records. Strict-not-idempotent:
re-deprecating a Deprecated entry raises
`LanguageModelCannotDeprecateError`.

## Validation

  - State must not be None -> `LanguageModelNotFoundError`
  - Current status must be `Defined`, `Approved`, or
    `RetirementAnnounced` -> `LanguageModelCannotDeprecateError`
  - `reason` REQUIRED; wrapped via `LanguageModelReason(...)`;
    1-500 chars after trim -> `InvalidLanguageModelReasonError`.
"""

from datetime import datetime

from cora.agent.aggregates.language_model import (
    LanguageModel,
    LanguageModelCannotDeprecateError,
    LanguageModelDeprecated,
    LanguageModelNotFoundError,
    LanguageModelReason,
    LanguageModelStatus,
)
from cora.agent.features.deprecate_language_model.command import DeprecateLanguageModel

_DEPRECATABLE_STATUSES: tuple[LanguageModelStatus, ...] = (
    LanguageModelStatus.DEFINED,
    LanguageModelStatus.APPROVED,
    LanguageModelStatus.RETIREMENT_ANNOUNCED,
)


def decide(
    state: LanguageModel | None,
    command: DeprecateLanguageModel,
    *,
    now: datetime,
) -> list[LanguageModelDeprecated]:
    """Decide the events produced by deprecating a LanguageModel.

    Invariants:
      - State must not be None -> LanguageModelNotFoundError
      - Current status must be Defined, Approved, or
        RetirementAnnounced -> LanguageModelCannotDeprecateError
      - Reason must be valid -> InvalidLanguageModelReasonError
        (via LanguageModelReason VO)
    """
    if state is None:
        raise LanguageModelNotFoundError(command.language_model_id)
    if state.status not in _DEPRECATABLE_STATUSES:
        raise LanguageModelCannotDeprecateError(state.id, state.status)

    reason = LanguageModelReason(command.reason)

    return [
        LanguageModelDeprecated(
            language_model_id=state.id,
            reason=reason.value,
            occurred_at=now,
        )
    ]
