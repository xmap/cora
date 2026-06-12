"""Property-based tests for `promote_dataset.decide` (Data BC).

Complements the example-based `test_promote_dataset_decider.py` with
universal claims across generated inputs. This is a cross-aggregate
decider validating loaded peer-Dataset lineage from a context:

    (state, command, context, now, promoted_by) -> list[DatasetPromoted]

Load-bearing properties:

  - A None state always raises `DatasetNotFoundError` regardless of the
    command (existence / genesis guard fires first).
  - A Discarded Dataset always raises `DatasetCannotPromoteError`
    regardless of its intent (status guard before intent guard).
  - A Registered Dataset whose intent is not Trial (Production or
    Retracted) always raises `DatasetAlreadyPromotedError` carrying the
    current intent (strict-not-idempotent).
  - A clean promotable Dataset (Registered + Trial + no producing Run +
    empty lineage) emits exactly one `DatasetPromoted` keyed on
    state.id with occurred_at=now and the threaded promoted_by.
  - Pure: same inputs return equal results (no clock leakage).

The full fail-fast gate matrix (Run-end-state, lineage, reason length)
is pinned by the example test; this file asserts only the universal
partitions that hold across the whole input space.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

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
)
from cora.data.features import promote_dataset
from cora.data.features.promote_dataset import DatasetPromotionContext, PromoteDataset
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH

_ALREADY_PROMOTED_INTENTS = (Intent.PRODUCTION, Intent.RETRACTED)
_ANY_INTENT = (Intent.TRIAL, Intent.PRODUCTION, Intent.RETRACTED)


def _reasons() -> st.SearchStrategy[str]:
    return printable_ascii_text(min_size=1, max_size=DATASET_PROMOTION_REASON_MAX_LENGTH)


def _dataset(
    *,
    dataset_id: UUID,
    status: DatasetStatus = DatasetStatus.REGISTERED,
    intent: Intent = Intent.TRIAL,
    producing_run_id: UUID | None = None,
    producing_run_end_state: str | None = None,
    derived_from: frozenset[UUID] = frozenset(),
) -> Dataset:
    return Dataset(
        id=dataset_id,
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


def _context() -> DatasetPromotionContext:
    return DatasetPromotionContext(derived_from={})


def _command(*, dataset_id: UUID, reason: str) -> PromoteDataset:
    return PromoteDataset(dataset_id=dataset_id, reason=reason)


@pytest.mark.unit
@given(dataset_id=st.uuids(), reason=_reasons(), now=aware_datetimes(), actor=st.uuids())
def test_decide_none_state_always_raises_not_found(
    dataset_id: UUID,
    reason: str,
    now: datetime,
    actor: UUID,
) -> None:
    """A None state raises DatasetNotFoundError before any other guard."""
    with pytest.raises(DatasetNotFoundError):
        promote_dataset.decide(
            state=None,
            command=_command(dataset_id=dataset_id, reason=reason),
            context=_context(),
            now=now,
            promoted_by=ActorId(actor),
        )


@pytest.mark.unit
@given(
    dataset_id=st.uuids(),
    intent=st.sampled_from(_ANY_INTENT),
    reason=_reasons(),
    now=aware_datetimes(),
    actor=st.uuids(),
)
def test_decide_discarded_always_raises_cannot_promote(
    dataset_id: UUID,
    intent: Intent,
    reason: str,
    now: datetime,
    actor: UUID,
) -> None:
    """A Discarded Dataset rejects promotion for any intent (status guard wins)."""
    state = _dataset(dataset_id=dataset_id, status=DatasetStatus.DISCARDED, intent=intent)
    with pytest.raises(DatasetCannotPromoteError) as exc:
        promote_dataset.decide(
            state=state,
            command=_command(dataset_id=dataset_id, reason=reason),
            context=_context(),
            now=now,
            promoted_by=ActorId(actor),
        )
    assert "discarded" in exc.value.reason.lower()


@pytest.mark.unit
@given(
    dataset_id=st.uuids(),
    intent=st.sampled_from(_ALREADY_PROMOTED_INTENTS),
    reason=_reasons(),
    now=aware_datetimes(),
    actor=st.uuids(),
)
def test_decide_non_trial_intent_always_raises_already_promoted(
    dataset_id: UUID,
    intent: Intent,
    reason: str,
    now: datetime,
    actor: UUID,
) -> None:
    """A Registered Dataset whose intent is not Trial raises with the current intent."""
    state = _dataset(dataset_id=dataset_id, status=DatasetStatus.REGISTERED, intent=intent)
    with pytest.raises(DatasetAlreadyPromotedError) as exc:
        promote_dataset.decide(
            state=state,
            command=_command(dataset_id=dataset_id, reason=reason),
            context=_context(),
            now=now,
            promoted_by=ActorId(actor),
        )
    assert exc.value.current_intent is intent


@pytest.mark.unit
@given(dataset_id=st.uuids(), reason=_reasons(), now=aware_datetimes(), actor=st.uuids())
def test_decide_clean_promotable_emits_one_promoted_event(
    dataset_id: UUID,
    reason: str,
    now: datetime,
    actor: UUID,
) -> None:
    """A Registered + Trial Dataset with no Run and empty lineage emits one DatasetPromoted."""
    promoted_by = ActorId(actor)
    state = _dataset(
        dataset_id=dataset_id,
        status=DatasetStatus.REGISTERED,
        intent=Intent.TRIAL,
        producing_run_id=None,
        derived_from=frozenset(),
    )
    events = promote_dataset.decide(
        state=state,
        command=_command(dataset_id=dataset_id, reason=reason),
        context=_context(),
        now=now,
        promoted_by=promoted_by,
    )
    assert events == [
        DatasetPromoted(
            dataset_id=state.id,
            reason=reason,
            occurred_at=now,
            promoted_by=promoted_by,
        )
    ]


@pytest.mark.unit
@given(dataset_id=st.uuids(), reason=_reasons(), now=aware_datetimes(), actor=st.uuids())
def test_decide_is_pure_same_input_same_output(
    dataset_id: UUID,
    reason: str,
    now: datetime,
    actor: UUID,
) -> None:
    """Two calls with identical args return equal results (no clock leakage)."""
    promoted_by = ActorId(actor)
    state = _dataset(dataset_id=dataset_id, status=DatasetStatus.REGISTERED, intent=Intent.TRIAL)
    command = _command(dataset_id=dataset_id, reason=reason)
    first = promote_dataset.decide(
        state=state, command=command, context=_context(), now=now, promoted_by=promoted_by
    )
    second = promote_dataset.decide(
        state=state, command=command, context=_context(), now=now, promoted_by=promoted_by
    )
    assert first == second
