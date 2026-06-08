"""Unit tests for the `promote_dataset` slice's pure decider.

Validation cascade pinned in order (fail-fast):
  1. DatasetNotFoundError on empty state
  2. DatasetCannotPromoteError on Discarded status
  3. DatasetAlreadyPromotedError on Production intent (strict-not-idempotent)
  4. DatasetCannotPromoteError when producing Run did not Complete
  5. DatasetCannotPromoteError when any derived_from is still Trial
  6. InvalidPromotionReasonError on bad reason length

Plus happy paths:
  - emits DatasetPromoted with trimmed reason
  - skips Run-completed guard when producing_run_id is None
  - skips lineage guard when derived_from is empty
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    DATASET_PROMOTION_REASON_MAX_LENGTH,
    Dataset,
    DatasetAlreadyPromotedError,
    DatasetCannotPromoteError,
    DatasetChecksum,
    DatasetEncoding,
    DatasetName,
    DatasetNotFoundError,
    DatasetPromoted,
    DatasetStatus,
    DatasetUri,
    Intent,
    InvalidPromotionReasonError,
)
from cora.data.features import promote_dataset
from cora.data.features.promote_dataset import DatasetPromotionContext, PromoteDataset
from cora.shared.identity import ActorId

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_PROMOTED_BY = ActorId(UUID("01900000-0000-7000-8000-000000000099"))


def _dataset(
    *,
    dataset_id: UUID | None = None,
    status: DatasetStatus = DatasetStatus.REGISTERED,
    intent: Intent = Intent.TRIAL,
    producing_run_id: UUID | None = None,
    producing_run_end_state: str | None = None,
    derived_from: frozenset[UUID] = frozenset(),
) -> Dataset:
    return Dataset(
        id=dataset_id or uuid4(),
        name=DatasetName("seed"),
        uri=DatasetUri("s3://b/k"),
        checksum=DatasetChecksum(algorithm="sha256", value=_GOOD_SHA256),
        byte_size=0,
        encoding=DatasetEncoding(media_type="application/x-hdf5"),
        producing_run_id=producing_run_id,
        derived_from=derived_from,
        status=status,
        producing_run_end_state=producing_run_end_state,
        intent=intent,
    )


@pytest.mark.unit
def test_decide_raises_dataset_not_found_when_state_is_none() -> None:
    with pytest.raises(DatasetNotFoundError):
        promote_dataset.decide(
            state=None,
            command=PromoteDataset(dataset_id=uuid4(), reason="passed peer review"),
            context=DatasetPromotionContext(derived_from={}),
            now=_NOW,
            promoted_by=_PROMOTED_BY,
        )


@pytest.mark.unit
def test_decide_raises_cannot_promote_when_discarded() -> None:
    state = _dataset(status=DatasetStatus.DISCARDED)
    with pytest.raises(DatasetCannotPromoteError) as exc_info:
        promote_dataset.decide(
            state=state,
            command=PromoteDataset(dataset_id=state.id, reason="trying to revive"),
            context=DatasetPromotionContext(derived_from={}),
            now=_NOW,
            promoted_by=_PROMOTED_BY,
        )
    assert "discarded" in exc_info.value.reason.lower()


@pytest.mark.unit
def test_decide_raises_already_promoted_when_intent_is_production() -> None:
    """Strict-not-idempotent: re-promoting raises rather than silent no-op."""
    state = _dataset(intent=Intent.PRODUCTION)
    with pytest.raises(DatasetAlreadyPromotedError) as exc_info:
        promote_dataset.decide(
            state=state,
            command=PromoteDataset(dataset_id=state.id, reason="re-promote attempt"),
            context=DatasetPromotionContext(derived_from={}),
            now=_NOW,
            promoted_by=_PROMOTED_BY,
        )
    assert exc_info.value.current_intent is Intent.PRODUCTION


@pytest.mark.unit
def test_decide_raises_cannot_promote_when_producing_run_aborted() -> None:
    """Run-must-be-Completed guard: aborted Runs cannot produce
    Production datasets."""
    state = _dataset(
        producing_run_id=uuid4(),
        producing_run_end_state="Aborted",
    )
    with pytest.raises(DatasetCannotPromoteError) as exc_info:
        promote_dataset.decide(
            state=state,
            command=PromoteDataset(dataset_id=state.id, reason="trying"),
            context=DatasetPromotionContext(derived_from={}),
            now=_NOW,
            promoted_by=_PROMOTED_BY,
        )
    assert "Aborted" in exc_info.value.reason
    assert "Completed" in exc_info.value.reason


@pytest.mark.unit
@pytest.mark.parametrize("end_state", ["Aborted", "Stopped", "Truncated"])
def test_decide_rejects_all_non_completed_run_end_states(end_state: str) -> None:
    """Stopped, Truncated, and Aborted Runs all reject promotion."""
    state = _dataset(
        producing_run_id=uuid4(),
        producing_run_end_state=end_state,
    )
    with pytest.raises(DatasetCannotPromoteError):
        promote_dataset.decide(
            state=state,
            command=PromoteDataset(dataset_id=state.id, reason="trying"),
            context=DatasetPromotionContext(derived_from={}),
            now=_NOW,
            promoted_by=_PROMOTED_BY,
        )


@pytest.mark.unit
def test_decide_skips_run_guard_when_no_producing_run() -> None:
    """Standalone-upload Datasets (no producing_run_id) skip the
    Run-must-be-Completed guard entirely."""
    state = _dataset(producing_run_id=None, producing_run_end_state=None)
    events = promote_dataset.decide(
        state=state,
        command=PromoteDataset(dataset_id=state.id, reason="reference dataset"),
        context=DatasetPromotionContext(derived_from={}),
        now=_NOW,
        promoted_by=_PROMOTED_BY,
    )
    assert len(events) == 1
    assert isinstance(events[0], DatasetPromoted)


@pytest.mark.unit
def test_decide_raises_cannot_promote_when_lineage_has_trial_dataset() -> None:
    """Lineage-must-be-Production guard: any derived_from in Trial
    intent rejects promotion."""
    upstream_id = uuid4()
    upstream = _dataset(dataset_id=upstream_id, intent=Intent.TRIAL)
    state = _dataset(
        producing_run_id=uuid4(),
        producing_run_end_state="Completed",
        derived_from=frozenset({upstream_id}),
    )
    with pytest.raises(DatasetCannotPromoteError) as exc_info:
        promote_dataset.decide(
            state=state,
            command=PromoteDataset(dataset_id=state.id, reason="trying"),
            context=DatasetPromotionContext(derived_from={upstream_id: upstream}),
            now=_NOW,
            promoted_by=_PROMOTED_BY,
        )
    assert "Trial" in exc_info.value.reason
    assert str(upstream_id) in exc_info.value.reason


@pytest.mark.unit
def test_decide_passes_when_lineage_all_production() -> None:
    """Happy path: all derived_from in Production intent + Run Completed."""
    up1, up2 = uuid4(), uuid4()
    upstream1 = _dataset(dataset_id=up1, intent=Intent.PRODUCTION)
    upstream2 = _dataset(dataset_id=up2, intent=Intent.PRODUCTION)
    state = _dataset(
        producing_run_id=uuid4(),
        producing_run_end_state="Completed",
        derived_from=frozenset({up1, up2}),
    )
    events = promote_dataset.decide(
        state=state,
        command=PromoteDataset(dataset_id=state.id, reason="passed peer review"),
        context=DatasetPromotionContext(derived_from={up1: upstream1, up2: upstream2}),
        now=_NOW,
        promoted_by=_PROMOTED_BY,
    )
    assert events == [
        DatasetPromoted(
            dataset_id=state.id,
            reason="passed peer review",
            occurred_at=_NOW,
            promoted_by=_PROMOTED_BY,
        )
    ]


@pytest.mark.unit
def test_decide_skips_lineage_guard_when_derived_from_empty() -> None:
    """Raw Datasets (empty derived_from) skip the lineage guard entirely."""
    state = _dataset(
        producing_run_id=uuid4(),
        producing_run_end_state="Completed",
        derived_from=frozenset(),
    )
    events = promote_dataset.decide(
        state=state,
        command=PromoteDataset(dataset_id=state.id, reason="raw acquisition"),
        context=DatasetPromotionContext(derived_from={}),
        now=_NOW,
        promoted_by=_PROMOTED_BY,
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_raises_invalid_reason_for_whitespace_only() -> None:
    state = _dataset(
        producing_run_id=uuid4(),
        producing_run_end_state="Completed",
    )
    with pytest.raises(InvalidPromotionReasonError):
        promote_dataset.decide(
            state=state,
            command=PromoteDataset(dataset_id=state.id, reason="   "),
            context=DatasetPromotionContext(derived_from={}),
            now=_NOW,
            promoted_by=_PROMOTED_BY,
        )


@pytest.mark.unit
def test_decide_raises_invalid_reason_for_too_long() -> None:
    state = _dataset(
        producing_run_id=uuid4(),
        producing_run_end_state="Completed",
    )
    overlong = "x" * (DATASET_PROMOTION_REASON_MAX_LENGTH + 1)
    with pytest.raises(InvalidPromotionReasonError):
        promote_dataset.decide(
            state=state,
            command=PromoteDataset(dataset_id=state.id, reason=overlong),
            context=DatasetPromotionContext(derived_from={}),
            now=_NOW,
            promoted_by=_PROMOTED_BY,
        )


@pytest.mark.unit
def test_decide_emits_event_with_trimmed_reason() -> None:
    """PromotionReason VO trims whitespace; payload carries trimmed value."""
    state = _dataset(producing_run_id=None)
    events = promote_dataset.decide(
        state=state,
        command=PromoteDataset(dataset_id=state.id, reason="  passed review  "),
        context=DatasetPromotionContext(derived_from={}),
        now=_NOW,
        promoted_by=_PROMOTED_BY,
    )
    assert events[0].reason == "passed review"


@pytest.mark.unit
def test_decide_validates_status_before_intent_guard() -> None:
    """Discarded check fires before intent check (status guard is more
    fundamental)."""
    # State is BOTH discarded AND production. Discard guard should fire
    # first (more fundamental rejection).
    state = _dataset(
        status=DatasetStatus.DISCARDED,
        intent=Intent.PRODUCTION,
    )
    with pytest.raises(DatasetCannotPromoteError) as exc_info:
        promote_dataset.decide(
            state=state,
            command=PromoteDataset(dataset_id=state.id, reason="trying"),
            context=DatasetPromotionContext(derived_from={}),
            now=_NOW,
            promoted_by=_PROMOTED_BY,
        )
    # Verify the discard-related message wins, not the already-promoted message
    assert "discarded" in exc_info.value.reason.lower()
