"""ingest_scan handler: the composition, the policies, the atomicity.

Fakes at the ports (ConfiguredScanReader, ConfiguredChecksumComputer,
a no-duplicate checksum lookup), real deciders and a real in-memory
event store underneath, so what these tests pin is the slice's actual
contract: every refusal leaves ZERO events across all three streams,
and the one success leaves exactly one genesis event on each.
"""

from dataclasses import replace as dc_replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data.aggregates.acquisition import AcquisitionCannotRecordWithoutCapturingError
from cora.data.aggregates.dataset import DatasetAlreadyIngestedError
from cora.data.aggregates.distribution import DistributionCannotRegisterOnNonStorageSupplyError
from cora.data.errors import InvalidScanFileError, UnauthorizedError
from cora.data.features import ingest_scan
from cora.data.features.ingest_scan import IngestScan
from cora.data.features.ingest_scan.handler import DATA_EXCHANGE_PROFILE, DatasetByChecksumLookup
from cora.data.ports.checksum_computer import (
    ChecksumComputationResult,
    ComputedChecksum,
    ConfiguredChecksumComputer,
)
from cora.data.ports.checksum_verifier import Unreachable
from cora.data.ports.scan_reader import (
    ConfiguredScanReader,
    Description,
    ScanReadResult,
    Unreadable,
)
from cora.infrastructure.adapters.in_memory_asset_lookup import InMemoryAssetLookup
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports.supply_lookup import SingleSupplyLookup, SupplyLookupResult
from tests.unit._helpers import build_deps

pytestmark = pytest.mark.unit

_LOCATOR = "file:///data2/2026-07/doe-12345/scan_001.h5"
_NOW = datetime(2026, 7, 29, 16, 0, 0, tzinfo=UTC)
_AWARE_RAW = "2026-07-29T10:15:30-05:00"
_PRINCIPAL_ID = uuid4()
_CORRELATION_ID = uuid4()
_ASSET_ID = uuid4()
_SUPPLY_ID = uuid4()
_SHA = "a" * 64

_IDS = [uuid4() for _ in range(6)]
_DATASET_ID, _DISTRIBUTION_ID, _ACQUISITION_ID = _IDS[0], _IDS[1], _IDS[2]


def _description(**overrides: object) -> Description:
    base = Description(
        media_type="application/x-hdf5",
        structurally_complete=True,
        projection_count=5,
        flat_count=2,
        dark_count=2,
        invalid_count=0,
        commanded_projection_count=5,
        commanded_flat_count=2,
        commanded_dark_count=2,
        dropped_frame_count=0,
        projection_angles_deg=(0.0, 45.0, 90.0, 135.0, 180.0),
        flat_angles_deg=None,
        dark_angles_deg=None,
        start_date=datetime.fromisoformat(_AWARE_RAW),
        start_date_raw=_AWARE_RAW,
        byte_size=4096,
        mtime_ns=111,
    )
    return dc_replace(base, **overrides)  # type: ignore[arg-type]


def _computed(**overrides: object) -> ComputedChecksum:
    base = ComputedChecksum(algorithm="sha256", value=_SHA, byte_size=4096, mtime_ns=111)
    return dc_replace(base, **overrides)  # type: ignore[arg-type]


class _NoDuplicate:
    async def __call__(self, *, checksum_algorithm: str, checksum_value: str) -> UUID | None:
        return None


class _KnownDuplicate:
    def __init__(self, existing: UUID) -> None:
        self._existing = existing

    async def __call__(self, *, checksum_algorithm: str, checksum_value: str) -> UUID | None:
        return self._existing


def _asset_lookup(*, affordances: frozenset[str] = frozenset({"Capturing"})) -> InMemoryAssetLookup:
    lookup = InMemoryAssetLookup()
    lookup.register(
        asset_id=_ASSET_ID,
        name="Oryx Detector",
        tier="Device",
        lifecycle="Active",
        family_affordances=affordances,
    )
    return lookup


def _supply(kind: str = "Storage") -> SupplyLookupResult:
    return SupplyLookupResult(
        supply_id=_SUPPLY_ID,
        kind=kind,
        name="analysis tier",
        status="Available",
        facility_code="aps",
    )


