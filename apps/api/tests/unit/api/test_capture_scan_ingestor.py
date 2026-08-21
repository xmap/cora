"""Unit tests for `CaptureScanIngestor` (cora.api._capture_scan_ingestor).

Covers the tick's dispatch logic against fakes for both collaborators
(`ScanIngestCandidateLookup` and `ingest_scan`): no candidate is a no-op,
a candidate with no configured binding is skipped WITHOUT starving
newer candidates (a gate review caught the original one-oldest-only
design head-of-line-blocking every run behind one stuck one), a
successful ingest calls `IngestScan` with the right fields, every
documented `IngestScan` failure mode is caught rather than propagated,
`UnauthorizedError` stops the whole tick rather than burning attempts on
candidates that would fail identically, and the observed path (personal
data) never reaches a log line.

The candidate SQL itself (`PostgresScanIngestCandidateLookup`) is an
integration-tier concern; see `test_capture_scan_ingestor_postgres.py`.
"""

# reportPrivateUsage: the recovery test reaches into `_FakeIngestScan`'s
# own `_raises` to change its script mid-test (this file's own test
# double, not a leak into production code), and the survives-a-failing-
# tick test drives `_sweep_loop` directly because the lifespan builds
# its own candidate lookup from `deps.pool` and so cannot be handed a
# raising one.
# pyright: reportPrivateUsage=false

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import pytest
import structlog.testing

from cora.api._capture_scan_ingestor import (
    CaptureScanIngestor,
    NeverScanIngestCandidateLookup,
    ScanIngestCandidate,
    _sweep_loop,
    capture_scan_ingestor_lifespan,
)
from cora.data.aggregates.acquisition import AcquisitionAssetNotFoundError
from cora.data.aggregates.dataset import (
    DatasetAlreadyIngestedError,
    ProducingRunNotFoundError,
)
from cora.data.aggregates.distribution import DistributionSupplyNotFoundError
from cora.data.errors import InvalidScanFileError, UnauthorizedError
from cora.infrastructure.capture_scan_ingestor_binding import (
    CaptureScanIngestorBinding,
    CaptureScanIngestorLocation,
)
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.ports import AllowAllAuthorize, FakeClock, FixedIdGenerator
from cora.infrastructure.routing import NIL_SENTINEL_ID
from tests.unit._helpers import DEFAULT_NOW

if TYPE_CHECKING:
    from cora.data.features.ingest_scan.command import IngestScan

_RUN_ID = UUID("01900000-0000-7000-8000-000000007101")
_RUN_ID_2 = UUID("01900000-0000-7000-8000-000000007102")
_RUN_ID_3 = UUID("01900000-0000-7000-8000-000000007103")
_CAPTURE_PATH_ID = UUID("01900000-0000-7000-8000-000000008101")
_CAPTURE_PATH_ID_2 = UUID("01900000-0000-7000-8000-000000008102")
_ASSET_ID = uuid4()
_SUPPLY_ID = uuid4()
_SUPPLY_ID_2 = uuid4()
_PERSONAL_PATH_FRAGMENT = "Smith-1015116"


def _deps(**settings_kwargs: Any) -> Any:
    from cora.infrastructure.config import Settings

    # A matching root so `_mint_locator` succeeds by default; tests
    # that need to exercise the no-matching-root SKIP path override
    # `posix_checksum_roots` explicitly.
    settings_kwargs.setdefault("posix_checksum_roots", ("/local1/2BM",))
    return make_inmemory_kernel(
        settings=Settings(**settings_kwargs),  # type: ignore[call-arg]
        clock=FakeClock(DEFAULT_NOW),
        id_generator=FixedIdGenerator([uuid4() for _ in range(10)]),
        authz=AllowAllAuthorize(),
    )


class _ListCandidateLookup:
    """Mirrors the real SQL's contract: returns the first candidate whose
    `capture_path_id` is NOT in `exclude`, oldest-first, or `None` when
    the list is exhausted -- close enough to
    `PostgresScanIngestCandidateLookup`'s behavior to exercise `tick()`'s
    bounded-retry loop without a database."""

    def __init__(self, candidates: list[ScanIngestCandidate]) -> None:
        self._candidates = candidates
        self.exclude_calls: list[frozenset[UUID]] = []

    async def next_candidate(
        self, *, exclude: frozenset[UUID] = frozenset()
    ) -> ScanIngestCandidate | None:
        self.exclude_calls.append(exclude)
        for candidate in self._candidates:
            if candidate.capture_path_id not in exclude:
                return candidate
        return None


