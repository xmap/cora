"""Energy calibration via a channel-cut crystal at APS 2-BM (item_022).

cluster: Commissioning
archetype: routine
bc_primary: Operation
bc_touches: Equipment, Operation, Calibration

Scenario test for the 2-BM "X-ray energy calibration using a channel-cut
crystal" routine, staff-documented on docs2bm `ops/item_022`. Rock a
crystal of known 2d through its Bragg peak, fit the peak angle, apply
Bragg's law to recover the true beam energy, and record the signed
correction against the commanded energy.

This mirrors the center-alignment scenario's shape (the Procedure is the
ACT; the Calibration BC stores the RESULT, bridged by `MeasuredSource`),
but for the energy domain: the recalibration appends a NEW REVISION of the
monochromator axis's `energy_position_curve`.

## Why this test exists

Gap-surfacing, like its sibling: it proves the energy-calibration
modelling holds against the real operator routine. Two deliberate
modelling choices it exercises:

  - **target is the Monochromator axis, not the crystal.** The calibrated
    entity is the monochromator's energy-tracked axis (here the upstream
    Bragg arm); the channel-cut crystal is the measuring tool. The crystal
    is documented as a calibration Subject (subjects.md), the way the
    resolution phantom is for center alignment, and like that phantom it is
    not a target Asset of the Procedure.
  - **a recalibration is a NEW REVISION, not an overwrite (ENERGY-8).**
    There is no separate energy offset: per staff the beamline re-saves the
    per-energy position table directly (`energy add`), so the curve itself
    carries the corrected positions. CORA models that as a second revision
    of the existing `energy_position_curve`, sourced from this Procedure
    (`MeasuredSource`), so the calibration HISTORY is preserved (the curve
    before and after, and which Procedure changed it) -- the provenance the
    file-overwrite workflow throws away. The fitted true energy is kept as
    logbook evidence, not an applied correction.

Energy calibration is measure-then-verify, not a convergence loop, so
(unlike center alignment) the Procedure runs without iteration brackets.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.calibration._projections import register_calibration_projections
from cora.calibration.aggregates.calibration import (
    AssertedSource,
    CalibrationStatus,
    MeasuredSource,
)
from cora.calibration.features.append_calibration_revision import (
    AppendCalibrationRevision,
)
from cora.calibration.features.append_calibration_revision import (
    bind as bind_append_calibration_revision,
)
from cora.calibration.features.define_calibration import DefineCalibration
from cora.calibration.features.define_calibration import (
    bind as bind_define_calibration,
)
from cora.calibration.quantities import CalibrationQuantity
from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.add_asset_family import bind as bind_add_asset_family
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_family import bind as bind_define_family
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.register_asset import bind as bind_register_asset
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.operation._projections import register_operation_projections
from cora.operation.aggregates.procedure import ProcedureStatus
from cora.operation.features.append_activities import (
    ActivityInput,
    AppendProcedureActivities,
)
from cora.operation.features.append_activities import (
    bind as bind_append_step,
)
from cora.operation.features.complete_procedure import CompleteProcedure
from cora.operation.features.complete_procedure import bind as bind_complete
from cora.operation.features.list_procedures import ListProcedures
from cora.operation.features.list_procedures import bind as bind_list
from cora.operation.features.register_procedure import RegisterProcedure
from cora.operation.features.register_procedure import (
    bind as bind_register_procedure,
)
from cora.operation.features.start_procedure import StartProcedure
from cora.operation.features.start_procedure import bind as bind_start
from cora.shared.identity import ActorId
from tests.integration._helpers import (
    build_postgres_deps,
    make_pg_profile_store,
)
from tests.integration.scenarios._facility_fixture import (
    DeviceSpec,
    facility_id_prefix,
    install_aps_unit,
    operator_for,
)

_NOW = datetime(2026, 5, 15, 14, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-000000037bb0")

# Asset hierarchy (scenario-supplied mnemonic-tagged ids; 37 segment).
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000370a01")
_CAP_MONOCHROMATOR_ID = family_stream_id(FamilyName("Monochromator"))
_CAP_PSEUDO_AXIS_ID = family_stream_id(FamilyName("PseudoAxis"))
_ASSET_MONOCHROMATOR_ID = UUID("01900000-0000-7000-8000-000000037a01")

_DEVICES = (
    DeviceSpec("Monochromator", _ASSET_MONOCHROMATOR_ID, "Monochromator", _CAP_MONOCHROMATOR_ID),
)

# The calibration is measured at a nominal commanded energy, in mono mode.
_NOMINAL_ENERGY_KEV = 20.0
_FITTED_ENERGY_KEV = 20.04  # true energy the rocking curve fits at the nominal 20.0 setpoint

# The upstream Bragg-arm energy -> position curve (deg), before and after this
# recalibration. The re-save (energy add) shifts only the recalibrated energy's
# saved position; the other anchors are unchanged. Real store_0 magnitudes per
# ENERGY-1; the small 20 keV shift stands in for the corrected motor position.
_AXIS_DESIGNATION = "dmm_us_arm"
_BEFORE_POINTS: list[dict[str, float]] = [
    {"energy": 18.0, "position": 0.822},
    {"energy": 20.0, "position": 0.726},
    {"energy": 25.0, "position": 0.577},
]
_AFTER_POINTS: list[dict[str, float]] = [
    {"energy": 18.0, "position": 0.822},
    {"energy": 20.0, "position": 0.7268},
    {"energy": 25.0, "position": 0.577},
]


def _id_queue() -> list[UUID]:
    """FixedIdGenerator queue: the facility prefix plus a generous anonymous
    tail. Aggregate ids (facet, calibration, revisions, procedure, logbook)
    are captured from the bind return values; event ids come from the tail."""
    return [
        *facility_id_prefix(unit_id=_2BM_UNIT_ID, devices=_DEVICES),
        *[uuid4() for _ in range(40)],
    ]


def _t(seconds: int) -> datetime:
    return datetime(2026, 5, 15, 14, 0, seconds, tzinfo=UTC)


def _setpoint(
    *, channel: str, target_value: float, units: str, note: str, sampled_at: datetime
) -> ActivityInput:
    return ActivityInput(
        event_id=uuid4(),
        step_kind="setpoint",
        payload={"channel": channel, "target_value": target_value, "units": units, "note": note},
        sampled_at=sampled_at,
    )


def _action(*, action_name: str, sampled_at: datetime, **params: Any) -> ActivityInput:
    return ActivityInput(
        event_id=uuid4(),
        step_kind="action",
        payload={"action_name": action_name, "params": params},
        sampled_at=sampled_at,
    )


def _check(
    *, channel: str, passed: bool, source: str, sampled_at: datetime, **evidence: Any
) -> ActivityInput:
    payload: dict[str, Any] = {"channel": channel, "passed": passed, "source": source}
    if evidence:
        payload["evidence"] = evidence
    return ActivityInput(
        event_id=uuid4(), step_kind="check", payload=payload, sampled_at=sampled_at
    )


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_operation_projections(registry)
    register_calibration_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


def _postgres_step_store(db_pool: asyncpg.Pool):
    from cora.operation.aggregates.procedure import PostgresActivityStore

    return PostgresActivityStore(db_pool)


async def _read_steps(db_pool: asyncpg.Pool, procedure_id: UUID) -> list[asyncpg.Record]:
    async with db_pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT step_kind, payload, sampled_at
            FROM entries_operation_procedure_activities
            WHERE procedure_id = $1 AND payload->>'result' IS DISTINCT FROM 'in_flight'
            ORDER BY sampled_at
            """,
            procedure_id,
        )


