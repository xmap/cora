"""End-to-end integration test: 6g-c parameter flow against real Postgres.

Exercises the cross-aggregate parameter resolution at start_run:
  - Plan.default_parameters (set via 6g-b update_plan_default_parameters)
  - merged with command.override_parameters (RFC 7396 via merge_patch)
  - validated against Method.parameters_schema (set via 6g-a)
  - persisted in RunStarted payload (override_parameters + effective_parameters + trigger_source)
  - folded into Run state on load
  - projection's `override_parameters_present` column flips TRUE
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.run._projections import register_run_projections
from cora.run.aggregates.run import InvalidRunParametersError, load_run
from cora.run.features import start_run
from cora.run.features.start_run import StartRun
from tests._drain import drain_deadline_s
from tests.integration._helpers import build_postgres_deps, seed_run_upstream_chain_postgres

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_DRAFT = "https://json-schema.org/draft/2020-12/schema"


async def _drain_run_projections(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_run_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())


def _energy_schema() -> dict[str, Any]:
    return {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {
            "energy": {
                "type": "number",
                "minimum": 5,
                "maximum": 50,
                "unit": {"system": "udunits", "code": "keV"},
            },
            "exposure": {
                "type": "integer",
                "minimum": 1,
                "unit": {"system": "udunits", "code": "ms"},
            },
        },
    }


@pytest.mark.integration
async def test_start_run_merges_defaults_and_overrides_into_effective_parameters(
    db_pool: asyncpg.Pool,
) -> None:
    """Plan defaults + Run overrides merge per RFC 7396; resolved set
    persists in RunStarted and folds onto Run state."""
    plan_id, subject_id = await seed_run_upstream_chain_postgres(
        db_pool,
        now=_NOW,
        method_schema=_energy_schema(),
        plan_defaults={"energy": 12.0, "exposure": 100},
    )
    # run id + RunStarted event id
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4(), uuid4()])

    run_id = await start_run.bind(deps)(
        StartRun(
            name="Run-with-overrides",
            plan_id=plan_id,
            subject_id=subject_id,
            override_parameters={"exposure": 250},
            trigger_source="operator:opid:5",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    loaded = await load_run(deps.event_store, run_id)
    assert loaded is not None
    assert loaded.override_parameters == {"exposure": 250}
    # Defaults' energy preserved; override's exposure wins.
    assert loaded.effective_parameters == {"energy": 12.0, "exposure": 250}
    assert loaded.trigger_source == "operator:opid:5"

    await _drain_run_projections(db_pool)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT override_parameters_present FROM proj_run_summary WHERE run_id = $1",
            run_id,
        )
    assert row is not None
    assert row["override_parameters_present"] is True


@pytest.mark.integration
async def test_start_run_with_no_overrides_uses_plan_defaults(
    db_pool: asyncpg.Pool,
) -> None:
    """Operator omits overrides -> effective_parameters == Plan defaults."""
    plan_id, subject_id = await seed_run_upstream_chain_postgres(
        db_pool,
        now=_NOW,
        method_schema=_energy_schema(),
        plan_defaults={"energy": 12.0, "exposure": 100},
    )
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4(), uuid4()])

    run_id = await start_run.bind(deps)(
        StartRun(name="Run-defaults-only", plan_id=plan_id, subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    loaded = await load_run(deps.event_store, run_id)
    assert loaded is not None
    assert loaded.override_parameters == {}
    assert loaded.effective_parameters == {"energy": 12.0, "exposure": 100}

    await _drain_run_projections(db_pool)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT override_parameters_present FROM proj_run_summary WHERE run_id = $1",
            run_id,
        )
    assert row is not None
    # Defaults straight, no overrides supplied -> projection FALSE.
    assert row["override_parameters_present"] is False


@pytest.mark.integration
async def test_start_run_rejects_overrides_violating_method_schema(
    db_pool: asyncpg.Pool,
) -> None:
    """Override pushes effective_parameters out of schema bounds ->
    InvalidRunParametersError; no event appended."""
    plan_id, subject_id = await seed_run_upstream_chain_postgres(
        db_pool,
        now=_NOW,
        method_schema=_energy_schema(),
        plan_defaults={"energy": 12.0},
    )
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4(), uuid4()])

    with pytest.raises(InvalidRunParametersError):
        await start_run.bind(deps)(
            StartRun(
                name="Run-bad",
                plan_id=plan_id,
                subject_id=subject_id,
                override_parameters={"energy": 1.0},
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# NOTE: an old `test_start_run_permissive_when_method_has_no_schema` test
# lived here pre-audit. It was replaced by the strict-mode pair
# (test_start_run_strict_when_method_has_no_schema +
# test_start_run_accepts_no_schema_when_no_overrides_and_no_defaults)
# in the audit reversal commit. See [[project_run_parameters_design]]
# §audit-correction.
