"""End-to-end integration: PseudoAxis virtual-axis SetpointStep round-trip.

Exercises the full Slice 2 path: a PseudoAxis Asset with an Aggregation
partition rule is set up via Slice 1 slices; a Procedure with a single
SetpointStep targeting `pseudoaxis://<asset_id>/virtual_y` is conducted;
the pre-Conductor PseudoAxis expansion rewrites the virtual-axis step
into N constituent SetpointSteps; the Conductor walks the constituents
sequentially, each emitting a `controlport.dispatch` event carrying the
shared correlation_id; the InMemoryControlPort store reflects the
resolved constituent values.

The Postgres event-store fixture pattern mirrors
`test_update_asset_settings_handler_postgres.py`. The expansion port
is hand-constructed with a stub constituent_resolver and the canonical
PseudoAxis Family id so the wiring-deferred default does not reject the
virtual-axis address.
"""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest
import structlog.testing

from cora.equipment.aggregates._partition_rule import (
    Affine,
    Aggregation,
    AggregatorKind,
)
from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.features import (
    add_asset_family,
    define_family,
    register_asset,
    update_asset_partition_rule,
)
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.update_asset_partition_rule import (
    UpdateAssetPartitionRule,
)
from cora.infrastructure.kernel import Kernel
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.adapters.in_memory_recipe_expander import (
    InMemoryRecipeExpander,
)
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
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 5, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-00000bad0099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000bad00aa")
_PARENT_ID = UUID("01900000-0000-7000-8000-00000bad0001")

_DISPATCH_EVENT = "controlport.dispatch"
_DISPATCH_COMPLETED_EVENT = "controlport.dispatch.completed"


def _dispatch_started(
    captured: Sequence[Mapping[str, object]],
) -> list[Mapping[str, object]]:
    return [e for e in captured if e.get("event") == _DISPATCH_EVENT]


def _dispatch_completed(
    captured: Sequence[Mapping[str, object]],
) -> list[Mapping[str, object]]:
    return [e for e in captured if e.get("event") == _DISPATCH_COMPLETED_EVENT]


