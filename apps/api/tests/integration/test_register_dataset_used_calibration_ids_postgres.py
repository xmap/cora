"""End-to-end integration test:
`Dataset.used_calibration_ids` lands on
`proj_data_dataset_summary.used_calibration_ids` after the projection drain.

Pins:
  - genesis-event payload carries the sorted list
  - projection writes the uuid[] column verbatim
  - the GIN index supports `WHERE used_calibration_ids @> ARRAY[$N]::uuid[]`
    membership lookup (the future agent-subscriber + operator-dashboard
    query path for "which reconstructions cited CalibrationRevision X")
  - omitted citation set lands an empty uuid[] (forward-compat-clean
    default mirrors the payload.get fold for payloads without the field)

Mirrors the pinned-calibrations integration test shape on the symmetric Run column.
Standalone Datasets (no producing_run / subject / derived_from)
keep the seed footprint minimal — used_calibration_ids is genesis-only
and orthogonal to the upstream chain.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.data._projections import register_data_projections
from cora.data.aggregates.dataset import DATASET_CHECKSUM_SHA256_HEX_LENGTH
from cora.data.features import register_dataset
from cora.data.features.register_dataset import RegisterDataset
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from tests._drain import drain_deadline_s
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH


async def _drain_data_projections(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_data_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())


def _good_register(
    *,
    name: str,
    used_calibration_ids: frozenset[UUID] = frozenset(),
) -> RegisterDataset:
    return RegisterDataset(
        name=name,
        uri=f"s3://b/{name}",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=0,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        producing_run_id=None,
        subject_id=None,
        derived_from=frozenset(),
        used_calibration_ids=used_calibration_ids,
    )


@pytest.mark.integration
async def test_register_dataset_lands_used_calibration_ids_on_projection(
    db_pool: asyncpg.Pool,
) -> None:
    """Happy path: register_dataset with two citations lands them on
    the projection's uuid[] column (sorted lexicographically per the
    decider's pre-emit sort)."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4(), uuid4()])

    cal_a = UUID("01900000-0000-7000-8000-00000000ca01")
    cal_b = UUID("01900000-0000-7000-8000-00000000ca02")
    dataset_id = await register_dataset.bind(deps)(
        _good_register(
            name="cited-reconstruction",
            used_calibration_ids=frozenset({cal_b, cal_a}),  # scrambled
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Event payload carries the sorted list.
    events, _v = await deps.event_store.load("Dataset", dataset_id)
    assert events[0].payload["used_calibration_ids"] == sorted([str(cal_a), str(cal_b)])

    # Drain projection; column lands the uuid[] array.
    await _drain_data_projections(db_pool)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT used_calibration_ids FROM proj_data_dataset_summary WHERE dataset_id = $1",
            dataset_id,
        )
    assert row is not None
    # asyncpg returns uuid[] as list[UUID]; ordering follows insert.
    cites_on_row = list(row["used_calibration_ids"])
    assert sorted(cites_on_row) == sorted([cal_a, cal_b])


@pytest.mark.integration
async def test_register_dataset_default_citations_land_empty_array(
    db_pool: asyncpg.Pool,
) -> None:
    """Omitted used_calibration_ids on the command land an empty uuid[]
    on the projection (forward-compat-clean default mirrors the pre-
    12c payload.get fold)."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4(), uuid4()])

    dataset_id = await register_dataset.bind(deps)(
        _good_register(name="no-citation-dataset"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain_data_projections(db_pool)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT used_calibration_ids FROM proj_data_dataset_summary WHERE dataset_id = $1",
            dataset_id,
        )
    assert row is not None
    assert list(row["used_calibration_ids"]) == []


@pytest.mark.integration
async def test_used_calibration_ids_gin_index_supports_contains_membership_lookup(
    db_pool: asyncpg.Pool,
) -> None:
    """The GIN index on used_calibration_ids powers the future agent-
    subscriber + operator-dashboard replay query via the array-contains
    operator: `WHERE used_calibration_ids @> ARRAY[$X]::uuid[]`.

    Pinning `@>` (not `= ANY(...)`): `= ANY` is rewritten internally
    and does NOT probe the GIN index on uuid[]; `@>` does. The query
    path future consumers ship MUST be the GIN-friendly one or the
    index is decorative (12b-3 gate-review finding, mirrored here).

    Lands two Datasets with overlapping + non-overlapping citation
    sets, then queries by one revision id and asserts only the
    matching Datasets come back."""
    cal_shared = UUID("01900000-0000-7000-8000-00000000ca10")
    cal_only_a = UUID("01900000-0000-7000-8000-00000000ca11")
    cal_only_b = UUID("01900000-0000-7000-8000-00000000ca12")

    # Dataset A: cites {shared, only_a}
    deps_a = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4(), uuid4()])
    dataset_a_id = await register_dataset.bind(deps_a)(
        _good_register(
            name="dataset-A",
            used_calibration_ids=frozenset({cal_shared, cal_only_a}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Dataset B: cites {shared, only_b}
    deps_b = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4(), uuid4()])
    dataset_b_id = await register_dataset.bind(deps_b)(
        _good_register(
            name="dataset-B",
            used_calibration_ids=frozenset({cal_shared, cal_only_b}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain_data_projections(db_pool)

    async with db_pool.acquire() as conn:
        # Query for the shared revision: both Datasets match.
        shared_rows = await conn.fetch(
            "SELECT dataset_id FROM proj_data_dataset_summary "
            "WHERE used_calibration_ids @> ARRAY[$1]::uuid[]",
            cal_shared,
        )
        # Query for cal_only_a: only Dataset A matches.
        a_only_rows = await conn.fetch(
            "SELECT dataset_id FROM proj_data_dataset_summary "
            "WHERE used_calibration_ids @> ARRAY[$1]::uuid[]",
            cal_only_a,
        )

    assert {row["dataset_id"] for row in shared_rows} == {dataset_a_id, dataset_b_id}
    assert {row["dataset_id"] for row in a_only_rows} == {dataset_a_id}
