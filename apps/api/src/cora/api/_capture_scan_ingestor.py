"""CaptureScanIngestor: sweep terminated witnessed Runs into Datasets.

Slice 17. The 2-BM pilot recorded 133 witnessed Runs and, before this
slice, zero Datasets: `ingest_scan` is a POST route and an MCP tool, and
by design a human invokes it (`run.aggregates.run.capture_path`'s
observed path stays unredacted specifically so an operator can locate
the file for it). That was tenable while scans were supervised one at a
time; it is not once a batch script runs 500+ scans unattended, which is
the trigger the design memo named and which has now fired at 2-BM.

## A sweep, not a terminal hook

Deliberately NOT wired onto `RunWitnessRecorder`'s own terminal, unlike
`CaptureBaselineReader` (invoked inline from `_promote`) and
`CaptureProgressFeeder` (fed observations as they arrive). A remote
scan-ingest probe measures tens of seconds (2026-08-18: ~26s to digest a
24 GB file even on the LOCAL disk holding it); `run_witness_loop` is a
single sequential `async for`, and missing a BEGUN observation while a
30-second-plus probe runs is not an acceptable trade for making this
one Run's ingest a few seconds faster. This module never imports
`_run_witness`, and `_run_witness.py` never imports this module.

Instead: a periodic sweep against the read model. Its only candidate
signal is "a terminated witnessed Run's capture path resolved
(`run_capture_path` holds a row) and no Dataset names it as
`producing_run_id` yet" -- which is restart-safe with no in-memory
queue, backfills whatever the witness already wrote before this switch
existed, and self-limits during a batch (falls behind, catches up
after, which is correct, not a bug).

## Bounded retry within a tick, not strict one-per-tick

A single successful ingest per tick (throttling the sweep to what the
transport can sustain) is NOT the same as trying only the single oldest
candidate: an early version of this slice did the latter, and a gate
review caught that it lets ONE permanently-stuck candidate (a missing
per-code binding, a file with no parseable timestamp) block EVERY
newer run forever, since `ORDER BY created_at ASC LIMIT 1` always
re-selects the same oldest row. `tick()` instead excludes each
candidate it gives up on THIS tick and tries the next-oldest, up to
`_MAX_CANDIDATES_PER_TICK` attempts, stopping at the first real success
(or the first systemic failure -- see below). A persistently-failing
candidate is still retried every tick, forever, by design: the failure
is logged loudly each time rather than parked in a dead-letter table
this slice does not build, so fixing the root cause (adding the
binding, or supplying `captured_at` by hand through the ordinary POST
route) is what actually clears it. It just no longer starves its
siblings while it waits.

## Never blocks, never raises past the tick

Every `IngestScan` failure mode is caught and logged; the tick returns
either way. A `DatasetAlreadyIngestedError` means a human already
ingested these bytes by hand (the ordinary POST route uses the SAME
`scan_reader` / `checksum_computer` pair, so this is a real race, not a
bug) and is logged at `info`, not `warning`. `UnauthorizedError` is
treated as SYSTEMIC, not per-candidate: a missing grant denies every
candidate identically, so retrying the next-oldest would just burn
`_MAX_CANDIDATES_PER_TICK` queries for the same verdict; the tick stops
immediately instead, and the warning is edge-triggered (once per denial
episode, with a matching recovery log), mirroring
`cora.api._flag_watcher`'s identical posture for the same reason.

## Never logs the observed path, and never mints an event carrying it

`observed_path` is personal data (2-BM's directory layout embeds
`{UserLastName}-{ProposalNumber}`; see
`run.aggregates.run.capture_path`'s module docstring) and this log sink
is not the vault: it cannot be erased. Every log line here carries
`run_id` and `capture_code` only, never the path and never an
exception's rendered message (`InvalidScanFileError`'s text embeds the
locator via `repr()`), mirroring `_run_witness.py`'s identical rule for
the same value.

The same reasoning extends past logging to what this module hands
`IngestScan`: `_mint_locator` builds an INDIRECT `cora-capture-path://`
locator (`cora.data.adapters.capture_path_locator`), never a `file://`
URI built directly from `observed_path`. `DatasetRegistered.uri` /
`DistributionRegistered.uri` are immutable, INSERT-only fields with no
erasure path today; this is the difference between a human pasting a
real path into the ordinary POST route (always possible, always their
choice) and this sweep doing it automatically and unconditionally for
every run.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# asyncpg's stubs are loose; suppress only at module level for
# `PostgresScanIngestCandidateLookup`, mirroring
# `run.aggregates.run.capture_path`'s identical suppress comment.

from __future__ import annotations

import asyncio
import contextlib
import enum
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from cora.agent.seed_capture_scan_ingestor import CAPTURE_SCAN_INGESTOR_AGENT_ID
from cora.api._flag_watcher import probe_read_grant
from cora.data.adapters.capture_path_locator import (
    active_scan_transport,
    mint_capture_path_locator,
)
from cora.data.aggregates.acquisition import AcquisitionAssetNotFoundError
from cora.data.aggregates.dataset import (
    DatasetAlreadyIngestedError,
    ProducingRunNotFoundError,
)
from cora.data.aggregates.distribution import DistributionSupplyNotFoundError
from cora.data.errors import InvalidScanFileError, UnauthorizedError
from cora.data.features.ingest_scan.command import IngestScan
from cora.infrastructure.logging import get_logger
from cora.shared.storage_root import normalize_storage_root

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Mapping
    from uuid import UUID

    import asyncpg

    from cora.data.features.ingest_scan.handler import IdempotentHandler
    from cora.infrastructure.capture_scan_ingestor_binding import CaptureScanIngestorBinding
    from cora.infrastructure.kernel import Kernel

_log = get_logger(__name__)

_READ_COMMAND = "IngestScan"
_LOG_PREFIX = "capture_scan_ingestor"

# Bounds how many candidates one tick will try before giving up for
# this pass: enough to walk past a small cluster of stuck runs, cheap
# enough (each excluded candidate costs one indexed query, no I/O to
# the substrate) that a pathological backlog cannot turn one tick into
# an unbounded loop.
_MAX_CANDIDATES_PER_TICK = 10

_CANDIDATE_SQL = """
SELECT rcp.capture_path_id, rcp.run_id, rcp.observed_path, rcp.host, rcp.root,
       prs.capture_code
