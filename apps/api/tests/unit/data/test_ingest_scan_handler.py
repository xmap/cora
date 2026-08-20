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

from cora.data.adapters.capture_path_locator import mint_capture_path_locator
from cora.data.aggregates.acquisition import (
    AcquisitionCannotRecordWithoutCapturingError,
    InvalidAcquisitionEvidenceError,
)
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
from cora.run.aggregates.run import CapturePathStore, InMemoryCapturePathStore
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
        captured_at=datetime.fromisoformat(_AWARE_RAW),
        captured_at_raw=_AWARE_RAW,
        captured_at_source="start_date",
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
    capture_path_store: CapturePathStore | None = None,
    locator: str = _LOCATOR,
) -> ingest_scan.Handler:
    reader = ConfiguredScanReader({locator: described if described is not None else _description()})
    computer = ConfiguredChecksumComputer(
        {locator: computed if computed is not None else _computed()}
    )
    return ingest_scan.bind(
        deps,
        scan_reader=reader,
        checksum_computer=computer,
        dataset_by_checksum_lookup=lookup if lookup is not None else _NoDuplicate(),
        capture_path_store=(
            capture_path_store if capture_path_store is not None else InMemoryCapturePathStore()
        ),
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


async def test_ingest_through_an_indirect_locator_records_the_indirect_form() -> None:
    """`CaptureScanIngestor`'s own path, exercised through the real
    handler: the reader/computer receive the RESOLVED real path (proven
    by keying the fakes on it, so a wrong resolution would 404 inside
    `ConfiguredScanReader`), while the event actually recorded carries
    the INDIRECT `cora-capture-path://` locator, never the real one -- the
    property this whole slice exists for."""
    real_path = "/local1/2BM/2026-08-Haridy-1015116/scan_005.h5"
    run_id = uuid4()
    capture_path_store = InMemoryCapturePathStore()
    await capture_path_store.upsert(
        run_id=run_id,
        observed_path=real_path,
        observed_at=_NOW,
        created_at=_NOW,
        host="tomdet",
        root="/local1/2BM",
    )
    indirect_locator = mint_capture_path_locator(
        observed_path=real_path, run_id=run_id, host="tomdet", root="/local1/2BM"
    )
    assert indirect_locator is not None
    resolved_locator = "file://" + real_path

    store = InMemoryEventStore()
    dataset_id = await _bind(
        _deps(store),
        capture_path_store=capture_path_store,
        locator=resolved_locator,
    )(
        _command(locator=indirect_locator),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert dataset_id == _DATASET_ID
    dataset_events, _ = await store.load("Dataset", _DATASET_ID)
    distribution_events, _ = await store.load("Distribution", _DISTRIBUTION_ID)
    assert dataset_events[0].payload["uri"] == indirect_locator
    assert distribution_events[0].payload["uri"] == indirect_locator
    assert "Haridy" not in dataset_events[0].payload["uri"]


async def test_ingest_through_an_indirect_locator_with_no_vault_row_raises() -> None:
    """The erasure case: no `run_capture_path` row for this run_id (never
    observed, or a future forget-style slice deleted it). Must refuse
    cleanly, matching every other refusal's zero-events guarantee."""
    run_id = uuid4()
    indirect_locator = mint_capture_path_locator(
        observed_path="/local1/2BM/2026-08-Haridy-1015116/scan_005.h5",
        run_id=run_id,
        host="tomdet",
        root="/local1/2BM",
    )
    assert indirect_locator is not None

    store = InMemoryEventStore()
    with pytest.raises(InvalidScanFileError):
        await _bind(_deps(store), capture_path_store=InMemoryCapturePathStore())(
            _command(locator=indirect_locator),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    assert await _stream_counts(store) == (0, 0, 0)


async def test_ingest_through_an_indirect_locator_never_echoes_the_real_path_on_failure() -> None:
    """P0 from the slice-18 security review: `Unreadable.reason` /
    `Unreachable.error_detail` are sourced from a bare os.stat/h5py
    error string that embeds whatever path the reader actually opened
    -- and `InvalidScanFileError` reaches an HTTP 400 body verbatim
    (`_handle_validation_error`). For a DIRECT file:// locator the
    caller supplied that path themselves, so echoing it is not a new
    disclosure (see the sibling test below). For an INDIRECT locator
    the caller has no such prior right to the REAL path it resolved
    to -- that is the whole point of the indirection -- so it must
    never reach the raised message."""
    real_path = "/local1/2BM/2026-08-Haridy-1015116/scan_005.h5"
    run_id = uuid4()
    capture_path_store = InMemoryCapturePathStore()
    await capture_path_store.upsert(
        run_id=run_id,
        observed_path=real_path,
        observed_at=_NOW,
        created_at=_NOW,
        host="tomdet",
        root="/local1/2BM",
    )
    indirect_locator = mint_capture_path_locator(
        observed_path=real_path, run_id=run_id, host="tomdet", root="/local1/2BM"
    )
    assert indirect_locator is not None
    resolved_locator = "file://" + real_path

    store = InMemoryEventStore()
    handler = _bind(
        _deps(store),
        capture_path_store=capture_path_store,
        locator=resolved_locator,
        described=Unreadable(
            reason=f"stat failed: [Errno 2] No such file or directory: '{real_path}'"
        ),
    )

    with pytest.raises(InvalidScanFileError) as exc_info:
        await handler(
            _command(locator=indirect_locator),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    assert "Haridy" not in str(exc_info.value)
    assert real_path not in str(exc_info.value)


async def test_ingest_through_a_direct_locator_still_echoes_the_reader_reason() -> None:
    """No regression for the existing, unaffected manual-route case: a
    direct file:// locator's reader failure detail is unchanged,
    because the caller supplied that exact path themselves."""
    store = InMemoryEventStore()
    handler = _bind(_deps(store), described=Unreadable(reason="half-copied, still transferring"))

    with pytest.raises(InvalidScanFileError, match="half-copied, still transferring"):
        await handler(_command(), principal_id=_PRINCIPAL_ID, correlation_id=_CORRELATION_ID)


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
    # Every field _description() populates survives the real
    # _build_evidence -> decide_ingest -> record_acquisition.decide ->
    # validate_evidence -> to_payload path, not just a hand-picked few.
    assert payload["evidence"] == {
        "reader_kind": "Configured",
        "checksum_computer_kind": "Configured",
        "captured_at_source": "start_date",
        "captured_at_raw": _AWARE_RAW,
        "projection_count": 5,
        "flat_count": 2,
        "dark_count": 2,
        "invalid_count": 0,
        "commanded_projection_count": 5,
        "commanded_flat_count": 2,
        "commanded_dark_count": 2,
        "dropped_frame_count": 0,
        "projection_angle_count": 5,
        "projection_angle_first": 0.0,
        "projection_angle_last": 180.0,
    }


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


async def test_ingest_reader_names_an_unrecognized_captured_at_source_refuses() -> None:
    """`Description.captured_at_source` is a plain str so a future layout
    can name a timestamp no reader has produced yet (its own docstring);
    `CapturedAtSource` has not caught up to that hypothetical layout yet.
    This is now an InvalidAcquisitionEvidenceError from the composed
    decider's validate_evidence call, not the InvalidScanFileError every
    other refusal in this file raises (EVIDENCE_SCHEMA's pre-decider
    check, which raised InvalidScanFileError for the same case, is gone;
    see the handler module docstring's "Refusal order" section)."""
    store = InMemoryEventStore()
    handler = _bind(
        _deps(store),
        described=_description(captured_at_source="acquisition_time"),
    )

    with pytest.raises(InvalidAcquisitionEvidenceError, match="captured_at_source"):
        await handler(_command(), principal_id=_PRINCIPAL_ID, correlation_id=_CORRELATION_ID)

    assert await _stream_counts(store) == (0, 0, 0)


async def test_ingest_timestampless_file_without_operator_value_refuses() -> None:
    store = InMemoryEventStore()
    handler = _bind(
        _deps(store),
        described=_description(captured_at=None, captured_at_raw="2026-07-29T10:15:30"),
    )

    with pytest.raises(InvalidScanFileError, match="captured_at"):
        await handler(_command(), principal_id=_PRINCIPAL_ID, correlation_id=_CORRELATION_ID)

    assert await _stream_counts(store) == (0, 0, 0)


async def test_ingest_timestampless_file_accepts_operator_captured_at() -> None:
    store = InMemoryEventStore()
    handler = _bind(
        _deps(store),
        described=_description(captured_at=None, captured_at_raw="2026-07-29T10:15:30"),
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
    assert payload["evidence"]["captured_at_raw"] == "2026-07-29T10:15:30"


async def test_ingest_records_the_source_the_reader_used_not_a_fixed_name() -> None:
    """The record says WHICH timestamp it believed.

    A deployment whose writer emits a bad `start_date` declares another
    source, and the record has to carry that rather than a hardcoded
    label, or a reader cannot tell which fact the capture time came
    from. This is the 2-BM posture: `end_date`, because `start_date`
    there is measurably the previous scan's.
    """
    store = InMemoryEventStore()
    handler = _bind(_deps(store), described=_description(captured_at_source="end_date"))

    await handler(_command(), principal_id=_PRINCIPAL_ID, correlation_id=_CORRELATION_ID)

    events, _ = await store.load("Acquisition", _ACQUISITION_ID)
    assert events[0].payload["evidence"]["captured_at_source"] == "end_date"


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
