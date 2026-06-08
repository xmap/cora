"""Unit tests for the `discard_dataset` slice's pure decider.

Single-source terminal: `Registered -> Discarded`. Strict semantics
(re-discarding raises). Reason validated via DatasetDiscardReason
VO.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    DATASET_DISCARD_REASON_MAX_LENGTH,
    Dataset,
    DatasetCannotDiscardError,
    DatasetChecksum,
    DatasetDiscarded,
    DatasetEncoding,
    DatasetName,
    DatasetNotFoundError,
    DatasetStatus,
    DatasetUri,
    InvalidDatasetDiscardReasonError,
)
from cora.data.features import discard_dataset
from cora.data.features.discard_dataset import DiscardDataset
from cora.shared.identity import ActorId

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)
_DISCARDED_BY = ActorId(UUID("01900000-0000-7000-8000-000000000099"))


def _dataset(*, status: DatasetStatus = DatasetStatus.REGISTERED) -> Dataset:
    return Dataset(
        id=uuid4(),
        name=DatasetName("seed"),
        uri=DatasetUri("s3://b/k"),
        checksum=DatasetChecksum(algorithm="sha256", value=_GOOD_SHA256),
        byte_size=0,
        encoding=DatasetEncoding(media_type="application/x-hdf5"),
        status=status,
    )


@pytest.mark.unit
def test_decide_emits_dataset_discarded_with_trimmed_reason() -> None:
    state = _dataset()
    events = discard_dataset.decide(
        state=state,
        command=DiscardDataset(
            dataset_id=state.id,
            reason="  GDPR Article 17 erasure request  ",
        ),
        now=_NOW,
        discarded_by=_DISCARDED_BY,
    )
    assert events == [
        DatasetDiscarded(
            dataset_id=state.id,
            reason="GDPR Article 17 erasure request",
            occurred_at=_NOW,
            discarded_by=_DISCARDED_BY,
        )
    ]


@pytest.mark.unit
def test_decide_raises_dataset_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(DatasetNotFoundError) as exc_info:
        discard_dataset.decide(
            state=None,
            command=DiscardDataset(dataset_id=target_id, reason="X"),
            now=_NOW,
            discarded_by=_DISCARDED_BY,
        )
    assert exc_info.value.dataset_id == target_id


@pytest.mark.unit
def test_decide_raises_invalid_reason_for_whitespace_only() -> None:
    state = _dataset()
    with pytest.raises(InvalidDatasetDiscardReasonError):
        discard_dataset.decide(
            state=state,
            command=DiscardDataset(dataset_id=state.id, reason="   "),
            now=_NOW,
            discarded_by=_DISCARDED_BY,
        )


@pytest.mark.unit
def test_decide_raises_invalid_reason_for_too_long() -> None:
    state = _dataset()
    with pytest.raises(InvalidDatasetDiscardReasonError):
        discard_dataset.decide(
            state=state,
            command=DiscardDataset(
                dataset_id=state.id,
                reason="a" * (DATASET_DISCARD_REASON_MAX_LENGTH + 1),
            ),
            now=_NOW,
            discarded_by=_DISCARDED_BY,
        )


@pytest.mark.unit
def test_decide_raises_cannot_discard_from_discarded() -> None:
    """Strict-not-idempotent: re-discarding raises."""
    state = _dataset(status=DatasetStatus.DISCARDED)
    with pytest.raises(DatasetCannotDiscardError) as exc_info:
        discard_dataset.decide(
            state=state,
            command=DiscardDataset(dataset_id=state.id, reason="second"),
            now=_NOW,
            discarded_by=_DISCARDED_BY,
        )
    assert exc_info.value.current_status is DatasetStatus.DISCARDED


@pytest.mark.unit
def test_decide_validates_reason_before_status_guard() -> None:
    """A whitespace-only reason from a terminal state should raise the
    reason error, not the cannot-discard error. Same precedent as
    stop_run / truncate_run."""
    state = _dataset(status=DatasetStatus.DISCARDED)
    with pytest.raises(InvalidDatasetDiscardReasonError):
        discard_dataset.decide(
            state=state,
            command=DiscardDataset(dataset_id=state.id, reason="   "),
            now=_NOW,
            discarded_by=_DISCARDED_BY,
        )


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _dataset()
    cmd = DiscardDataset(dataset_id=state.id, reason="X")
    first = discard_dataset.decide(state=state, command=cmd, now=_NOW, discarded_by=_DISCARDED_BY)
    second = discard_dataset.decide(state=state, command=cmd, now=_NOW, discarded_by=_DISCARDED_BY)
    assert first == second
