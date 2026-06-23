"""End-to-end integration test: record_attestation handler against real Postgres.

Pins the verifier-port-driven Attestation genesis cross-BC contract:

  - Happy: register Storage Supply -> Dataset -> Distribution (https) ->
    record Attestation; CORA's verifier computes the digest, the
    AttestationRecorded event lands with canonical payload + version=1, and
    the proj_data_attestation_summary projection row exists after drain.
  - Verifier Mismatch records a Mismatch outcome.
  - Distribution missing -> AttestationDistributionNotFoundError.
  - Distribution dataset_id mismatch -> AttestationDistributionDatasetMismatchError.
  - Unsupported URI scheme (no verifier) -> ChecksumVerifierUnsupportedSchemeError.
  - Unsupported kind handler-tier rejection.

The ChecksumVerifier is injected as a stub on ``deps.data`` so no real I/O
runs; the rest of the pipeline (event store, projection) is real Postgres.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.data._projections import register_data_projections
from cora.data.aggregates.attestation import (
    AttestationDistributionDatasetMismatchError,
    AttestationDistributionNotFoundError,
    AttestationKindNotYetSupportedError,
)
from cora.data.features import (
    record_attestation,
    register_dataset,
    register_distribution,
)
from cora.data.features.record_attestation import RecordAttestation
from cora.data.features.register_dataset import RegisterDataset
from cora.data.features.register_distribution import RegisterDistribution
from cora.data.ports.checksum_verifier import (
    AlwaysMatchingChecksumVerifier,
    AlwaysMismatchingChecksumVerifier,
    ChecksumVerifier,
    ChecksumVerifierUnsupportedSchemeError,
)
from cora.infrastructure.deps import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.supply._projections import register_supply_projections
from cora.supply.adapters import PostgresSupplyLookup
from cora.supply.features import register_supply
from cora.supply.features.register_supply import RegisterSupply
from tests.integration._helpers import build_postgres_deps

_GOOD_SHA = "a" * 64
_MISMATCH_SHA = "f" * 64  # AlwaysMismatchingChecksumVerifier's fixed digest
_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")

_HTTPS_URI = "https://store.example/runs/recon.h5"


async def _drain_supply(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_supply_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _drain_data(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_data_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


def _with_postgres_supply_lookup(deps: Kernel, pool: asyncpg.Pool) -> Kernel:
    return replace(deps, supply_lookup=PostgresSupplyLookup(pool))


def _with_verifier(
    deps: Kernel,
    verifier: ChecksumVerifier | None = None,
    *,
    scheme: str = "https",
) -> Kernel:
    """Attach a stub verifier map onto deps.data (must run after any replace())."""
    verifiers: dict[str, ChecksumVerifier] = {} if verifier is None else {scheme: verifier}
    object.__setattr__(deps, "data", SimpleNamespace(checksum_verifiers=verifiers))
    return deps


async def _register_storage_supply(db_pool: asyncpg.Pool, supply_id: UUID) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[supply_id, uuid4()])
    await register_supply.bind(deps)(
        RegisterSupply(kind="Storage", name="primary-store", facility_code="cora"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_supply(db_pool)


async def _register_dataset(
    db_pool: asyncpg.Pool,
    dataset_id: UUID,
    *,
    checksum: str = _GOOD_SHA,
    byte_size: int = 1024,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[dataset_id, uuid4()])
    await register_dataset.bind(deps)(
        RegisterDataset(
            name=f"dataset-{dataset_id.hex[:8]}",
            uri=_HTTPS_URI,
            checksum_algorithm="sha256",
            checksum_value=checksum,
            byte_size=byte_size,
            media_type="application/x-hdf5",
            conforms_to=frozenset(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _register_distribution(
    db_pool: asyncpg.Pool,
    *,
    dataset_id: UUID,
    supply_id: UUID,
    distribution_id: UUID,
    checksum: str = _GOOD_SHA,
    byte_size: int = 1024,
    uri: str = _HTTPS_URI,
    access_protocol: str = "HTTPS",
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[distribution_id, uuid4()])
    deps = _with_postgres_supply_lookup(deps, db_pool)
    await register_distribution.bind(deps)(
        RegisterDistribution(
            dataset_id=dataset_id,
            supply_id=supply_id,
            uri=uri,
            checksum_algorithm="sha256",
            checksum_value=checksum,
            byte_size=byte_size,
            media_type="application/x-hdf5",
            conforms_to=frozenset(),
            access_protocol=access_protocol,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


def _command(dataset_id: UUID, distribution_id: UUID | None) -> RecordAttestation:
    return RecordAttestation(
        dataset_id=dataset_id,
        distribution_id=distribution_id,
        kind="ChecksumVerified",
    )


# ---------- Happy path + projection ----------


@pytest.mark.integration
async def test_record_attestation_persists_event_and_projection_row(
    db_pool: asyncpg.Pool,
) -> None:
    dataset_id = uuid4()
    supply_id = uuid4()
    distribution_id = uuid4()
    attestation_id = uuid4()
    event_id = uuid4()

    await _register_dataset(db_pool, dataset_id)
    await _register_storage_supply(db_pool, supply_id)
    await _register_distribution(
        db_pool,
        dataset_id=dataset_id,
        supply_id=supply_id,
        distribution_id=distribution_id,
    )

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[attestation_id, event_id])
    deps = _with_verifier(deps, AlwaysMatchingChecksumVerifier())
    returned_id = await record_attestation.bind(deps)(
        _command(dataset_id, distribution_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_id == attestation_id

    events, version = await deps.event_store.load("Attestation", attestation_id)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "AttestationRecorded"
    payload = stored.payload
    assert payload["attestation_id"] == str(attestation_id)
    assert payload["dataset_id"] == str(dataset_id)
    assert payload["distribution_id"] == str(distribution_id)
    assert payload["kind"] == "ChecksumVerified"
    assert payload["outcome"] == "Match"
    assert payload["evidence"]["value"] == _GOOD_SHA
    assert payload["evidence"]["verifier_kind"] == "AlwaysMatching"
    assert payload["attested_by"] == str(_PRINCIPAL_ID)

    await _drain_data(db_pool)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT attestation_id, dataset_id, distribution_id, kind, outcome, "
            "evidence, attested_at, attested_by "
            "FROM proj_data_attestation_summary WHERE attestation_id = $1",
            attestation_id,
        )
    assert row is not None
    assert row["attestation_id"] == attestation_id
    assert row["dataset_id"] == dataset_id
    assert row["distribution_id"] == distribution_id
    assert row["kind"] == "ChecksumVerified"
    assert row["outcome"] == "Match"
    assert row["attested_by"] == _PRINCIPAL_ID
    assert json.loads(row["evidence"])["algorithm"] == "sha256"
    assert json.loads(row["evidence"])["value"] == _GOOD_SHA


@pytest.mark.integration
async def test_record_attestation_records_mismatch_from_verifier(
    db_pool: asyncpg.Pool,
) -> None:
    dataset_id = uuid4()
    supply_id = uuid4()
    distribution_id = uuid4()
    attestation_id = uuid4()
    event_id = uuid4()

    await _register_dataset(db_pool, dataset_id)
    await _register_storage_supply(db_pool, supply_id)
    await _register_distribution(
        db_pool,
        dataset_id=dataset_id,
        supply_id=supply_id,
        distribution_id=distribution_id,
    )

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[attestation_id, event_id])
    deps = _with_verifier(deps, AlwaysMismatchingChecksumVerifier())
    await record_attestation.bind(deps)(
        _command(dataset_id, distribution_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await deps.event_store.load("Attestation", attestation_id)
    payload = events[0].payload
    assert payload["outcome"] == "Mismatch"
    assert payload["evidence"]["value"] == _MISMATCH_SHA


# ---------- Rejection branches ----------


@pytest.mark.integration
async def test_record_attestation_rejects_unknown_distribution(
    db_pool: asyncpg.Pool,
) -> None:
    dataset_id = uuid4()
    supply_id = uuid4()
    distribution_id = uuid4()
    attestation_id = uuid4()
    event_id = uuid4()

    await _register_dataset(db_pool, dataset_id)
    await _register_storage_supply(db_pool, supply_id)
    # NOTE: do not register the Distribution.

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[attestation_id, event_id])
    deps = _with_verifier(deps, AlwaysMatchingChecksumVerifier())
    with pytest.raises(AttestationDistributionNotFoundError):
        await record_attestation.bind(deps)(
            _command(dataset_id, distribution_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.integration
async def test_record_attestation_rejects_dataset_mismatch_with_distribution(
    db_pool: asyncpg.Pool,
) -> None:
    parent_dataset_id = uuid4()
    other_dataset_id = uuid4()
    supply_id = uuid4()
    distribution_id = uuid4()
    attestation_id = uuid4()
    event_id = uuid4()

    await _register_dataset(db_pool, parent_dataset_id)
    await _register_dataset(db_pool, other_dataset_id)
    await _register_storage_supply(db_pool, supply_id)
    await _register_distribution(
        db_pool,
        dataset_id=parent_dataset_id,
        supply_id=supply_id,
        distribution_id=distribution_id,
    )

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[attestation_id, event_id])
    deps = _with_verifier(deps, AlwaysMatchingChecksumVerifier())
    with pytest.raises(AttestationDistributionDatasetMismatchError):
        await record_attestation.bind(deps)(
            _command(other_dataset_id, distribution_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.integration
async def test_record_attestation_rejects_unsupported_uri_scheme(
    db_pool: asyncpg.Pool,
) -> None:
    dataset_id = uuid4()
    supply_id = uuid4()
    distribution_id = uuid4()
    attestation_id = uuid4()
    event_id = uuid4()

    await _register_dataset(db_pool, dataset_id)
    await _register_storage_supply(db_pool, supply_id)
    await _register_distribution(
        db_pool,
        dataset_id=dataset_id,
        supply_id=supply_id,
        distribution_id=distribution_id,
        uri="globus://endpoint/runs/recon.h5",
        access_protocol="Globus",
    )

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[attestation_id, event_id])
    # Only an https verifier is configured; a globus:// Distribution has none.
    deps = _with_verifier(deps, AlwaysMatchingChecksumVerifier(), scheme="https")
    with pytest.raises(ChecksumVerifierUnsupportedSchemeError):
        await record_attestation.bind(deps)(
            _command(dataset_id, distribution_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.integration
async def test_record_attestation_rejects_kind_not_yet_supported(
    db_pool: asyncpg.Pool,
) -> None:
    """FormatValidated lifts to AttestationKindNotYetSupportedError;
    handler-tier rejection runs BEFORE the Distribution pre-load."""
    dataset_id = uuid4()
    supply_id = uuid4()
    distribution_id = uuid4()
    attestation_id = uuid4()
    event_id = uuid4()

    await _register_dataset(db_pool, dataset_id)
    await _register_storage_supply(db_pool, supply_id)
    await _register_distribution(
        db_pool,
        dataset_id=dataset_id,
        supply_id=supply_id,
        distribution_id=distribution_id,
    )

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[attestation_id, event_id])
    deps = _with_verifier(deps, AlwaysMatchingChecksumVerifier())
    with pytest.raises(AttestationKindNotYetSupportedError):
        await record_attestation.bind(deps)(
            RecordAttestation(
                dataset_id=dataset_id,
                distribution_id=distribution_id,
                kind="FormatValidated",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
