"""End-to-end Slice C test: AttestationRecorded flips Distribution.status.

The Attestation projection-writer extension on
``DistributionSummaryProjection`` subscribes to ``AttestationRecorded``
and writes ``proj_data_distribution_summary.status`` to:

  - 'Verified' on (kind=ChecksumVerified, outcome=Match).
  - 'Stale'    on (kind=ChecksumVerified, outcome=Mismatch).
  - no-op      on outcome=Unreachable.
  - no-op      on distribution_id=None (ConformsToValidated).
  - no-op      on rowcount=0 (Distribution row not yet materialized
                              or already Discarded); writer logs WARN
                              and bookmark advances.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.data._projections import register_data_projections
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
    AlwaysUnreachableChecksumVerifier,
    ChecksumVerifier,
)
from cora.infrastructure.deps import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.supply._projections import register_supply_projections
from cora.supply.adapters import PostgresSupplyLookup
from cora.supply.features import register_supply
from cora.supply.features.register_supply import RegisterSupply
from tests.integration._helpers import build_postgres_deps

_GOOD_SHA = "a" * 64
_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_HTTPS_URI = "https://store.example/runs/recon.h5"


def _with_verifier(deps: Kernel, verifier: ChecksumVerifier, *, scheme: str = "https") -> Kernel:
    """Attach a stub verifier map onto deps.data (after any replace())."""
    object.__setattr__(deps, "data", SimpleNamespace(checksum_verifiers={scheme: verifier}))
    return deps


def _command(dataset_id: UUID, distribution_id: UUID) -> RecordAttestation:
    return RecordAttestation(
        dataset_id=dataset_id,
        distribution_id=distribution_id,
        kind="ChecksumVerified",
    )


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


async def _seed_distribution(
    db_pool: asyncpg.Pool,
) -> tuple[UUID, UUID, UUID]:
    """Register Storage Supply + Dataset + Distribution; return ids."""
    dataset_id = uuid4()
    supply_id = uuid4()
    distribution_id = uuid4()

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[supply_id, uuid4()])
    await register_supply.bind(deps)(
        RegisterSupply(kind="Storage", name="primary-store", facility_code="cora"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_supply(db_pool)

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[dataset_id, uuid4()])
    await register_dataset.bind(deps)(
        RegisterDataset(
            name="d",
            uri="s3://aps/runs/recon.h5",
            checksum_algorithm="sha256",
            checksum_value=_GOOD_SHA,
            byte_size=1024,
            media_type="application/x-hdf5",
            conforms_to=frozenset(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[distribution_id, uuid4()])
    deps = _with_postgres_supply_lookup(deps, db_pool)
    await register_distribution.bind(deps)(
        RegisterDistribution(
            dataset_id=dataset_id,
            supply_id=supply_id,
            uri=_HTTPS_URI,
            checksum_algorithm="sha256",
            checksum_value=_GOOD_SHA,
            byte_size=1024,
            media_type="application/x-hdf5",
            conforms_to=frozenset(),
            access_protocol="HTTPS",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return dataset_id, supply_id, distribution_id


async def _read_distribution_status(db_pool: asyncpg.Pool, distribution_id: UUID) -> str | None:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status FROM proj_data_distribution_summary WHERE distribution_id = $1",
            distribution_id,
        )
    if row is None:
        return None
    return row["status"]


@pytest.mark.integration
async def test_match_attestation_flips_distribution_status_to_verified(
    db_pool: asyncpg.Pool,
) -> None:
    dataset_id, _supply_id, distribution_id = await _seed_distribution(db_pool)
    await _drain_data(db_pool)
    assert await _read_distribution_status(db_pool, distribution_id) == "Registered"

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4(), uuid4()])
    deps = _with_verifier(deps, AlwaysMatchingChecksumVerifier())
    await record_attestation.bind(deps)(
        _command(dataset_id, distribution_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_data(db_pool)
    assert await _read_distribution_status(db_pool, distribution_id) == "Verified"


@pytest.mark.integration
async def test_mismatch_attestation_flips_distribution_status_to_stale(
    db_pool: asyncpg.Pool,
) -> None:
    dataset_id, _supply_id, distribution_id = await _seed_distribution(db_pool)
    await _drain_data(db_pool)

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4(), uuid4()])
    deps = _with_verifier(deps, AlwaysMismatchingChecksumVerifier())
    await record_attestation.bind(deps)(
        _command(dataset_id, distribution_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_data(db_pool)
    assert await _read_distribution_status(db_pool, distribution_id) == "Stale"


@pytest.mark.integration
async def test_unreachable_attestation_leaves_distribution_status_unchanged(
    db_pool: asyncpg.Pool,
) -> None:
    dataset_id, _supply_id, distribution_id = await _seed_distribution(db_pool)
    await _drain_data(db_pool)

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4(), uuid4()])
    deps = _with_verifier(
        deps, AlwaysUnreachableChecksumVerifier(error_detail="HEAD timeout after 30s")
    )
    await record_attestation.bind(deps)(
        _command(dataset_id, distribution_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_data(db_pool)
    # Unreachable is transient; Distribution.status stays Registered.
    assert await _read_distribution_status(db_pool, distribution_id) == "Registered"
