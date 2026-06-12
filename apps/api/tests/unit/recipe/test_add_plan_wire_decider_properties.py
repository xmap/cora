"""Property-based tests for `add_plan_wire.decide` (Recipe BC).

Complements the example-based `test_add_plan_wire_decider.py` with
universal claims across generated inputs. This is a cross-aggregate
decider validating a proposed Wire against loaded Asset state carried
in a context:

    (state, command, context, now) -> list[PlanWireAdded]

Load-bearing properties:

  - Empty state (no prior Plan events) always raises
    `PlanNotFoundError` carrying the command's plan_id.
  - A Wire already present in `state.wires` always raises
    `PlanWireAlreadyExistsError` (strict-not-idempotent re-add).
  - A structurally valid wire against bound, port-carrying,
    direction- and signal-type-compatible Assets emits exactly one
    `PlanWireAdded` keyed on state.id with occurred_at=now, across any
    Plan lifecycle status (wire mutation is lifecycle-independent).
  - Pure: same inputs return equal results (no clock leakage).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.equipment.aggregates.asset import (
    Asset,
    AssetLifecycle,
    AssetName,
    AssetPort,
    AssetTier,
    PortDirection,
)
from cora.recipe.aggregates.plan import (
    Plan,
    PlanName,
    PlanNotFoundError,
    PlanStatus,
    PlanWireAdded,
    PlanWireAlreadyExistsError,
    Wire,
)
from cora.recipe.features import add_plan_wire
from cora.recipe.features.add_plan_wire import AddPlanWire, PlanWireContext
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_LIFECYCLE_STATES = (
    PlanStatus.DEFINED,
    PlanStatus.VERSIONED,
    PlanStatus.DEPRECATED,
)


def _asset(
    *,
    asset_id: UUID,
    ports: frozenset[AssetPort] = frozenset(),
) -> Asset:
    return Asset(
        id=asset_id,
        name=AssetName("Test Asset"),
        tier=AssetTier.DEVICE,
        parent_id=None,
        lifecycle=AssetLifecycle.ACTIVE,
        ports=ports,
        family_ids=frozenset(),
        partition_rule=None,
    )


def _plan(
    *,
    plan_id: UUID,
    asset_ids: frozenset[UUID],
    status: PlanStatus = PlanStatus.DEFINED,
    wires: frozenset[Wire] = frozenset(),
) -> Plan:
    return Plan(
        id=plan_id,
        name=PlanName("32-ID FlyScan"),
        practice_id=UUID(int=1),
        asset_ids=asset_ids,
        status=status,
        method_id=UUID(int=2),
        wires=wires,
    )


def _ports(*defs: tuple[str, PortDirection, str]) -> frozenset[AssetPort]:
    return frozenset(
        AssetPort(name=name, direction=direction, signal_type=signal_type)
        for name, direction, signal_type in defs
    )


def _compatible_context(src_id: UUID, tgt_id: UUID) -> PlanWireContext:
    return PlanWireContext(
        assets={
            src_id: _asset(
                asset_id=src_id,
                ports=_ports(("trigger_out", PortDirection.OUTPUT, "TTL")),
            ),
            tgt_id: _asset(
                asset_id=tgt_id,
                ports=_ports(("trigger_in", PortDirection.INPUT, "TTL")),
            ),
        }
    )


@pytest.mark.unit
@given(
    plan_id=st.uuids(),
    source_asset_id=st.uuids(),
    target_asset_id=st.uuids(),
    source_port_name=printable_ascii_text(max_size=16),
    target_port_name=printable_ascii_text(max_size=16),
    now=aware_datetimes(),
)
def test_add_plan_wire_empty_state_raises_plan_not_found(
    plan_id: UUID,
    source_asset_id: UUID,
    target_asset_id: UUID,
    source_port_name: str,
    target_port_name: str,
    now: datetime,
) -> None:
    """A wire add against a non-existent Plan always raises PlanNotFoundError."""
    with pytest.raises(PlanNotFoundError):
        add_plan_wire.decide(
            state=None,
            command=AddPlanWire(
                plan_id=plan_id,
                source_asset_id=source_asset_id,
                source_port_name=source_port_name,
                target_asset_id=target_asset_id,
                target_port_name=target_port_name,
            ),
            context=PlanWireContext(assets={}),
            now=now,
        )


@pytest.mark.unit
@given(
    plan_id=st.uuids(),
    src_id=st.uuids(),
    tgt_id=st.uuids(),
    status=st.sampled_from(_LIFECYCLE_STATES),
    now=aware_datetimes(),
)
def test_add_plan_wire_duplicate_wire_raises_already_exists(
    plan_id: UUID,
    src_id: UUID,
    tgt_id: UUID,
    status: PlanStatus,
    now: datetime,
) -> None:
    """Re-adding a wire already in state.wires always raises PlanWireAlreadyExistsError."""
    assume(src_id != tgt_id)
    existing = Wire(
        source_asset_id=src_id,
        source_port_name="trigger_out",
        target_asset_id=tgt_id,
        target_port_name="trigger_in",
    )
    state = _plan(
        plan_id=plan_id,
        asset_ids=frozenset({src_id, tgt_id}),
        status=status,
        wires=frozenset({existing}),
    )
    with pytest.raises(PlanWireAlreadyExistsError):
        add_plan_wire.decide(
            state=state,
            command=AddPlanWire(
                plan_id=state.id,
                source_asset_id=src_id,
                source_port_name="trigger_out",
                target_asset_id=tgt_id,
                target_port_name="trigger_in",
            ),
            context=_compatible_context(src_id, tgt_id),
            now=now,
        )


@pytest.mark.unit
@given(
    plan_id=st.uuids(),
    src_id=st.uuids(),
    tgt_id=st.uuids(),
    status=st.sampled_from(_LIFECYCLE_STATES),
    now=aware_datetimes(),
)
def test_add_plan_wire_valid_endpoints_emits_wire_added_keyed_on_state_id(
    plan_id: UUID,
    src_id: UUID,
    tgt_id: UUID,
    status: PlanStatus,
    now: datetime,
) -> None:
    """A valid wire emits exactly one PlanWireAdded with state.id and occurred_at=now."""
    assume(src_id != tgt_id)
    state = _plan(
        plan_id=plan_id,
        asset_ids=frozenset({src_id, tgt_id}),
        status=status,
    )
    events = add_plan_wire.decide(
        state=state,
        command=AddPlanWire(
            plan_id=state.id,
            source_asset_id=src_id,
            source_port_name="trigger_out",
            target_asset_id=tgt_id,
            target_port_name="trigger_in",
        ),
        context=_compatible_context(src_id, tgt_id),
        now=now,
    )
    assert events == [
        PlanWireAdded(
            plan_id=state.id,
            source_asset_id=src_id,
            source_port_name="trigger_out",
            target_asset_id=tgt_id,
            target_port_name="trigger_in",
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    plan_id=st.uuids(),
    src_id=st.uuids(),
    tgt_id=st.uuids(),
    now=aware_datetimes(),
)
def test_add_plan_wire_is_pure_same_input_same_output(
    plan_id: UUID,
    src_id: UUID,
    tgt_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal results (no clock leakage)."""
    assume(src_id != tgt_id)
    state = _plan(plan_id=plan_id, asset_ids=frozenset({src_id, tgt_id}))
    command = AddPlanWire(
        plan_id=state.id,
        source_asset_id=src_id,
        source_port_name="trigger_out",
        target_asset_id=tgt_id,
        target_port_name="trigger_in",
    )
    first = add_plan_wire.decide(
        state=state,
        command=command,
        context=_compatible_context(src_id, tgt_id),
        now=now,
    )
    second = add_plan_wire.decide(
        state=state,
        command=command,
        context=_compatible_context(src_id, tgt_id),
        now=now,
    )
    assert first == second
