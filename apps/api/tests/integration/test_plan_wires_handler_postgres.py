"""End-to-end integration test: add_plan_wire + remove_plan_wire against real Postgres.

Round-trips the new events through real PG, including the cross-
aggregate Asset loads that validate Wire endpoints (port-existence,
direction, signal_type). Mirrors `test_update_plan_default_parameters_handler_postgres.py`
shape but exercises Plan.wires.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment.aggregates.asset.events import (
    AssetPortAdded,
    AssetRegistered,
)
from cora.equipment.aggregates.asset.events import event_type_name as asset_event_type_name
from cora.equipment.aggregates.asset.events import to_payload as asset_to_payload
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.recipe.aggregates.plan import Wire, load_plan
from cora.recipe.aggregates.plan.events import (
    PlanDefined,
    event_type_name,
    to_payload,
)
from cora.recipe.features import add_plan_wire, remove_plan_wire
from cora.recipe.features.add_plan_wire import AddPlanWire
from cora.recipe.features.remove_plan_wire import RemovePlanWire
from cora.shared.identity import ActorId
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(db_pool: asyncpg.Pool, ids: list[UUID]) -> Kernel:
    return build_postgres_deps(db_pool, now=_NOW, ids=ids)


async def _seed_asset_with_port(
    deps: Kernel,
    asset_id: UUID,
    *,
    name: str,
    port_name: str,
    direction: str,
    signal_type: str,
) -> None:
    """Seed an Asset with a single port directly into the event store."""
    register = AssetRegistered(
        asset_id=asset_id,
        name=name,
        tier="Device",
        parent_id=None,
        occurred_at=_NOW,
        commissioned_by=ActorId(uuid4()),
    )
    add_port = AssetPortAdded(
        asset_id=asset_id,
        port_name=port_name,
        direction=direction,
        signal_type=signal_type,
        occurred_at=_NOW,
    )
    events = []
    for ev in (register, add_port):
        events.append(
            to_new_event(
                event_type=asset_event_type_name(ev),
                payload=asset_to_payload(ev),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="Seed",
                correlation_id=_CORRELATION_ID,
                principal_id=_PRINCIPAL_ID,
            )
        )
    await deps.event_store.append(
        stream_type="Asset", stream_id=asset_id, expected_version=0, events=events
    )


async def _seed_plan(
    deps: Kernel,
    plan_id: UUID,
    *,
    asset_ids: tuple[UUID, ...],
) -> None:
    """Seed a Plan binding the given Asset ids."""
    practice_id = uuid4()
    method_id = uuid4()
    event = PlanDefined(
        plan_id=plan_id,
        name="32-ID Triggered Acquisition",
        practice_id=practice_id,
        asset_ids=asset_ids,
        method_id=method_id,
        method_needed_family_ids_snapshot=(),
        asset_families_snapshot={a: () for a in asset_ids},
        occurred_at=_NOW,
    )
    await deps.event_store.append(
        stream_type="Plan",
        stream_id=plan_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="DefinePlan",
                correlation_id=_CORRELATION_ID,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )


@pytest.mark.integration
async def test_add_plan_wire_round_trips_event_against_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """Full end-to-end: seed source/target Assets with ports, seed Plan,
    add a Wire, fold-on-read shows the Wire in Plan.wires."""
    src_asset_id = uuid4()
    tgt_asset_id = uuid4()
    plan_id = uuid4()
    deps = _build_deps(db_pool, [uuid4()])  # one event id for the Wire-add event

    await _seed_asset_with_port(
        deps,
        src_asset_id,
        name="PandABox",
        port_name="trigger_out",
        direction="Output",
        signal_type="TTL",
    )
    await _seed_asset_with_port(
        deps,
        tgt_asset_id,
        name="Camera",
        port_name="trigger_in",
        direction="Input",
        signal_type="TTL",
    )
    await _seed_plan(deps, plan_id, asset_ids=(src_asset_id, tgt_asset_id))

    await add_plan_wire.bind(deps)(
        AddPlanWire(
            plan_id=plan_id,
            source_asset_id=src_asset_id,
            source_port_name="trigger_out",
            target_asset_id=tgt_asset_id,
            target_port_name="trigger_in",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    loaded = await load_plan(deps.event_store, plan_id)
    assert loaded is not None
    expected = Wire(
        source_asset_id=src_asset_id,
        source_port_name="trigger_out",
        target_asset_id=tgt_asset_id,
        target_port_name="trigger_in",
    )
    assert loaded.wires == frozenset({expected})


@pytest.mark.integration
async def test_remove_plan_wire_clears_wire_from_state_against_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """Full end-to-end: add then remove the same Wire. Plan.wires ends empty."""
    src_asset_id = uuid4()
    tgt_asset_id = uuid4()
    plan_id = uuid4()
    deps = _build_deps(db_pool, [uuid4(), uuid4()])  # add + remove event ids

    await _seed_asset_with_port(
        deps,
        src_asset_id,
        name="PandABox",
        port_name="trigger_out",
        direction="Output",
        signal_type="TTL",
    )
    await _seed_asset_with_port(
        deps,
        tgt_asset_id,
        name="Camera",
        port_name="trigger_in",
        direction="Input",
        signal_type="TTL",
    )
    await _seed_plan(deps, plan_id, asset_ids=(src_asset_id, tgt_asset_id))

    add_handler = add_plan_wire.bind(deps)
    remove_handler = remove_plan_wire.bind(deps)

    await add_handler(
        AddPlanWire(
            plan_id=plan_id,
            source_asset_id=src_asset_id,
            source_port_name="trigger_out",
            target_asset_id=tgt_asset_id,
            target_port_name="trigger_in",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await remove_handler(
        RemovePlanWire(
            plan_id=plan_id,
            source_asset_id=src_asset_id,
            source_port_name="trigger_out",
            target_asset_id=tgt_asset_id,
            target_port_name="trigger_in",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    loaded = await load_plan(deps.event_store, plan_id)
    assert loaded is not None
    assert loaded.wires == frozenset()
