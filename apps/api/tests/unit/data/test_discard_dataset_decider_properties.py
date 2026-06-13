"""Property-based tests for `discard_dataset.decide` (Data BC).

Complements the example-based `test_discard_dataset_decider.py` with
universal claims across generated inputs. The decider is a pure
single-source terminal FSM transition with actor attribution

    (state, command, now, discarded_by) -> list[DatasetDiscarded]

Load-bearing properties:

  - state=None always raises `DatasetNotFoundError` carrying
    command.dataset_id.
  - The source-state partition is total over `DatasetStatus`: only
    `Registered` emits exactly one `DatasetDiscarded` (dataset_id=state.id,
    occurred_at=now, discarded_by threaded); every other status raises
    `DatasetCannotDiscardError` carrying the current status.
  - The emitted event's dataset_id is `state.id`, never
    command.dataset_id.
  - Pure: same (state, command, now, discarded_by) returns equal events.

The full reason-gate matrix and gate precedence are pinned by the
example test; this file does not duplicate them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    Dataset,
    DatasetCannotDiscardError,
    DatasetChecksum,
    DatasetDiscarded,
    DatasetEncoding,
    DatasetName,
    DatasetNotFoundError,
    DatasetStatus,
    DatasetUri,
)
from cora.data.features import discard_dataset
from cora.data.features.discard_dataset import DiscardDataset
from cora.shared.identity import ActorId
from cora.shared.text_bounds import REASON_MAX_LENGTH
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_DISCARDABLE_SOURCES = (DatasetStatus.REGISTERED,)
_DISALLOWED_SOURCES = tuple(s for s in DatasetStatus if s not in frozenset(_DISCARDABLE_SOURCES))


def _dataset(*, dataset_id: UUID, status: DatasetStatus) -> Dataset:
    return Dataset(
        id=dataset_id,
        name=DatasetName("seed"),
        uri=DatasetUri("s3://b/k"),
        checksum=DatasetChecksum(algorithm="sha256", value=_GOOD_SHA256),
        byte_size=0,
        encoding=DatasetEncoding(media_type="application/x-hdf5"),
        status=status,
    )


_reasons = printable_ascii_text(min_size=1, max_size=REASON_MAX_LENGTH)


@pytest.mark.unit
@given(
    dataset_id=st.uuids(),
    reason=_reasons,
    now=aware_datetimes(),
    discarded_by_uuid=st.uuids(),
)
def test_discard_with_none_state_always_raises_not_found(
    dataset_id: UUID,
    reason: str,
    now: datetime,
    discarded_by_uuid: UUID,
) -> None:
    """Empty stream always raises `DatasetNotFoundError` carrying command.dataset_id."""
    with pytest.raises(DatasetNotFoundError) as exc:
        discard_dataset.decide(
            state=None,
            command=DiscardDataset(dataset_id=dataset_id, reason=reason),
            now=now,
            discarded_by=ActorId(discarded_by_uuid),
        )
    assert exc.value.dataset_id == dataset_id


@pytest.mark.unit
@given(
    dataset_id=st.uuids(),
    reason=_reasons,
    now=aware_datetimes(),
    discarded_by_uuid=st.uuids(),
)
def test_discard_from_registered_emits_single_event(
    dataset_id: UUID,
    reason: str,
    now: datetime,
    discarded_by_uuid: UUID,
) -> None:
    """Registered is the only discardable source; emits one DatasetDiscarded."""
    discarded_by = ActorId(discarded_by_uuid)
    events = discard_dataset.decide(
        state=_dataset(dataset_id=dataset_id, status=DatasetStatus.REGISTERED),
        command=DiscardDataset(dataset_id=dataset_id, reason=reason),
        now=now,
        discarded_by=discarded_by,
    )
    assert events == [
        DatasetDiscarded(
            dataset_id=dataset_id,
            reason=reason,
            occurred_at=now,
            discarded_by=discarded_by,
        )
    ]


@pytest.mark.unit
@given(
    dataset_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    reason=_reasons,
    now=aware_datetimes(),
    discarded_by_uuid=st.uuids(),
)
def test_discard_from_disallowed_source_always_raises_cannot_discard(
    dataset_id: UUID,
    source: DatasetStatus,
    reason: str,
    now: datetime,
    discarded_by_uuid: UUID,
) -> None:
    """Any source other than Registered raises, carrying the current status."""
    with pytest.raises(DatasetCannotDiscardError) as exc:
        discard_dataset.decide(
            state=_dataset(dataset_id=dataset_id, status=source),
            command=DiscardDataset(dataset_id=dataset_id, reason=reason),
            now=now,
            discarded_by=ActorId(discarded_by_uuid),
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    state_dataset_id=st.uuids(),
    command_dataset_id=st.uuids(),
    reason=_reasons,
    now=aware_datetimes(),
    discarded_by_uuid=st.uuids(),
)
def test_discard_uses_state_id_not_command_dataset_id(
    state_dataset_id: UUID,
    command_dataset_id: UUID,
    reason: str,
    now: datetime,
    discarded_by_uuid: UUID,
) -> None:
    """The emitted event's dataset_id is state.id, not command.dataset_id."""
    assume(state_dataset_id != command_dataset_id)
    events = discard_dataset.decide(
        state=_dataset(dataset_id=state_dataset_id, status=DatasetStatus.REGISTERED),
        command=DiscardDataset(dataset_id=command_dataset_id, reason=reason),
        now=now,
        discarded_by=ActorId(discarded_by_uuid),
    )
    assert events[0].dataset_id == state_dataset_id


@pytest.mark.unit
@given(
    dataset_id=st.uuids(),
    reason=_reasons,
    now=aware_datetimes(),
    discarded_by_uuid=st.uuids(),
)
def test_discard_is_pure_same_input_same_output(
    dataset_id: UUID,
    reason: str,
    now: datetime,
    discarded_by_uuid: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _dataset(dataset_id=dataset_id, status=DatasetStatus.REGISTERED)
    command = DiscardDataset(dataset_id=dataset_id, reason=reason)
    discarded_by = ActorId(discarded_by_uuid)
    first = discard_dataset.decide(state=state, command=command, now=now, discarded_by=discarded_by)
    second = discard_dataset.decide(
        state=state, command=command, now=now, discarded_by=discarded_by
    )
    assert first == second
