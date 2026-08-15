"""Postgres integration test for the `record_witnessed_run_outcome` handler.

Seeds a real Witnessed Run via `record_witnessed_run` (the genesis, same
fixture as `test_record_witnessed_run_handler_postgres.py`), then closes
it through the new handler and confirms the terminal event round-trips
through a real event store, `observed_at` included.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.run.features.record_witnessed_run import RecordWitnessedRun
from cora.run.features.record_witnessed_run import bind as bind_genesis
from cora.run.features.record_witnessed_run_outcome import RecordWitnessedRunOutcome
from cora.run.features.record_witnessed_run_outcome import bind as bind_outcome
from cora.shared.capture_phase import CapturePhase
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

_NOW = datetime(2026, 8, 15, 3, 0, 0, tzinfo=UTC)
_OBSERVED_AT = datetime(2026, 8, 15, 2, 58, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000004ca601")
_MONITOR_SOURCE_ID = MonitorSourceId(UUID("01900000-0000-7000-8000-000072756e01"))

# Scenario tag: 4ca6 (record_witnessed_run_outcome handler round-trip).
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-00000004caa1")

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
    practice_name="2BM_tomography_practice",
    site_id=_2BM_UNIT_ID,
    plan_id=_PLAN_ID,
    plan_name="2BM_witnessed_outcome_tomography_plan",
    plan_asset_ids=frozenset(
        {_ASSET_ROTARY_ID, _ASSET_LINEAR_X_ID, _ASSET_CAMERA_ID, _ASSET_SCINTILLATOR_ID}
    ),
)


def _id_queue() -> list[UUID]:
    e = uuid4
    return [
        *tomography_install_id_prefix(asset_ids=_TOMO_ASSETS),
        *recipe_ladder_id_prefix(spec=_RECIPE),
        *[e() for _ in range(20)],  # headroom: genesis + outcome event ids
    ]


async def _seed_witnessed_run(deps: object, *, capture_code: str) -> UUID:
    handler = bind_genesis(deps)  # type: ignore[arg-type]
    return await handler(
        RecordWitnessedRun(
            name="2BM witnessed capture",
            plan_id=_PLAN_ID,
            capture_code=capture_code,
            monitor_source_id=_MONITOR_SOURCE_ID,
            trigger="Monitor",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.integration
async def test_ended_outcome_persists_run_completed_with_observed_at(
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
    run_id = await _seed_witnessed_run(deps, capture_code="2bmb-tomoscan")

    outcome_handler = bind_outcome(deps)  # type: ignore[arg-type]
    result = await outcome_handler(
        RecordWitnessedRunOutcome(
            run_id=run_id,
            capture_code="2bmb-tomoscan",
            observed_phase=CapturePhase.ENDED,
            observed_at=_OBSERVED_AT,
            monitor_source_id=_MONITOR_SOURCE_ID,
            trigger="Monitor",
            capture_progress_snapshot=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None

    events, stream_version = await deps.event_store.load("Run", run_id)  # type: ignore[attr-defined]
    assert stream_version == 2
    assert [e.event_type for e in events] == ["RunStarted", "RunCompleted"]
    outcome_event = events[1]
    assert outcome_event.payload["observed_at"] == _OBSERVED_AT.isoformat()
    assert outcome_event.metadata == {"command": "RecordWitnessedRunOutcome"}


@pytest.mark.integration
async def test_aborted_outcome_persists_run_aborted_with_capture_code_in_reason(
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
    run_id = await _seed_witnessed_run(deps, capture_code="2bmb-tomoscan")

    outcome_handler = bind_outcome(deps)  # type: ignore[arg-type]
    await outcome_handler(
        RecordWitnessedRunOutcome(
            run_id=run_id,
            capture_code="2bmb-tomoscan",
            observed_phase=CapturePhase.ABORTED,
            observed_at=None,
            monitor_source_id=_MONITOR_SOURCE_ID,
            trigger="Monitor",
            capture_progress_snapshot=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await deps.event_store.load("Run", run_id)  # type: ignore[attr-defined]
    assert [e.event_type for e in events] == ["RunStarted", "RunAborted"]
    outcome_event = events[1]
    assert outcome_event.payload["observed_at"] is None
    assert "2bmb-tomoscan" in outcome_event.payload["reason"]
