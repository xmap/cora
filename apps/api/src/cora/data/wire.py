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
from uuid import UUID

from cora.data.adapters.http_range_checksum import HttpRangeChecksumAdapter
from cora.data.adapters.in_memory_distribution_lookup import (
    InMemoryDistributionLookup,
)
from cora.data.adapters.posix_checksum import PosixChecksumAdapter
from cora.data.adapters.postgres_distribution_lookup import (
    PostgresDistributionLookup,
)
from cora.data.adapters.rocrate12_serializer import RoCrate12Adapter
from cora.data.aggregates.edition import EditionKind
from cora.data.features import (
    add_dataset_to_edition,
    demote_dataset,
    discard_dataset,
    get_dataset,
    list_datasets,
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
from cora.data.ports.checksum_verifier import ChecksumVerifier
from cora.data.ports.distribution_lookup import DistributionLookup
from cora.data.ports.edition_serializer import EditionSerializer
from cora.infrastructure.adapters.stub_persistent_identifier_minter import (
    StubPersistentIdentifierMinter,
)
from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing
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
    register_distribution: register_distribution.IdempotentHandler
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
        verifiers["file"] = PosixChecksumAdapter(allowed_roots=roots)
    return verifiers


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
    )
