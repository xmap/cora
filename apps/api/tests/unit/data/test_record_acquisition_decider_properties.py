"""Property-based tests for `record_acquisition.decide` (Data BC).

Mirrors the Access / Enclosure / Supply decider-PBT pattern. Universal
claims across generated inputs:

  - state=None + valid command (Capturing-bearing Asset, sane
    captured_at) emits a single AcquisitionRecorded with the injected
    acquisition_id / now (-> occurred_at) / recorded_by and the
    command's bindings; the dual-time pair is preserved correctly
    (captured_at verbatim, occurred_at == now).
  - state=Acquisition always raises AcquisitionAlreadyExistsError,
    regardless of command shape.
  - An Asset whose family_affordances lacks "Capturing" always raises
    AcquisitionCannotRecordWithoutCapturingError.
  - Pure: same args return the same events.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.data.aggregates.acquisition import (
    AcquisitionAlreadyExistsError,
    AcquisitionCannotRecordWithoutCapturingError,
    AcquisitionStatus,
)
from cora.data.aggregates.acquisition.state import Acquisition
from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    Dataset,
    DatasetChecksum,
    DatasetEncoding,
    DatasetName,
    DatasetUri,
)
from cora.data.features import record_acquisition
from cora.data.features.record_acquisition import (
    AcquisitionRecordingContext,
    RecordAcquisition,
)
from cora.infrastructure.ports.asset_lookup import AssetLookupResult
from cora.shared.identity import ActorId

if TYPE_CHECKING:
    from uuid import UUID

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH

# Keep captured_at within [now - 365d, now] so the future-skew guard
# never rejects (backfills are legitimate; only future-beyond-skew is
# rejected, covered by the example-based decider test).
_BACKFILL_DELTA = st.timedeltas(min_value=timedelta(0), max_value=timedelta(days=365))

# Primitive-leaf carrier dicts (settings / evidence shape today).
_CARRIER = st.dictionaries(
    keys=st.text(min_size=1, max_size=12),
    values=st.one_of(st.integers(), st.text(max_size=12), st.booleans(), st.none()),
    max_size=4,
)


def _dataset(dataset_id: UUID) -> Dataset:
    return Dataset(
        id=dataset_id,
        name=DatasetName("recon.h5"),
        uri=DatasetUri("s3://b/recon.h5"),
        checksum=DatasetChecksum(algorithm="sha256", value=_GOOD_SHA256),
        byte_size=1024,
        encoding=DatasetEncoding(media_type="application/x-hdf5"),
    )


def _asset(asset_id: UUID, *, affordances: frozenset[str]) -> AssetLookupResult:
    return AssetLookupResult(
        id=asset_id,
        name="Detector",
        tier="Device",
        lifecycle="Active",
        family_affordances=affordances,
    )


def _context(
    dataset_id: UUID,
    asset_id: UUID,
    *,
    affordances: frozenset[str] = frozenset({"Capturing"}),
) -> AcquisitionRecordingContext:
    return AcquisitionRecordingContext(
        dataset=_dataset(dataset_id),
        asset=_asset(asset_id, affordances=affordances),
        run=None,
    )


@pytest.mark.unit
@given(
    now=st.datetimes(min_value=datetime(2000, 1, 1), timezones=st.just(UTC)),
    backfill=_BACKFILL_DELTA,
    acquisition_id=st.uuids(),
    dataset_id=st.uuids(),
    asset_id=st.uuids(),
    actor_id=st.uuids(),
    settings=_CARRIER,
    evidence=_CARRIER,
)
def test_genesis_emits_single_event_with_injected_fields_and_dual_time(
    now: datetime,
    backfill: timedelta,
    acquisition_id: UUID,
    dataset_id: UUID,
    asset_id: UUID,
    actor_id: UUID,
    settings: dict[str, object],
    evidence: dict[str, object],
) -> None:
    captured_at = now - backfill
    command = RecordAcquisition(
        dataset_id=dataset_id,
        producing_asset_id=asset_id,
        captured_at=captured_at,
        producing_run_id=None,
        settings=settings,
        evidence=evidence,
    )
    events = record_acquisition.decide(
        state=None,
        command=command,
        context=_context(dataset_id, asset_id),
        now=now,
        new_id=acquisition_id,
        recorded_by=ActorId(actor_id),
    )
    assert len(events) == 1
    event = events[0]
    assert event.acquisition_id == acquisition_id
    assert event.dataset_id == dataset_id
    assert event.producing_asset_id == asset_id
    assert event.recorded_by == actor_id
    # Dual-time: captured_at verbatim, occurred_at == now (recording time).
    assert event.captured_at == captured_at
    assert event.occurred_at == now
    assert event.settings == settings
    assert event.evidence == evidence


@pytest.mark.unit
@given(
    now=st.datetimes(min_value=datetime(2000, 1, 1), timezones=st.just(UTC)),
    backfill=_BACKFILL_DELTA,
    existing_id=st.uuids(),
    new_id=st.uuids(),
    dataset_id=st.uuids(),
    asset_id=st.uuids(),
    actor_id=st.uuids(),
)
def test_non_none_state_always_raises_already_exists(
    now: datetime,
    backfill: timedelta,
    existing_id: UUID,
    new_id: UUID,
    dataset_id: UUID,
    asset_id: UUID,
    actor_id: UUID,
) -> None:
    existing = Acquisition(
        id=existing_id,
        dataset_id=dataset_id,
        producing_asset_id=asset_id,
        producing_run_id=None,
        captured_at=now - backfill,
        settings={},
        evidence={},
        recorded_at=now,
        recorded_by=ActorId(actor_id),
        status=AcquisitionStatus.RECORDED,
    )
    command = RecordAcquisition(
        dataset_id=dataset_id,
        producing_asset_id=asset_id,
        captured_at=now - backfill,
    )
    with pytest.raises(AcquisitionAlreadyExistsError) as exc:
        record_acquisition.decide(
            state=existing,
            command=command,
            context=_context(dataset_id, asset_id),
            now=now,
            new_id=new_id,
            recorded_by=ActorId(actor_id),
        )
    assert exc.value.acquisition_id == existing_id


@pytest.mark.unit
@given(
    now=st.datetimes(min_value=datetime(2000, 1, 1), timezones=st.just(UTC)),
    backfill=_BACKFILL_DELTA,
    new_id=st.uuids(),
    dataset_id=st.uuids(),
    asset_id=st.uuids(),
    actor_id=st.uuids(),
    affordances=st.sets(
        st.sampled_from(["Imageable", "Binnable", "Recording", "Streamable"]),
        max_size=4,
    ),
)
def test_asset_without_capturing_always_raises(
    now: datetime,
    backfill: timedelta,
    new_id: UUID,
    dataset_id: UUID,
    asset_id: UUID,
    actor_id: UUID,
    affordances: set[str],
) -> None:
    """No matter which non-Capturing affordances the Family declares,
    the gate rejects (Capturing is never in the sampled set)."""
    command = RecordAcquisition(
        dataset_id=dataset_id,
        producing_asset_id=asset_id,
        captured_at=now - backfill,
    )
    with pytest.raises(AcquisitionCannotRecordWithoutCapturingError):
        record_acquisition.decide(
            state=None,
            command=command,
            context=_context(dataset_id, asset_id, affordances=frozenset(affordances)),
            now=now,
            new_id=new_id,
            recorded_by=ActorId(actor_id),
        )


@pytest.mark.unit
@given(
    now=st.datetimes(min_value=datetime(2000, 1, 1), timezones=st.just(UTC)),
    backfill=_BACKFILL_DELTA,
    new_id=st.uuids(),
    dataset_id=st.uuids(),
    asset_id=st.uuids(),
    actor_id=st.uuids(),
)
def test_decide_is_pure_same_input_same_output(
    now: datetime,
    backfill: timedelta,
    new_id: UUID,
    dataset_id: UUID,
    asset_id: UUID,
    actor_id: UUID,
) -> None:
    command = RecordAcquisition(
        dataset_id=dataset_id,
        producing_asset_id=asset_id,
        captured_at=now - backfill,
    )
    context = _context(dataset_id, asset_id)
    first = record_acquisition.decide(
        state=None,
        command=command,
        context=context,
        now=now,
        new_id=new_id,
        recorded_by=ActorId(actor_id),
    )
    second = record_acquisition.decide(
        state=None,
        command=command,
        context=context,
        now=now,
        new_id=new_id,
        recorded_by=ActorId(actor_id),
    )
    assert first == second