@pytest.mark.integration
async def test_energy_characterization_appends_an_energy_curve_revision(
    db_pool: asyncpg.Pool,
) -> None:
    """Run the channel-cut rocking-curve characterization and assert it appends
    a NEW revision of the monochromator axis's energy_position_curve, sourced
    from the Procedure (MeasuredSource), Provisional until blessed, leaving the
    prior revision intact as history (ENERGY-8)."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())
    actor = ActorId(_PRINCIPAL_ID)

    # ----- Seed facility hierarchy: operators + 2-BM Unit + Monochromator -----
    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_2BM_UNIT_ID,
        devices=_DEVICES,
    )

    # ----- Equipment BC: the energy-tracked axis + its existing energy curve -----
    #
    # The upstream Bragg-arm PseudoAxis facet under the Monochromator already
    # carries a Verified energy_position_curve (the calibration in force before
    # this characterization). The recalibration below appends a second revision.
    await bind_define_family(deps)(
        DefineFamily(name="PseudoAxis", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    facet_id = await bind_register_asset(deps)(
        RegisterAsset(
            name="Monochromator_BraggArmUpstream",
            tier=AssetTier.DEVICE,
            parent_id=_ASSET_MONOCHROMATOR_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_add_asset_family(deps)(
        AddAssetFamily(asset_id=facet_id, family_id=_CAP_PSEUDO_AXIS_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    cal_id = await bind_define_calibration(deps)(
        DefineCalibration(
            target_id=facet_id,
            quantity=CalibrationQuantity.ENERGY_POSITION_CURVE,
            operating_point={"axis_designation": _AXIS_DESIGNATION, "beam_mode": "mono"},
            description="Upstream Bragg-arm energy -> position curve for the 2-BM monochromator.",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_append_calibration_revision(deps)(
        AppendCalibrationRevision(
            calibration_id=cal_id,
            value={"points": _BEFORE_POINTS, "position_unit": "deg"},
            status=CalibrationStatus.VERIFIED,
            source=AssertedSource(asserted_by=actor),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Operation BC: register + start the energy_characterization Procedure -----
    #
    # Target is the Monochromator (the calibrated entity). capability_id is left
    # unset in v1; binding to a characterization Capability follows once the 2-BM
    # capability catalog settles.
    procedure_id = await bind_register_procedure(deps)(
        RegisterProcedure(
            name="2-BM energy calibration via channel-cut crystal",
            kind="energy_characterization",
            target_asset_ids=frozenset({_ASSET_MONOCHROMATOR_ID}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_start(deps)(
        StartProcedure(procedure_id=procedure_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- The rocking-curve act: drive to the expected Bragg angle, scan, fit -----
    steps = (
        _setpoint(
            channel="ChannelCut_Theta",
            target_value=9.29,
            units="deg",
            note="expected Bragg angle for 20 keV at a 2d of 3.84 angstrom (item_022)",
            sampled_at=_t(1),
        ),
        _action(
            action_name="rocking_curve_scan",
            scan_range_deg=0.4,
            step_deg=0.002,
            roi_plugin="Stat2",
            hdf5_location="/exchange/data/energy_cal_rocking_20kev.h5",
            sampled_at=_t(2),
        ),
        _check(
            channel="bragg_peak_theta_deg",
            passed=True,
            source="rocking_curve_fit",
            fitted_peak_theta_deg=9.272,
            fitted_energy_kev=20.04,
            nominal_energy_kev=20.0,
            sampled_at=_t(3),
        ),
        _action(
            action_name="energy_add",
            energy_kev=_NOMINAL_ENERGY_KEV,
            mode="mono",
            note="re-save the per-energy table at 20 keV with the corrected motor "
            "positions (no separate offset is stored); appended below as a new "
            "energy_position_curve revision",
            sampled_at=_t(4),
        ),
    )

    step_store = _postgres_step_store(db_pool)
    count = await bind_append_step(deps, step_store=step_store)(
        AppendProcedureActivities(procedure_id=procedure_id, entries=steps),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count == 4

    await bind_complete(deps)(
        CompleteProcedure(procedure_id=procedure_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- The result: a NEW revision of the existing energy_position_curve -----
    #
    # The Procedure is the ACT; the Calibration BC stores the RESULT. The
    # recalibration does not produce a separate offset (ENERGY-8): it re-saves
    # the corrected per-energy positions as a second revision of the curve,
    # sourced from this Procedure (MeasuredSource), Provisional until blessed.
    # The prior Verified revision stays on the stream as history.
    await bind_append_calibration_revision(deps)(
        AppendCalibrationRevision(
            calibration_id=cal_id,
            value={"points": _AFTER_POINTS, "position_unit": "deg"},
            status=CalibrationStatus.PROVISIONAL,
            source=MeasuredSource(procedure_id=procedure_id),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- The Calibration stream proves the act -> result link + history -----
    calibration_events, _ = await deps.event_store.load("Calibration", cal_id)
    assert [e.event_type for e in calibration_events] == [
        "CalibrationDefined",
        "CalibrationRevisionAppended",
        "CalibrationRevisionAppended",
    ]
    defined = calibration_events[0].payload
    assert defined["quantity"] == "energy_position_curve"
    assert defined["target_id"] == str(facet_id)
    assert defined["operating_point"] == {
        "axis_designation": _AXIS_DESIGNATION,
        "beam_mode": "mono",
    }
    # The prior calibration stays on the stream as history (the asserted baseline).
    baseline = calibration_events[1].payload
    assert baseline["status"] == "Verified"
    assert baseline["value"]["points"] == _BEFORE_POINTS
    # The recalibration is the new revision, sourced from this Procedure.
    recalibration = calibration_events[2].payload
    assert recalibration["status"] == "Provisional"
    assert recalibration["source_procedure_id"] == str(procedure_id)
    assert recalibration["value"]["points"] == _AFTER_POINTS

    # ----- The Procedure stream tells the right lifecycle story -----
    procedure_events, procedure_version = await deps.event_store.load("Procedure", procedure_id)
    assert procedure_version == 4, f"expected 4 events on Procedure stream, got {procedure_version}"
    assert [e.event_type for e in procedure_events] == [
        "ProcedureRegistered",
        "ProcedureStarted",
        "ProcedureActivitiesLogbookOpened",
        "ProcedureCompleted",
    ]

    # ----- The per-step logbook carries the rocking-curve evidence -----
    step_rows = await _read_steps(db_pool, procedure_id)
    assert [r["step_kind"] for r in step_rows] == ["setpoint", "action", "check", "action"]

    # ----- Drain the projection and assert the read-side record is correct -----
    await _drain(db_pool)
    async with db_pool.acquire() as conn:
        cal_row = await conn.fetchrow(
            "SELECT quantity, latest_revision_status, latest_revision_source_kind "
            "FROM proj_calibration_summary WHERE calibration_id = $1",
            cal_id,
        )
    assert cal_row is not None
    assert cal_row["quantity"] == "energy_position_curve"
    assert cal_row["latest_revision_status"] == "Provisional"
    assert cal_row["latest_revision_source_kind"] == "measured"

    # ----- The Procedure surfaces in the read model under its kind -----
    page = await bind_list(deps)(
        ListProcedures(kind="energy_characterization"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    matching = [item for item in page.items if item.procedure_id == procedure_id]
    assert len(matching) == 1
    proc_summary = matching[0]
    assert proc_summary.name == "2-BM energy calibration via channel-cut crystal"
    assert proc_summary.kind == "energy_characterization"
    assert proc_summary.status == ProcedureStatus.COMPLETED.value
    assert set(proc_summary.target_asset_ids) == {_ASSET_MONOCHROMATOR_ID}
    assert proc_summary.parent_run_id is None
