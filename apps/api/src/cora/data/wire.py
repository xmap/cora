"""Compose the Data BC's handlers from `Kernel`.

`wire_data(deps)` is invoked once from the FastAPI lifespan and the
returned `DataHandlers` bundle is stored on `app.state.data`. Routes
and MCP tools pull their handler out of that bundle. New slices add
a new field on `DataHandlers` and a single line in this factory.

Cross-cutting decorators applied here mirror every other BC
(composition order matters, innermost first):

1. `bind(deps)`: bare handler.
2. `with_idempotency` (create-style commands only): Idempotency-Key
   support. Wrapped before tracing so cache-hits and cache-misses
   both attribute to the tracing span.
3. `with_tracing`: OTel span around every handler call.

`register_dataset` is the create-style genesis (idempotency-wrapped).
The transitions (`discard`, `promote`, `demote`) are update-style
with bare handlers, strict-not-idempotent via their respective
`DatasetCannot*Error` / `DatasetAlready*Error` errors. `promote_dataset`
cross-loads peer Datasets via slice-local `DatasetPromotionContext` for the
lineage-must-be-Production guard; `demote_dataset` is the compensation
primitive and does no peer loads (no cross-BC cascade per
[[project-dataset-demote-design]] lock).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import SimpleNamespace
from typing import cast
from uuid import UUID

from cora.data.adapters._ssh_probe import SshProbeConfig
from cora.data.adapters.capture_path_locator import CapturePathLookup, active_scan_transport
from cora.data.adapters.data_exchange_scan_reader import DataExchangeScanReader
from cora.data.adapters.http_range_checksum import HttpRangeChecksumAdapter
from cora.data.adapters.in_memory_distribution_lookup import (
    InMemoryDistributionLookup,
)
from cora.data.adapters.posix_checksum import PosixChecksumAdapter
from cora.data.adapters.postgres_distribution_lookup import (
    PostgresDistributionLookup,
)
from cora.data.adapters.rocrate12_serializer import RoCrate12Adapter
from cora.data.adapters.ssh_data_exchange_scan_reader import SshDataExchangeScanReader
from cora.data.adapters.ssh_posix_checksum_computer import SshPosixChecksumComputer
from cora.data.aggregates.edition import EditionKind
from cora.data.features import (
    add_dataset_to_edition,
    demote_dataset,
    discard_dataset,
    discard_distribution,
    get_dataset,
    ingest_scan,
    list_datasets,
    mark_distribution_stale,
    promote_dataset,
    publish_edition,
    record_acquisition,
    record_attestation,
    register_dataset,
    register_distribution,
    register_edition,
    remove_dataset_from_edition,
    seal_edition,
    withdraw_edition,
)
from cora.data.features.ingest_scan.handler import DatasetByChecksumLookup
from cora.data.ports.checksum_computer import ChecksumComputer
from cora.data.ports.checksum_verifier import ChecksumVerifier
from cora.data.ports.distribution_lookup import DistributionLookup
from cora.data.ports.edition_serializer import EditionSerializer
from cora.data.ports.scan_reader import ScanReader
from cora.infrastructure.adapters.stub_persistent_identifier_minter import (
    StubPersistentIdentifierMinter,
)
from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing
from cora.run.aggregates.run import (
    InMemoryCapturePathStore,
    PostgresCapturePathStore,
)
from cora.shared.ports.persistent_identifier_minter import PersistentIdentifierMinter

_BC = "data"


@dataclass(frozen=True)
class DataHandlers:
    """The Data BC's handler bundle, each closed over Kernel."""

    register_dataset: register_dataset.IdempotentHandler
    discard_dataset: discard_dataset.Handler
    promote_dataset: promote_dataset.Handler
    demote_dataset: demote_dataset.Handler
    get_dataset: get_dataset.Handler
    list_datasets: list_datasets.Handler
    record_acquisition: record_acquisition.IdempotentHandler
    ingest_scan: ingest_scan.IdempotentHandler
    register_distribution: register_distribution.IdempotentHandler
    discard_distribution: discard_distribution.Handler
    mark_distribution_stale: mark_distribution_stale.Handler
    register_edition: register_edition.IdempotentHandler
    add_dataset_to_edition: add_dataset_to_edition.Handler
    remove_dataset_from_edition: remove_dataset_from_edition.Handler
    seal_edition: seal_edition.Handler
    publish_edition: publish_edition.Handler
    withdraw_edition: withdraw_edition.Handler
    record_attestation: record_attestation.IdempotentHandler


