"""Postgres integration test for the `record_witnessed_run` handler.

Round-trips the witnessed genesis through a real event store: authorize,
load the Plan -> Practice -> Method -> Asset chain, decide, append, and
reload. Confirms the new nested `safety_envelope_verdict` VO survives the jsonb
round-trip and that `conduct_mode` lands as `Witnessed`.

Reuses the shared 2-BM tomography fixture (`_tomography_fixture.py`)
already exercised by the RunInitiator tick scenario, minus the
beamtime / Subject setup this genesis does not need
(`subject_id=None`, the common case for a watched capture).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.run.aggregates.run import (
    ConductMode,
    RunMonitorTriggerNotPermittedError,
    fold,
    from_stored,
)
from cora.run.features.record_witnessed_run import RecordWitnessedRun, bind
from cora.shared.identity import MonitorSourceId
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

_NOW = datetime(2026, 8, 14, 3, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000004c9601")

# Scenario tag: 4c96 (record_witnessed_run handler round-trip).
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-00000004c9a1")

_CAP_ROTARY_STAGE_ID = family_stream_id(FamilyName("RotaryStage"))
_CAP_LINEAR_STAGE_ID = family_stream_id(FamilyName("LinearStage"))
_CAP_CAMERA_ID = family_stream_id(FamilyName("Camera"))
_CAP_SCINTILLATOR_ID = family_stream_id(FamilyName("Scintillator"))

_ASSET_ROTARY_ID = UUID("01900000-0000-7000-8000-00000004c9b1")
_ASSET_LINEAR_X_ID = UUID("01900000-0000-7000-8000-00000004c9b2")
_ASSET_CAMERA_ID = UUID("01900000-0000-7000-8000-00000004c9b3")
_ASSET_SCINTILLATOR_ID = UUID("01900000-0000-7000-8000-00000004c9b4")

_METHOD_ID = UUID("01900000-0000-7000-8000-00000004c9c1")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-00000004c9c2")
_PRACTICE_ID = UUID("01900000-0000-7000-8000-00000004c9c3")
_PLAN_ID = UUID("01900000-0000-7000-8000-00000004c9c4")

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
    practice_name="2BM_tomography_practice",
    site_id=_2BM_UNIT_ID,
    plan_id=_PLAN_ID,
    plan_name="2BM_witnessed_tomography_plan",
    plan_asset_ids=frozenset(
        {_ASSET_ROTARY_ID, _ASSET_LINEAR_X_ID, _ASSET_CAMERA_ID, _ASSET_SCINTILLATOR_ID}
    ),
)


def _id_queue() -> list[UUID]:
    e = uuid4
    return [
        *tomography_install_id_prefix(asset_ids=_TOMO_ASSETS),
        *recipe_ladder_id_prefix(spec=_RECIPE),
        *[e() for _ in range(20)],  # headroom: record_witnessed_run's own event ids
    ]


@pytest.mark.integration
async def test_record_witnessed_run_persists_witnessed_run_with_safety_envelope_verdict(
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

    events, stream_version = await deps.event_store.load("Run", run_id)
    assert stream_version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "RunStarted"
    assert stored.payload["conduct_mode"] == "Witnessed"
    assert stored.payload["subject_id"] is None
    assert stored.payload["safety_envelope_verdict"] == {
        "enclosure_permitted": True,
        "beam_available": True,
    }
    assert stored.payload["external_refs"] == [{"scheme": "capture-code", "value": "2bmb-tomoscan"}]

    # Reload through from_stored/fold to confirm the nested VO
    # reconstructs correctly, not just that raw jsonb round-trips.
    state = fold([from_stored(e) for e in events])
    assert state is not None
    assert state.conduct_mode is ConductMode.WITNESSED


@pytest.mark.integration
async def test_record_witnessed_run_rejects_non_monitor_trigger(db_pool: asyncpg.Pool) -> None:
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
    with pytest.raises(RunMonitorTriggerNotPermittedError):
        await handler(
            RecordWitnessedRun(
                name="2BM witnessed capture",
                plan_id=_PLAN_ID,
                capture_code="2bmb-tomoscan",
                monitor_source_id=MonitorSourceId(UUID("01900000-0000-7000-8000-000063617001")),
                trigger="Operator",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
