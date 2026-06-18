"""Slit centering at APS 2-BM.

cluster: Commissioning
archetype: routine
bc_primary: Operation
bc_touches: Equipment, Operation, Recipe

Scenario test for the staff-validated "centre and close an L3-style slit
aperture" routine (2bm-procedures `centre_and_close_slits`): drive a slit
so the beam image centres on the detector (centre phase), then step the
aperture down to a target size (close phase).

Modeled in the CORA lens, not mirrored. CORA names the act by its
operation noun last (`slit_centering`), not the staff verb-phrase
`centre_and_close_slits`; the close-to-target aperture is recorded as
steps inside the one act. It is an alignment Procedure (Operation BC),
NOT a Run. The centring search lives at the edge; CORA records the
converged centre + aperture setpoints in the step-log. No Calibration:
the slit centre is beam-conditioning state, not a data-interpretation
constant. See `docs/deployments/2-bm/procedures.md`.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

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

_NOW = datetime(2026, 5, 20, 11, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000003a15bb")

_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-0000003a1a01")
_APS_SITE_ID = UUID("01900000-0000-7000-8000-0000003a1501")

_FAM_SLIT_ID = family_stream_id(FamilyName("Slit"))
_FAM_CAMERA_ID = family_stream_id(FamilyName("Camera"))
_FAM_SCINTILLATOR_ID = family_stream_id(FamilyName("Scintillator"))

_ASSET_CONDITIONING_SLIT_ID = UUID("01900000-0000-7000-8000-0000003a1a11")
_ASSET_CAMERA_ID = UUID("01900000-0000-7000-8000-0000003a1a21")
_ASSET_SCINTILLATOR_ID = UUID("01900000-0000-7000-8000-0000003a1a31")

_METHOD_ID = UUID("01900000-0000-7000-8000-0000003a1d01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-0000003a1d31")
_PRACTICE_ID = UUID("01900000-0000-7000-8000-0000003a1d11")
_PLAN_ID = UUID("01900000-0000-7000-8000-0000003a1d21")

_PROCEDURE_ID = UUID("01900000-0000-7000-8000-0000003a1e01")
_STEPS_LOGBOOK_ID = UUID("01900000-0000-7000-8000-0000003a1f01")
_STEPS_OPEN_EVENT_ID = UUID("01900000-0000-7000-8000-0000003a1f02")


_DEVICES = (
    DeviceSpec("ConditioningSlit", _ASSET_CONDITIONING_SLIT_ID, "Slit", _FAM_SLIT_ID),
    DeviceSpec("Camera", _ASSET_CAMERA_ID, "Camera", _FAM_CAMERA_ID),
    DeviceSpec("Scintillator", _ASSET_SCINTILLATOR_ID, "Scintillator", _FAM_SCINTILLATOR_ID),
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
        # first append (lazy-open): logbook_id, open_event_id
        _STEPS_LOGBOOK_ID,
        _STEPS_OPEN_EVENT_ID,
        # complete_procedure: event_id (second append: no generator ids)
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
    expected: float | None = None,
    note: str | None = None,
) -> ActivityInput:
    payload: dict[str, Any] = {"channel": channel, "passed": passed, "source": source}
    if actual is not None:
        payload["actual"] = actual
    if expected is not None:
        payload["expected"] = expected
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
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _read_steps(db_pool: asyncpg.Pool, procedure_id: UUID) -> list[asyncpg.Record]:
    async with db_pool.acquire() as conn:
        return await conn.fetch(
            "SELECT step_kind, payload, sampled_at "
            "FROM entries_operation_procedure_activities "
            "WHERE procedure_id = $1 ORDER BY sampled_at",
            procedure_id,
        )


@pytest.mark.integration
async def test_slit_centering_plays_out_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """Seed Equipment + Recipe + Operation, run the two-phase slit
    centre-then-close act, and assert the operator-readable record."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_2BM_UNIT_ID,
        devices=_DEVICES,
    )

    await seed_capability_postgres(
        deps.event_store, _CAPABILITY_ID, code="cora.capability.alignment", name="Alignment"
    )
    await bind_define_method(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            capability_id=_CAPABILITY_ID,
            name="slit_centering",
            needed_family_ids=frozenset({_FAM_SLIT_ID, _FAM_CAMERA_ID, _FAM_SCINTILLATOR_ID}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_practice(deps)(
        DefinePractice(
            name="2BM_slit_centering_practice", method_id=_METHOD_ID, site_id=_APS_SITE_ID
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_plan(deps)(
        DefinePlan(
            name="2BM_conditioning_slit_centering_plan",
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
            name="2-BM conditioning-slit centering (A-station)",
            kind="slit_centering",
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
        return datetime(2026, 5, 20, 11, 0, seconds, tzinfo=UTC)

    step_store = _postgres_step_store(db_pool)

    # Centre leg: centre the beam image on the detector via the slit centre.
    centre_steps = (
        _setpoint(
            channel="Hcenter",
            target_value=0.0,
            units="mm",
            note="converged horizontal centre",
            sampled_at=t(1),
        ),
        _setpoint(
            channel="Vcenter",
            target_value=0.0,
            units="mm",
            note="converged vertical centre",
            sampled_at=t(2),
        ),
        _action(
            action_name="acquire_alignment_frame",
            exposure_time=0.05,
            hdf5_location="/exchange/data/slit_centre.h5",
            sampled_at=t(3),
        ),
        _check(
            channel="beam_centroid_offset_px",
            passed=True,
            actual=0.4,
            expected=0.0,
            source="bbox_centroid",
            note="beam centred within tolerance",
            sampled_at=t(4),
        ),
    )
    count_centre = await bind_append_step(deps, step_store=step_store)(
        AppendProcedureActivities(procedure_id=_PROCEDURE_ID, entries=centre_steps),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count_centre == 4

    # Close leg: close the aperture to the target size, holding the centre.
    close_steps = (
        _setpoint(
            channel="Hsize",
            target_value=0.5,
            units="mm",
            note="close horizontal aperture to target",
            sampled_at=t(5),
        ),
        _setpoint(
            channel="Vsize",
            target_value=0.5,
            units="mm",
            note="close vertical aperture to target",
            sampled_at=t(6),
        ),
        _action(
            action_name="acquire_alignment_frame",
            exposure_time=0.05,
            hdf5_location="/exchange/data/slit_closed.h5",
            sampled_at=t(7),
        ),
        _check(
            channel="aperture_image_size_px",
            passed=True,
            actual=145.0,
            expected=145.0,
            source="bbox_size",
            note="aperture at target, beam still centred",
            sampled_at=t(8),
        ),
    )
    count_close = await bind_append_step(deps, step_store=step_store)(
        AppendProcedureActivities(procedure_id=_PROCEDURE_ID, entries=close_steps),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count_close == 4

    await bind_complete(deps)(
        CompleteProcedure(procedure_id=_PROCEDURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Assert the Procedure stream lifecycle (no iterations) -----

    procedure_events, procedure_version = await deps.event_store.load("Procedure", _PROCEDURE_ID)
    assert procedure_version == 4
    assert [e.event_type for e in procedure_events] == [
        "ProcedureRegistered",
        "ProcedureStarted",
        "ProcedureActivitiesLogbookOpened",
        "ProcedureCompleted",
    ]

    # ----- Steps: 8 entries, centre phase then close phase -----

    step_rows = await _read_steps(db_pool, _PROCEDURE_ID)
    assert len(step_rows) == 8
    assert [r["step_kind"] for r in step_rows] == [
        "setpoint",
        "setpoint",
        "action",
        "check",  # centre
        "setpoint",
        "setpoint",
        "action",
        "check",  # close
    ]
    close_size = json.loads(step_rows[4]["payload"])
    assert close_size["channel"] == "Hsize"
    assert close_size["target_value"] == 0.5

    # ----- Read-side: COMPLETED, standalone, all target assets -----

    await _drain(db_pool)
    page = await bind_list(deps)(
        ListProcedures(kind="slit_centering"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    matching = [item for item in page.items if item.procedure_id == _PROCEDURE_ID]
    assert len(matching) == 1
    summary = matching[0]
    assert summary.kind == "slit_centering"
    assert summary.status == ProcedureStatus.COMPLETED.value
    assert summary.parent_run_id is None
    assert set(summary.target_asset_ids) == {
        _ASSET_CONDITIONING_SLIT_ID,
        _ASSET_CAMERA_ID,
        _ASSET_SCINTILLATOR_ID,
    }
