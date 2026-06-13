"""Unit tests for the `demote_dataset` slice's pure decider.

First concrete instantiation of the Q4 compensation-primitive pattern
(per [[project-dataset-demote-design]]).

Validation cascade pinned in order (fail-fast):
  1. DatasetNotFoundError on empty state
  2. DatasetCannotDemoteError on Discarded status
  3. DatasetAlreadyRetractedError on Retracted intent (strict-not-idempotent)
  4. DatasetCannotDemoteError on Trial intent (semantic guard;
     use discard_dataset for never-authoritative cleanup)
  5. InvalidDemotionReasonError on bad reason length

Plus happy paths:
  - emits DatasetDemoted with trimmed reason from Production state
  - skips all guards when state is Production + reason valid
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    Dataset,
    DatasetAlreadyRetractedError,
    DatasetCannotDemoteError,
    DatasetChecksum,
    DatasetDemoted,
    DatasetEncoding,
    DatasetName,
    DatasetNotFoundError,
    DatasetStatus,
    DatasetUri,
    Intent,
    InvalidDemotionReasonError,
)
from cora.data.features import demote_dataset
from cora.data.features.demote_dataset import DemoteDataset
from cora.shared.identity import ActorId
from cora.shared.text_bounds import REASON_MAX_LENGTH

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 5, 20, 12, 0, 0, tzinfo=UTC)
_DEMOTED_BY = ActorId(UUID("01900000-0000-7000-8000-000000000099"))


def _dataset(
    *,
    dataset_id: UUID | None = None,
    status: DatasetStatus = DatasetStatus.REGISTERED,
    intent: Intent = Intent.PRODUCTION,
) -> Dataset:
    return Dataset(
        id=dataset_id or uuid4(),
        name=DatasetName("seed"),
        uri=DatasetUri("s3://b/k"),
        checksum=DatasetChecksum(algorithm="sha256", value=_GOOD_SHA256),
        byte_size=0,
        encoding=DatasetEncoding(media_type="application/x-hdf5"),
        producing_run_id=None,
        derived_from=frozenset(),
        status=status,
        producing_run_end_state=None,
        intent=intent,
    )


@pytest.mark.unit
def test_decide_raises_dataset_not_found_when_state_is_none() -> None:
    with pytest.raises(DatasetNotFoundError):
        demote_dataset.decide(
            state=None,
            command=DemoteDataset(dataset_id=uuid4(), reason="calibration error"),
            now=_NOW,
            demoted_by=_DEMOTED_BY,
        )


@pytest.mark.unit
def test_decide_raises_cannot_demote_when_discarded() -> None:
    """Discarded is a stronger terminal than Retracted; reject before
    intent guard."""
    state = _dataset(status=DatasetStatus.DISCARDED)
    with pytest.raises(DatasetCannotDemoteError) as exc_info:
        demote_dataset.decide(
            state=state,
            command=DemoteDataset(dataset_id=state.id, reason="trying"),
            now=_NOW,
            demoted_by=_DEMOTED_BY,
        )
    assert "discarded" in exc_info.value.reason.lower()


@pytest.mark.unit
def test_decide_raises_already_retracted_when_intent_is_retracted() -> None:
    """Strict-not-idempotent: re-demote raises rather than silent no-op."""
    state = _dataset(intent=Intent.RETRACTED)
    with pytest.raises(DatasetAlreadyRetractedError) as exc_info:
        demote_dataset.decide(
            state=state,
            command=DemoteDataset(dataset_id=state.id, reason="re-demote attempt"),
            now=_NOW,
            demoted_by=_DEMOTED_BY,
        )
    assert exc_info.value.current_intent is Intent.RETRACTED


@pytest.mark.unit
def test_decide_raises_cannot_demote_when_intent_is_trial() -> None:
    """Trial→Retracted is semantically meaningless (would conflate
    'never authoritative' with 'was authoritative but now isn't').
    Operators should use discard_dataset for the former."""
    state = _dataset(intent=Intent.TRIAL)
    with pytest.raises(DatasetCannotDemoteError) as exc_info:
        demote_dataset.decide(
            state=state,
            command=DemoteDataset(dataset_id=state.id, reason="trying"),
            now=_NOW,
            demoted_by=_DEMOTED_BY,
        )
    assert "Trial" in exc_info.value.reason
    assert "Production" in exc_info.value.reason


@pytest.mark.unit
def test_decide_raises_invalid_reason_for_whitespace_only() -> None:
    state = _dataset(intent=Intent.PRODUCTION)
    with pytest.raises(InvalidDemotionReasonError):
        demote_dataset.decide(
            state=state,
            command=DemoteDataset(dataset_id=state.id, reason="   "),
            now=_NOW,
            demoted_by=_DEMOTED_BY,
        )


@pytest.mark.unit
def test_decide_raises_invalid_reason_for_too_long() -> None:
    state = _dataset(intent=Intent.PRODUCTION)
    overlong = "x" * (REASON_MAX_LENGTH + 1)
    with pytest.raises(InvalidDemotionReasonError):
        demote_dataset.decide(
            state=state,
            command=DemoteDataset(dataset_id=state.id, reason=overlong),
            now=_NOW,
            demoted_by=_DEMOTED_BY,
        )


@pytest.mark.unit
def test_decide_emits_event_with_trimmed_reason() -> None:
    """DemotionReason VO trims whitespace; payload carries trimmed value."""
    state = _dataset(intent=Intent.PRODUCTION)
    events = demote_dataset.decide(
        state=state,
        command=DemoteDataset(dataset_id=state.id, reason="  calibration error  "),
        now=_NOW,
        demoted_by=_DEMOTED_BY,
    )
    assert events == [
        DatasetDemoted(
            dataset_id=state.id,
            reason="calibration error",
            occurred_at=_NOW,
            demoted_by=_DEMOTED_BY,
        )
    ]


@pytest.mark.unit
def test_decide_validates_status_before_intent_guard() -> None:
    """Discarded check fires before intent check (status guard is more
    fundamental; bytes are gone)."""
    # State is BOTH discarded AND production. Discard guard should fire
    # first (more fundamental rejection).
    state = _dataset(
        status=DatasetStatus.DISCARDED,
        intent=Intent.PRODUCTION,
    )
    with pytest.raises(DatasetCannotDemoteError) as exc_info:
        demote_dataset.decide(
            state=state,
            command=DemoteDataset(dataset_id=state.id, reason="trying"),
            now=_NOW,
            demoted_by=_DEMOTED_BY,
        )
    # Verify the discard-related message wins, not the intent message
    assert "discarded" in exc_info.value.reason.lower()


@pytest.mark.unit
def test_decide_already_retracted_fires_before_trial_guard() -> None:
    """If state were impossibly both Retracted and Trial, AlreadyRetracted
    wins (strict-not-idempotent check is the natural retry-safety net
    and must surface to the operator over the semantic-Trial message)."""
    # Construct state with Retracted intent; verify the already-retracted
    # branch wins over any subsequent intent check.
    state = _dataset(intent=Intent.RETRACTED)
    with pytest.raises(DatasetAlreadyRetractedError):
        demote_dataset.decide(
            state=state,
            command=DemoteDataset(dataset_id=state.id, reason="trying"),
            now=_NOW,
            demoted_by=_DEMOTED_BY,
        )