def _build_distribution_lookup(deps: Kernel) -> DistributionLookup:
    """Pick `PostgresDistributionLookup` when a pool is wired; else in-memory."""
    if deps.pool is not None:
        return PostgresDistributionLookup(deps.pool)
    return InMemoryDistributionLookup()


def _build_edition_serializers() -> dict[EditionKind, EditionSerializer]:
    """Per-kind serializer adapter map. Only `ROCRATE` is wired today."""
    return {EditionKind.ROCRATE: RoCrate12Adapter()}


def _build_persistent_identifier_minter() -> PersistentIdentifierMinter:
    """Wire the stub PersistentIdentifierMinter; production DataCite adapter swap is deferred."""
    return StubPersistentIdentifierMinter()


def _build_checksum_verifiers(deps: Kernel) -> Mapping[str, ChecksumVerifier]:
    """Per-scheme ChecksumVerifier map for `record_attestation`.

    http/https -> `HttpRangeChecksumAdapter` (always). file:// ->
    `PosixChecksumAdapter` only when `posix_checksum_roots` is configured;
    with no roots the deployment cannot reach local bytes, so a file:// URI
    is absent from the map and the handler raises
    `ChecksumVerifierUnsupportedSchemeError` (HTTP 400). A scheme not in the
    map means "no verifier for this scheme yet" (globus / s3 stay deferred
    per the rule-of-three; see `cora.data.ports.checksum_verifier`).
    """
    http = HttpRangeChecksumAdapter()
    verifiers: dict[str, ChecksumVerifier] = {"http": http, "https": http}
    roots = deps.settings.posix_checksum_roots
    if roots:
        verifiers["file"] = PosixChecksumAdapter(
            allowed_roots=roots,
            max_walk_seconds=deps.settings.posix_checksum_max_walk_seconds,
        )
    return verifiers


def _build_scan_ingest_pair(deps: Kernel) -> tuple[ScanReader, ChecksumComputer]:
    """Pick the SSH pair when `scan_probe_remote_host` is set, else the
    local pair keyed off `posix_checksum_roots`.

    The SSH pair is what a real 2-BM deployment needs (measured
    2026-08-18: the scan bytes live on the detector host, not CORA's
    own, and pulling one over the link takes roughly twice the scan
    cadence -- see `cora.data._remote_scan_probe`). The local pair
    stays the default for a deployment or test environment where the
    files really are local; `ingest_scan`'s own POST route and MCP
    tool use this SAME pair regardless of caller, so a human-triggered
    ingest and `CaptureScanIngestor`'s sweep read bytes identically.
    """
    # Sourced from `active_scan_transport` (not read directly here)
    # so this pair and `CaptureScanIngestor`'s minted locator always
    # describe the SAME transport, per that function's own docstring.
    host, roots = active_scan_transport(deps)
    if deps.settings.scan_probe_remote_host is not None:
        remote_python = deps.settings.scan_probe_remote_python
        # `_validate_scan_probe_remote_python` already refused a
        # deployment where `host` is set and `remote_python` is not;
        # this is that invariant made visible rather than papered over
        # with a silent `or ""` that would launch `ssh host '' -m ...`.
        assert remote_python is not None, (
            "scan_probe_remote_host is set; Settings validation guarantees "
            "scan_probe_remote_python is too"
        )
        config = SshProbeConfig(
            host=host,
            remote_python=remote_python,
            allowed_roots=roots,
            connect_timeout_seconds=deps.settings.scan_probe_ssh_connect_timeout_seconds,
            command_timeout_seconds=deps.settings.scan_probe_ssh_command_timeout_seconds,
        )
        return (
            SshDataExchangeScanReader(
                config=config, captured_at_source=deps.settings.scan_captured_at_source
            ),
            SshPosixChecksumComputer(config=config),
        )
    return (
        DataExchangeScanReader(
            allowed_roots=roots, captured_at_source=deps.settings.scan_captured_at_source
        ),
        PosixChecksumAdapter(
            allowed_roots=roots, max_walk_seconds=deps.settings.posix_checksum_max_walk_seconds
        ),
    )