FROM run_capture_path rcp
JOIN proj_run_summary prs ON prs.run_id = rcp.run_id
WHERE prs.capture_code IS NOT NULL
  AND prs.status IN ('Completed', 'Aborted')
  -- A row whose location was never recorded cannot produce a
  -- resolvable locator: `mint` declines, and `resolve` keys on
  -- (run_id, host, root) with no fallback. Excluding it here turns a
  -- candidate that would be re-selected and SKIPped on every tick,
  -- forever, into an explicit non-candidate. Rows predating the
  -- location columns are the population this covers.
  AND rcp.host IS NOT NULL
  AND rcp.root IS NOT NULL
  AND NOT (rcp.capture_path_id = ANY($1::uuid[]))
  AND NOT EXISTS (
      SELECT 1 FROM proj_data_dataset_summary dds
      WHERE dds.producing_run_id = rcp.run_id
  )
ORDER BY rcp.created_at ASC
LIMIT 1
"""


@dataclass(frozen=True)
class ScanIngestCandidate:
    """One terminated witnessed Run's vault row whose capture path
    resolved and which has no Dataset yet."""

    capture_path_id: UUID
    run_id: UUID
    capture_code: str
    observed_path: str
    host: str
    root: str
    """The location the vault RECORDED for this observation. Carried so
    the locator is minted from the same fact `resolve` will look the row
    up by, rather than from a second read of settings that may have
    moved since. `_CANDIDATE_SQL` excludes NULL-location rows, so both
    are non-null here."""


class ScanIngestCandidateLookup(Protocol):
    """Composition-root-owned read: joins Run BC's own `run_capture_path`
    / `proj_run_summary` against Data BC's `proj_data_dataset_summary`.
    Neither BC owns this query alone, mirroring `main.py`'s own
    "only cora.api may depend on both" placement rule.

    `exclude` holds `capture_path_id` values, not `run_id` values: a Run
    may hold more than one vault row (one per storage location it was
    observed under), and a tick that skips one location's row must still
    be free to try that SAME run's other location on the next attempt.
    Excluding by `run_id` would wrongly rule out every row for a run
    after just one of its locations proved unbound or unreadable. Lets
    one tick walk past candidates it already gave up on without
    re-selecting the same stuck head repeatedly; see
    `CaptureScanIngestor.tick`'s bounded-retry loop.
    """

    async def next_candidate(
        self, *, exclude: frozenset[UUID] = frozenset()
    ) -> ScanIngestCandidate | None: ...


class PostgresScanIngestCandidateLookup:
    """Production `ScanIngestCandidateLookup`."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def next_candidate(
        self, *, exclude: frozenset[UUID] = frozenset()
    ) -> ScanIngestCandidate | None:
        row = await self._pool.fetchrow(_CANDIDATE_SQL, list(exclude))  # pyright: ignore[reportUnknownMemberType]
        if row is None:
            return None
        return ScanIngestCandidate(
            capture_path_id=row["capture_path_id"],
            run_id=row["run_id"],
            capture_code=row["capture_code"],
            observed_path=row["observed_path"],
            host=row["host"],
            root=row["root"],
        )


