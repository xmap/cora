"""Pure decider for the `ApproveLanguageModel` command.

Single-source transition: `Defined -> Approved`. Strict-not-idempotent.

## Validation

  - State must not be None -> `LanguageModelNotFoundError`
  - Current status must be `Defined` -> `LanguageModelCannotApproveError`
  - The entry must not be priced per GPU-hour ->
    `LanguageModelCannotApproveGpuHourBasisError`. The pricing bridge
    skips a GPU-hour basis on ANY serving route, so approving one would
    install a live catalog member that silently records $0. Approval is
    what feeds the entry to the bridge, so this is where the built
    path's "declared free, never silent $0" rule is enforced; a GPU-hour
    entry stays definable (the honest primitive can be recorded) but is
    not approvable until the GPU-hour-debit arc gives it a live consumer.
"""

from datetime import datetime

from cora.agent.aggregates.language_model import (
    GpuHourPricing,
    LanguageModel,
    LanguageModelApproved,
    LanguageModelCannotApproveError,
    LanguageModelCannotApproveGpuHourBasisError,
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
      - Cost basis must not be GpuHourPricing (bridge-skipped on any
        route) -> LanguageModelCannotApproveGpuHourBasisError
    """
    if state is None:
        raise LanguageModelNotFoundError(command.language_model_id)
    if state.status not in _APPROVABLE_STATUSES:
        raise LanguageModelCannotApproveError(state.id, state.status)
    if isinstance(state.cost_basis, GpuHourPricing):
        raise LanguageModelCannotApproveGpuHourBasisError(state.id)

    return [
        LanguageModelApproved(
            language_model_id=state.id,
            occurred_at=now,
        )
    ]
