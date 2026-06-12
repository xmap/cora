"""Property-based tests for `register_dataset.decide` (Data BC).

Complements the example-based `test_register_dataset_decider.py` with
universal claims across generated inputs. The genesis decider is pure

    (state, command, context, now, new_id, registered_by)
        -> list[DatasetRegistered]

Load-bearing properties:

  - Any non-None state always raises `DatasetAlreadyExistsError`
    carrying state.id (idempotency-as-error), regardless of command.
  - On the happy path (state None, no cross-BC refs) the single
    `DatasetRegistered` carries the injected/passthrough fields:
    dataset_id=new_id, registered_by, occurred_at=now, and the
    canonical metadata.
  - A producing_run_id set with a None producing_run in context always
    raises `ProducingRunNotFoundError` carrying the run id.
  - Pure: same inputs return equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    Dataset,
    DatasetAlreadyExistsError,
    DatasetChecksum,
    DatasetEncoding,
    DatasetName,
    DatasetRegistered,
    DatasetUri,
    ProducingRunNotFoundError,
)
from cora.data.features import register_dataset
from cora.data.features.register_dataset import (
    DatasetRegistrationContext,
    RegisterDataset,
)
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NAME = printable_ascii_text(min_size=1, max_size=200)


def _good_command(**overrides: object) -> RegisterDataset:
    base: dict[str, object] = {
        "name": "32-ID FlyScan recon",
        "uri": "s3://aps-32id/runs/abc/recon.h5",
        "checksum_algorithm": "sha256",
        "checksum_value": _GOOD_SHA256,
        "byte_size": 1024,
        "media_type": "application/x-hdf5",
        "conforms_to": frozenset[str](),
        "producing_run_id": None,
        "subject_id": None,
        "derived_from": frozenset[UUID](),
    }
    base.update(overrides)
    return RegisterDataset(**base)  # type: ignore[arg-type]


def _existing_dataset(*, dataset_id: UUID) -> Dataset:
    return Dataset(
        id=dataset_id,
        name=DatasetName("seed"),
        uri=DatasetUri("s3://b/k"),
        checksum=DatasetChecksum(algorithm="sha256", value=_GOOD_SHA256),
        byte_size=0,
        encoding=DatasetEncoding(media_type="application/x-hdf5"),
    )


@pytest.mark.unit
@given(
    existing_id=st.uuids(),
    registered_by_uuid=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_dataset_on_existing_state_always_raises_already_exists(
    existing_id: UUID,
    registered_by_uuid: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """Any non-None state raises DatasetAlreadyExistsError carrying state.id."""
    existing = _existing_dataset(dataset_id=existing_id)
    with pytest.raises(DatasetAlreadyExistsError) as exc:
        register_dataset.decide(
            state=existing,
            command=_good_command(),
            context=DatasetRegistrationContext(),
            now=now,
            new_id=new_id,
            registered_by=ActorId(registered_by_uuid),
        )
    assert exc.value.dataset_id == existing_id


@pytest.mark.unit
@given(
    name=_NAME,
    registered_by_uuid=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_dataset_on_empty_state_emits_single_event_with_injected_fields(
    name: str,
    registered_by_uuid: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """Empty state emits one DatasetRegistered with injected/passthrough fields."""
    registered_by = ActorId(registered_by_uuid)
    events = register_dataset.decide(
        state=None,
        command=_good_command(name=name),
        context=DatasetRegistrationContext(),
        now=now,
        new_id=new_id,
        registered_by=registered_by,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, DatasetRegistered)
    assert event.dataset_id == new_id
    assert event.name == name
    assert event.registered_by == registered_by
    assert event.occurred_at == now
    assert event.producing_run_id is None
    assert event.subject_id is None
    assert event.derived_from == frozenset()
    assert event.producing_run_end_state is None


@pytest.mark.unit
@given(
    run_id=st.uuids(),
    registered_by_uuid=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_dataset_with_producing_run_set_but_unloaded_always_raises_not_found(
    run_id: UUID,
    registered_by_uuid: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """producing_run_id set with a None producing_run raises ProducingRunNotFoundError."""
    with pytest.raises(ProducingRunNotFoundError):
        register_dataset.decide(
            state=None,
            command=_good_command(producing_run_id=run_id),
            context=DatasetRegistrationContext(producing_run=None),
            now=now,
            new_id=new_id,
            registered_by=ActorId(registered_by_uuid),
        )


@pytest.mark.unit
@given(
    name=_NAME,
    registered_by_uuid=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_dataset_is_pure_same_input_same_output(
    name: str,
    registered_by_uuid: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock/id leakage)."""
    command = _good_command(name=name)
    ctx = DatasetRegistrationContext()
    registered_by = ActorId(registered_by_uuid)
    first = register_dataset.decide(
        state=None,
        command=command,
        context=ctx,
        now=now,
        new_id=new_id,
        registered_by=registered_by,
    )
    second = register_dataset.decide(
        state=None,
        command=command,
        context=ctx,
        now=now,
        new_id=new_id,
        registered_by=registered_by,
    )
    assert first == second
