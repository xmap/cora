"""Property-based tests for `remove_plan_wire.decide` (Recipe BC).

Complements the example-based `test_remove_plan_wire_decider.py` with
universal claims across generated inputs. The decider is a pure
guard-free set-difference mutation

    (state, command, now) -> list[PlanWireRemoved]

It has no status partition: removal is a structural operation on the
wire set, so any `PlanStatus` with the target wire present emits the
event. The only "absent source" partition is a wire not in the set.

Load-bearing properties:

  - state=None always raises `PlanNotFoundError` carrying command.plan_id.
  - A wire that is NOT in `state.wires` always raises
    `PlanWireNotFoundError` carrying the proposed Wire
    (strict-not-idempotent), regardless of the Plan's status.
  - A wire that IS in `state.wires` emits exactly one `PlanWireRemoved`
    carrying the full 4-tuple and occurred_at=now, for ANY `PlanStatus`
    (removal is status-independent).
  - The emitted event's plan_id is `state.id`, never `command.plan_id`.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.recipe.aggregates.plan import (
    Plan,
    PlanName,
    PlanNotFoundError,
    PlanStatus,
    PlanWireNotFoundError,
    PlanWireRemoved,
    Wire,
)
from cora.recipe.features import remove_plan_wire
from cora.recipe.features.remove_plan_wire import RemovePlanWire
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_SOURCE_PORT = "trigger_out"
_TARGET_PORT = "trigger_in"


def _plan(*, plan_id: UUID, status: PlanStatus, wires: frozenset[Wire]) -> Plan:
    return Plan(
        id=plan_id,
        name=PlanName("32-ID FlyScan"),
        practice_id=UUID(int=1),
        asset_ids=frozenset({UUID(int=2)}),
        status=status,
        method_id=UUID(int=3),
        wires=wires,
    )


def _command(
    *,
    plan_id: UUID,
    source_asset_id: UUID,
    target_asset_id: UUID,
    source_port_name: str = _SOURCE_PORT,
    target_port_name: str = _TARGET_PORT,
) -> RemovePlanWire:
    return RemovePlanWire(
        plan_id=plan_id,
        source_asset_id=source_asset_id,
        source_port_name=source_port_name,
        target_asset_id=target_asset_id,
        target_port_name=target_port_name,
    )


@pytest.mark.unit
@given(
    plan_id=st.uuids(),
    source_asset_id=st.uuids(),
    target_asset_id=st.uuids(),
    now=aware_datetimes(),
)
def test_remove_with_none_state_always_raises_not_found(
    plan_id: UUID,
    source_asset_id: UUID,
    target_asset_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `PlanNotFoundError` carrying command.plan_id."""
    with pytest.raises(PlanNotFoundError) as exc:
        remove_plan_wire.decide(
            state=None,
            command=_command(
                plan_id=plan_id,
                source_asset_id=source_asset_id,
                target_asset_id=target_asset_id,
            ),
            now=now,
        )
    assert exc.value.plan_id == plan_id


@pytest.mark.unit
@given(
    plan_id=st.uuids(),
    source_asset_id=st.uuids(),
    target_asset_id=st.uuids(),
    status=st.sampled_from(PlanStatus),
    now=aware_datetimes(),
)
def test_remove_absent_wire_always_raises_wire_not_found(
    plan_id: UUID,
    source_asset_id: UUID,
    target_asset_id: UUID,
    status: PlanStatus,
    now: datetime,
) -> None:
    """A wire not in the set raises, carrying the proposed Wire, for any status."""
    with pytest.raises(PlanWireNotFoundError) as exc:
        remove_plan_wire.decide(
            state=_plan(plan_id=plan_id, status=status, wires=frozenset()),
            command=_command(
                plan_id=plan_id,
                source_asset_id=source_asset_id,
                target_asset_id=target_asset_id,
            ),
            now=now,
        )
    assert exc.value.wire == Wire(
        source_asset_id=source_asset_id,
        source_port_name=_SOURCE_PORT,
        target_asset_id=target_asset_id,
        target_port_name=_TARGET_PORT,
    )


@pytest.mark.unit
@given(
    plan_id=st.uuids(),
    source_asset_id=st.uuids(),
    target_asset_id=st.uuids(),
    source_port_name=printable_ascii_text(max_size=100),
    target_port_name=printable_ascii_text(max_size=100),
    status=st.sampled_from(PlanStatus),
    now=aware_datetimes(),
)
def test_remove_present_wire_emits_single_event_for_any_status(
    plan_id: UUID,
    source_asset_id: UUID,
    target_asset_id: UUID,
    source_port_name: str,
    target_port_name: str,
    status: PlanStatus,
    now: datetime,
) -> None:
    """A wire in the set emits exactly one PlanWireRemoved, status-independent."""
    existing = Wire(
        source_asset_id=source_asset_id,
        source_port_name=source_port_name,
        target_asset_id=target_asset_id,
        target_port_name=target_port_name,
    )
    events = remove_plan_wire.decide(
        state=_plan(plan_id=plan_id, status=status, wires=frozenset({existing})),
        command=_command(
            plan_id=plan_id,
            source_asset_id=source_asset_id,
            target_asset_id=target_asset_id,
            source_port_name=source_port_name,
            target_port_name=target_port_name,
        ),
        now=now,
    )
    assert events == [
        PlanWireRemoved(
            plan_id=plan_id,
            source_asset_id=existing.source_asset_id,
            source_port_name=existing.source_port_name,
            target_asset_id=existing.target_asset_id,
            target_port_name=existing.target_port_name,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    state_plan_id=st.uuids(),
    command_plan_id=st.uuids(),
    source_asset_id=st.uuids(),
    target_asset_id=st.uuids(),
    now=aware_datetimes(),
)
def test_remove_emits_event_with_state_id_not_command_plan_id(
    state_plan_id: UUID,
    command_plan_id: UUID,
    source_asset_id: UUID,
    target_asset_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's plan_id is state.id, not command.plan_id."""
    assume(state_plan_id != command_plan_id)
    existing = Wire(
        source_asset_id=source_asset_id,
        source_port_name=_SOURCE_PORT,
        target_asset_id=target_asset_id,
        target_port_name=_TARGET_PORT,
    )
    events = remove_plan_wire.decide(
        state=_plan(
            plan_id=state_plan_id,
            status=PlanStatus.DEFINED,
            wires=frozenset({existing}),
        ),
        command=_command(
            plan_id=command_plan_id,
            source_asset_id=source_asset_id,
            target_asset_id=target_asset_id,
        ),
        now=now,
    )
    assert events[0].plan_id == state_plan_id


@pytest.mark.unit
@given(
    plan_id=st.uuids(),
    source_asset_id=st.uuids(),
    target_asset_id=st.uuids(),
    now=aware_datetimes(),
)
def test_remove_is_pure_same_input_same_output(
    plan_id: UUID,
    source_asset_id: UUID,
    target_asset_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    existing = Wire(
        source_asset_id=source_asset_id,
        source_port_name=_SOURCE_PORT,
        target_asset_id=target_asset_id,
        target_port_name=_TARGET_PORT,
    )
    state = _plan(
        plan_id=plan_id,
        status=PlanStatus.DEFINED,
        wires=frozenset({existing}),
    )
    command = _command(
        plan_id=plan_id,
        source_asset_id=source_asset_id,
        target_asset_id=target_asset_id,
    )
    first = remove_plan_wire.decide(state=state, command=command, now=now)
    second = remove_plan_wire.decide(state=state, command=command, now=now)
    assert first == second
