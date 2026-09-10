"""ingest_scan's second outcome: recording a capture that can never
become a Dataset.

What these tests pin is the SHAPE of the decision, not just that a row
appears: which refusals qualify, what evidence is required before CORA
will make a permanent claim, and that the refusal itself is unchanged.

## The three instants are deliberately distinct

`deps.clock` (`_NOW`), the Run's terminal (`_RUN_ENDED_AT`) and the
file's mtime (`_FINAL_MTIME_AT`) are three different times, and
`test_shortfall_fixture_instants_are_independent` fails if any two are
ever collapsed. The finality check compares the file against the Run's
terminal; a fixture that let one clock supply both sides would agree by
construction and pass no matter what the production code did (see
[[project_independent_check_principle]]).

The nanosecond conversion is derived differently here than in
production for the same reason: `_ns` walks a `timedelta` from the
epoch, while `_instant_of` uses `divmod` and `datetime.fromtimestamp`.
A rounding bug in one is not reproduced by the other.

The 8-second gap in `_FINAL_MTIME_AT` is not arbitrary: across 329 scan
files on the 2-BM detector host, every one settled 7.0 to 8.8 seconds
before its Run's terminal was recorded.
"""

from dataclasses import replace as dc_replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.data.adapters.capture_path_locator import mint_capture_path_locator
from cora.data.aggregates.shortfall import ShortfallReason, shortfall_stream_id
from cora.data.errors import InvalidScanFileError
from cora.data.features import ingest_scan
from cora.data.features.ingest_scan import IngestScan
from cora.data.ports.checksum_computer import ComputedChecksum, ConfiguredChecksumComputer
from cora.data.ports.scan_reader import (
    ConfiguredScanReader,
    Description,
    ScanReadResult,
    Unreadable,
)
from cora.infrastructure.adapters.in_memory_asset_lookup import InMemoryAssetLookup
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.ports.supply_lookup import SingleSupplyLookup, SupplyLookupResult
from cora.run.aggregates.run import (
    InMemoryCapturePathStore,
    RunCompleted,
    RunStarted,
)
from cora.run.aggregates.run import event_type_name as run_event_type_name
from cora.run.aggregates.run import to_payload as run_to_payload
from tests.unit._helpers import build_deps

pytestmark = pytest.mark.unit

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)

_NOW = datetime(2026, 7, 29, 16, 0, 0, tzinfo=UTC)
_RUN_ENDED_AT = datetime(2026, 7, 29, 15, 0, 0, tzinfo=UTC)
_FINAL_MTIME_AT = _RUN_ENDED_AT - timedelta(seconds=8)
_STILL_WRITING_MTIME_AT = _RUN_ENDED_AT + timedelta(seconds=5)

_HOST = "tomdet"
_ROOT = "/local1/2BM"
_OBSERVED_PATH = f"{_ROOT}/2026-08-Smith-1015116/scan_042.h5"
_DIRECT_LOCATOR = "file:///data2/2026-07/doe-12345/scan_001.h5"

_PRINCIPAL_ID = uuid4()
_CORRELATION_ID = uuid4()
_ASSET_ID = uuid4()
_SUPPLY_ID = uuid4()
_RUN_ID = UUID("01900000-0000-7000-8000-0000000090a1")
_SHA = "b" * 64

_IDS = [uuid4() for _ in range(8)]


def _ns(moment: datetime) -> int:
    """Nanoseconds since the epoch, by timedelta arithmetic.

    Deliberately a different derivation from production's
    `_instant_of`; see this module's docstring.
    """
    delta = moment - _EPOCH
    return (delta.days * 86_400 + delta.seconds) * 1_000_000_000 + delta.microseconds * 1_000


def _incomplete(**overrides: object) -> Description:
    """A real 2-BM shortfall: 1 projection of a commanded 1541, and no
    rotation-angle dataset, so `structurally_complete` is False."""
    base = Description(
        media_type="application/x-hdf5",
        structurally_complete=False,
        projection_count=1,
        flat_count=0,
        dark_count=0,
        invalid_count=0,
        commanded_projection_count=1541,
        commanded_flat_count=20,
        commanded_dark_count=20,
        dropped_frame_count=0,
        projection_angles_deg=None,
        flat_angles_deg=None,
        dark_angles_deg=None,
        captured_at=None,
        captured_at_raw=None,
        captured_at_source="end_date",
        byte_size=4096,
        mtime_ns=_ns(_FINAL_MTIME_AT),
    )
    return dc_replace(base, **overrides)  # type: ignore[arg-type]


class _NoDuplicate:
    async def __call__(self, *, checksum_algorithm: str, checksum_value: str) -> UUID | None:
        return None


