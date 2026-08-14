"""Postgres integration test for `rebuild_open_captures`
(cora.api._run_witness).

Proves the restart-rebuild query composes correctly end-to-end against
real Postgres: the `conduct_mode` list_runs filter, the
`proj_run_summary` projection, `load_run`'s stream read, and the
`Identifier(scheme="capture-code", ...)` extraction. No unit test (all
fake handlers) can prove this chain.

Reuses the shared 2-BM tomography fixture, the same one
`test_record_witnessed_run_handler_postgres.py` exercises.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.api._run_witness import rebuild_open_captures
from cora.equipment._projections import register_equipment_projections
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.recipe._projections import register_recipe_projections
from cora.run._projections import register_run_projections
from cora.run.features.list_runs import bind as bind_list_runs
from cora.run.features.record_witnessed_run import RecordWitnessedRun, bind
from cora.shared.identity import MonitorSourceId
from tests._drain import drain_deadline_s
from tests.integration._helpers import build_postgres_deps, make_pg_profile_store
from tests.integration.scenarios._facility_fixture import operator_for
from tests.integration.scenarios._tomography_fixture import (
    RecipeSpec,
    TomographyAssetIds,
    define_recipe_ladder,
    install_and_activate_tomography_assets,
    recipe_ladder_id_prefix,
    tomography_install_id_prefix,
)

_NOW = datetime(2026, 8, 14, 4, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000004caa01")

# Scenario tag: 4caa (RunWitness restart-rebuild round-trip).
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-00000004caa2")

_CAP_ROTARY_STAGE_ID = family_stream_id(FamilyName("RotaryStage"))
_CAP_LINEAR_STAGE_ID = family_stream_id(FamilyName("LinearStage"))
_CAP_CAMERA_ID = family_stream_id(FamilyName("Camera"))
_CAP_SCINTILLATOR_ID = family_stream_id(FamilyName("Scintillator"))

_ASSET_ROTARY_ID = UUID("01900000-0000-7000-8000-00000004cab1")
_ASSET_LINEAR_X_ID = UUID("01900000-0000-7000-8000-00000004cab2")
_ASSET_CAMERA_ID = UUID("01900000-0000-7000-8000-00000004cab3")
_ASSET_SCINTILLATOR_ID = UUID("01900000-0000-7000-8000-00000004cab4")

_METHOD_ID = UUID("01900000-0000-7000-8000-00000004cac1")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-00000004cac2")
_PRACTICE_ID = UUID("01900000-0000-7000-8000-00000004cac3")
_PLAN_ID = UUID("01900000-0000-7000-8000-00000004cac4")

_TOMO_ASSETS = TomographyAssetIds(
    unit_id=_2BM_UNIT_ID,
    rotary_cap_id=_CAP_ROTARY_STAGE_ID,
    linear_x_cap_id=_CAP_LINEAR_STAGE_ID,
    camera_cap_id=_CAP_CAMERA_ID,
    scintillator_cap_id=_CAP_SCINTILLATOR_ID,
    rotary_id=_ASSET_ROTARY_ID,
    linear_x_id=_ASSET_LINEAR_X_ID,
    camera_id=_ASSET_CAMERA_ID,
    scintillator_id=_ASSET_SCINTILLATOR_ID,
)

_RECIPE = RecipeSpec(
    capability_id=_CAPABILITY_ID,
    capability_code="cora.capability.tomography",
    capability_name="Tomography",
    method_id=_METHOD_ID,
    method_name="tomography",
    needed_family_ids=frozenset(
        {_CAP_ROTARY_STAGE_ID, _CAP_LINEAR_STAGE_ID, _CAP_CAMERA_ID, _CAP_SCINTILLATOR_ID}
    ),
    practice_id=_PRACTICE_ID,
    practice_name="2BM_tomography_practice_witness_rebuild",
    site_id=_2BM_UNIT_ID,
    plan_id=_PLAN_ID,
    plan_name="2BM_witnessed_tomography_plan_witness_rebuild",
    plan_asset_ids=frozenset(
        {_ASSET_ROTARY_ID, _ASSET_LINEAR_X_ID, _ASSET_CAMERA_ID, _ASSET_SCINTILLATOR_ID}
    ),
)


def _id_queue() -> list[UUID]:
    e = uuid4
    return [
        *tomography_install_id_prefix(asset_ids=_TOMO_ASSETS),
        *recipe_ladder_id_prefix(spec=_RECIPE),
        *[e() for _ in range(20)],
    ]


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_equipment_projections(registry)
    register_recipe_projections(registry)
    register_run_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())


@pytest.mark.integration
async def test_rebuild_open_captures_seeds_dedup_map_from_a_real_open_witnessed_run(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())
    await install_and_activate_tomography_assets(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        asset_ids=_TOMO_ASSETS,
    )
    await define_recipe_ladder(
        deps,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        spec=_RECIPE,
    )

    handler = bind(deps)
    run_id = await handler(
        RecordWitnessedRun(
            name="2BM witnessed capture",
            plan_id=_PLAN_ID,
            capture_code="2bmb-tomoscan",
            monitor_source_id=MonitorSourceId(UUID("01900000-0000-7000-8000-000063617001")),
            trigger="Monitor",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    result = await rebuild_open_captures(deps, list_runs=bind_list_runs(deps))

    assert result == {"2bmb-tomoscan": run_id}