def _deps(
    store: InMemoryEventStore,
    *,
    supply_kind: str = "Storage",
    affordances: frozenset[str] = frozenset({"Capturing"}),
    deny: bool = False,
) -> Kernel:
    base = build_deps(
        ids=list(_IDS),
        now=_NOW,
        event_store=store,
        asset_lookup=_asset_lookup(affordances=affordances),
        deny=deny,
    )
    return dc_replace(base, supply_lookup=SingleSupplyLookup(_supply(supply_kind)))


def _bind(
    deps: Kernel,
    *,
    described: ScanReadResult | None = None,
    computed: ChecksumComputationResult | None = None,
    lookup: DatasetByChecksumLookup | None = None,
) -> ingest_scan.Handler:
    reader = ConfiguredScanReader(
        {_LOCATOR: described if described is not None else _description()}
    )
    computer = ConfiguredChecksumComputer(
        {_LOCATOR: computed if computed is not None else _computed()}
    )
    return ingest_scan.bind(
        deps,
        scan_reader=reader,
        checksum_computer=computer,
        dataset_by_checksum_lookup=lookup if lookup is not None else _NoDuplicate(),
    )


def _command(**overrides: object) -> IngestScan:
    values: dict[str, object] = {
        "locator": _LOCATOR,
        "producing_asset_id": _ASSET_ID,
        "supply_id": _SUPPLY_ID,
        "access_protocol": "POSIX",
    }
    values.update(overrides)
    return IngestScan(**values)  # type: ignore[arg-type]


async def _stream_counts(store: InMemoryEventStore) -> tuple[int, int, int]:
    dataset = await store.load("Dataset", _DATASET_ID)
    distribution = await store.load("Distribution", _DISTRIBUTION_ID)
    acquisition = await store.load("Acquisition", _ACQUISITION_ID)
    return (len(dataset[0]), len(distribution[0]), len(acquisition[0]))


async def test_ingest_lands_all_three_genesis_streams_atomically() -> None:
    store = InMemoryEventStore()
    dataset_id = await _bind(_deps(store))(
        _command(), principal_id=_PRINCIPAL_ID, correlation_id=_CORRELATION_ID
    )

    assert dataset_id == _DATASET_ID
    assert await _stream_counts(store) == (1, 1, 1)

    dataset_events, _ = await store.load("Dataset", _DATASET_ID)
    payload = dataset_events[0].payload
    assert payload["checksum"]["value"] == _SHA
    assert payload["byte_size"] == 4096
    assert payload["name"] == "scan_001.h5"
    assert DATA_EXCHANGE_PROFILE in payload["encoding"]["conforms_to"]


async def test_ingest_records_file_timestamp_with_source_marker() -> None:
    store = InMemoryEventStore()
    await _bind(_deps(store))(
        _command(), principal_id=_PRINCIPAL_ID, correlation_id=_CORRELATION_ID
    )

    events, _ = await store.load("Acquisition", _ACQUISITION_ID)
    payload = events[0].payload
    assert payload["captured_at"] == datetime.fromisoformat(_AWARE_RAW).isoformat()
    assert payload["evidence"]["captured_at_source"] == "start_date"
    assert payload["evidence"]["projection_count"] == 5
    assert payload["evidence"]["reader_kind"] == "Configured"


async def test_ingest_unreadable_file_refusal_leaves_zero_events() -> None:
    store = InMemoryEventStore()
    handler = _bind(_deps(store), described=Unreadable(reason="half-copied"))

    with pytest.raises(InvalidScanFileError):
        await handler(_command(), principal_id=_PRINCIPAL_ID, correlation_id=_CORRELATION_ID)

    assert await _stream_counts(store) == (0, 0, 0)


async def test_ingest_incomplete_file_refusal_leaves_zero_events() -> None:
    store = InMemoryEventStore()
    handler = _bind(
        _deps(store),
        described=_description(structurally_complete=False, projection_angles_deg=None),
    )

    with pytest.raises(InvalidScanFileError):
        await handler(_command(), principal_id=_PRINCIPAL_ID, correlation_id=_CORRELATION_ID)

    assert await _stream_counts(store) == (0, 0, 0)