class _FakeIngestScan:
    """Records the command it was called with; raises the scripted error.

    `raises` may be a single exception (every call raises it) or a dict
    keyed by `producing_run_id` (per-candidate scripted outcomes, for
    the bounded-retry tests)."""

    def __init__(
        self,
        *,
        raises: BaseException | dict[UUID, BaseException] | None = None,
        returns: UUID | None = None,
    ) -> None:
        self.calls: list[IngestScan] = []
        self._raises = raises
        self._returns = returns or uuid4()

    async def __call__(
        self,
        command: IngestScan,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID:
        self.calls.append(command)
        if isinstance(self._raises, dict):
            error = (
                self._raises.get(command.producing_run_id)
                if command.producing_run_id is not None
                else None
            )
            if error is not None:
                raise error
        elif self._raises is not None:
            raise self._raises
        return self._returns


def _candidate(
    run_id: UUID = _RUN_ID,
    capture_path_id: UUID = _CAPTURE_PATH_ID,
    capture_code: str = "2bmb-tomoscan",
    observed_path: str = f"/local1/2BM/2026-08-{_PERSONAL_PATH_FRAGMENT}/scan_005.h5",
    host: str = "localhost",
    root: str = "/local1/2BM",
) -> ScanIngestCandidate:
    return ScanIngestCandidate(
        capture_path_id=capture_path_id,
        run_id=run_id,
        capture_code=capture_code,
        observed_path=observed_path,
        host=host,
        root=root,
    )


def _bindings() -> dict[str, CaptureScanIngestorBinding]:
    return {
        "2bmb-tomoscan": CaptureScanIngestorBinding(
            producing_asset_id=_ASSET_ID,
            locations={
                "/local1/2BM": CaptureScanIngestorLocation(
                    supply_id=_SUPPLY_ID, access_protocol="POSIX"
                )
            },
        )
    }


def _bindings_with_two_locations() -> dict[str, CaptureScanIngestorBinding]:
    """A binding configured for BOTH the acquisition tier and the durable
    APS Data Management copy, with a distinct Supply/protocol pair on
    each -- used to prove `_ingest_one` reads the location matching the
    CANDIDATE's own root, not whichever location happens to be first."""
    return {
        "2bmb-tomoscan": CaptureScanIngestorBinding(
            producing_asset_id=_ASSET_ID,
            locations={
                "/local1/2BM": CaptureScanIngestorLocation(
                    supply_id=_SUPPLY_ID, access_protocol="POSIX"
                ),
                "/gdata/dm/2BM": CaptureScanIngestorLocation(
                    supply_id=_SUPPLY_ID_2, access_protocol="NFS"
                ),
            },
        )
    }


@pytest.mark.unit
async def test_tick_with_no_candidate_skips_ingest() -> None:
    lookup = _ListCandidateLookup([])
    ingest_scan = _FakeIngestScan()
    ingestor = CaptureScanIngestor(
        deps=_deps(), candidate_lookup=lookup, ingest_scan=ingest_scan, bindings=_bindings()
    )

    await ingestor.tick()

    assert ingest_scan.calls == []


@pytest.mark.unit
async def test_tick_with_no_binding_for_the_capture_code_skips_ingest() -> None:
    lookup = _ListCandidateLookup([_candidate(capture_code="unbound-code")])
    ingest_scan = _FakeIngestScan()
    ingestor = CaptureScanIngestor(
        deps=_deps(), candidate_lookup=lookup, ingest_scan=ingest_scan, bindings=_bindings()
    )

    await ingestor.tick()

    assert ingest_scan.calls == []


@pytest.mark.unit
async def test_tick_with_no_root_matching_the_observed_path_skips_ingest() -> None:
    """A misconfigured or drifted allowlist (`posix_checksum_roots` /
    `scan_probe_allowed_roots`) must SKIP this candidate rather than
    mint a locator with a fabricated tier segment; see
    `test_capture_path_locator.py` for the minting unit itself."""
    lookup = _ListCandidateLookup([_candidate()])
    ingest_scan = _FakeIngestScan()
    ingestor = CaptureScanIngestor(
        deps=_deps(posix_checksum_roots=("/somewhere/else",)),
        candidate_lookup=lookup,
        ingest_scan=ingest_scan,
        bindings=_bindings(),
    )

    await ingestor.tick()

    assert ingest_scan.calls == []


@pytest.mark.unit
async def test_tick_with_a_bound_candidate_records_the_right_fields() -> None:
    lookup = _ListCandidateLookup([_candidate()])
    ingest_scan = _FakeIngestScan()
    ingestor = CaptureScanIngestor(
        deps=_deps(), candidate_lookup=lookup, ingest_scan=ingest_scan, bindings=_bindings()
    )

    await ingestor.tick()

    assert len(ingest_scan.calls) == 1
    command = ingest_scan.calls[0]
    assert command.producing_run_id == _RUN_ID
    assert command.producing_asset_id == _ASSET_ID
    assert command.supply_id == _SUPPLY_ID
    assert command.access_protocol == "POSIX"
    # The bare observed_path becomes an INDIRECT cora-capture-path:// locator,
    # never the real file:// path (that would put a personal-data path
    # onto the immutable event); see test_capture_path_locator.py for
    # the minting/resolution unit tests themselves.
    assert command.locator.startswith(f"cora-capture-path://localhost/local1/2BM/run-{_RUN_ID}/")
    assert _PERSONAL_PATH_FRAGMENT not in command.locator


@pytest.mark.unit
async def test_tick_with_a_stuck_oldest_candidate_still_ingests_the_next_one() -> None:
    """The head-of-line-blocking regression this gate review caught: an
    oldest candidate with no binding must not prevent a later, bindable
    candidate from being ingested in the SAME tick."""
    stuck = _candidate(
        run_id=_RUN_ID, capture_path_id=_CAPTURE_PATH_ID, capture_code="unbound-code"
    )
    good = _candidate(run_id=_RUN_ID_2, capture_path_id=_CAPTURE_PATH_ID_2)
    lookup = _ListCandidateLookup([stuck, good])
    ingest_scan = _FakeIngestScan()
    ingestor = CaptureScanIngestor(
        deps=_deps(), candidate_lookup=lookup, ingest_scan=ingest_scan, bindings=_bindings()
    )

    await ingestor.tick()

    assert len(ingest_scan.calls) == 1
    assert ingest_scan.calls[0].producing_run_id == _RUN_ID_2
    # The lookup was asked to exclude the stuck candidate's vault row on
    # the retry -- by capture_path_id, not run_id.
    assert lookup.exclude_calls[-1] == frozenset({_CAPTURE_PATH_ID})


@pytest.mark.unit
async def test_tick_with_one_of_a_runs_two_locations_unbound_still_ingests_the_bound_one() -> None:
    """`exclude` is keyed by `capture_path_id`, not `run_id`: a Run with
    two vault rows (one per location) whose binding only covers ONE of
    them must not have the unbound location's SKIP also rule out the
    SAME run's other, bound location."""
    unbound = _candidate(
        run_id=_RUN_ID,
        capture_path_id=_CAPTURE_PATH_ID,
        root="/gdata/dm/2BM",
        observed_path=f"/gdata/dm/2BM/2026-08-{_PERSONAL_PATH_FRAGMENT}/scan_005.h5",
    )
    bound = _candidate(run_id=_RUN_ID, capture_path_id=_CAPTURE_PATH_ID_2, root="/local1/2BM")
    lookup = _ListCandidateLookup([unbound, bound])
    ingest_scan = _FakeIngestScan()
    ingestor = CaptureScanIngestor(
        deps=_deps(posix_checksum_roots=("/local1/2BM", "/gdata/dm/2BM")),
        candidate_lookup=lookup,
        ingest_scan=ingest_scan,
        bindings=_bindings(),
    )

    await ingestor.tick()

    assert len(ingest_scan.calls) == 1
    assert ingest_scan.calls[0].producing_run_id == _RUN_ID
    assert ingest_scan.calls[0].supply_id == _SUPPLY_ID


@pytest.mark.unit
async def test_tick_stops_after_one_success_even_with_more_candidates_left() -> None:
    """One ingest per tick throttles the sweep to what the transport can
    sustain; a second bindable candidate waits for the next tick."""
    lookup = _ListCandidateLookup([_candidate(run_id=_RUN_ID), _candidate(run_id=_RUN_ID_2)])
    ingest_scan = _FakeIngestScan()
    ingestor = CaptureScanIngestor(
        deps=_deps(), candidate_lookup=lookup, ingest_scan=ingest_scan, bindings=_bindings()
    )

    await ingestor.tick()

    assert len(ingest_scan.calls) == 1
    assert ingest_scan.calls[0].producing_run_id == _RUN_ID


@pytest.mark.unit
async def test_tick_with_every_candidate_stuck_gives_up_after_the_attempt_cap() -> None:
    candidates = [
        _candidate(run_id=UUID(int=n), capture_path_id=UUID(int=n), capture_code="unbound-code")
        for n in range(1, 15)
    ]
    lookup = _ListCandidateLookup(candidates)
    ingest_scan = _FakeIngestScan()
    ingestor = CaptureScanIngestor(
        deps=_deps(), candidate_lookup=lookup, ingest_scan=ingest_scan, bindings=_bindings()
    )

    with structlog.testing.capture_logs() as logs:
        await ingestor.tick()

    assert ingest_scan.calls == []
    assert len(lookup.exclude_calls) == 10
    assert any(entry["event"] == "capture_scan_ingestor.tick_exhausted_attempts" for entry in logs)


@pytest.mark.unit
async def test_tick_with_unauthorized_stops_without_trying_the_next_candidate() -> None:
    """A denied grant fails every candidate identically; retrying the
    next-oldest would just burn queries for the same verdict."""
    lookup = _ListCandidateLookup([_candidate(run_id=_RUN_ID), _candidate(run_id=_RUN_ID_2)])
    ingest_scan = _FakeIngestScan(raises=UnauthorizedError("denied for test"))
    ingestor = CaptureScanIngestor(
        deps=_deps(), candidate_lookup=lookup, ingest_scan=ingest_scan, bindings=_bindings()
    )

    await ingestor.tick()

    assert len(ingest_scan.calls) == 1
    assert len(lookup.exclude_calls) == 1


@pytest.mark.unit
async def test_repeated_unauthorized_ticks_log_the_denial_only_once() -> None:
    """Edge-triggered, mirroring `_flag_watcher`'s identical posture: a
    standing denial must not spam a warning every tick."""
    ingestor = CaptureScanIngestor(
        deps=_deps(),
        candidate_lookup=_ListCandidateLookup([_candidate()]),
        ingest_scan=_FakeIngestScan(raises=UnauthorizedError("denied for test")),
        bindings=_bindings(),
    )

    with structlog.testing.capture_logs() as logs:
        await ingestor.tick()
        await ingestor.tick()
        await ingestor.tick()

    denials = [e for e in logs if e["event"] == "capture_scan_ingestor.ingest_unauthorized"]
    assert len(denials) == 1


@pytest.mark.unit
async def test_authorization_recovering_after_a_denial_logs_the_recovery() -> None:
    ingest_scan = _FakeIngestScan(raises=UnauthorizedError("denied for test"))
    ingestor = CaptureScanIngestor(
        deps=_deps(),
        candidate_lookup=_ListCandidateLookup([_candidate()]),
        ingest_scan=ingest_scan,
        bindings=_bindings(),
    )

    with structlog.testing.capture_logs() as logs:
        await ingestor.tick()
        ingest_scan._raises = None
        await ingestor.tick()

    assert any(e["event"] == "capture_scan_ingestor.ingest_authorized_recovered" for e in logs)


@pytest.mark.parametrize(
    "raises",
    [
        DatasetAlreadyIngestedError(uuid4(), "deadbeef"),
        InvalidScanFileError("scan file is structurally incomplete"),
        ProducingRunNotFoundError(_RUN_ID),
        AcquisitionAssetNotFoundError(_ASSET_ID),
        DistributionSupplyNotFoundError(_SUPPLY_ID),
        RuntimeError("something unexpected"),
    ],
)
@pytest.mark.unit
async def test_tick_never_raises_past_any_ingest_scan_failure(raises: Exception) -> None:
    """Every documented `IngestScan` failure mode except `UnauthorizedError`
    (covered separately: it stops the tick rather than being skipped)
    is caught inside the tick and treated as this-candidate-only, so the
    sweep loop itself must never see an exception."""
    lookup = _ListCandidateLookup([_candidate()])
    ingest_scan = _FakeIngestScan(raises=raises)
    ingestor = CaptureScanIngestor(
        deps=_deps(), candidate_lookup=lookup, ingest_scan=ingest_scan, bindings=_bindings()
    )

    await ingestor.tick()  # must not raise

    assert len(ingest_scan.calls) == 1


@pytest.mark.unit
async def test_tick_propagates_cancellation_instead_of_swallowing_it() -> None:
    import asyncio

    lookup = _ListCandidateLookup([_candidate()])
    ingest_scan = _FakeIngestScan(raises=asyncio.CancelledError())
    ingestor = CaptureScanIngestor(
        deps=_deps(), candidate_lookup=lookup, ingest_scan=ingest_scan, bindings=_bindings()
    )

    with pytest.raises(asyncio.CancelledError):
        await ingestor.tick()


@pytest.mark.unit
async def test_a_failed_ingest_never_logs_the_observed_path() -> None:
    """`observed_path` is personal data and this log sink cannot be
    erased; every failure mode's log line must carry `run_id` /
    `capture_code` only, never the path or an exception message that
    embeds it (`InvalidScanFileError`'s text does, via `repr()`)."""
    lookup = _ListCandidateLookup([_candidate()])
    ingest_scan = _FakeIngestScan(
        raises=InvalidScanFileError(
            f"scan file is not readable: /local1/2BM/2026-08-{_PERSONAL_PATH_FRAGMENT}/scan_005.h5"
        )
    )
    ingestor = CaptureScanIngestor(
        deps=_deps(), candidate_lookup=lookup, ingest_scan=ingest_scan, bindings=_bindings()
    )

    with structlog.testing.capture_logs() as logs:
        await ingestor.tick()

    for entry in logs:
        for value in entry.values():
            assert _PERSONAL_PATH_FRAGMENT not in str(value)


@pytest.mark.unit
async def test_tick_with_no_location_for_the_candidate_root_skips_ingest() -> None:
    """A capture code CAN have a binding and still have no location for
    THIS candidate's root -- e.g. a binding configured for only the
    acquisition tier while the durable APS Data Management copy under
    `/gdata` has no entry yet. This must be a distinct skip from
    `no_binding` (no binding at all for the capture code): the two mean
    different things to whoever reads the log."""
    lookup = _ListCandidateLookup(
        [
            _candidate(
                root="/gdata/dm/2BM",
                observed_path=f"/gdata/dm/2BM/2026-08-{_PERSONAL_PATH_FRAGMENT}/scan_005.h5",
            )
        ]
    )
    ingest_scan = _FakeIngestScan()
    ingestor = CaptureScanIngestor(
        deps=_deps(),
        candidate_lookup=lookup,
        ingest_scan=ingest_scan,
        bindings=_bindings(),
    )

    with structlog.testing.capture_logs() as logs:
        await ingestor.tick()

    assert ingest_scan.calls == []
    events = [entry["event"] for entry in logs]
    assert "capture_scan_ingestor.no_location_for_root" in events
    assert "capture_scan_ingestor.no_binding" not in events
    for entry in logs:
        for value in entry.values():
            assert _PERSONAL_PATH_FRAGMENT not in str(value)


@pytest.mark.unit
async def test_tick_with_a_gdata_candidate_uses_the_gdata_locations_fields() -> None:
    """A binding with two locations must resolve each candidate against
    the location matching ITS OWN root, not whichever location a naive
    single-entry lookup would have returned first."""
    lookup = _ListCandidateLookup(
        [
            _candidate(
                root="/gdata/dm/2BM",
                observed_path=f"/gdata/dm/2BM/2026-08-{_PERSONAL_PATH_FRAGMENT}/scan_005.h5",
            )
        ]
    )
    ingest_scan = _FakeIngestScan()
    ingestor = CaptureScanIngestor(
        deps=_deps(posix_checksum_roots=("/local1/2BM", "/gdata/dm/2BM")),
        candidate_lookup=lookup,
        ingest_scan=ingest_scan,
        bindings=_bindings_with_two_locations(),
    )

    await ingestor.tick()

    assert len(ingest_scan.calls) == 1
    command = ingest_scan.calls[0]
    assert command.supply_id == _SUPPLY_ID_2
    assert command.access_protocol == "NFS"


@pytest.mark.unit
async def test_never_candidate_lookup_yields_no_candidate() -> None:
    """The no-pool fallback: an in-memory deployment has no projection to
    probe, so the sweep must idle rather than fail."""
    lookup = NeverScanIngestCandidateLookup()

    assert await lookup.next_candidate() is None
    assert await lookup.next_candidate(exclude=frozenset({_RUN_ID})) is None


@pytest.mark.unit
async def test_sweep_loop_survives_a_tick_that_raises() -> None:
    """`tick()` swallows every per-candidate failure, but the candidate
    QUERY itself sits outside that guard, so a database blip surfaces
    here. The loop must log it and keep sweeping rather than die and
    leave the ingestor silently stopped for the process's lifetime."""
    import asyncio

    class _RaisingLookup:
        async def next_candidate(
            self, *, exclude: frozenset[UUID] = frozenset()
        ) -> ScanIngestCandidate | None:
            _ = exclude
            raise RuntimeError("candidate query boom")

    ingestor = CaptureScanIngestor(
        deps=_deps(),
        candidate_lookup=_RaisingLookup(),
        ingest_scan=_FakeIngestScan(),
        bindings=_bindings(),
    )

    task = asyncio.create_task(_sweep_loop(ingestor, interval_seconds=0.01))
    await asyncio.sleep(0.05)
    still_running = not task.done()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert still_running


@pytest.mark.unit
async def test_sweep_loop_stops_when_cancelled_mid_tick() -> None:
    """Cancellation arriving DURING a tick (the likely case: a tick is
    ~30s of remote probing, the sleep between them is short) must end the
    loop, not be caught by the same guard that keeps it alive through a
    failing tick. Swallowing it there would hang shutdown forever."""
    import asyncio

    entered = asyncio.Event()

    class _HangingLookup:
        async def next_candidate(
            self, *, exclude: frozenset[UUID] = frozenset()
        ) -> ScanIngestCandidate | None:
            _ = exclude
            entered.set()
            await asyncio.sleep(10)
            return None

    ingestor = CaptureScanIngestor(
        deps=_deps(),
        candidate_lookup=_HangingLookup(),
        ingest_scan=_FakeIngestScan(),
        bindings=_bindings(),
    )

    task = asyncio.create_task(_sweep_loop(ingestor, interval_seconds=10))
    await asyncio.wait_for(entered.wait(), timeout=1)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=1)


@pytest.mark.unit
async def test_lifespan_when_enabled_sweeps_until_the_context_exits() -> None:
    """The enabled path end to end: startup grant probe, candidate-lookup
    selection (no pool here, so the Never fallback), spawned sweep task,
    and cancellation on exit. Without this the whole enabled branch of
    the lifespan runs for the first time on the deployment."""
    import asyncio

    deps = _deps(
        capture_scan_ingestor_enabled=True,
        capture_path_recording_enabled=True,
        capture_scan_ingestor_bindings=_bindings(),
    )
    ingest_scan = _FakeIngestScan()

    with structlog.testing.capture_logs() as logs:
        async with capture_scan_ingestor_lifespan(
            deps, ingest_scan=ingest_scan, interval_seconds=0.01
        ):
            await asyncio.sleep(0.05)

    events = [entry.get("event") for entry in logs]
    assert "capture_scan_ingestor.started" in events
    assert "capture_scan_ingestor.stopped" in events
    assert ingest_scan.calls == []
