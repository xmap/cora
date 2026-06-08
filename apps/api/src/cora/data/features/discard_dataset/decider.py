"""Pure decider for the `DiscardDataset` command.

Single-source terminal: `Registered -> Discarded`. Strict semantics,
not idempotent: re-discarding an already-`Discarded` Dataset raises
rather than no-op (matches every other terminal-transition pattern
in the codebase).

`reason` validation goes through the `DatasetDiscardReason` VO
(which calls the shared `validate_bounded_text` helper). The on-the-wire
payload in `DatasetDiscarded.reason` carries the trimmed string.

Invariants:
  - State must not be None  -> DatasetNotFoundError
  - command.reason must be 1-500 chars after trimming
    -> InvalidDatasetDiscardReasonError
  - State.status must be `Registered`
    -> DatasetCannotDiscardError(current_status=...)
"""

from datetime import datetime

from cora.data.aggregates.dataset import (
    Dataset,
    DatasetCannotDiscardError,
    DatasetDiscarded,
    DatasetDiscardReason,
    DatasetNotFoundError,
    DatasetStatus,
)
from cora.data.features.discard_dataset.command import DiscardDataset
from cora.shared.identity import ActorId


def decide(
    state: Dataset | None,
    command: DiscardDataset,
    *,
    now: datetime,
    discarded_by: ActorId,
) -> list[DatasetDiscarded]:
    """Decide the events produced by discarding a Dataset."""
    if state is None:
        raise DatasetNotFoundError(command.dataset_id)
    reason = DatasetDiscardReason(command.reason)
    if state.status is not DatasetStatus.REGISTERED:
        raise DatasetCannotDiscardError(state.id, current_status=state.status)
    return [
        DatasetDiscarded(
            dataset_id=state.id,
            reason=reason.value,
            occurred_at=now,
            discarded_by=discarded_by,
        )
    ]