async def test_ingest_timestampless_file_without_operator_value_refuses() -> None:
    store = InMemoryEventStore()
    handler = _bind(
        _deps(store), described=_description(start_date=None, start_date_raw="2026-07-29T10:15:30")
    )

    with pytest.raises(InvalidScanFileError, match="captured_at"):
        await handler(_command(), principal_id=_PRINCIPAL_ID, correlation_id=_CORRELATION_ID)

    assert await _stream_counts(store) == (0, 0, 0)


async def test_ingest_timestampless_file_accepts_operator_captured_at() -> None:
    store = InMemoryEventStore()
    handler = _bind(
        _deps(store), described=_description(start_date=None, start_date_raw="2026-07-29T10:15:30")
    )
    operator_time = datetime(2026, 7, 29, 10, 20, 0, tzinfo=UTC)

    await handler(
        _command(captured_at=operator_time),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Acquisition", _ACQUISITION_ID)
    payload = events[0].payload
    assert payload["captured_at"] == operator_time.isoformat()
    assert payload["evidence"]["captured_at_source"] == "operator"
    assert payload["evidence"]["start_date_raw"] == "2026-07-29T10:15:30"


async def test_ingest_operator_value_alongside_file_timestamp_refuses_as_ambiguous() -> None:
    store = InMemoryEventStore()
    handler = _bind(_deps(store))

    with pytest.raises(InvalidScanFileError, match="wins"):
        await handler(
            _command(captured_at=_NOW),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    assert await _stream_counts(store) == (0, 0, 0)


async def test_ingest_digest_failure_refusal_leaves_zero_events() -> None:
    store = InMemoryEventStore()
    handler = _bind(_deps(store), computed=Unreachable(error_detail="walk timed out"))

    with pytest.raises(InvalidScanFileError, match="digest"):
        await handler(_command(), principal_id=_PRINCIPAL_ID, correlation_id=_CORRELATION_ID)

    assert await _stream_counts(store) == (0, 0, 0)


async def test_ingest_file_changed_between_read_and_digest_refuses() -> None:
    store = InMemoryEventStore()
    handler = _bind(_deps(store), computed=_computed(mtime_ns=999))

    with pytest.raises(InvalidScanFileError, match="changed"):
        await handler(_command(), principal_id=_PRINCIPAL_ID, correlation_id=_CORRELATION_ID)

    assert await _stream_counts(store) == (0, 0, 0)


async def test_ingest_known_digest_refuses_naming_the_existing_dataset() -> None:
    store = InMemoryEventStore()
    existing = uuid4()
    handler = _bind(_deps(store), lookup=_KnownDuplicate(existing))

    with pytest.raises(DatasetAlreadyIngestedError) as caught:
        await handler(_command(), principal_id=_PRINCIPAL_ID, correlation_id=_CORRELATION_ID)

    assert caught.value.existing_dataset_id == existing
    assert await _stream_counts(store) == (0, 0, 0)


async def test_ingest_decider_rejection_mid_composition_leaves_zero_events() -> None:
    """The Capturing gate fires in the LAST decider; nothing from the
    first two may survive it. This is the partial-chain scenario the
    atomic composition exists to prevent."""
    store = InMemoryEventStore()
    handler = _bind(_deps(store, affordances=frozenset()))

    with pytest.raises(AcquisitionCannotRecordWithoutCapturingError):
        await handler(_command(), principal_id=_PRINCIPAL_ID, correlation_id=_CORRELATION_ID)

    assert await _stream_counts(store) == (0, 0, 0)


async def test_ingest_non_storage_supply_rejection_leaves_zero_events() -> None:
    store = InMemoryEventStore()
    handler = _bind(_deps(store, supply_kind="LiquidNitrogen"))

    with pytest.raises(DistributionCannotRegisterOnNonStorageSupplyError):
        await handler(_command(), principal_id=_PRINCIPAL_ID, correlation_id=_CORRELATION_ID)

    assert await _stream_counts(store) == (0, 0, 0)


async def test_ingest_denied_principal_is_refused_before_any_read() -> None:
    store = InMemoryEventStore()
    handler = _bind(_deps(store, deny=True))

    with pytest.raises(UnauthorizedError):
        await handler(_command(), principal_id=_PRINCIPAL_ID, correlation_id=_CORRELATION_ID)

    assert await _stream_counts(store) == (0, 0, 0)
