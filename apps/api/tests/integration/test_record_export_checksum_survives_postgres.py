"""The campaign's proof: a real checksum, registered through the real
command path, survives redaction and lands in the published bundle.

F6 found the published record of a real scan scientifically empty:
`checksum_value` dropped, along with `uri`, `name`, `media_type`,
`intent`, `conforms_to`, and `evidence` entire. Without the checksum a
published record cannot be checked against the data it describes,
which is the whole proposition. This test is that proposition, proven
against a real database through the real `register_dataset` and
`register_distribution` handlers -- not a synthetic `ExportedRecord`
built to already have the right shape.

Deliberately standalone (`producing_run_id=None`, `subject_id=None`,
`derived_from=frozenset()`): this is the exact shape of the first real
2-BM ingest (`project_2bm_first_scan_record.md`), a commissioning scan
with no Run context, so this test does not carry the cost of seeding
Family -> Asset -> Method -> Practice -> Plan -> Subject -> Run just to
prove the checksum survives.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.data.aggregates.dataset import DATASET_CHECKSUM_SHA256_HEX_LENGTH
from cora.data.features import register_dataset, register_distribution
from cora.data.features.register_dataset import RegisterDataset
from cora.data.features.register_distribution import RegisterDistribution
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.infrastructure.record_export import (
    build_manifest,
    capture_git_commit,
    export_record,
    hash_redaction_profile,
    read_bundle_body,
    redact_record,
    write_bundle,
)
from cora.supply._projections import register_supply_projections
from cora.supply.adapters import PostgresSupplyLookup
from cora.supply.features import register_supply
from cora.supply.features.register_supply import RegisterSupply
from tests._drain import drain_deadline_s
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 8, 12, 6, 21, 17, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")

# A realistic-shaped digest, not the live 2-BM scan's own value: this test
# proves the MECHANISM survives redaction, and pinning a real production
# digest into test source would be a second, unrelated way to leak it.
_CHECKSUM_VALUE = "96360334138a1d63aa080f799e040fc6c93493b407908c83c90a4474fac19842"
assert len(_CHECKSUM_VALUE) == DATASET_CHECKSUM_SHA256_HEX_LENGTH


async def _drain_supply(db_pool: asyncpg.Pool) -> None:
    """`register_distribution` pre-loads the Supply via a projection-backed
    `SupplyLookup` port, not by folding the Supply's own event stream, so
    a freshly-registered Supply is invisible until its projection catches
    up."""
    registry = ProjectionRegistry()
    register_supply_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())


async def _register_dataset_and_distribution_standalone(
    db_pool: asyncpg.Pool, *, dataset_id: UUID, distribution_id: UUID, supply_id: UUID
) -> None:
    """The 2-BM commissioning shape: no Run, no Subject, no lineage."""
    supply_deps = build_postgres_deps(db_pool, now=_NOW, ids=[supply_id, uuid4()])
    await register_supply.bind(supply_deps)(
        RegisterSupply(kind="Storage", name="checksum-survives-test-supply", facility_code="cora"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_supply(db_pool)

    dataset_deps = build_postgres_deps(db_pool, now=_NOW, ids=[dataset_id, uuid4()])
    await register_dataset.bind(dataset_deps)(
        RegisterDataset(
            name="test_005.h5",
            uri="file:///local/cora-scans/test_005.h5",
            checksum_algorithm="sha256",
            checksum_value=_CHECKSUM_VALUE,
            byte_size=24_504_057_268,
            media_type="application/x-hdf5",
            conforms_to=frozenset({"https://www.aps.anl.gov/DataExchange"}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    distribution_deps = build_postgres_deps(db_pool, now=_NOW, ids=[distribution_id, uuid4()])
    # `supply_lookup` defaults to the AllSatisfiedSupplyLookup synthetic
    # stub; register_distribution's cross-BC Supply pre-load needs the
    # real projection-backed port to see a Supply this test just wrote.
    distribution_deps = replace(distribution_deps, supply_lookup=PostgresSupplyLookup(db_pool))
    await register_distribution.bind(distribution_deps)(
        RegisterDistribution(
            dataset_id=dataset_id,
            supply_id=supply_id,
            uri="file:///local/cora-scans/test_005.h5",
            checksum_algorithm="sha256",
            checksum_value=_CHECKSUM_VALUE,
            byte_size=24_504_057_268,
            media_type="application/x-hdf5",
            access_protocol="POSIX",
            conforms_to=frozenset({"https://www.aps.anl.gov/DataExchange"}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


def _all_string_leaves(record: object) -> set[str]:
    leaves: set[str] = set()

    def _walk(value: object) -> None:
        if isinstance(value, dict):
            for sub in value.values():
                _walk(sub)
        elif isinstance(value, (list, tuple)):
            for item in value:
                _walk(item)
        elif isinstance(value, str):
            leaves.add(value)

    _walk(record)
    return leaves


@pytest.mark.integration
async def test_checksum_survives_redaction_through_the_real_command_path(
    db_pool: asyncpg.Pool,
) -> None:
    dataset_id, distribution_id, supply_id = uuid4(), uuid4(), uuid4()
    await _register_dataset_and_distribution_standalone(
        db_pool, dataset_id=dataset_id, distribution_id=distribution_id, supply_id=supply_id
    )

    async with db_pool.acquire() as conn:
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        exported = await export_record(pg_conn)

    redaction = redact_record(exported, expected_redaction_profile_hash=hash_redaction_profile())

    redacted = redaction.redacted_record
    redacted_leaves = _all_string_leaves(
        {"streams": redacted.streams, "logbooks": redacted.logbooks}
    )
    assert _CHECKSUM_VALUE in redacted_leaves, (
        "the checksum did not survive redaction: a published record of this "
        "Dataset would be unable to be checked against the data it describes"
    )

    # Named F6 drops, confirmed still dropping by decision, not oversight:
    # uri and name never publish. A 2-BM experiment folder is
    # `/local2/2BM/2026-08-DeCarlo-1015116`, so the locator carries a PI
    # surname and a proposal number. A publishable locator is its own
    # decision with its own threat model, deliberately not taken here.
    assert "test_005.h5" not in redacted_leaves
    assert "file:///local/cora-scans/test_005.h5" not in redacted_leaves


@pytest.mark.integration
async def test_checksum_survives_redaction_in_the_published_bundle_on_disk(
    db_pool: asyncpg.Pool, tmp_path: Path
) -> None:
    """The literal proof: the digest string, findable by a stranger reading
    the bundle files, no CORA required."""
    dataset_id, distribution_id, supply_id = uuid4(), uuid4(), uuid4()
    await _register_dataset_and_distribution_standalone(
        db_pool, dataset_id=dataset_id, distribution_id=distribution_id, supply_id=supply_id
    )

    async with db_pool.acquire() as conn:
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        exported = await export_record(pg_conn)

    redaction = redact_record(exported, expected_redaction_profile_hash=hash_redaction_profile())
    manifest = build_manifest(exported, git_commit=capture_git_commit(), redaction=redaction)
    bundle = write_bundle(redaction.redacted_record, manifest, tmp_path / "published")

    body = read_bundle_body(bundle)
    assert _CHECKSUM_VALUE in _all_string_leaves(body), (
        "the checksum is not readable in the published bundle on disk -- "
        "the one fact that makes a published record checkable against the "
        "data it describes"
    )
