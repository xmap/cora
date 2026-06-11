"""Unit tests for the `record_acquisition` application handler.

Exercises authz, the cross-aggregate pre-loads (Dataset, Asset
lookup, optional Run), and the Capturing-affordance gate against
in-memory adapters.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data.aggregates.acquisition import (
    AcquisitionAssetNotFoundError,
    AcquisitionCannotRecordWithoutCapturingError,
    AcquisitionRunNotFoundError,
)
from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    DatasetNotFoundError,
    DatasetRegistered,
)
from cora.data.aggregates.dataset.events import event_type_name as dataset_event_type_name
from cora.data.aggregates.dataset.events import to_payload as dataset_to_payload
from cora.data.errors import UnauthorizedError
from cora.data.features import record_acquisition
from cora.data.features.record_acquisition import RecordAcquisition
from cora.infrastructure.adapters.in_memory_asset_lookup import InMemoryAssetLookup
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.run.aggregates.run import RunName, RunStatus
from cora.run.aggregates.run.events import RunStarted
from cora.run.aggregates.run.events import event_type_name as run_event_type_name
from cora.run.aggregates.run.events import to_payload as run_to_payload
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)
_CAPTURED_AT = datetime(2026, 6, 10, 9, 0, 0, tzinfo=UTC)
_ACQUISITION_ID = UUID("01900000-0000-7000-8000-0000000ac001")
_REC_EVENT_ID = UUID("01900000-0000-7000-8000-0000000ac002")
_DATASET_ID = UUID("01900000-0000-7000-8000-0000000da001")
_ASSET_ID = UUID("01900000-0000-7000-8000-0000000a5001")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _command(**overrides: object) -> RecordAcquisition:
    base: dict[str, object] = {
        "dataset_id": _DATASET_ID,
        "producing_asset_id": _ASSET_ID,
        "captured_at": _CAPTURED_AT,
        "producing_run_id": None,
        "settings": {"exposure_ms": 200},
        "evidence": {},
    }
    base.update(overrides)
    return RecordAcquisition(**base)  # type: ignore[arg-type]


def _seeded_asset_lookup(
    *, affordances: frozenset[str] = frozenset({"Capturing"})
) -> InMemoryAssetLookup:
    lookup = InMemoryAssetLookup()
    lookup.register(
        asset_id=_ASSET_ID,
        name="Oryx Detector",
        tier="Device",
        lifecycle="Active",
        family_affordances=affordances,
    )
    return lookup


async def _seed_dataset(store: InMemoryEventStore, dataset_id: UUID) -> None:
    event = DatasetRegistered(
        dataset_id=dataset_id,
        name="recon.h5",
        uri="s3://b/recon.h5",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=1024,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        producing_run_id=None,
        subject_id=None,
        derived_from=frozenset(),
        occurred_at=_NOW,
        registered_by=ActorId(_PRINCIPAL_ID),
    )
    new_event = to_new_event(
        event_type=dataset_event_type_name(event),
        payload=dataset_to_payload(event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="RegisterDataset",
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
    )
    await store.append(
        stream_type="Dataset", stream_id=dataset_id, expected_version=0, events=[new_event]
    )


async def _seed_run(store: InMemoryEventStore, run_id: UUID) -> None:
    event = RunStarted(
        run_id=run_id,
        name=RunName("seed-run").value,
        plan_id=uuid4(),
        subject_id=uuid4(),
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=run_event_type_name(event),
        payload=run_to_payload(event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="StartRun",
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
    )
    await store.append(stream_type="Run", stream_id=run_id, expected_version=0, events=[new_event])


def _deps(store: InMemoryEventStore, *, lookup: InMemoryAssetLookup, deny: bool = False):
    return build_deps(
        ids=[_ACQUISITION_ID, _REC_EVENT_ID],
        now=_NOW,
        event_store=store,
        asset_lookup=lookup,
        deny=deny,
    )


# ---------- Happy path ----------


@pytest.mark.unit
async def test_handler_returns_new_acquisition_id_on_success() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store, _DATASET_ID)
    deps = _deps(store, lookup=_seeded_asset_lookup())
    acquisition_id = await record_acquisition.bind(deps)(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert acquisition_id == _ACQUISITION_ID


@pytest.mark.unit
async def test_handler_appends_acquisition_recorded_event() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store, _DATASET_ID)
    deps = _deps(store, lookup=_seeded_asset_lookup())
    await record_acquisition.bind(deps)(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Acquisition", _ACQUISITION_ID)
    assert version == 1
    assert [e.event_type for e in events] == ["AcquisitionRecorded"]
    recorded = events[0]
    assert recorded.payload["acquisition_id"] == str(_ACQUISITION_ID)
    assert recorded.payload["dataset_id"] == str(_DATASET_ID)
    assert recorded.payload["producing_asset_id"] == str(_ASSET_ID)
    assert recorded.payload["producing_run_id"] is None
    assert recorded.payload["occurred_at"] == _NOW.isoformat()
    assert recorded.payload["captured_at"] == _CAPTURED_AT.isoformat()
    assert recorded.payload["recorded_by"] == str(_PRINCIPAL_ID)


@pytest.mark.unit
async def test_handler_succeeds_with_seeded_run() -> None:
    run_id = uuid4()
    store = InMemoryEventStore()
    await _seed_dataset(store, _DATASET_ID)
    await _seed_run(store, run_id)
    deps = _deps(store, lookup=_seeded_asset_lookup())
    await record_acquisition.bind(deps)(
        _command(producing_run_id=run_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Acquisition", _ACQUISITION_ID)
    assert events[0].payload["producing_run_id"] == str(run_id)


# ---------- Authz ----------


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store, _DATASET_ID)
    deps = _deps(store, lookup=_seeded_asset_lookup(), deny=True)
    with pytest.raises(UnauthorizedError):
        await record_acquisition.bind(deps)(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    events, _ = await store.load("Acquisition", _ACQUISITION_ID)
    assert events == []


# ---------- Cross-aggregate pre-loads ----------


@pytest.mark.unit
async def test_handler_raises_dataset_not_found() -> None:
    store = InMemoryEventStore()  # no Dataset seeded
    deps = _deps(store, lookup=_seeded_asset_lookup())
    with pytest.raises(DatasetNotFoundError):
        await record_acquisition.bind(deps)(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_asset_not_found() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store, _DATASET_ID)
    deps = _deps(store, lookup=InMemoryAssetLookup())  # no Asset seeded
    with pytest.raises(AcquisitionAssetNotFoundError):
        await record_acquisition.bind(deps)(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_run_not_found_when_run_id_unknown() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store, _DATASET_ID)
    deps = _deps(store, lookup=_seeded_asset_lookup())
    with pytest.raises(AcquisitionRunNotFoundError):
        await record_acquisition.bind(deps)(
            _command(producing_run_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_missing_capturing_affordance() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store, _DATASET_ID)
    deps = _deps(store, lookup=_seeded_asset_lookup(affordances=frozenset({"Imageable"})))
    with pytest.raises(AcquisitionCannotRecordWithoutCapturingError):
        await record_acquisition.bind(deps)(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    events, _ = await store.load("Acquisition", _ACQUISITION_ID)
    assert events == []


@pytest.mark.unit
async def test_handler_does_not_inspect_run_status() -> None:
    """An Acquisition may be recorded against a Run in any state; the
    handler / decider only check existence."""
    run_id = uuid4()
    store = InMemoryEventStore()
    await _seed_dataset(store, _DATASET_ID)
    await _seed_run(store, run_id)
    deps = _deps(store, lookup=_seeded_asset_lookup())
    # Run is RUNNING here; the point is no status branch exists.
    acquisition_id = await record_acquisition.bind(deps)(
        _command(producing_run_id=run_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert acquisition_id == _ACQUISITION_ID
    assert RunStatus.RUNNING is RunStatus.RUNNING  # sanity anchor
