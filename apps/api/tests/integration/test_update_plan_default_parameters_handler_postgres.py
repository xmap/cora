"""End-to-end integration test: update_plan_default_parameters against real Postgres.

Round-trips the event + projection column through real PG, including
the cross-aggregate Method load that validates default_parameters
against parameters_schema.

Mirrors `test_update_method_parameters_schema_handler_postgres.py`
shape but exercises the cross-aggregate validation path.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.recipe._projections import register_recipe_projections
from cora.recipe.aggregates.method.events import MethodDefined, MethodParametersSchemaUpdated
from cora.recipe.aggregates.method.events import event_type_name as method_event_type_name
from cora.recipe.aggregates.method.events import to_payload as method_to_payload
from cora.recipe.aggregates.plan import (
    InvalidPlanDefaultParametersError,
    load_plan,
)
from cora.recipe.aggregates.plan.events import (
    PlanDefined,
    event_type_name,
    to_payload,
)
from cora.recipe.features import update_plan_default_parameters
from cora.recipe.features.update_plan_default_parameters import (
    UpdatePlanDefaultParameters,
)
from tests._drain import drain_deadline_s
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _build_deps(db_pool: asyncpg.Pool, ids: list[UUID]) -> Kernel:
    return build_postgres_deps(db_pool, now=_NOW, ids=ids)


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_recipe_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())


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
            "exposure": {
                "type": "integer",
                "minimum": 1,
                "unit": {"system": "udunits", "code": "ms"},
            },
        },
    }


async def _seed_method_with_schema(
    deps: Kernel, method_id: UUID, schema: dict[str, Any] | None
) -> None:
    """Seed a Method directly into the event store with optional
    parameters_schema (avoids the upstream BC chain for integration
    tests focused on the Plan-side update slice)."""
    define = MethodDefined(
        method_id=method_id,
        name="Phase-Contrast Micro-CT",
        needed_family_ids=(),
        occurred_at=_NOW,
    )
    events = [
        to_new_event(
            event_type=method_event_type_name(define),
            payload=method_to_payload(define),
            occurred_at=_NOW,
            event_id=uuid4(),
            command_name="DefineMethod",
            correlation_id=_CORRELATION_ID,
            principal_id=_PRINCIPAL_ID,
        )
    ]
    if schema is not None:
        s = MethodParametersSchemaUpdated(
            method_id=method_id, parameters_schema=schema, occurred_at=_NOW
        )
        events.append(
            to_new_event(
                event_type=method_event_type_name(s),
                payload=method_to_payload(s),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="UpdateMethodParametersSchema",
                correlation_id=_CORRELATION_ID,
                principal_id=_PRINCIPAL_ID,
            )
        )
    await deps.event_store.append(
        stream_type="Method", stream_id=method_id, expected_version=0, events=events
    )


async def _seed_plan(deps: Kernel, plan_id: UUID, method_id: UUID) -> None:
    """Seed a Plan referencing the Method directly."""
    practice_id = uuid4()
    asset_id = uuid4()
    event = PlanDefined(
        plan_id=plan_id,
        name="32-ID FlyScan",
        practice_id=practice_id,
        asset_ids=(asset_id,),
        method_id=method_id,
        method_needed_family_ids_snapshot=(),
        asset_families_snapshot={asset_id: ()},
        occurred_at=_NOW,
    )
    await deps.event_store.append(
        stream_type="Plan",
        stream_id=plan_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="DefinePlan",
                correlation_id=_CORRELATION_ID,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )


@pytest.mark.integration
async def test_update_plan_default_parameters_round_trips_event_and_projection(
    db_pool: asyncpg.Pool,
) -> None:
    """Full end-to-end: seed Method with schema, seed Plan, update
    defaults, fold-on-read returns merged dict, projection
    default_parameters_present = TRUE."""
    plan_id = uuid4()
    method_id = uuid4()
    deps = _build_deps(db_pool, [uuid4()])  # one event id for the defaults-update event

    await _seed_method_with_schema(deps, method_id, _example_schema())
    await _seed_plan(deps, plan_id, method_id)

    await update_plan_default_parameters.bind(deps)(
        UpdatePlanDefaultParameters(plan_id=plan_id, default_parameters_patch={"energy": 12.0}),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    loaded = await load_plan(deps.event_store, plan_id)
    assert loaded is not None
    assert loaded.default_parameters == {"energy": 12.0}

    await _drain(db_pool)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT default_parameters_present FROM proj_recipe_plan_summary WHERE plan_id = $1",
            plan_id,
        )
    assert row is not None
    assert row["default_parameters_present"] is True


@pytest.mark.integration
async def test_clearing_all_keys_flips_projection_present_back_to_false(
    db_pool: asyncpg.Pool,
) -> None:
    """RFC 7396 null-deletes-key sequence: set then delete leaves
    empty dict; projection flips back to FALSE."""
    plan_id = uuid4()
    method_id = uuid4()
    deps = _build_deps(db_pool, [uuid4(), uuid4()])  # two defaults-update event ids

    await _seed_method_with_schema(deps, method_id, _example_schema())
    await _seed_plan(deps, plan_id, method_id)

    await update_plan_default_parameters.bind(deps)(
        UpdatePlanDefaultParameters(plan_id=plan_id, default_parameters_patch={"energy": 12.0}),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await update_plan_default_parameters.bind(deps)(
        UpdatePlanDefaultParameters(plan_id=plan_id, default_parameters_patch={"energy": None}),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    loaded = await load_plan(deps.event_store, plan_id)
    assert loaded is not None
    assert loaded.default_parameters == {}

    await _drain(db_pool)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT default_parameters_present FROM proj_recipe_plan_summary WHERE plan_id = $1",
            plan_id,
        )
    assert row is not None
    assert row["default_parameters_present"] is False


@pytest.mark.integration
async def test_validation_rejects_post_merge_violation(
    db_pool: asyncpg.Pool,
) -> None:
    """Post-merge result violates Method.parameters_schema -> raise.
    No event appended; stream version unchanged."""
    plan_id = uuid4()
    method_id = uuid4()
    deps = _build_deps(db_pool, [uuid4()])  # event id won't be consumed

    await _seed_method_with_schema(deps, method_id, _example_schema())
    await _seed_plan(deps, plan_id, method_id)

    with pytest.raises(InvalidPlanDefaultParametersError):
        await update_plan_default_parameters.bind(deps)(
            UpdatePlanDefaultParameters(plan_id=plan_id, default_parameters_patch={"energy": 1.0}),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    _, version = await deps.event_store.load("Plan", plan_id)
    assert version == 1  # define only; no defaults-update appended


@pytest.mark.integration
async def test_no_op_on_unchanged_does_not_emit(
    db_pool: asyncpg.Pool,
) -> None:
    """Re-submitting an empty patch on existing defaults: no event."""
    plan_id = uuid4()
    method_id = uuid4()
    deps = _build_deps(db_pool, [uuid4()])

    await _seed_method_with_schema(deps, method_id, _example_schema())
    await _seed_plan(deps, plan_id, method_id)

    await update_plan_default_parameters.bind(deps)(
        UpdatePlanDefaultParameters(plan_id=plan_id, default_parameters_patch={"energy": 12.0}),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    _, version_after_first = await deps.event_store.load("Plan", plan_id)

    await update_plan_default_parameters.bind(deps)(
        UpdatePlanDefaultParameters(plan_id=plan_id, default_parameters_patch={"energy": 12.0}),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    _, version_after_second = await deps.event_store.load("Plan", plan_id)
    assert version_after_second == version_after_first
