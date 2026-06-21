"""Slit blade-throw characterization at APS 2-BM.

cluster: Commissioning
archetype: routine
bc_primary: Operation
bc_touches: Equipment, Operation, Recipe, Calibration

Scenario test for the staff-validated "calibrate the throw of each L3
slit blade motor" routine (2bm-procedures `calibrate_slit_blade_throw`):
drive each blade by a known throw, measure the bright-spot edge shift on
the detector, and fit a per-blade pixels-per-mm slope. An outlier blade
flags a mis-calibrated motor.

Modeled in the CORA lens, not mirrored. The ACT is a characterization
Procedure (`blade_throw_characterization`, the family of
`energy_characterization` / `sensitivity_characterization`), NOT a Run.
The slope FIT lives at the edge (downstream of CORA). The durable
RESULT, the per-blade pixels-per-mm scale, is a cite-later instrument
constant, so it is stored in the Calibration module as a
`blade_throw_scale` quantity, appended with a `MeasuredSource` citing
this Procedure. This is the same act/value split as
`center_alignment` -> `rotation_center` and `energy_characterization` ->
a new `energy_position_curve` revision. See `docs/deployments/2-bm/procedures.md`.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.calibration._projections import register_calibration_projections
from cora.calibration.aggregates.calibration import CalibrationStatus, MeasuredSource
from cora.calibration.features.append_calibration_revision import AppendCalibrationRevision
from cora.calibration.features.append_calibration_revision import (
    bind as bind_append_calibration_revision,
)
from cora.calibration.features.define_calibration import DefineCalibration
from cora.calibration.features.define_calibration import bind as bind_define_calibration
from cora.calibration.quantities import CalibrationQuantity
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.operation._projections import register_operation_projections
from cora.operation.aggregates.procedure import ProcedureStatus
from cora.operation.features.append_activities import (
    ActivityInput,
    AppendProcedureActivities,
)
from cora.operation.features.append_activities import bind as bind_append_step
from cora.operation.features.complete_procedure import CompleteProcedure
from cora.operation.features.complete_procedure import bind as bind_complete
from cora.operation.features.list_procedures import ListProcedures
from cora.operation.features.list_procedures import bind as bind_list
from cora.operation.features.register_procedure import RegisterProcedure
from cora.operation.features.register_procedure import bind as bind_register_procedure
from cora.operation.features.start_procedure import StartProcedure
from cora.operation.features.start_procedure import bind as bind_start
from cora.recipe.aggregates.method import ExecutionPattern
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_method import bind as bind_define_method
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_plan import bind as bind_define_plan
from cora.recipe.features.define_practice import DefinePractice
from cora.recipe.features.define_practice import bind as bind_define_practice
from tests.integration._helpers import (
    build_postgres_deps,
    make_pg_profile_store,
    seed_capability_postgres,
)
from tests.integration.scenarios._facility_fixture import (
    DeviceSpec,
    facility_id_prefix,
    install_aps_unit,
    operator_for,
)

_NOW = datetime(2026, 5, 21, 13, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000003a25bb")

_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-0000003a2a01")
_APS_SITE_ID = UUID("01900000-0000-7000-8000-0000003a2501")

_FAM_SLIT_ID = family_stream_id(FamilyName("Slit"))
_FAM_CAMERA_ID = family_stream_id(FamilyName("Camera"))
_FAM_SCINTILLATOR_ID = family_stream_id(FamilyName("Scintillator"))

_ASSET_CONDITIONING_SLIT_ID = UUID("01900000-0000-7000-8000-0000003a2a11")
_ASSET_CAMERA_ID = UUID("01900000-0000-7000-8000-0000003a2a21")
_ASSET_SCINTILLATOR_ID = UUID("01900000-0000-7000-8000-0000003a2a31")

_METHOD_ID = UUID("01900000-0000-7000-8000-0000003a2d01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-0000003a2d31")
_PRACTICE_ID = UUID("01900000-0000-7000-8000-0000003a2d11")
_PLAN_ID = UUID("01900000-0000-7000-8000-0000003a2d21")

_PROCEDURE_ID = UUID("01900000-0000-7000-8000-0000003a2e01")
_STEPS_LOGBOOK_ID = UUID("01900000-0000-7000-8000-0000003a2f01")
_STEPS_OPEN_EVENT_ID = UUID("01900000-0000-7000-8000-0000003a2f02")

_CALIBRATION_ID = UUID("01900000-0000-7000-8000-0000003a2c01")
_CALIBRATION_REVISION_ID = UUID("01900000-0000-7000-8000-0000003a2c02")


_DEVICES = (
    DeviceSpec("ConditioningSlit", _ASSET_CONDITIONING_SLIT_ID, "Slit", _FAM_SLIT_ID),
    DeviceSpec("Camera", _ASSET_CAMERA_ID, "Camera", _FAM_CAMERA_ID),
    DeviceSpec("Scintillator", _ASSET_SCINTILLATOR_ID, "Scintillator", _FAM_SCINTILLATOR_ID),
)

# (blade name, throw mm, fitted pixels-per-mm). Outboard is an outlier:
# the characterization flags it as a likely mis-calibrated motor.
_BLADES: tuple[tuple[str, float, float], ...] = (
    ("top", 0.5, 14.2),
    ("bottom", 0.5, 14.0),
    ("inboard", 0.5, 13.8),
    ("outboard", 0.5, 20.9),
)


def _id_queue() -> list[UUID]:
    e = uuid4
    return [
        *facility_id_prefix(unit_id=_2BM_UNIT_ID, devices=_DEVICES),
        _METHOD_ID,
        e(),
        _PRACTICE_ID,
        e(),
        _PLAN_ID,
        e(),
        _PROCEDURE_ID,
        e(),
        # start_procedure: event_id
        e(),
        # append (lazy-open): logbook_id, open_event_id
        _STEPS_LOGBOOK_ID,
        _STEPS_OPEN_EVENT_ID,
        # complete_procedure: event_id
        e(),
        # define_calibration: calibration_id, event_id
        _CALIBRATION_ID,
        e(),
        # append_calibration_revision: revision_id, event_id
        _CALIBRATION_REVISION_ID,
        e(),
    ]


def _setpoint(
    *,
    channel: str,
    target_value: float | str,
    units: str,
    note: str | None = None,
    sampled_at: datetime,
) -> ActivityInput:
    payload: dict[str, Any] = {"channel": channel, "target_value": target_value, "units": units}
    if note is not None:
        payload["note"] = note
    return ActivityInput(
        event_id=uuid4(), step_kind="setpoint", payload=payload, sampled_at=sampled_at
    )


def _action(*, action_name: str, sampled_at: datetime, **params: Any) -> ActivityInput:
    return ActivityInput(
        event_id=uuid4(),
        step_kind="action",
        payload={"action_name": action_name, "params": params},
        sampled_at=sampled_at,
    )


def _check(
    *,
    channel: str,
    passed: bool,
    source: str,
    sampled_at: datetime,
    actual: float | None = None,
    note: str | None = None,
) -> ActivityInput:
    payload: dict[str, Any] = {"channel": channel, "passed": passed, "source": source}
    if actual is not None:
        payload["actual"] = actual
    if note is not None:
        payload["note"] = note
    return ActivityInput(
        event_id=uuid4(), step_kind="check", payload=payload, sampled_at=sampled_at
    )


def _postgres_step_store(db_pool: asyncpg.Pool):
    from cora.operation.aggregates.procedure import PostgresActivityStore

    return PostgresActivityStore(db_pool)


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_operation_projections(registry)
    register_calibration_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _read_steps(db_pool: asyncpg.Pool, procedure_id: UUID) -> list[asyncpg.Record]:
    async with db_pool.acquire() as conn:
        return await conn.fetch(
            "SELECT step_kind, payload, sampled_at "
            "FROM entries_operation_procedure_activities "
            "WHERE procedure_id = $1 "
            "AND payload->>'result' IS DISTINCT FROM 'in_flight' "
            "ORDER BY sampled_at",
            procedure_id,
        )


@pytest.mark.integration
async def test_blade_throw_characterization_plays_out_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """Seed Equipment + Recipe + Operation, sweep each blade by a known
    throw, complete the Procedure, then emit the per-blade
    blade_throw_scale Calibration sourced from it."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_2BM_UNIT_ID,
        devices=_DEVICES,
    )

    await seed_capability_postgres(
        deps.event_store,
        _CAPABILITY_ID,
        code="cora.capability.characterization",
        name="Characterization",
    )
    await bind_define_method(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            capability_id=_CAPABILITY_ID,
            name="blade_throw_characterization",
            needed_family_ids=frozenset({_FAM_SLIT_ID, _FAM_CAMERA_ID, _FAM_SCINTILLATOR_ID}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_practice(deps)(
        DefinePractice(name="2BM_blade_throw_practice", method_id=_METHOD_ID, site_id=_APS_SITE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_plan(deps)(
        DefinePlan(
            name="2BM_conditioning_slit_blade_throw_plan",
            practice_id=_PRACTICE_ID,
            asset_ids=frozenset(
                {_ASSET_CONDITIONING_SLIT_ID, _ASSET_CAMERA_ID, _ASSET_SCINTILLATOR_ID}
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await bind_register_procedure(deps)(
        RegisterProcedure(
            name="2-BM conditioning-slit blade-throw characterization (A-station)",
            kind="blade_throw_characterization",
            target_asset_ids=frozenset(
                {_ASSET_CONDITIONING_SLIT_ID, _ASSET_CAMERA_ID, _ASSET_SCINTILLATOR_ID}
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_start(deps)(
        StartProcedure(procedure_id=_PROCEDURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    def t(seconds: int) -> datetime:
        return datetime(2026, 5, 21, 13, 0, seconds, tzinfo=UTC)

    # Per-blade sweep: drive +throw, acquire, measure edge shift. The slope
    # fit (pixels-per-mm) is downstream of CORA; the Calibration below stores it.
    steps: list[ActivityInput] = []
    second = 1
    for blade, throw, scale in _BLADES:
        steps.append(
            _setpoint(
                channel=f"{blade}_blade",
                target_value=throw,
                units="mm",
                note=f"drive {blade} blade by +throw",
                sampled_at=t(second),
            )
        )
        steps.append(
            _action(
                action_name="acquire_alignment_frame",
                exposure_time=0.05,
                hdf5_location=f"/exchange/data/blade_{blade}.h5",
                sampled_at=t(second + 1),
            )
        )
        steps.append(
            _check(
                channel=f"{blade}_edge_shift_px",
                passed=True,
                actual=throw * scale,
                source="bbox_edge_fit",
                note=f"edge shift for {blade}",
                sampled_at=t(second + 2),
            )
        )
        second += 3

    count = await bind_append_step(deps, step_store=_postgres_step_store(db_pool))(
        AppendProcedureActivities(procedure_id=_PROCEDURE_ID, entries=tuple(steps)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count == 12

    await bind_complete(deps)(
        CompleteProcedure(procedure_id=_PROCEDURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Emit the blade_throw_scale Calibration the characterization produced -----
    #
    # The Procedure is the ACT; the Calibration BC stores the RESULT. The
    # caller bridges them: define the calibration for the slit, then append a
    # Provisional revision sourced from this Procedure (MeasuredSource).

    blade_value = {"blades": [{"blade": b, "scale": s} for b, _throw, s in _BLADES]}
    calibration_id = await bind_define_calibration(deps)(
        DefineCalibration(
            target_id=_ASSET_CONDITIONING_SLIT_ID,
            quantity=CalibrationQuantity.BLADE_THROW_SCALE,
            operating_point={"optics_config": "5x"},
            description="Per-blade pixels-per-mm from the 2-BM blade-throw characterization.",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert calibration_id == _CALIBRATION_ID
    revision_id = await bind_append_calibration_revision(deps)(
        AppendCalibrationRevision(
            calibration_id=calibration_id,
            value=blade_value,
            status=CalibrationStatus.PROVISIONAL,
            source=MeasuredSource(procedure_id=_PROCEDURE_ID),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert revision_id == _CALIBRATION_REVISION_ID

    # ----- Assert the Procedure stream lifecycle -----

    procedure_events, procedure_version = await deps.event_store.load("Procedure", _PROCEDURE_ID)
    assert procedure_version == 4
    assert [e.event_type for e in procedure_events] == [
        "ProcedureRegistered",
        "ProcedureStarted",
        "ProcedureActivitiesLogbookOpened",
        "ProcedureCompleted",
    ]

    # ----- Steps: 12 entries, the setpoint/action/check triad per blade -----

    step_rows = await _read_steps(db_pool, _PROCEDURE_ID)
    assert len(step_rows) == 12
    assert [r["step_kind"] for r in step_rows] == ["setpoint", "action", "check"] * 4

    # ----- Calibration stream proves the act -> result link -----

    calibration_events, _ = await deps.event_store.load("Calibration", _CALIBRATION_ID)
    assert [e.event_type for e in calibration_events] == [
        "CalibrationDefined",
        "CalibrationRevisionAppended",
    ]
    appended = calibration_events[1].payload
    assert appended["status"] == "Provisional"
    assert appended["source_procedure_id"] == str(_PROCEDURE_ID)
    assert appended["value"] == blade_value
    # The outlier blade is preserved verbatim for the operator to act on.
    outboard = next(b for b in appended["value"]["blades"] if b["blade"] == "outboard")
    assert outboard["scale"] == 20.9

    # ----- Read-side: Procedure COMPLETED + Calibration summary renders measured -----

    await _drain(db_pool)
    page = await bind_list(deps)(
        ListProcedures(kind="blade_throw_characterization"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    matching = [item for item in page.items if item.procedure_id == _PROCEDURE_ID]
    assert len(matching) == 1
    assert matching[0].status == ProcedureStatus.COMPLETED.value
    assert set(matching[0].target_asset_ids) == {
        _ASSET_CONDITIONING_SLIT_ID,
        _ASSET_CAMERA_ID,
        _ASSET_SCINTILLATOR_ID,
    }

    async with db_pool.acquire() as conn:
        cal_row = await conn.fetchrow(
            "SELECT latest_revision_status, latest_revision_source_kind "
            "FROM proj_calibration_summary WHERE calibration_id = $1",
            _CALIBRATION_ID,
        )
    assert cal_row is not None
    assert cal_row["latest_revision_status"] == "Provisional"
    assert cal_row["latest_revision_source_kind"] == "measured"