class NeverScanIngestCandidateLookup:
    """No-pool fallback (in-memory deployment / test env): no projection
    to probe, so there is never a candidate, mirroring
    `_build_dataset_by_checksum_lookup`'s own `never_found` shape."""

    async def next_candidate(
        self, *, exclude: frozenset[UUID] = frozenset()
    ) -> ScanIngestCandidate | None:
        _ = exclude
        return None


def _mint_locator(candidate: ScanIngestCandidate, *, deps: Kernel) -> str | None:
    """`run_capture_path.observed_path` is a bare filesystem path (the
    raw PV value) and, at 2-BM, embeds a real person's surname
    (`{PIlastname}-{GUP#}`). `IngestScan.locator` gets an INDIRECT
    `cora-capture-path://` locator instead of a `file://` URI built directly
    from it: this is the one call in the whole automated sweep that
    would otherwise put personal data onto an immutable event, per
    `cora.data.adapters.capture_path_locator`'s module docstring.

    The locator is built from the location the VAULT ROW recorded, not
    from a fresh match against current settings. `resolve` looks the row
    up by exactly that pair, so re-deriving it here would mean two reads
    of a mutable setting at two different times (the Run's terminal, and
    this tick, arbitrarily later); any change between them mints a
    locator that resolves to nothing, silently.

    Current settings still get a say, as a REFUSAL rather than a
    re-match: a row whose recorded root is no longer in the active
    transport's allowlist is skipped, because the probe would decline to
    read it anyway (`resolve_confined_file_uri` gates the read on the
    same allowlist). Refusing here makes that an explicit SKIP instead of
    a failure several layers down.
    """
    host, roots = active_scan_transport(deps)
    allowed = {normalize_storage_root(root) for root in roots}
    if candidate.host != host or candidate.root not in allowed:
        return None
    return mint_capture_path_locator(
        observed_path=candidate.observed_path,
        run_id=candidate.run_id,
        host=candidate.host,
        root=candidate.root,
    )


class _Outcome(enum.Enum):
    """What one candidate's attempt means for the REST of this tick."""

    SUCCESS = enum.auto()
    """Ingested. The tick stops here (one success per tick)."""
    SKIP = enum.auto()
    """This candidate specifically is stuck; exclude it and try the
    next-oldest within the same tick."""
    STOP_TICK = enum.auto()
    """A systemic problem (a denied grant) makes every OTHER candidate
    fail identically; stop trying rather than burn the attempt budget."""


class CaptureScanIngestor:
    """Sweeps `ScanIngestCandidateLookup` and issues `IngestScan`,
    trying up to `_MAX_CANDIDATES_PER_TICK` candidates per tick and
    stopping at the first success."""

    def __init__(
        self,
        *,
        deps: Kernel,
        candidate_lookup: ScanIngestCandidateLookup,
        ingest_scan: IdempotentHandler,
        bindings: Mapping[str, CaptureScanIngestorBinding],
    ) -> None:
        self._deps = deps
        self._candidate_lookup = candidate_lookup
        self._ingest_scan = ingest_scan
        self._bindings = bindings
        self._authz_denied = False

    async def tick(self) -> None:
        excluded: set[UUID] = set()
        for _ in range(_MAX_CANDIDATES_PER_TICK):
            candidate = await self._candidate_lookup.next_candidate(exclude=frozenset(excluded))
            if candidate is None:
                return
            outcome = await self._ingest_one(candidate)
            if outcome is _Outcome.STOP_TICK:
                return
            if outcome is _Outcome.SUCCESS:
                return
            excluded.add(candidate.capture_path_id)
        _log.warning(
            "capture_scan_ingestor.tick_exhausted_attempts",
            attempts=_MAX_CANDIDATES_PER_TICK,
        )

    async def _ingest_one(self, candidate: ScanIngestCandidate) -> _Outcome:
        binding = self._bindings.get(candidate.capture_code)
        if binding is None:
            _log.info(
                "capture_scan_ingestor.no_binding",
                capture_code=candidate.capture_code,
                run_id=str(candidate.run_id),
            )
            return _Outcome.SKIP

        location = binding.locations.get(candidate.root)
        if location is None:
            _log.warning(
                "capture_scan_ingestor.no_location_for_root",
                capture_code=candidate.capture_code,
                run_id=str(candidate.run_id),
                root=candidate.root,
            )
            return _Outcome.SKIP

        locator = _mint_locator(candidate, deps=self._deps)
        if locator is None:
            _log.warning(
                "capture_scan_ingestor.no_matching_root",
                capture_code=candidate.capture_code,
                run_id=str(candidate.run_id),
            )
            return _Outcome.SKIP

        command = IngestScan(
            locator=locator,
            producing_asset_id=binding.producing_asset_id,
            supply_id=location.supply_id,
            access_protocol=location.access_protocol,
            producing_run_id=candidate.run_id,
        )
        try:
            dataset_id = await self._ingest_scan(
                command,
                principal_id=CAPTURE_SCAN_INGESTOR_AGENT_ID,
                correlation_id=self._deps.id_generator.new_id(),
            )
        except asyncio.CancelledError:
            raise
        except UnauthorizedError:
            if not self._authz_denied:
                _log.warning(
                    "capture_scan_ingestor.ingest_unauthorized",
                    capture_code=candidate.capture_code,
                    run_id=str(candidate.run_id),
                )
                self._authz_denied = True
            return _Outcome.STOP_TICK
        except DatasetAlreadyIngestedError as exc:
            _log.info(
                "capture_scan_ingestor.already_ingested",
                capture_code=candidate.capture_code,
                run_id=str(candidate.run_id),
                existing_dataset_id=str(exc.existing_dataset_id),
            )
            return _Outcome.SKIP
        except InvalidScanFileError:
            # Never `str(exc)`: the message embeds the locator via
            # `repr()` (see this module's own docstring). The class
            # alone already says "structurally incomplete", "unreadable",
            # or "no timestamp"; that's enough for an operator to act on
            # without the path.
            _log.warning(
                "capture_scan_ingestor.invalid_scan_file",
                capture_code=candidate.capture_code,
                run_id=str(candidate.run_id),
            )
            return _Outcome.SKIP
        except (
            ProducingRunNotFoundError,
            AcquisitionAssetNotFoundError,
            DistributionSupplyNotFoundError,
        ):
            _log.exception(
                "capture_scan_ingestor.cross_reference_missing",
                capture_code=candidate.capture_code,
                run_id=str(candidate.run_id),
            )
            return _Outcome.SKIP
        except Exception:
            _log.exception(
                "capture_scan_ingestor.ingest_failed",
                capture_code=candidate.capture_code,
                run_id=str(candidate.run_id),
            )
            return _Outcome.SKIP
        if self._authz_denied:
            _log.info("capture_scan_ingestor.ingest_authorized_recovered")
            self._authz_denied = False
        _log.info(
            "capture_scan_ingestor.ingested",
            capture_code=candidate.capture_code,
            run_id=str(candidate.run_id),
            dataset_id=str(dataset_id),
        )
        return _Outcome.SUCCESS