def _build_dataset_by_checksum_lookup(deps: Kernel) -> DatasetByChecksumLookup:
    """Digest-equality probe for ingest's natural-key refusal.

    Postgres: reads the checksum columns on `proj_data_dataset_summary`,
    matching Registered rows only, so a Discarded record (bytes
    retracted) does not block re-ingesting bytes that reappear. The
    in-memory deployment has no projection to probe, so it never
    reports a duplicate; the test env exercises the refusal through an
    injected lookup instead.
    """
    pool = deps.pool
    if pool is None:

        async def never_found(*, checksum_algorithm: str, checksum_value: str) -> UUID | None:
            _ = checksum_algorithm, checksum_value
            return None

        return never_found

    async def probe(*, checksum_algorithm: str, checksum_value: str) -> UUID | None:
        row = cast(
            "Mapping[str, UUID] | None",
            await pool.fetchrow(  # pyright: ignore[reportUnknownMemberType]
                "SELECT dataset_id FROM proj_data_dataset_summary "
                "WHERE checksum_algorithm = $1 AND checksum_value = $2 "
                "AND status = 'Registered' LIMIT 1",
                checksum_algorithm,
                checksum_value,
            ),
        )
        return row["dataset_id"] if row is not None else None

    return probe


def _build_capture_path_store(deps: Kernel) -> CapturePathLookup:
    """Data BC's own `CapturePathStore` instance, for resolving a
    `cora-capture-path://` locator back to its real path at ingest time.
    Returned as `CapturePathLookup`, the narrow get-only Protocol
    `resolve_capture_path_locator` actually calls.

    `cora.run.wire`'s own `capture_path_store` is not reused: it lives
    on `RunHandlers`, not the Kernel (see that module's docstring on
    why it has exactly one BC), so Data BC constructs its own instance
    rather than reaching into Run BC's handler bundle. Sanctioned by
    `tach.toml`: `cora.data` already depends on `cora.run.aggregates`,
    which is where `CapturePathStore` is re-exported from.

    With a real pool, this and Run BC's own instance both wrap the SAME
    connection pool and therefore the same `run_capture_path` table:
    consistent. With `deps.pool is None` (in-memory), this builds a
    SEPARATE `InMemoryCapturePathStore` with its own `_rows` dict --
    genuinely divergent from Run BC's in-memory instance, not merely
    stateless-and-therefore-equivalent. This is harmless on the
    INTENDED path: `capture_scan_ingestor_lifespan` picks
    `NeverScanIngestCandidateLookup` under the identical `pool is None`
    condition, so the automated sweep never finds a candidate to mint a
    `cora-capture-path://` locator for in the first place, and the manual
    POST route never mints one either. It would matter only for a test
    (or a crafted manual-route call) that seeds Run BC's in-memory store
    directly and expects Data BC's resolve to see it in an in-memory
    Kernel; no test in this codebase does that today.
    """
    return (
        PostgresCapturePathStore(deps.pool) if deps.pool is not None else InMemoryCapturePathStore()
    )


