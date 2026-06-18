"""End-to-end integration test: update_method_parameters_schema against real Postgres.

Round-trips the event + projection column:
  - Define method
  - Update parameters_schema
  - Load via fold-on-read returns the schema
  - Projection's parameters_schema_present column flips TRUE
  - Clear the schema (None payload)
  - Projection flips back to FALSE

Mirrors `test_update_family_settings_schema_handler_postgres.py`.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.recipe._projections import register_recipe_projections
from cora.recipe.aggregates.method import ExecutionPattern, load_method
from cora.recipe.features import define_method, update_method_parameters_schema
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.update_method_parameters_schema import (
    UpdateMethodParametersSchema,
)
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0d574")
_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _build_deps(db_pool: asyncpg.Pool, ids: list[UUID]) -> Kernel:
    return build_postgres_deps(db_pool, now=_NOW, ids=ids)


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_recipe_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


def _example_schema() -> dict[str, Any]:
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
            "filter_material": {"type": "string", "enum": ["Cu", "Al", "Mo"]},
        },
        "required": ["energy"],
    }


@pytest.mark.integration
async def test_update_method_parameters_schema_round_trips_through_event_store_and_projection(
    db_pool: asyncpg.Pool,
) -> None:
    """Full end-to-end: define, set schema, fold-on-read returns the
    schema, projection parameters_schema_present = TRUE."""
    method_id = uuid4()
    deps = _build_deps(db_pool, [method_id, uuid4(), uuid4()])  # method_id + 2 event_ids

    await seed_capability_postgres(deps.event_store, _CAPABILITY_ID)
    await define_method.bind(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            capability_id=_CAPABILITY_ID,
            name="Phase-Contrast Micro-CT",
            needed_family_ids=frozenset(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    schema = _example_schema()
    await update_method_parameters_schema.bind(deps)(
        UpdateMethodParametersSchema(method_id=method_id, parameters_schema=schema),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    loaded = await load_method(deps.event_store, method_id)
    assert loaded is not None
    assert loaded.parameters_schema == schema

    await _drain(db_pool)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT parameters_schema_present FROM proj_recipe_method_summary WHERE method_id = $1",
            method_id,
        )
    assert row is not None
    assert row["parameters_schema_present"] is True


@pytest.mark.integration
async def test_clearing_schema_flips_projection_present_back_to_false(
    db_pool: asyncpg.Pool,
) -> None:
    """Operator removes a previously-declared schema; projection flips back to FALSE."""
    method_id = uuid4()
    deps = _build_deps(
        db_pool,
        # method_id + 1 define + 2 schema-update event_ids
        [method_id, uuid4(), uuid4(), uuid4()],
    )

    await seed_capability_postgres(deps.event_store, _CAPABILITY_ID)
    await define_method.bind(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            capability_id=_CAPABILITY_ID,
            name="Phase-Contrast Micro-CT",
            needed_family_ids=frozenset(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await update_method_parameters_schema.bind(deps)(
        UpdateMethodParametersSchema(method_id=method_id, parameters_schema=_example_schema()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await update_method_parameters_schema.bind(deps)(
        UpdateMethodParametersSchema(method_id=method_id, parameters_schema=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    loaded = await load_method(deps.event_store, method_id)
    assert loaded is not None
    assert loaded.parameters_schema is None

    await _drain(db_pool)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT parameters_schema_present FROM proj_recipe_method_summary WHERE method_id = $1",
            method_id,
        )
    assert row is not None
    assert row["parameters_schema_present"] is False


@pytest.mark.integration
async def test_no_op_on_unchanged_schema_does_not_emit_event(
    db_pool: asyncpg.Pool,
) -> None:
    """Re-submitting the same schema must NOT emit a new event."""
    method_id = uuid4()
    deps = _build_deps(db_pool, [method_id, uuid4(), uuid4()])

    await seed_capability_postgres(deps.event_store, _CAPABILITY_ID)
    await define_method.bind(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            capability_id=_CAPABILITY_ID,
            name="Phase-Contrast Micro-CT",
            needed_family_ids=frozenset(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    schema = _example_schema()
    await update_method_parameters_schema.bind(deps)(
        UpdateMethodParametersSchema(method_id=method_id, parameters_schema=schema),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    _, version_after_first = await deps.event_store.load("Method", method_id)

    await update_method_parameters_schema.bind(deps)(
        UpdateMethodParametersSchema(method_id=method_id, parameters_schema=schema),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    _, version_after_second = await deps.event_store.load("Method", method_id)
    assert version_after_second == version_after_first, (
        "Re-submitting unchanged schema should not append a new event"
    )
