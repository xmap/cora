"""End-to-end: conduct resolves a pseudoaxis's constituents from Plan wires.

The runtime win for item 4a. A Phase-of-Run Procedure (`parent_run_id` set)
conducts a virtual-axis SetpointStep; the conduct handler walks
`parent_run_id -> Run.plan_id -> Plan.wires`, builds a constituent resolver
from the wires, and the pre-Conductor expander rewrites the pseudoaxis
setpoint into its constituent motor's setpoint - with NO hand-wired resolver
(unlike `test_pseudoaxis_roundtrip.py`, which injects a stub). This proves
the wires-validate-at-bind -> wires-resolve-at-conduct loop closes.

Setup mirrors the wiring ceremony of `test_2bm_hexapod_pose_wiring.py`
(typed ports + Plan + `add_plan_wire`) and the Run ladder of the start_run
tests, then conducts via the production `conduct_procedure` handler.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment.aggregates._partition_rule import Affine, Aggregation, AggregatorKind
from cora.equipment.aggregates.asset import AssetTier, PortDirection
from cora.equipment.features import (
    add_asset_family,
    add_asset_port,
    define_family,
    register_asset,
    update_asset_partition_rule,
)
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.add_asset_port import AddAssetPort
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.update_asset_partition_rule import UpdateAssetPartitionRule
from cora.infrastructure.kernel import Kernel
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.adapters.in_memory_recipe_expander import InMemoryRecipeExpander
from cora.operation.aggregates.procedure import InMemoryActivityStore
from cora.operation.conductor import Conductor, InMemoryActionRegistry, SetpointStep
from cora.operation.features import (
    abort_procedure,
    append_activities,
    complete_procedure,
    conduct_procedure,
    register_procedure,
    start_procedure,
)
from cora.operation.features.conduct_procedure import ConductProcedure
from cora.operation.features.register_procedure import RegisterProcedure
from cora.recipe.aggregates.method import ExecutionPattern
from cora.recipe.features import add_plan_wire, define_method, define_plan, define_practice
from cora.recipe.features.add_plan_wire import AddPlanWire
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_practice import DefinePractice
from cora.run.aggregates.run import RunNotFoundError
from cora.run.features import start_run
from cora.run.features.start_run import StartRun
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres

_NOW = datetime(2026, 6, 16, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-00000bad6099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000bad60aa")
_PARENT_ID = UUID("01900000-0000-7000-8000-00000bad6001")
_SITE_ID = UUID("01900000-0000-7000-8000-00000bad6002")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-00000bad6003")
_SIGNAL = "position_setpoint_linear_mm"


def _constituent_address(constituent_id: UUID) -> str:
    return f"epics_ca://{constituent_id}/setpoint"


def _build_conduct_handler(
    deps: Kernel, *, control_port: InMemoryControlPort
) -> conduct_procedure.Handler:
    """conduct_procedure wired with an expander that has NO configured
    resolver, so the handler's Plan.wiring-backed resolver is the only
    source of constituents."""
    conductor = Conductor(
        control_port=control_port,
        append_step=append_activities.bind(deps, step_store=InMemoryActivityStore()),
        clock=deps.clock,
        id_generator=deps.id_generator,
        action_registry=InMemoryActionRegistry({}),
        start_procedure=start_procedure.bind(deps),
        complete_procedure=complete_procedure.bind(deps),
        abort_procedure=abort_procedure.bind(deps),
    )
    return conduct_procedure.bind(
        deps, conductor=conductor, expansion_port=InMemoryRecipeExpander()
    )


@pytest.mark.integration
async def test_conduct_resolves_constituents_from_run_plan_wires_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(120)])

    # ----- A virtual axis (Affine, single constituent) + its motor -----
    family_id = await define_family.bind(deps)(
        DefineFamily(name="PseudoAxis", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    pseudoaxis_id = await register_asset.bind(deps)(
        RegisterAsset(name="VirtualAxis", tier=AssetTier.DEVICE, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=pseudoaxis_id, family_id=family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_port.bind(deps)(
        AddAssetPort(
            asset_id=pseudoaxis_id,
            port_name="constituent_in",
            direction=PortDirection.INPUT,
            signal_type=_SIGNAL,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # A PseudoAxis must declare exactly one OUTPUT port (the virtual-axis
    # output the operator addresses), per the Plan-wire validation.
    await add_asset_port.bind(deps)(
        AddAssetPort(
            asset_id=pseudoaxis_id,
            port_name="virtual_out",
            direction=PortDirection.OUTPUT,
            signal_type="virtual_axis_setpoint_mm",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await update_asset_partition_rule.bind(deps)(
        UpdateAssetPartitionRule(
            asset_id=pseudoaxis_id,
            partition_rule=Affine(gain=2.0, offset=1.0, unit_in="deg", unit_out="mm"),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    motor_id = await register_asset.bind(deps)(
        RegisterAsset(name="PhysicalMotor", tier=AssetTier.DEVICE, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_port.bind(deps)(
        AddAssetPort(
            asset_id=motor_id,
            port_name="out",
            direction=PortDirection.OUTPUT,
            signal_type=_SIGNAL,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Recipe ladder + a Plan that wires the motor into the axis -----
    await seed_capability_postgres(
        deps.event_store, _CAPABILITY_ID, code="cora.capability.wired_move", name="WiredMove"
    )
    method_id = await define_method.bind(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            capability_id=_CAPABILITY_ID,
            name="wired_move",
            needed_family_ids=frozenset({family_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    practice_id = await define_practice.bind(deps)(
        DefinePractice(name="wired_move_practice", method_id=method_id, site_id=_SITE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    plan_id = await define_plan.bind(deps)(
        DefinePlan(
            name="wired_move_plan",
            practice_id=practice_id,
            asset_ids=frozenset({pseudoaxis_id, motor_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_plan_wire.bind(deps)(
        AddPlanWire(
            plan_id=plan_id,
            source_asset_id=motor_id,
            source_port_name="out",
            target_asset_id=pseudoaxis_id,
            target_port_name="constituent_in",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- A Run binding the Plan + a Phase-of-Run Procedure -----
    run_id = await start_run.bind(deps)(
        StartRun(name="wired move run", plan_id=plan_id, subject_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    procedure_id = await register_procedure.bind(deps)(
        RegisterProcedure(
            name="wired move",
            kind="bakeout",
            target_asset_ids=frozenset(),
            parent_run_id=run_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Conduct the virtual-axis setpoint (resolver from the wires) -----
    control_port = InMemoryControlPort()
    control_port.simulate_connect(_constituent_address(motor_id))
    handler = _build_conduct_handler(deps, control_port=control_port)

    commanded = 4.0
    result = await handler(
        ConductProcedure(
            procedure_id=procedure_id,
            steps=(SetpointStep(address=f"pseudoaxis://{pseudoaxis_id}/virtual", value=commanded),),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert result.succeeded is True
    assert result.completed_count == 1
    # Affine forward: gain*commanded + offset = 2*4 + 1 = 9.0, dispatched to
    # the motor discovered purely from the Plan wire.
    reading = await control_port.read(_constituent_address(motor_id))
    assert reading.value == 9.0


@pytest.mark.integration
async def test_conduct_multi_constituent_orders_constituents_by_wire_port_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """A multi-constituent pseudoaxis splits across its constituents in the
    order the Plan wires assign. Uses Aggregation(Difference) so the order
    is observable end-to-end: constituent 0 gets -V/2, constituent 1 gets
    +V/2. Wiring motor_0 -> constituent_in_0 and motor_1 -> constituent_in_1
    must therefore drive motor_0 to -V/2 and motor_1 to +V/2 - proving the
    constituent ORDER comes from the wires, not insertion or hashing."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(140)])
    capability_id = uuid4()

    family_id = await define_family.bind(deps)(
        DefineFamily(name="PseudoAxis", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    pseudoaxis_id = await register_asset.bind(deps)(
        RegisterAsset(name="VirtualDiff", tier=AssetTier.DEVICE, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=pseudoaxis_id, family_id=family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    for input_port in ("constituent_in_0", "constituent_in_1"):
        await add_asset_port.bind(deps)(
            AddAssetPort(
                asset_id=pseudoaxis_id,
                port_name=input_port,
                direction=PortDirection.INPUT,
                signal_type=_SIGNAL,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    await add_asset_port.bind(deps)(
        AddAssetPort(
            asset_id=pseudoaxis_id,
            port_name="virtual_out",
            direction=PortDirection.OUTPUT,
            signal_type="virtual_axis_setpoint_mm",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await update_asset_partition_rule.bind(deps)(
        UpdateAssetPartitionRule(
            asset_id=pseudoaxis_id,
            partition_rule=Aggregation(
                aggregator_kind=AggregatorKind.DIFFERENCE, constituent_count=2
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    motor_ids: list[UUID] = []
    for name in ("Motor0", "Motor1"):
        motor_id = await register_asset.bind(deps)(
            RegisterAsset(name=name, tier=AssetTier.DEVICE, parent_id=_PARENT_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        await add_asset_port.bind(deps)(
            AddAssetPort(
                asset_id=motor_id,
                port_name="out",
                direction=PortDirection.OUTPUT,
                signal_type=_SIGNAL,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        motor_ids.append(motor_id)
    motor_0, motor_1 = motor_ids

    await seed_capability_postgres(
        deps.event_store, capability_id, code="cora.capability.wired_diff", name="WiredDiff"
    )
    method_id = await define_method.bind(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            capability_id=capability_id,
            name="wired_diff",
            needed_family_ids=frozenset({family_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    practice_id = await define_practice.bind(deps)(
        DefinePractice(name="wired_diff_practice", method_id=method_id, site_id=_SITE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    plan_id = await define_plan.bind(deps)(
        DefinePlan(
            name="wired_diff_plan",
            practice_id=practice_id,
            asset_ids=frozenset({pseudoaxis_id, motor_0, motor_1}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # motor_0 -> constituent_in_0, motor_1 -> constituent_in_1: the port
    # names assign the constituent order.
    for motor_id, input_port in ((motor_0, "constituent_in_0"), (motor_1, "constituent_in_1")):
        await add_plan_wire.bind(deps)(
            AddPlanWire(
                plan_id=plan_id,
                source_asset_id=motor_id,
                source_port_name="out",
                target_asset_id=pseudoaxis_id,
                target_port_name=input_port,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    run_id = await start_run.bind(deps)(
        StartRun(name="diff run", plan_id=plan_id, subject_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    procedure_id = await register_procedure.bind(deps)(
        RegisterProcedure(
            name="diff move",
            kind="bakeout",
            target_asset_ids=frozenset(),
            parent_run_id=run_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    control_port = InMemoryControlPort()
    control_port.simulate_connect(_constituent_address(motor_0))
    control_port.simulate_connect(_constituent_address(motor_1))
    handler = _build_conduct_handler(deps, control_port=control_port)

    commanded = 6.0
    result = await handler(
        ConductProcedure(
            procedure_id=procedure_id,
            steps=(SetpointStep(address=f"pseudoaxis://{pseudoaxis_id}/virtual", value=commanded),),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert result.succeeded is True
    assert result.completed_count == 2
    # Difference split is (-V/2, +V/2): constituent 0 (motor_0, wired to
    # constituent_in_0) gets -3.0; constituent 1 (motor_1) gets +3.0.
    assert (await control_port.read(_constituent_address(motor_0))).value == -3.0
    assert (await control_port.read(_constituent_address(motor_1))).value == 3.0


@pytest.mark.integration
async def test_conduct_phase_of_run_procedure_with_dangling_run_raises_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """A Phase-of-Run Procedure whose `parent_run_id` references no Run is
    corruption: conduct refuses with `RunNotFoundError` rather than silently
    skipping wire resolution. `register_procedure` does not validate
    `parent_run_id`, so a dangling reference is constructible, and the
    resolver block raises before any actuation."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(20)])
    missing_run_id = uuid4()
    procedure_id = await register_procedure.bind(deps)(
        RegisterProcedure(
            name="orphan phase",
            kind="bakeout",
            target_asset_ids=frozenset(),
            parent_run_id=missing_run_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    handler = _build_conduct_handler(deps, control_port=InMemoryControlPort())

    with pytest.raises(RunNotFoundError):
        await handler(
            ConductProcedure(
                procedure_id=procedure_id,
                steps=(SetpointStep(address="epics_ca://noop/setpoint", value=0.0),),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