async def _sweep_loop(ingestor: CaptureScanIngestor, *, interval_seconds: float) -> None:
    """Periodic sweep. A failed tick is logged (inside `tick()` itself,
    which never raises); cancellation propagates."""
    while True:
        try:
            await ingestor.tick()
        except asyncio.CancelledError:
            raise
        except Exception:
            _log.exception("capture_scan_ingestor.tick_failed")
        await asyncio.sleep(interval_seconds)


@contextlib.asynccontextmanager
async def capture_scan_ingestor_lifespan(
    deps: Kernel,
    *,
    ingest_scan: IdempotentHandler,
    interval_seconds: float | None = None,
) -> AsyncGenerator[None]:
    """Spawn the CaptureScanIngestor sweep for the duration of the
    context. No-op unless `settings.capture_scan_ingestor_enabled` is
    True (default off, so a deployment opts in explicitly). When
    enabled, probes the `IngestScan` grant once at startup (or refuses
    boot in strict mode) so a missing grant is surfaced immediately
    rather than only at the first denied tick, mirroring every sibling
    watcher/writer runtime's `probe_read_grant` startup check."""
    if not deps.settings.capture_scan_ingestor_enabled:
        _log.info("capture_scan_ingestor.skipped", reason="disabled")
        yield
        return

    await probe_read_grant(
        deps,
        agent_id=CAPTURE_SCAN_INGESTOR_AGENT_ID,
        read_command=_READ_COMMAND,
        log_prefix=_LOG_PREFIX,
        strict=deps.settings.watcher_authz_strict,
    )

    candidate_lookup: ScanIngestCandidateLookup = (
        PostgresScanIngestCandidateLookup(deps.pool)
        if deps.pool is not None
        else NeverScanIngestCandidateLookup()
    )
    ingestor = CaptureScanIngestor(
        deps=deps,
        candidate_lookup=candidate_lookup,
        ingest_scan=ingest_scan,
        bindings=deps.settings.capture_scan_ingestor_bindings,
    )
    default_interval = deps.settings.capture_scan_ingestor_tick_seconds
    interval = interval_seconds if interval_seconds is not None else default_interval
    _log.info("capture_scan_ingestor.started", interval_seconds=interval)
    task = asyncio.create_task(
        _sweep_loop(ingestor, interval_seconds=interval), name="capture-scan-ingestor"
    )
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        _log.info("capture_scan_ingestor.stopped")


__all__ = [
    "CaptureScanIngestor",
    "NeverScanIngestCandidateLookup",
    "PostgresScanIngestCandidateLookup",
    "ScanIngestCandidate",
    "ScanIngestCandidateLookup",
    "capture_scan_ingestor_lifespan",
]
