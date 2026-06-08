"""Pure decider for the `DemoteDataset` command (post-Q4 compensation primitive).

Validation cascade (fail-fast in this order; cheap rejections first):

  1. Dataset exists -> DatasetNotFoundError
  2. Dataset is not Discarded -> DatasetCannotDemoteError
     (Discarded is GDPR-shaped terminal; bytes gone; no point demoting.
     Rejected before intent guard because discard is a stronger
     statement than current-intent.)
  3. Intent is currently Production:
       - if currently Retracted -> DatasetAlreadyRetractedError
         (strict-not-idempotent: re-demote raises)
       - if currently Trial -> DatasetCannotDemoteError
         (semantically meaningless: Trial→Retracted would conflate
         "never authoritative" with "was authoritative but now isn't";
         use discard_dataset for the former)
  4. DemotionReason VO validates length (1-500 after trim)
     -> InvalidDemotionReasonError

NO cross-BC cascade: demoting this Dataset does NOT auto-demote
downstream Datasets that derived_from it. Operator must demote each
explicitly (mirrors [[project-calibration-design]] anti-hook #3).

See [[project-dataset-demote-design]] for the locked design.
"""

from datetime import datetime

from cora.data.aggregates.dataset import (
    Dataset,
    DatasetAlreadyRetractedError,
    DatasetCannotDemoteError,
    DatasetDemoted,
    DatasetNotFoundError,
    DatasetStatus,
    DemotionReason,
    Intent,
)
from cora.data.features.demote_dataset.command import DemoteDataset
from cora.shared.identity import ActorId


def decide(
    state: Dataset | None,
    command: DemoteDataset,
    *,
    now: datetime,
    demoted_by: ActorId,
) -> list[DatasetDemoted]:
    """Decide the events produced by demoting a Dataset to Retracted.

    Invariants:
      - State must not be None -> DatasetNotFoundError
      - Status must not be Discarded -> DatasetCannotDemoteError
      - Intent must not already be Retracted (strict-not-idempotent)
        -> DatasetAlreadyRetractedError
      - Intent must currently be Production
        -> DatasetCannotDemoteError (Trial uses discard_dataset)
      - Reason must be valid -> InvalidDemotionReasonError
        (via DemotionReason VO)
    """
    if state is None:
        raise DatasetNotFoundError(command.dataset_id)

    # Guard 2: discarded Datasets cannot be demoted. Discarded is a
    # stronger terminal than Retracted (GDPR-shaped: bytes are gone).
    # Rejected before intent guard because discard is a stronger
    # statement than current-intent.
    if state.status is DatasetStatus.DISCARDED:
        raise DatasetCannotDemoteError(
            state.id,
            reason=(
                f"dataset is currently {state.status.value}; "
                "discarded datasets cannot be demoted to Retracted"
            ),
        )

    # Guard 3a: strict-not-idempotent. Re-demote raises rather than
    # silently no-op (mirrors promote, discard, add_plan_wire, every
    # other terminal-mutation pattern in the codebase).
    if state.intent is Intent.RETRACTED:
        raise DatasetAlreadyRetractedError(state.id, current_intent=state.intent)

    # Guard 3b: source-state must be Production. Trial→Retracted
    # would conflate "never authoritative" with "was authoritative
    # but now isn't"; operators should use discard_dataset for the
    # former (per [[project-dataset-demote-design]] lock).
    if state.intent is not Intent.PRODUCTION:
        raise DatasetCannotDemoteError(
            state.id,
            reason=(
                f"dataset is currently in intent {state.intent.value}; "
                f"demotion requires {Intent.PRODUCTION.value} "
                f"(use discard_dataset for {Intent.TRIAL.value} cleanup)"
            ),
        )

    # Guard 4: reason length validation. Last because it's a primitive
    # check the operator can fix without changing any state.
    reason = DemotionReason(command.reason)

    return [
        DatasetDemoted(
            dataset_id=state.id,
            reason=reason.value,
            occurred_at=now,
            demoted_by=demoted_by,
        )
    ]
