"""Pure decider for the `PromoteDataset` command.

Validation cascade (fail-fast in this order; cheap rejections first):

  1. Dataset exists -> DatasetNotFoundError (existing class, reused)
  2. Dataset is not Discarded -> DatasetCannotPromoteError
  3. Intent is currently Trial -> DatasetAlreadyPromotedError
     (strict-not-idempotent: re-promote raises)
  4. If producing_run_id is set, producing_run_end_state must be
     "Completed" -> DatasetCannotPromoteError
  5. All derived_from Datasets are Production -> DatasetCannotPromoteError
     (lineage integrity; mirrors prior lineage-into-Discarded guard)
  6. PromotionReason VO validates length (1-500 after trim)
     -> InvalidPromotionReasonError

See [[project_dataset_lineage_design]] for the locked design.
"""

from datetime import datetime

from cora.data.aggregates.dataset import (
    RUN_END_STATE_COMPLETED,
    Dataset,
    DatasetAlreadyPromotedError,
    DatasetCannotPromoteError,
    DatasetNotFoundError,
    DatasetPromoted,
    DatasetStatus,
    Intent,
    PromotionReason,
)
from cora.data.features.promote_dataset.command import PromoteDataset
from cora.data.features.promote_dataset.context import DatasetPromotionContext
from cora.shared.identity import ActorId


def decide(
    state: Dataset | None,
    command: PromoteDataset,
    *,
    context: DatasetPromotionContext,
    now: datetime,
    promoted_by: ActorId,
) -> list[DatasetPromoted]:
    """Decide the events produced by promoting a Dataset to Production.

    Invariants:
      - State must not be None -> DatasetNotFoundError
      - Status must not be Discarded -> DatasetCannotPromoteError
      - Intent must currently be Trial (strict-not-idempotent)
        -> DatasetAlreadyPromotedError
      - When producing_run_id is set, producing_run_end_state must
        be Completed -> DatasetCannotPromoteError
      - All derived_from Datasets must be Production
        -> DatasetCannotPromoteError
      - Reason must be valid -> InvalidPromotionReasonError
        (via PromotionReason VO)
    """
    if state is None:
        raise DatasetNotFoundError(command.dataset_id)

    # Guard 2: discarded Datasets cannot be promoted (no point — bytes
    # are gone). Rejected before intent + Run guards because discard
    # is a stronger statement than not-yet-promoted.
    if state.status is DatasetStatus.DISCARDED:
        raise DatasetCannotPromoteError(
            state.id,
            reason=(
                f"dataset is currently {state.status.value}; "
                "discarded datasets cannot be promoted to Production"
            ),
        )

    # Guard 3: strict-not-idempotent. Re-promote raises rather than
    # silently no-op (mirrors discard_dataset, add_plan_wire, every
    # other terminal-mutation pattern in the codebase).
    if state.intent is not Intent.TRIAL:
        raise DatasetAlreadyPromotedError(state.id, current_intent=state.intent)

    # Guard 4: producing-Run-must-be-Completed. Skipped when
    # producing_run_id is None (standalone-upload Dataset). Operationally:
    # a Run that aborted, stopped early, or got truncated didn't
    # produce publication-grade data.
    if (
        state.producing_run_id is not None
        and state.producing_run_end_state != RUN_END_STATE_COMPLETED
    ):
        raise DatasetCannotPromoteError(
            state.id,
            reason=(
                f"producing Run {state.producing_run_id} ended in "
                f"{state.producing_run_end_state!r}; only Runs that ended in "
                f"{RUN_END_STATE_COMPLETED!r} can produce Production datasets"
            ),
        )

    # Guard 5: lineage-must-be-Production. Skipped when derived_from
    # is empty (raw / standalone Datasets). Loaded peer states are
    # passed in via context.derived_from. Mirrors the lineage-into-
    # Discarded guard already shipped.
    if state.derived_from:
        not_yet_production = sorted(
            (
                derived_id
                for derived_id, loaded in context.derived_from.items()
                if loaded.intent is not Intent.PRODUCTION
            ),
            key=str,
        )
        if not_yet_production:
            raise DatasetCannotPromoteError(
                state.id,
                reason=(
                    f"the following derived_from Datasets are still "
                    f"{Intent.TRIAL.value}: {[str(d) for d in not_yet_production]}; "
                    "cannot promote a Dataset above its inputs (promote inputs first)"
                ),
            )

    # Guard 6: reason length validation. Last because it's a primitive
    # check the operator can fix without changing any state.
    reason = PromotionReason(command.reason)

    return [
        DatasetPromoted(
            dataset_id=state.id,
            reason=reason.value,
            occurred_at=now,
            promoted_by=promoted_by,
        )
    ]
