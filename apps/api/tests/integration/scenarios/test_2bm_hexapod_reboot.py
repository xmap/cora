"""Hexapod reboot at APS 2-BM.

cluster: Commissioning
archetype: fsm
bc_primary: Equipment
bc_touches: Caution, Equipment, Operation, Recipe

Scenario test for the canonical hexapod-recovery routine: the
PI-Hexapod sample-positioning controller locks up (HexapodAllEnabled
PV stuck at 0), operator power-cycles outlet 4 on the network PDU
+ restarts the hexapod EPICS IOC + verifies the controller comes
back enabled. Sourced directly from `2bmb-bin/hexapod_reboot.py`
(the best-documented script in that repo).

See [[project_pilot_docs_design]] for the phase / file-naming
taxonomy this scenario fits into.

## Why this scenario exists

This is CORA's first **Asset.fault / restore** scenario (distinct
from the Nominal / Degraded condition cycle that motor_homing
exercises). The condition FSM has three states: Nominal -> Degraded
-> Faulted (per [[project_asset_condition_design]]). Motor_homing
covered Nominal <-> Degraded (recoverable misbehavior); this
covers Nominal -> Faulted -> Nominal (hardware stuck, recovered
via a deliberate reboot ceremony).

The operator's observation (HexapodAllEnabled stuck at 0) is the
precondition for the procedure; the FaultAsset slice fires BEFORE
the reboot Procedure starts. Once the procedure completes and the
hexapod is verified enabled again, RestoreAsset fires.

The scenario also unlocks four firsts in CORA's 2-BM doc tree:

  1. New Family `Hexapod` joins the cross-facility catalog.
  2. New Device `Hexapod` joins the 2-BM Asset inventory.
  3. New Procedure kind `hexapod_reboot` joins the 2-BM Procedure
     list (first maintenance-phase routine).
  4. New Caution about cold-start lockups joins the 2-BM operator
     playbook.

## Domain shape (synthesized from `2bmb-bin/hexapod_reboot.py`)

Seven-step reboot ceremony with two power-settling sleeps:

  1. Stop hexapod IOC via `hexapod_IOC_stop.sh`.
  2. Power OFF outlet 4 on the network PDU (HTTP POST to NetBooter
     `/cmd.cgi?rly=3`; verify state via `GET /status.xml`).
  3. Sleep 10 s for controller de-energization.
  4. Power ON outlet 4.
  5. Sleep 10 s for controller boot.
  6. Start hexapod IOC via `hexapod_IOC.sh`.
  7. Poll `2bmHXP:HexapodAllEnabled.VAL` for value `1` (180 s
     timeout). Fallback: if not enabled, `caput
     2bmHXP:EnableWork.PROC 1` to force-enable + re-poll.

This scenario captures the happy path (controller comes back on
first poll); the fallback caput is a watch item for a sibling
scenario.

## Asset stack (hexapod controller + hexapod stage)

This scenario registers the Hexapod Device alongside its drive
electronics (`HexapodDrive`, the second MotionController
Asset shipped per the controller-as-Asset design). The
hexapod's `controller_id` carries the back-reference to the drive.
The broader 2-BM stack (other motors, optics, detector) doesn't
participate in the reboot ceremony and is registered by separate
scenarios. Each scenario isolates its world via the per-test template
DB.

## What this scenario surfaces (gap-finding intent)

  - **Fault vs Degrade is a different shape than just "worse".**
    Faulted is an unrecoverable-without-intervention state;
    Degraded is recoverable in-flight. The reboot Procedure is
    the intervention that takes Faulted -> Nominal. Whether the
    domain should model "RecoveryProcedure" as a first-class
    Procedure kind binding (rather than a free-form `kind` string)
    is a watch item.
  - **External-system actions are opaque to CORA.** PDU HTTP
    requests, shell-script invocations, and EPICS PV polls all
    happen outside CORA's spine; the scenario records them as
    Action step entries with payload encoding the external call
    (script name, PV name, outlet number) but cannot verify
    success against the external system from inside the test.
    Whether the Operation BC should grow a `external_call_audit`
    payload key is a watch item.
  - **Sleep is a first-class step.** The two 10-second waits are
    not no-ops; they are operator-enforced settling time. Sleeps
    appear as Action entries with `role=power_settling` /
    `controller_boot`; whether sleeps deserve their own step_kind
    is a watch item.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.caution.aggregates.caution import (
    AssetTarget,
    CautionCategory,
    CautionSeverity,
)
from cora.caution.features.register_caution import RegisterCaution
from cora.caution.features.register_caution import bind as bind_register_caution
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.features.activate_asset import ActivateAsset
from cora.equipment.features.activate_asset import bind as bind_activate_asset
from cora.equipment.features.fault_asset import FaultAsset
from cora.equipment.features.fault_asset import bind as bind_fault_asset
from cora.equipment.features.restore_asset import RestoreAsset
from cora.equipment.features.restore_asset import bind as bind_restore_asset
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.operation._projections import register_operation_projections
from cora.operation.features.append_activities import (
    ActivityInput,
    AppendProcedureActivities,
)
from cora.operation.features.append_activities import bind as bind_append_step
from cora.operation.features.complete_procedure import CompleteProcedure
from cora.operation.features.complete_procedure import bind as bind_complete
from cora.operation.features.register_procedure import RegisterProcedure
from cora.operation.features.register_procedure import bind as bind_register_procedure
from cora.operation.features.start_procedure import StartProcedure
from cora.operation.features.start_procedure import bind as bind_start
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

_NOW = datetime(2026, 5, 17, 14, 30, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000360bb")

# Facility hierarchy mnemonic hex tags: a=unit. Scenario tag: 360.
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000360501")
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000360a01")

# Families (2: motion controller + hexapod)
_CAP_MOTION_CONTROLLER_ID = family_stream_id(FamilyName("MotionController"))
_CAP_HEXAPOD_ID = family_stream_id(FamilyName("Hexapod"))

# Devices: controller registered first (so the hexapod's controller_id
# back-reference targets an already-registered Asset stream), then the
# hexapod stage itself. HexapodDrive is the SECOND
# MotionController Asset shipped per
# [[project-controller-as-asset-stage1-design]], anchoring the hexapod
# controller class. The drive's specific product line is not named on
# the 2-BM source page (which calls the EPICS interface "native Aerotech
# Ensemble" but does not name the controller box or confirm rack-separate
# vs sealed-in integration); the Asset name records what is known
# (Aerotech vendor, drives the hexapod) and defers the rest to settings
# placeholders (unknown-pending-confirmation per the intentional-modeling
# rule). The other 5 controller hardware classes at 2-BM remain deferred
# per [[project-controller-as-asset-research]].
_ASSET_AEROTECH_HEXAPOD_DRIVE_ID = UUID("01900000-0000-7000-8000-000000360a21")
_ASSET_HEXAPOD_ID = UUID("01900000-0000-7000-8000-000000360a11")

# Recipe ladder
_METHOD_REBOOT_ID = UUID("01900000-0000-7000-8000-000000360d01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0e4ab")
_PRACTICE_REBOOT_ID = UUID("01900000-0000-7000-8000-000000360d11")
_PLAN_REBOOT_ID = UUID("01900000-0000-7000-8000-000000360d21")

# Procedure + lazy steps logbook
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-000000360f01")
_STEPS_LOGBOOK_ID = UUID("01900000-0000-7000-8000-000000360f11")
_STEPS_OPEN_EVENT_ID = UUID("01900000-0000-7000-8000-000000360f12")

# Caution registered against Hexapod
_CAUTION_HEXAPOD_LOCKUP_ID = UUID("01900000-0000-7000-8000-000000360f21")


_DEVICES = (
    DeviceSpec(
        "HexapodDrive",
        _ASSET_AEROTECH_HEXAPOD_DRIVE_ID,
        "MotionController",
        _CAP_MOTION_CONTROLLER_ID,
    ),
    DeviceSpec(
        "Hexapod",
        _ASSET_HEXAPOD_ID,
        "Hexapod",
        _CAP_HEXAPOD_ID,
        controller_id=_ASSET_AEROTECH_HEXAPOD_DRIVE_ID,
    ),
)


def _id_queue() -> list[UUID]:
    """Pre-allocated FixedIdGenerator queue (head-first consumption)."""
    e = uuid4
    return [
        *facility_id_prefix(
            unit_id=_2BM_UNIT_ID,
            devices=_DEVICES,
        ),
        # activate_asset x 1: event_id only
        e(),
        # define_method: method_id, event_id
        _METHOD_REBOOT_ID,
        e(),
        # define_practice: practice_id, event_id
        _PRACTICE_REBOOT_ID,
        e(),
        # define_plan: plan_id, event_id
        _PLAN_REBOOT_ID,
        e(),
        # fault_asset (operator notes lockup before reboot): event_id
        e(),
        # register_procedure: procedure_id, event_id
        _PROCEDURE_ID,
        e(),
        # start_procedure: event_id
        e(),
        # append_activities (lazy open on first call): logbook_id, open_event_id
        _STEPS_LOGBOOK_ID,
        _STEPS_OPEN_EVENT_ID,
        # restore_asset (after reboot succeeds): event_id
        e(),
        # complete_procedure: event_id
        e(),
        # register_caution (Hexapod cold-start lockup): caution_id, event_id
        _CAUTION_HEXAPOD_LOCKUP_ID,
        e(),
    ]


def _setpoint(
    *,
    channel: str,
    target_value: str,
    units: str = "state",
    role: str | None = None,
    note: str | None = None,
    sampled_at: datetime,
) -> ActivityInput:
    payload: dict[str, Any] = {
        "channel": channel,
        "target_value": target_value,
        "units": units,
    }
    if role is not None:
        payload["role"] = role
    if note is not None:
        payload["note"] = note
    return ActivityInput(
        event_id=uuid4(),
        step_kind="setpoint",
        payload=payload,
        sampled_at=sampled_at,
    )


def _action(
    *,
    action_name: str,
    sampled_at: datetime,
    role: str | None = None,
    **params: Any,
) -> ActivityInput:
    payload: dict[str, Any] = {"action_name": action_name, "params": params}
    if role is not None:
        payload["role"] = role
    return ActivityInput(
        event_id=uuid4(),
        step_kind="action",
        payload=payload,
        sampled_at=sampled_at,
    )


def _check(
    *,
    channel: str,
    passed: bool,
    source: str,
    sampled_at: datetime,
    expected: str | None = None,
    actual: str | None = None,
    note: str | None = None,
) -> ActivityInput:
    payload: dict[str, Any] = {"channel": channel, "passed": passed, "source": source}
    if expected is not None:
        payload["expected"] = expected
    if actual is not None:
        payload["actual"] = actual
    if note is not None:
        payload["note"] = note
    return ActivityInput(
        event_id=uuid4(),
        step_kind="check",
        payload=payload,
        sampled_at=sampled_at,
    )


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_operation_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


def _postgres_step_store(db_pool: asyncpg.Pool):
    """Build a PostgresActivityStore for the BC-internal step writer."""
    from cora.operation.aggregates.procedure import PostgresActivityStore

    return PostgresActivityStore(db_pool)


@pytest.mark.integration
async def test_hexapod_reboot_plays_out_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """Seed Hexapod Device, fault it on observed lockup, run the
    reboot Procedure (IOC stop + PDU power-cycle + IOC start + EPICS
    enable check), restore the Asset, register the operator-playbook
    Caution. Assert the auditable record carries the full fault ->
    reboot -> restore arc plus the procedure step entries that mirror
    `2bmb-bin/hexapod_reboot.py`."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    # ----- Seed facility hierarchy: actor + Argonne -> APS -> 2-BM + Hexapod Device -----

    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_2BM_UNIT_ID,
        devices=_DEVICES,
        unit_name="2-BM",
    )

    # ----- Equipment BC: activate the Hexapod (Commissioned -> Active) -----

    await bind_activate_asset(deps)(
        ActivateAsset(asset_id=_ASSET_HEXAPOD_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Recipe BC: Method + Practice + Plan for the reboot routine -----

    await seed_capability_postgres(
        deps.event_store,
        _CAPABILITY_ID,
        code="cora.capability.maintenance",
        name="Maintenance",
    )

    await bind_define_method(deps)(
        DefineMethod(
            capability_id=_CAPABILITY_ID,
            name="hexapod_reboot",
            needed_family_ids=frozenset({_CAP_HEXAPOD_ID}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_practice(deps)(
        DefinePractice(
            name="2BM_hexapod_reboot_practice",
            method_id=_METHOD_REBOOT_ID,
            site_id=_APS_SITE_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_plan(deps)(
        DefinePlan(
            name="2BM_hexapod_reboot_plan",
            practice_id=_PRACTICE_REBOOT_ID,
            asset_ids=frozenset({_ASSET_HEXAPOD_ID}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Equipment BC: fault the Hexapod (operator observes lockup) -----
    # Precondition for the reboot. The HexapodAllEnabled PV is stuck at 0;
    # operator marks Asset condition Nominal -> Faulted before reboot starts.

    await bind_fault_asset(deps)(
        FaultAsset(
            asset_id=_ASSET_HEXAPOD_ID,
            reason="controller lockup observed: 2bmHXP:HexapodAllEnabled stuck at 0",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Operation BC: register + start the reboot Procedure -----

    await bind_register_procedure(deps)(
        RegisterProcedure(
            name="2-BM hexapod reboot (PDU outlet 4 power-cycle + IOC restart)",
            kind="hexapod_reboot",
            target_asset_ids=frozenset({_ASSET_HEXAPOD_ID}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_start(deps)(
        StartProcedure(procedure_id=_PROCEDURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Procedure step entries: the 7-step reboot ceremony -----
    # Mirrors the hexapod_reboot.py control flow exactly.

    t = _NOW
    await bind_append_step(deps, step_store=_postgres_step_store(db_pool))(
        AppendProcedureActivities(
            procedure_id=_PROCEDURE_ID,
            entries=(
                # 1. Stop hexapod IOC
                _setpoint(
                    channel="hexapod_ioc",
                    target_value="stopped",
                    role="ioc_stop_request",
                    sampled_at=t,
                ),
                _action(
                    action_name="run_shell_script",
                    script="hexapod_IOC_stop.sh",
                    sampled_at=t,
                ),
                _check(
                    channel="hexapod_ioc.running",
                    passed=True,
                    source="shell_exit_code",
                    expected="false",
                    actual="false",
                    note="hexapod_IOC_stop.sh returned 0",
                    sampled_at=t,
                ),
                # 2. Power OFF outlet 4 on PDU
                _setpoint(
                    channel="pdu_a.outlet_4",
                    target_value="off",
                    role="power_cycle_off",
                    sampled_at=t,
                ),
                _action(
                    action_name="pdu_power_toggle",
                    pdu="a",
                    outlet=4,
                    direction="off",
                    method="netbooter_http",
                    sampled_at=t,
                ),
                _check(
                    channel="pdu_a.outlet_4.state",
                    passed=True,
                    source="netbooter_status_xml",
                    expected="off",
                    actual="off",
                    note="GET /status.xml: <rly3>0</rly3>",
                    sampled_at=t,
                ),
                # 3. Wait for power to settle (10s default)
                _action(
                    action_name="sleep",
                    seconds=10,
                    role="power_settling",
                    sampled_at=t,
                ),
                # 4. Power ON outlet 4 on PDU
                _setpoint(
                    channel="pdu_a.outlet_4",
                    target_value="on",
                    role="power_cycle_on",
                    sampled_at=t,
                ),
                _action(
                    action_name="pdu_power_toggle",
                    pdu="a",
                    outlet=4,
                    direction="on",
                    method="netbooter_http",
                    sampled_at=t,
                ),
                _check(
                    channel="pdu_a.outlet_4.state",
                    passed=True,
                    source="netbooter_status_xml",
                    expected="on",
                    actual="on",
                    note="GET /status.xml: <rly3>1</rly3>",
                    sampled_at=t,
                ),
                # 5. Wait for controller boot (10s default)
                _action(
                    action_name="sleep",
                    seconds=10,
                    role="controller_boot",
                    sampled_at=t,
                ),
                # 6. Start hexapod IOC
                _setpoint(
                    channel="hexapod_ioc",
                    target_value="running",
                    role="ioc_start_request",
                    sampled_at=t,
                ),
                _action(
                    action_name="run_shell_script",
                    script="hexapod_IOC.sh",
                    sampled_at=t,
                ),
                _check(
                    channel="hexapod_ioc.running",
                    passed=True,
                    source="shell_exit_code",
                    expected="true",
                    actual="true",
                    note="hexapod_IOC.sh returned 0",
                    sampled_at=t,
                ),
                # 7. Poll HexapodAllEnabled PV (180s timeout, happy path = enabled on first poll)
                _setpoint(
                    channel="2bmHXP:HexapodAllEnabled.VAL",
                    target_value="1",
                    role="ca_poll_request",
                    sampled_at=t,
                ),
                _action(
                    action_name="caget_poll",
                    pv="2bmHXP:HexapodAllEnabled.VAL",
                    timeout_seconds=180,
                    poll_interval_seconds=2,
                    sampled_at=t,
                ),
                _check(
                    channel="2bmHXP:HexapodAllEnabled.VAL",
                    passed=True,
                    source="caget",
                    expected="1",
                    actual="1",
                    note="happy path: controller enabled on first poll iteration",
                    sampled_at=t,
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Equipment BC: restore the Hexapod (reboot verified) -----

    await bind_restore_asset(deps)(
        RestoreAsset(
            asset_id=_ASSET_HEXAPOD_ID,
            reason="reboot succeeded; 2bmHXP:HexapodAllEnabled=1; controller responding",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Operation BC: complete the Procedure -----

    await bind_complete(deps)(
        CompleteProcedure(procedure_id=_PROCEDURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Caution BC: register the operator-playbook Caution on the controller -----
    # Targets HexapodDrive (the actual hardware that locks up)
    # rather than the stage proxy. The failure mode and the workaround
    # were always controller-side; only with controller-as-Asset shipped
    # does CORA have a controller Asset to point at honestly. In
    # production, a similar move on an already-registered Caution uses
    # the locked retire + re-register path (CautionRetired with
    # reason=WrongTarget on the stage stream, fresh CautionRegistered on
    # the controller stream); this test fixture uses ephemeral event
    # stores, so it registers fresh against the controller directly.

    await bind_register_caution(deps)(
        RegisterCaution(
            target=AssetTarget(asset_id=_ASSET_AEROTECH_HEXAPOD_DRIVE_ID),
            category=CautionCategory.WEAR,
            severity=CautionSeverity.CAUTION,
            text=(
                "Hexapod controller occasionally locks up under sustained load: "
                "2bmHXP:HexapodAllEnabled stuck at 0 while motion commands return no error. "
                "Symptom observed 2026-05-17 during 2-BM operations."
            ),
            workaround=(
                "Run hexapod_reboot.py (in 2bmb-bin): stops hexapod IOC, power-cycles "
                "PDU outlet 4 with 10s settling each way, restarts IOC, polls "
                "HexapodAllEnabled. If still 0 after 180s, caput EnableWork.PROC=1 to "
                "force enable, then re-poll. Manual checks: verify outlet state via "
                "NetBooter /status.xml; SSH 2bmb@arcturus for IOC log inspection."
            ),
            tags=frozenset({"hexapod", "controller_lockup", "pdu_power_cycle", "ioc_restart"}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Assert: facility hierarchy + controller + Hexapod landed -----

    for asset_id in (
        _2BM_UNIT_ID,
        _ASSET_AEROTECH_HEXAPOD_DRIVE_ID,
        _ASSET_HEXAPOD_ID,
    ):
        _events, version = await deps.event_store.load("Asset", asset_id)
        assert version >= 1, f"Asset {asset_id} did not land"

    # ----- Assert: HexapodDrive controller stream landed -----

    controller_events, _ = await deps.event_store.load("Asset", _ASSET_AEROTECH_HEXAPOD_DRIVE_ID)
    assert [e.event_type for e in controller_events] == [
        "AssetRegistered",  # genesis (Commissioned)
        "AssetFamilyAdded",  # +MotionController
    ]
    # The controller itself carries no controller_id back-reference
    # (controllers ARE the leaf of the drive-electronics chain at v1).
    # Omit-when-None wire shape: key absent rather than serialized as null.
    assert "controller_id" not in controller_events[0].payload

    # ----- Assert: Hexapod stream carries the full lifecycle + fault/restore arc -----

    hexapod_events, _ = await deps.event_store.load("Asset", _ASSET_HEXAPOD_ID)
    hexapod_event_types = [e.event_type for e in hexapod_events]
    assert hexapod_event_types == [
        "AssetRegistered",  # genesis (Commissioned)
        "AssetFamilyAdded",  # +Hexapod capability
        "AssetActivated",  # Commissioned -> Active
        "AssetFaulted",  # condition Nominal -> Faulted (operator observed lockup)
        "AssetRestored",  # condition Faulted -> Nominal (reboot succeeded)
    ]

    # ----- Assert: hexapod's AssetRegistered payload carries the controller_id back-reference -----

    hexapod_registered_payload = hexapod_events[0].payload
    assert UUID(hexapod_registered_payload["controller_id"]) == _ASSET_AEROTECH_HEXAPOD_DRIVE_ID

    # ----- Assert: Procedure stream has the expected lifecycle (4 events) -----

    procedure_events, procedure_version = await deps.event_store.load("Procedure", _PROCEDURE_ID)
    assert procedure_version == 4
    assert [e.event_type for e in procedure_events] == [
        "ProcedureRegistered",
        "ProcedureStarted",
        "ProcedureActivitiesLogbookOpened",
        "ProcedureCompleted",
    ]

    # ----- Assert: 18 step entries landed in the projection -----
    # Six setpoint/action/check triplets (steps 1, 2, 4, 6, 7) + two standalone
    # sleep Actions (steps 3 and 5) = 5*3 + 2 + 3 = 17 + 1 standalone-sleep ...
    # Actually: 5 triplets (15 entries) + 2 sleeps (2 entries) + the final
    # ca_poll triplet (already counted) = wait, let me recount: steps 1, 2,
    # 4, 6, 7 are the five setpoint/action/check triplets (15 entries); steps
    # 3 and 5 are the two standalone sleep Actions (2 entries). Total = 17.
    # Re-check from the entries tuple: 5 setpoints + 5 actions + 5 checks +
    # 2 sleep actions = 17 step entries.

    await _drain(db_pool)
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT step_kind, payload FROM entries_operation_procedure_activities "
            "WHERE procedure_id = $1 ORDER BY sampled_at, event_id",
            _PROCEDURE_ID,
        )
    assert len(rows) == 17
    kinds = [r["step_kind"] for r in rows]
    # Per-step ordering is not guaranteed across siblings with identical sampled_at,
    # but the kind distribution should match: 5 setpoints, 7 actions (5 routine +
    # 2 sleeps), 5 checks = 17.
    assert kinds.count("setpoint") == 5
    assert kinds.count("action") == 7
    assert kinds.count("check") == 5

    # ----- Assert: Caution registered against Hexapod with expected shape -----

    caution_events, caution_version = await deps.event_store.load(
        "Caution", _CAUTION_HEXAPOD_LOCKUP_ID
    )
    assert caution_version == 1
    assert [e.event_type for e in caution_events] == ["CautionRegistered"]
    caution_payload = caution_events[0].payload
    assert caution_payload["target"]["kind"] == "Asset"
    assert UUID(caution_payload["target"]["id"]) == _ASSET_AEROTECH_HEXAPOD_DRIVE_ID
    assert caution_payload["category"] == "Wear"
    assert caution_payload["severity"] == "Caution"
    assert "hexapod" in caution_payload["tags"]
    assert "controller_lockup" in caution_payload["tags"]