async def _setup_pseudoaxis_asset_with_aggregation(
    deps: Kernel,
    *,
    constituent_count: int,
) -> tuple[UUID, tuple[UUID, ...], UUID]:
    """Define the PseudoAxis Family, register the virtual Asset + N
    constituent Assets, attach the Family to the virtual Asset, and
    install an Aggregation(Sum) partition rule.

    Returns `(pseudoaxis_asset_id, constituent_asset_ids, family_id)`.
    """
    family_id = await define_family.bind(deps)(
        DefineFamily(name="PseudoAxis", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    pseudoaxis_asset_id = await register_asset.bind(deps)(
        RegisterAsset(name="VirtualY", tier=AssetTier.DEVICE, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=pseudoaxis_asset_id, family_id=family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    rule = Aggregation(
        aggregator_kind=AggregatorKind.SUM,
        constituent_count=constituent_count,
    )
    await update_asset_partition_rule.bind(deps)(
        UpdateAssetPartitionRule(asset_id=pseudoaxis_asset_id, partition_rule=rule),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    constituent_ids: list[UUID] = []
    for i in range(constituent_count):
        constituent_id = await register_asset.bind(deps)(
            RegisterAsset(name=f"PhysicalY{i}", tier=AssetTier.DEVICE, parent_id=_PARENT_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        constituent_ids.append(constituent_id)
    return pseudoaxis_asset_id, tuple(constituent_ids), family_id


def _constituent_address(constituent_id: UUID) -> str:
    return f"epics_ca://{constituent_id}/setpoint"


def _build_conduct_handler(
    deps: Kernel,
    *,
    control_port: InMemoryControlPort,
    constituent_map: Mapping[UUID, tuple[UUID, ...]],
) -> conduct_procedure.Handler:
    """Compose conduct_procedure with the same wiring as `wire_operation`
    plus a populated `InMemoryRecipeExpander` so the PseudoAxis
    address resolves against the supplied constituent map."""
    append_step = append_activities.bind(deps, step_store=InMemoryActivityStore())
    start_handler = start_procedure.bind(deps)
    complete_handler = complete_procedure.bind(deps)
    abort_handler = abort_procedure.bind(deps)
    conductor = Conductor(
        control_port=control_port,
        append_step=append_step,
        clock=deps.clock,
        id_generator=deps.id_generator,
        action_registry=InMemoryActionRegistry({}),
        start_procedure=start_handler,
        complete_procedure=complete_handler,
        abort_procedure=abort_handler,
    )

    def resolver(asset_id: UUID) -> tuple[UUID, ...]:
        return constituent_map[asset_id]

    expansion_port = InMemoryRecipeExpander(constituent_resolver=resolver)
    return conduct_procedure.bind(deps, conductor=conductor, expansion_port=expansion_port)


@pytest.mark.integration
async def test_conduct_pseudoaxis_setpoint_fans_out_to_two_constituents_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    ids = [UUID(int=0x01900000_0000_7000_8000_00000BAD1000 + i) for i in range(60)]
    deps = build_postgres_deps(db_pool, now=_NOW, ids=ids)

    (
        pseudoaxis_asset_id,
        constituent_ids,
        _family_id,
    ) = await _setup_pseudoaxis_asset_with_aggregation(deps, constituent_count=2)

    procedure_id = await register_procedure.bind(deps)(
        RegisterProcedure(
            name="VirtualMove",
            kind="bakeout",
            target_asset_ids=frozenset(),
            parent_run_id=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    control_port = InMemoryControlPort()
    for cid in constituent_ids:
        control_port.simulate_connect(_constituent_address(cid))

    handler = _build_conduct_handler(
        deps,
        control_port=control_port,
        constituent_map={pseudoaxis_asset_id: constituent_ids},
    )

    commanded = 10.0
    with structlog.testing.capture_logs() as captured:
        result = await handler(
            ConductProcedure(
                procedure_id=procedure_id,
                steps=(
                    SetpointStep(
                        address=f"pseudoaxis://{pseudoaxis_asset_id}/virtual_y",
                        value=commanded,
                    ),
                ),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    assert result.succeeded is True
    assert result.failure is None
    assert result.completed_count == 2

    started = _dispatch_started(captured)
    completed = _dispatch_completed(captured)
    assert len(started) == 2
    assert len(completed) == 2
    assert {e["address"] for e in started} == {_constituent_address(cid) for cid in constituent_ids}
    assert all(e["correlation_id"] == str(_CORRELATION_ID) for e in started)
    assert all(e["correlation_id"] == str(_CORRELATION_ID) for e in completed)

    half = commanded / 2.0
    for cid in constituent_ids:
        reading = await control_port.read(_constituent_address(cid))
        assert reading.value == half
        assert reading.quality == "Good"

    events, _version = await deps.event_store.load("Procedure", procedure_id)
    event_types = [e.event_type for e in events]
    assert event_types[0] == "ProcedureRegistered"
    assert "ProcedureStarted" in event_types
    assert "ProcedureCompleted" in event_types


@pytest.mark.integration
async def test_conduct_pseudoaxis_setpoint_with_affine_rule_fans_out_to_one_constituent_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    ids = [UUID(int=0x01900000_0000_7000_8000_00000BAD2000 + i) for i in range(60)]
    deps = build_postgres_deps(db_pool, now=_NOW, ids=ids)

    family_id = await define_family.bind(deps)(
        DefineFamily(name="PseudoAxis", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    pseudoaxis_asset_id = await register_asset.bind(deps)(
        RegisterAsset(name="VirtualY", tier=AssetTier.DEVICE, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=pseudoaxis_asset_id, family_id=family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await update_asset_partition_rule.bind(deps)(
        UpdateAssetPartitionRule(
            asset_id=pseudoaxis_asset_id,
            partition_rule=Affine(gain=2.0, offset=1.0, unit_in="deg", unit_out="mm"),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    constituent_id = await register_asset.bind(deps)(
        RegisterAsset(name="PhysicalY", tier=AssetTier.DEVICE, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    procedure_id = await register_procedure.bind(deps)(
        RegisterProcedure(
            name="VirtualMoveAffine",
            kind="bakeout",
            target_asset_ids=frozenset(),
            parent_run_id=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    control_port = InMemoryControlPort()
    control_port.simulate_connect(_constituent_address(constituent_id))

    handler = _build_conduct_handler(
        deps,
        control_port=control_port,
        constituent_map={pseudoaxis_asset_id: (constituent_id,)},
    )

    commanded = 4.0
    with structlog.testing.capture_logs() as captured:
        result = await handler(
            ConductProcedure(
                procedure_id=procedure_id,
                steps=(
                    SetpointStep(
                        address=f"pseudoaxis://{pseudoaxis_asset_id}/virtual_y",
                        value=commanded,
                    ),
                ),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    assert result.succeeded is True
    assert result.completed_count == 1

    started = _dispatch_started(captured)
    assert len(started) == 1
    assert started[0]["address"] == _constituent_address(constituent_id)
    assert started[0]["correlation_id"] == str(_CORRELATION_ID)

    reading = await control_port.read(_constituent_address(constituent_id))
    assert reading.value == 2.0 * commanded + 1.0
