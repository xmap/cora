"""End-to-end integration test for the `adjust_run` slice.

Exercises the cross-aggregate adjust flow against real Postgres:
  - seed upstream chain (Family + Asset + Method (with schema) +
    Practice + Plan + Subject + RunStarted)
  - adjust_run with valid patch -> RunAdjusted persisted; Run state
    folds with merged effective_parameters + last_adjusted_at +
    adjustment_count=1
  - second adjust_run with a different patch -> adjustment_count=2 +
    cumulative effective_parameters
  - adjust_run with decided_by_decision_id -> link flows through to
    event payload (no Decision aggregate seeded; eventual-consistency
    proven)
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.features import (
    add_asset_family,
    define_family,
    register_asset,
)
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.register_asset import RegisterAsset
from cora.infrastructure.kernel import Kernel
from cora.recipe.aggregates.method import ExecutionPattern
from cora.recipe.features import (
    define_method,
    define_plan,
    define_practice,
    update_method_parameters_schema,
    update_plan_default_parameters,
)
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_practice import DefinePractice
from cora.recipe.features.update_method_parameters_schema import (
    UpdateMethodParametersSchema,
)
from cora.recipe.features.update_plan_default_parameters import (
    UpdatePlanDefaultParameters,
)
from cora.run.aggregates.run import load_run
from cora.run.features import adjust_run, start_run
from cora.run.features.adjust_run import AdjustRun
from cora.run.features.start_run import StartRun
from cora.subject.features import mount_subject, register_subject
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.register_subject import RegisterSubject
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres
from tests.unit.subject._helpers import seed_active_asset

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0d101")
_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _build_deps(db_pool: asyncpg.Pool, ids: list[UUID]) -> Kernel:
    return build_postgres_deps(db_pool, now=_NOW, ids=ids)


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


async def _seed_full_chain(
    db_pool: asyncpg.Pool,
    *,
    method_schema: dict[str, Any] | None,
    plan_defaults: dict[str, Any] | None,
) -> tuple[UUID, UUID]:
    """Seed Family + Method (with schema) + Practice + Asset +
    Plan (with defaults) + Subject (Mounted). Returns (plan_id, subject_id)."""
    ids = [uuid4() for _ in range(40)]
    deps = _build_deps(db_pool, ids)

    cap_id = await define_family.bind(deps)(
        DefineFamily(name="FlyMotion", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await seed_capability_postgres(deps.event_store, _CAPABILITY_ID)
    method_id = await define_method.bind(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            capability_id=_CAPABILITY_ID,
            name="Test Method",
            needed_family_ids=frozenset({cap_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    if method_schema is not None:
        await update_method_parameters_schema.bind(deps)(
            UpdateMethodParametersSchema(method_id=method_id, parameters_schema=method_schema),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    practice_id = await define_practice.bind(deps)(
        DefinePractice(name="Test Practice", method_id=method_id, site_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    asset_id = await register_asset.bind(deps)(
        RegisterAsset(name="TestAsset", tier=AssetTier.UNIT, parent_id=None, facility_code="cora"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=cap_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    plan_id = await define_plan.bind(deps)(
        DefinePlan(
            name="32-ID FlyScan",
            practice_id=practice_id,
            asset_ids=frozenset({asset_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    if plan_defaults:
        await update_plan_default_parameters.bind(deps)(
            UpdatePlanDefaultParameters(plan_id=plan_id, default_parameters_patch=plan_defaults),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    subject_id = await register_subject.bind(deps)(
        RegisterSubject(name="PorousCeramicSample-A"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    mount_asset_id = await seed_active_asset(
        deps.event_store, now=_NOW, correlation_id=_CORRELATION_ID
    )
    await mount_subject.bind(deps)(
        MountSubject(subject_id=subject_id, asset_id=mount_asset_id, reason="test"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return plan_id, subject_id


@pytest.mark.integration
async def test_adjust_run_persists_run_adjusted_and_folds_into_state(
    db_pool: asyncpg.Pool,
) -> None:
    """End-to-end happy path: seed full chain → start_run → adjust_run
    once → RunAdjusted on stream + Run state reflects merged effective."""
    plan_id, subject_id = await _seed_full_chain(
        db_pool,
        method_schema=_energy_schema(),
        plan_defaults={"energy": 10.0, "exposure": 100},
    )
    deps = _build_deps(db_pool, [uuid4(), uuid4(), uuid4()])

    run_id = await start_run.bind(deps)(
        StartRun(name="Run-X", plan_id=plan_id, subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await adjust_run.bind(deps)(
        AdjustRun(
            run_id=run_id,
            parameters_patch={"energy": 12.0},
            reason="re-center on ROI",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    loaded = await load_run(deps.event_store, run_id)
    assert loaded is not None
    assert loaded.effective_parameters == {"energy": 12.0, "exposure": 100}
    assert loaded.adjustment_count == 1
    assert loaded.last_adjusted_at == _NOW
    # override_parameters is untouched by adjust (immutable post-start
    # snapshot of "what the operator originally asked for").
    assert loaded.override_parameters == {}


@pytest.mark.integration
async def test_two_consecutive_adjust_run_increments_count_cumulatively(
    db_pool: asyncpg.Pool,
) -> None:
    """Two consecutive adjustments → adjustment_count=2; effective
    reflects cumulative patches (RFC 7396 merge each step)."""
    plan_id, subject_id = await _seed_full_chain(
        db_pool,
        method_schema=_energy_schema(),
        plan_defaults={"energy": 10.0},
    )
    deps = _build_deps(db_pool, [uuid4() for _ in range(4)])

    run_id = await start_run.bind(deps)(
        StartRun(name="Run-Y", plan_id=plan_id, subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await adjust_run.bind(deps)(
        AdjustRun(
            run_id=run_id,
            parameters_patch={"energy": 12.0},
            reason="first",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await adjust_run.bind(deps)(
        AdjustRun(
            run_id=run_id,
            parameters_patch={"exposure": 200},
            reason="second",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    loaded = await load_run(deps.event_store, run_id)
    assert loaded is not None
    assert loaded.adjustment_count == 2
    assert loaded.effective_parameters == {"energy": 12.0, "exposure": 200}

    # Per-event snapshot pin: each RunAdjusted carries its own
    # effective_parameters snapshot (not overwriting). The first event
    # reflects the post-first-patch state; the second reflects the
    # cumulative merge. Replay never needs to fold prior RunAdjusted
    # events to surface the current value.
    stored, _ = await deps.event_store.load("Run", run_id)
    types = [s.event_type for s in stored]
    assert types == ["RunStarted", "RunAdjusted", "RunAdjusted"]
    assert stored[1].payload["effective_parameters"] == {"energy": 12.0}
    assert stored[2].payload["effective_parameters"] == {
        "energy": 12.0,
        "exposure": 200,
    }


@pytest.mark.integration
async def test_adjust_run_with_decision_id_persists_link_on_payload(
    db_pool: asyncpg.Pool,
) -> None:
    """adjust_run with decided_by_decision_id → event payload carries
    the link verbatim. NO Decision aggregate is seeded (eventual-
    consistency stance proven against real PG)."""
    plan_id, subject_id = await _seed_full_chain(
        db_pool,
        method_schema=_energy_schema(),
        plan_defaults={"energy": 10.0},
    )
    deps = _build_deps(db_pool, [uuid4(), uuid4(), uuid4()])

    decision_id = uuid4()
    run_id = await start_run.bind(deps)(
        StartRun(name="Run-Z", plan_id=plan_id, subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await adjust_run.bind(deps)(
        AdjustRun(
            run_id=run_id,
            parameters_patch={"energy": 13.0},
            reason="agent steering iteration",
            decided_by_decision_id=decision_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    stored, _ = await deps.event_store.load("Run", run_id)
    types = [s.event_type for s in stored]
    assert types == ["RunStarted", "RunAdjusted"]
    adjusted_payload = stored[1].payload
    assert adjusted_payload["decided_by_decision_id"] == str(decision_id)
    assert adjusted_payload["parameters_patch"] == {"energy": 13.0}
    assert adjusted_payload["effective_parameters"] == {"energy": 13.0}
    assert adjusted_payload["reason"] == "agent steering iteration"
