"""End-to-end integration test for `Run.pinned_calibration_ids` landing on
`proj_run_summary.pinned_calibration_ids` after the projection drain.

Pins:
  - genesis-event payload carries the sorted list
  - projection writes the uuid[] column verbatim
  - the GIN index supports `WHERE pinned_calibration_ids @> ARRAY[$N]::uuid[]`
    membership lookup (the Dataset back-fill query path)
  - legacy RunStarted payloads without pins fold to empty array
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.run._projections import register_run_projections
from cora.run.features import start_run
from cora.run.features.start_run import StartRun
from tests._drain import drain_deadline_s
from tests.integration._helpers import build_postgres_deps, seed_run_upstream_chain_postgres

_NOW = datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _drain_run_projections(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_run_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())


@pytest.mark.integration
async def test_start_run_lands_pinned_calibration_ids_on_projection(
    db_pool: asyncpg.Pool,
) -> None:
    """Happy path: start_run with two pins lands them on the
    projection's uuid[] column (sorted lexicographically per the
    decider's pre-emit sort)."""
    plan_id, subject_id = await seed_run_upstream_chain_postgres(
        db_pool, now=_NOW, method_schema=None, plan_defaults=None
    )
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4(), uuid4()])

    pin_a = UUID("01900000-0000-7000-8000-00000000ca01")
    pin_b = UUID("01900000-0000-7000-8000-00000000ca02")
    run_id = await start_run.bind(deps)(
        StartRun(
            name="Pinned run",
            plan_id=plan_id,
            subject_id=subject_id,
            pinned_calibration_ids=frozenset({pin_b, pin_a}),  # scrambled
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Event payload carries the sorted list.
    events, _v = await deps.event_store.load("Run", run_id)
    assert events[0].payload["pinned_calibration_ids"] == sorted([str(pin_a), str(pin_b)])

    # Drain projection; column lands the uuid[] array.
    await _drain_run_projections(db_pool)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT pinned_calibration_ids FROM proj_run_summary WHERE run_id = $1",
            run_id,
        )
    assert row is not None
    # asyncpg returns uuid[] as list[UUID]; ordering follows insert.
    pins_on_row = list(row["pinned_calibration_ids"])
    assert sorted(pins_on_row) == sorted([pin_a, pin_b])


@pytest.mark.integration
async def test_start_run_default_pins_land_empty_array(
    db_pool: asyncpg.Pool,
) -> None:
    """Omitted pinned_calibration_ids on the command land an empty uuid[] on
    the projection (forward-compat-clean default)."""
    plan_id, subject_id = await seed_run_upstream_chain_postgres(
        db_pool, now=_NOW, method_schema=None, plan_defaults=None
    )
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4(), uuid4()])

    run_id = await start_run.bind(deps)(
        StartRun(
            name="No-pin run",
            plan_id=plan_id,
            subject_id=subject_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain_run_projections(db_pool)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT pinned_calibration_ids FROM proj_run_summary WHERE run_id = $1",
            run_id,
        )
    assert row is not None
    assert list(row["pinned_calibration_ids"]) == []


@pytest.mark.integration
async def test_pinned_calibration_ids_gin_index_supports_contains_membership_lookup(
    db_pool: asyncpg.Pool,
) -> None:
    """The GIN index on pinned_calibration_ids powers the future 12c
    Dataset back-fill + agent-subscriber replay query via the
    array-contains operator: `WHERE pinned_calibration_ids @> ARRAY[$X]::uuid[]`.

    Pinning `@>` (not `= ANY(...)`): `= ANY` is rewritten internally
    and does NOT probe the GIN index on uuid[]; `@>` does. The query
    path we ship must be the GIN-friendly one or the index is
    decorative.

    Lands two Runs with overlapping + non-overlapping pin sets, then
    queries by one pin and asserts only the matching Runs come back."""
    plan_id, subject_id = await seed_run_upstream_chain_postgres(
        db_pool, now=_NOW, method_schema=None, plan_defaults=None
    )

    pin_shared = UUID("01900000-0000-7000-8000-00000000ca10")
    pin_only_a = UUID("01900000-0000-7000-8000-00000000ca11")
    pin_only_b = UUID("01900000-0000-7000-8000-00000000ca12")

    # Run A: pins {shared, only_a}
    deps_a = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4(), uuid4()])
    run_a_id = await start_run.bind(deps_a)(
        StartRun(
            name="Run A",
            plan_id=plan_id,
            subject_id=subject_id,
            pinned_calibration_ids=frozenset({pin_shared, pin_only_a}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Run B: pins {shared, only_b}
    deps_b = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4(), uuid4()])
    run_b_id = await start_run.bind(deps_b)(
        StartRun(
            name="Run B",
            plan_id=plan_id,
            subject_id=subject_id,
            pinned_calibration_ids=frozenset({pin_shared, pin_only_b}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain_run_projections(db_pool)

    async with db_pool.acquire() as conn:
        # Query for the shared pin: both Runs match.
        shared_rows = await conn.fetch(
            "SELECT run_id FROM proj_run_summary WHERE pinned_calibration_ids @> ARRAY[$1]::uuid[]",
            pin_shared,
        )
        # Query for pin_only_a: only Run A matches.
        a_only_rows = await conn.fetch(
            "SELECT run_id FROM proj_run_summary WHERE pinned_calibration_ids @> ARRAY[$1]::uuid[]",
            pin_only_a,
        )

    assert {row["run_id"] for row in shared_rows} == {run_a_id, run_b_id}
    assert {row["run_id"] for row in a_only_rows} == {run_a_id}
