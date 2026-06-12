"""Property-based tests for `demote_dataset.decide` (Data BC).

Complements the example-based `test_demote_dataset_decider.py` with
universal claims across generated inputs. The decider is a pure
compensation-primitive transition with actor attribution

    (state, command, now, demoted_by) -> list[DatasetDemoted]

partitioned on both `DatasetStatus` and `Intent`. The full gate matrix
(Discarded-before-intent ordering, Trial semantic guard, reason-length
validation) is pinned by the example test; this file asserts only the
claims that hold across the whole input space.

Load-bearing properties:

  - state=None always raises `DatasetNotFoundError` carrying
    command.dataset_id.
  - A non-Discarded dataset already at Intent.RETRACTED always raises
    `DatasetAlreadyRetractedError` carrying current_intent=Retracted and
    dataset_id=state.id (strict-not-idempotent).
  - The clean demotable partition (status=Registered, intent=Production,
    valid reason) emits exactly one `DatasetDemoted`
    (dataset_id=state.id, occurred_at=now, demoted_by threaded, reason
    trimmed).
  - The emitted event's dataset_id is `state.id`, never
    command.dataset_id.
  - Pure: same (state, command, now, demoted_by) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    DATASET_DEMOTION_REASON_MAX_LENGTH,
    Dataset,
    DatasetAlreadyRetractedError,
    DatasetChecksum,
    DatasetDemoted,
    DatasetEncoding,
    DatasetName,
    DatasetNotFoundError,
    DatasetStatus,
    DatasetUri,
    Intent,
)
from cora.data.features import demote_dataset
from cora.data.features.demote_dataset import DemoteDataset
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH


def _dataset(
    *,
    dataset_id: UUID,
    status: DatasetStatus = DatasetStatus.REGISTERED,
    intent: Intent = Intent.PRODUCTION,
) -> Dataset:
    return Dataset(
        id=dataset_id,
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


def _command(*, dataset_id: UUID, reason: str) -> DemoteDataset:
    return DemoteDataset(dataset_id=dataset_id, reason=reason)


@pytest.mark.unit
@given(
    dataset_id=st.uuids(),
    reason=printable_ascii_text(max_size=DATASET_DEMOTION_REASON_MAX_LENGTH),
    now=aware_datetimes(),
    demoted_by_uuid=st.uuids(),
)
def test_demote_with_none_state_always_raises_not_found(
    dataset_id: UUID,
    reason: str,
    now: datetime,
    demoted_by_uuid: UUID,
) -> None:
    """Empty stream always raises `DatasetNotFoundError` carrying command.dataset_id."""
    with pytest.raises(DatasetNotFoundError) as exc:
        demote_dataset.decide(
            state=None,
            command=_command(dataset_id=dataset_id, reason=reason),
            now=now,
            demoted_by=ActorId(demoted_by_uuid),
        )
    assert exc.value.dataset_id == dataset_id


@pytest.mark.unit
@given(
    dataset_id=st.uuids(),
    reason=printable_ascii_text(max_size=DATASET_DEMOTION_REASON_MAX_LENGTH),
    now=aware_datetimes(),
    demoted_by_uuid=st.uuids(),
)
def test_demote_when_already_retracted_always_raises_already_retracted(
    dataset_id: UUID,
    reason: str,
    now: datetime,
    demoted_by_uuid: UUID,
) -> None:
    """A non-Discarded dataset already at Retracted raises strict-not-idempotent."""
    state = _dataset(
        dataset_id=dataset_id,
        status=DatasetStatus.REGISTERED,
        intent=Intent.RETRACTED,
    )
    with pytest.raises(DatasetAlreadyRetractedError) as exc:
        demote_dataset.decide(
            state=state,
            command=_command(dataset_id=dataset_id, reason=reason),
            now=now,
            demoted_by=ActorId(demoted_by_uuid),
        )
    assert exc.value.current_intent is Intent.RETRACTED
    assert exc.value.dataset_id == dataset_id


@pytest.mark.unit
@given(
    dataset_id=st.uuids(),
    reason=printable_ascii_text(max_size=DATASET_DEMOTION_REASON_MAX_LENGTH),
    now=aware_datetimes(),
    demoted_by_uuid=st.uuids(),
)
def test_demote_from_clean_demotable_emits_single_event(
    dataset_id: UUID,
    reason: str,
    now: datetime,
    demoted_by_uuid: UUID,
) -> None:
    """Registered + Production + valid reason emits one DatasetDemoted, reason trimmed."""
    demoted_by = ActorId(demoted_by_uuid)
    state = _dataset(
        dataset_id=dataset_id,
        status=DatasetStatus.REGISTERED,
        intent=Intent.PRODUCTION,
    )
    events = demote_dataset.decide(
        state=state,
        command=_command(dataset_id=dataset_id, reason=reason),
        now=now,
        demoted_by=demoted_by,
    )
    assert events == [
        DatasetDemoted(
            dataset_id=dataset_id,
            reason=reason.strip(),
            occurred_at=now,
            demoted_by=demoted_by,
        )
    ]


@pytest.mark.unit
@given(
    state_dataset_id=st.uuids(),
    command_dataset_id=st.uuids(),
    reason=printable_ascii_text(max_size=DATASET_DEMOTION_REASON_MAX_LENGTH),
    now=aware_datetimes(),
    demoted_by_uuid=st.uuids(),
)
def test_demote_uses_state_id_not_command_dataset_id(
    state_dataset_id: UUID,
    command_dataset_id: UUID,
    reason: str,
    now: datetime,
    demoted_by_uuid: UUID,
) -> None:
    """The emitted event's dataset_id is state.id, not command.dataset_id."""
    assume(state_dataset_id != command_dataset_id)
    state = _dataset(
        dataset_id=state_dataset_id,
        status=DatasetStatus.REGISTERED,
        intent=Intent.PRODUCTION,
    )
    events = demote_dataset.decide(
        state=state,
        command=_command(dataset_id=command_dataset_id, reason=reason),
        now=now,
        demoted_by=ActorId(demoted_by_uuid),
    )
    assert events[0].dataset_id == state_dataset_id


@pytest.mark.unit
@given(
    dataset_id=st.uuids(),
    reason=printable_ascii_text(max_size=DATASET_DEMOTION_REASON_MAX_LENGTH),
    now=aware_datetimes(),
    demoted_by_uuid=st.uuids(),
)
def test_demote_is_pure_same_input_same_output(
    dataset_id: UUID,
    reason: str,
    now: datetime,
    demoted_by_uuid: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _dataset(
        dataset_id=dataset_id,
        status=DatasetStatus.REGISTERED,
        intent=Intent.PRODUCTION,
    )
    command = _command(dataset_id=dataset_id, reason=reason)
    demoted_by = ActorId(demoted_by_uuid)
    first = demote_dataset.decide(state=state, command=command, now=now, demoted_by=demoted_by)
    second = demote_dataset.decide(state=state, command=command, now=now, demoted_by=demoted_by)
    assert first == second