def wire_data(deps: Kernel) -> DataHandlers:
    """Build the Data BC handlers from shared dependencies."""
    # Attach BC-local adapters BEFORE binding handlers that read them.
    # Per the Equipment precedent, the BC-local namespace lives at
    # `deps.data` and is set via `object.__setattr__` since `Kernel`
    # is frozen.
    if not hasattr(deps, "data"):
        object.__setattr__(
            deps,
            "data",
            SimpleNamespace(
                distribution_lookup=_build_distribution_lookup(deps),
                edition_serializers=_build_edition_serializers(),
                persistent_identifier_minter=_build_persistent_identifier_minter(),
                checksum_verifiers=_build_checksum_verifiers(deps),
            ),
        )
    scan_reader, checksum_computer = _build_scan_ingest_pair(deps)
    return DataHandlers(
        register_dataset=with_tracing(
            with_idempotency(
                register_dataset.bind(deps),
                deps.idempotency_store,
                command_name="RegisterDataset",
                # Handler returns UUID; cache as str (jsonb-friendly) and
                # rebuild via UUID() on retrieval.
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="RegisterDataset",
            bc=_BC,
        ),
        discard_dataset=with_tracing(
            discard_dataset.bind(deps),
            command_name="DiscardDataset",
            bc=_BC,
        ),
        promote_dataset=with_tracing(
            promote_dataset.bind(deps),
            command_name="PromoteDataset",
            bc=_BC,
        ),
        demote_dataset=with_tracing(
            demote_dataset.bind(deps),
            command_name="DemoteDataset",
            bc=_BC,
        ),
        get_dataset=with_tracing(
            get_dataset.bind(deps),
            command_name="GetDataset",
            bc=_BC,
            kind="query",
        ),
        list_datasets=with_tracing(
            list_datasets.bind(deps),
            command_name="ListDatasets",
            bc=_BC,
            kind="query",
        ),
        record_acquisition=with_tracing(
            with_idempotency(
                record_acquisition.bind(deps),
                deps.idempotency_store,
                command_name="RecordAcquisition",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="RecordAcquisition",
            bc=_BC,
        ),
        register_distribution=with_tracing(
            with_idempotency(
                register_distribution.bind(deps),
                deps.idempotency_store,
                command_name="RegisterDistribution",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="RegisterDistribution",
            bc=_BC,
        ),
        discard_distribution=with_tracing(
            discard_distribution.bind(deps),
            command_name="DiscardDistribution",
            bc=_BC,
        ),
        mark_distribution_stale=with_tracing(
            mark_distribution_stale.bind(deps),
            command_name="MarkDistributionStale",
            bc=_BC,
        ),
        register_edition=with_tracing(
            with_idempotency(
                register_edition.bind(deps),
                deps.idempotency_store,
                command_name="RegisterEdition",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="RegisterEdition",
            bc=_BC,
        ),
        add_dataset_to_edition=with_tracing(
            add_dataset_to_edition.bind(deps),
            command_name="AddDatasetToEdition",
            bc=_BC,
        ),
        remove_dataset_from_edition=with_tracing(
            remove_dataset_from_edition.bind(deps),
            command_name="RemoveDatasetFromEdition",
            bc=_BC,
        ),
        seal_edition=with_tracing(
            seal_edition.bind(deps),
            command_name="SealEdition",
            bc=_BC,
        ),
        publish_edition=with_tracing(
            publish_edition.bind(deps),
            command_name="PublishEdition",
            bc=_BC,
        ),
        withdraw_edition=with_tracing(
            withdraw_edition.bind(deps),
            command_name="WithdrawEdition",
            bc=_BC,
        ),
        record_attestation=with_tracing(
            with_idempotency(
                record_attestation.bind(deps),
                deps.idempotency_store,
                command_name="RecordAttestation",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="RecordAttestation",
            bc=_BC,
        ),
        # The scan reader and the digest computer are the SAME pair
        # regardless of caller (the POST route, the MCP tool, or
        # CaptureScanIngestor's sweep): see
        # `_build_scan_ingest_pair`. Both share one root
        # allowlist, local or remote depending on which pair is
        # selected; an empty allowlist refuses every locator, so ingest
        # is off until a deployment opts in. `capture_path_store`
        # resolves a `cora-capture-path://` locator (minted only by
        # CaptureScanIngestor) back to the real path before either
        # port sees it; the POST route and MCP tool never mint one, so
        # this is a pass-through for them (see
        # `cora.data.adapters.capture_path_locator`).
        ingest_scan=with_tracing(
            with_idempotency(
                ingest_scan.bind(
                    deps,
                    scan_reader=scan_reader,
                    checksum_computer=checksum_computer,
                    dataset_by_checksum_lookup=_build_dataset_by_checksum_lookup(deps),
                    capture_path_store=_build_capture_path_store(deps),
                ),
                deps.idempotency_store,
                command_name="IngestScan",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="IngestScan",
            bc=_BC,
        ),
    )