def _deps(store: InMemoryEventStore) -> Kernel:
    lookup = InMemoryAssetLookup()
    lookup.register(
        asset_id=_ASSET_ID,
        name="Oryx Detector",
        tier="Device",
        lifecycle="Active",
        family_affordances=frozenset({"Capturing"}),
    )
    base = build_deps(ids=list(_IDS), now=_NOW, event_store=store, asset_lookup=lookup)
    return dc_replace(
        base,
        supply_lookup=SingleSupplyLookup(
            SupplyLookupResult(
                supply_id=_SUPPLY_ID,
                kind="Storage",
                name="analysis tier",
                status="Available",
                facility_code="aps",
            )
        ),
    )


async def _seed_run(
    store: InMemoryEventStore, *, ended: bool, naive_terminal: bool = False
) -> None:
    started = RunStarted(
        run_id=_RUN_ID,
        name="Shortfall Run",
        plan_id=UUID("01900000-0000-7000-8000-000000000401"),
        subject_id=None,
        occurred_at=_RUN_ENDED_AT - timedelta(hours=1),
    )
    await store.append(
        stream_type="Run",
        stream_id=_RUN_ID,
        expected_version=0,
        events=[
            to_new_event(
                event_type=run_event_type_name(started),
                payload=run_to_payload(started),
                occurred_at=started.occurred_at,
                event_id=uuid4(),
                command_name="StartRun",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )
    if not ended:
        return
    if naive_terminal:
        # A malformed stream, built the only way it can arise:
        # `to_payload` isoformats without an offset, and
        # `datetime.fromisoformat` reads that back naive.
        await _append_naive_terminal(store)
        return
    finished = RunCompleted(
        run_id=_RUN_ID,
        occurred_at=_RUN_ENDED_AT,
        observed_at=_RUN_ENDED_AT,
    )
    await store.append(
        stream_type="Run",
        stream_id=_RUN_ID,
        expected_version=1,
        events=[
            to_new_event(
                event_type=run_event_type_name(finished),
                payload=run_to_payload(finished),
                occurred_at=_RUN_ENDED_AT,
                event_id=uuid4(),
                command_name="CompleteRun",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )


async def _append_naive_terminal(store: InMemoryEventStore) -> None:
    naive = _RUN_ENDED_AT.replace(tzinfo=None)
    finished = RunCompleted(run_id=_RUN_ID, occurred_at=naive, observed_at=None)
    await store.append(
        stream_type="Run",
        stream_id=_RUN_ID,
        expected_version=1,
        events=[
            to_new_event(
                event_type=run_event_type_name(finished),
                payload=run_to_payload(finished),
                occurred_at=_RUN_ENDED_AT,
                event_id=uuid4(),
                command_name="CompleteRun",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )


async def _vault(store: InMemoryCapturePathStore) -> UUID:
    """Record the capture observation and hand back its surrogate key."""
    await store.upsert(
        run_id=_RUN_ID,
        observed_path=_OBSERVED_PATH,
        observed_at=_RUN_ENDED_AT,
        created_at=_RUN_ENDED_AT,
        host=_HOST,
        root=_ROOT,
    )
    row = await store.get(_RUN_ID, host=_HOST, root=_ROOT)
    assert row is not None
    return row.capture_path_id


def _bind(
    deps: Kernel,
    *,
    locator: str,
    described: ScanReadResult,
    capture_path_store: InMemoryCapturePathStore,
) -> ingest_scan.Handler:
    resolved_uri = "file://" + _OBSERVED_PATH if locator != _DIRECT_LOCATOR else _DIRECT_LOCATOR
    return ingest_scan.bind(
        deps,
        scan_reader=ConfiguredScanReader({resolved_uri: described}),
        checksum_computer=ConfiguredChecksumComputer(
            {
                resolved_uri: ComputedChecksum(
                    algorithm="sha256",
                    value=_SHA,
                    byte_size=4096,
                    mtime_ns=_ns(_FINAL_MTIME_AT),
                )
            }
        ),
        dataset_by_checksum_lookup=_NoDuplicate(),
        capture_path_store=capture_path_store,
    )


def _command(locator: str) -> IngestScan:
    return IngestScan(
        locator=locator,
        producing_asset_id=_ASSET_ID,
        supply_id=_SUPPLY_ID,
        access_protocol="POSIX",
        producing_run_id=_RUN_ID,
    )


async def _shortfall_events(store: InMemoryEventStore, capture_path_id: UUID) -> list[StoredEvent]:
    events, _ = await store.load("Shortfall", shortfall_stream_id(capture_path_id))
    return list(events)


async def _shortfall_payload(store: InMemoryEventStore, capture_path_id: UUID) -> dict[str, Any]:
    events = await _shortfall_events(store, capture_path_id)
    assert len(events) == 1
    return events[0].payload


async def _dataset_chain_counts(store: InMemoryEventStore) -> tuple[int, int, int]:
    counts: list[int] = []
    for stream_type, stream_id in (
        ("Dataset", _IDS[0]),
        ("Distribution", _IDS[1]),
        ("Acquisition", _IDS[2]),
    ):
        events, _ = await store.load(stream_type, stream_id)
        counts.append(len(events))
    return counts[0], counts[1], counts[2]


async def _run_incomplete_ingest(
    store: InMemoryEventStore,
    *,
    locator: str,
    described: ScanReadResult | None = None,
    capture_path_store: InMemoryCapturePathStore,
) -> None:
    """Drive one ingest that is expected to refuse, and swallow only
    the refusal itself so each test asserts on the RECORD rather than
    on the exception it already knows is coming."""
    handler = _bind(
        _deps(store),
        locator=locator,
        described=described if described is not None else _incomplete(),
        capture_path_store=capture_path_store,
    )
    with pytest.raises(InvalidScanFileError):
        await handler(_command(locator), principal_id=_PRINCIPAL_ID, correlation_id=_CORRELATION_ID)


def _indirect_locator() -> str:
    locator = mint_capture_path_locator(
        observed_path=_OBSERVED_PATH, run_id=_RUN_ID, host=_HOST, root=_ROOT
    )
    assert locator is not None
    return locator


def test_shortfall_fixture_instants_are_independent() -> None:
    """Guard the fixture, not the code: the finality check compares the
    file against the Run's terminal, so a fixture that ever collapses
    those two (or sources either from `deps.clock`) would make every
    test below pass by construction."""
    assert len({_NOW, _RUN_ENDED_AT, _FINAL_MTIME_AT, _STILL_WRITING_MTIME_AT}) == 4
    assert _FINAL_MTIME_AT < _RUN_ENDED_AT
    assert _STILL_WRITING_MTIME_AT > _RUN_ENDED_AT


async def test_ingest_incomplete_file_from_ended_run_records_a_shortfall() -> None:
    """The motivating 2-BM case: 1 projection of a commanded 1541, no
    rotation angles, on a Run that finished eight seconds after the
    file stopped changing."""
    store = InMemoryEventStore()
    vault = InMemoryCapturePathStore()
    await _seed_run(store, ended=True)
    capture_path_id = await _vault(vault)

    await _run_incomplete_ingest(store, locator=_indirect_locator(), capture_path_store=vault)

    events = await _shortfall_events(store, capture_path_id)
    assert len(events) == 1
    payload = events[0].payload
    assert payload["projection_count"] == 1
    assert payload["commanded_projection_count"] == 1541
    assert payload["reason"] == ShortfallReason.STRUCTURALLY_INCOMPLETE.value
    assert payload["producing_run_id"] == str(_RUN_ID)
    assert payload["capture_path_id"] == str(capture_path_id)
    assert payload["host"] == _HOST
    assert payload["root"] == _ROOT


async def test_ingest_shortfall_carries_both_sides_of_the_finality_judgement() -> None:
    """The verdict has to stay checkable from the payload alone: the
    file outlives neither the detector host nor this row."""
    store = InMemoryEventStore()
    vault = InMemoryCapturePathStore()
    await _seed_run(store, ended=True)
    capture_path_id = await _vault(vault)

    await _run_incomplete_ingest(store, locator=_indirect_locator(), capture_path_store=vault)

    payload = await _shortfall_payload(store, capture_path_id)
    assert datetime.fromisoformat(payload["file_modified_at"]) == _FINAL_MTIME_AT
    assert datetime.fromisoformat(payload["run_ended_at"]) == _RUN_ENDED_AT
    assert datetime.fromisoformat(payload["occurred_at"]) == _NOW


async def test_ingest_incomplete_file_still_being_written_records_nothing() -> None:
    """THE guard. A file whose mtime is NEWER than the Run's terminal
    is one something is still writing to, so the absent rotation angles
    may yet arrive. Condemning it would be permanent and wrong, and
    this is the assertion that fails if the comparison is ever
    loosened or inverted."""
    store = InMemoryEventStore()
    vault = InMemoryCapturePathStore()
    await _seed_run(store, ended=True)
    capture_path_id = await _vault(vault)

    await _run_incomplete_ingest(
        store,
        locator=_indirect_locator(),
        described=_incomplete(mtime_ns=_ns(_STILL_WRITING_MTIME_AT)),
        capture_path_store=vault,
    )

    assert await _shortfall_events(store, capture_path_id) == []


async def test_ingest_incomplete_file_from_open_run_records_nothing() -> None:
    """No terminal means no finality evidence at all, so there is
    nothing to base a permanent claim on."""
    store = InMemoryEventStore()
    vault = InMemoryCapturePathStore()
    await _seed_run(store, ended=False)
    capture_path_id = await _vault(vault)

    await _run_incomplete_ingest(store, locator=_indirect_locator(), capture_path_store=vault)

    assert await _shortfall_events(store, capture_path_id) == []


async def test_ingest_transient_refusal_records_nothing() -> None:
    """An unreadable file is the documented TRANSIENT refusal. Keying a
    Shortfall on the exception class rather than the specific cause
    would permanently condemn every file caught mid-transfer, which is
    the one mistake in this design that loses data silently."""
    store = InMemoryEventStore()
    vault = InMemoryCapturePathStore()
    await _seed_run(store, ended=True)
    capture_path_id = await _vault(vault)

    await _run_incomplete_ingest(
        store,
        locator=_indirect_locator(),
        described=Unreadable(reason="half-transferred"),
        capture_path_store=vault,
    )

    assert await _shortfall_events(store, capture_path_id) == []


async def test_ingest_incomplete_file_at_a_direct_path_records_nothing() -> None:
    """A hand-typed `file://` path has no vault row, so there is no
    observation surrogate to key the stream on. The rule is about what
    CORA can prove, not about who is calling: a human POSTing an
    INDIRECT locator is treated exactly like the sweep."""
    store = InMemoryEventStore()
    vault = InMemoryCapturePathStore()
    await _seed_run(store, ended=True)
    capture_path_id = await _vault(vault)

    await _run_incomplete_ingest(store, locator=_DIRECT_LOCATOR, capture_path_store=vault)

    assert await _shortfall_events(store, capture_path_id) == []


async def test_ingest_repeated_incomplete_reads_record_one_shortfall() -> None:
    """The sweep re-selects a candidate until `proj_data_shortfall_summary`
    catches up, so the second attempt is routine, not exceptional. It
    must leave the record unchanged and still raise the ordinary
    refusal rather than a conflict the operator cannot act on."""
    store = InMemoryEventStore()
    vault = InMemoryCapturePathStore()
    await _seed_run(store, ended=True)
    capture_path_id = await _vault(vault)
    locator = _indirect_locator()

    await _run_incomplete_ingest(store, locator=locator, capture_path_store=vault)
    await _run_incomplete_ingest(store, locator=locator, capture_path_store=vault)

    assert len(await _shortfall_events(store, capture_path_id)) == 1


async def test_ingest_shortfall_leaves_the_dataset_chain_empty() -> None:
    """The all-or-nothing guarantee is about the Dataset chain, and it
    is untouched: a Shortfall is a complete fact on its own stream, not
    half of a Dataset."""
    store = InMemoryEventStore()
    vault = InMemoryCapturePathStore()
    await _seed_run(store, ended=True)
    await _vault(vault)

    await _run_incomplete_ingest(store, locator=_indirect_locator(), capture_path_store=vault)

    assert await _dataset_chain_counts(store) == (0, 0, 0)


async def test_ingest_shortfall_payload_carries_no_part_of_the_observed_path() -> None:
    """`observed_path` embeds a surname and a proposal number at 2-BM,
    and this row can never be erased. The tier segments are carried
    deliberately and are not personal data; the experiment folder and
    the filename must appear nowhere."""
    store = InMemoryEventStore()
    vault = InMemoryCapturePathStore()
    await _seed_run(store, ended=True)
    capture_path_id = await _vault(vault)

    await _run_incomplete_ingest(store, locator=_indirect_locator(), capture_path_store=vault)

    payload = await _shortfall_payload(store, capture_path_id)
    rendered = repr(payload)
    assert "Smith" not in rendered
    assert "1015116" not in rendered
    assert "scan_042" not in rendered
    assert _OBSERVED_PATH not in rendered


async def test_ingest_with_a_naive_run_terminal_records_nothing() -> None:
    """A terminal without an offset means the Run stream is malformed,
    not that the file is final, so the judgement is refused. Failing
    closed is the easy half; the branch also LOGS, because a silent
    refusal here is indistinguishable from an open Run and the
    difference is a corrupt stream nobody would go looking for."""
    store = InMemoryEventStore()
    vault = InMemoryCapturePathStore()
    await _seed_run(store, ended=True, naive_terminal=True)
    capture_path_id = await _vault(vault)

    await _run_incomplete_ingest(store, locator=_indirect_locator(), capture_path_store=vault)

    assert await _shortfall_events(store, capture_path_id) == []
