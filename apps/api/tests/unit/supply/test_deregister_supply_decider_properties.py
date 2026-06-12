"""Property-based tests for `deregister_supply.decide` (Supply BC).

Complements the example-based `test_deregister_supply_decider.py` with
universal claims across generated inputs. The decider is a pure
operator-driven FSM transition

    (state, command, now, triggered_by) -> list[SupplyDeregistered]

so the load-bearing properties are about the source-state partition
and field threading:

  - state=None always raises `SupplyNotFoundError`, regardless of
    command shape.
  - Every source status in the permitted set (any status except
    Decommissioned; lifecycle terminal; widest source set) emits
    exactly one `SupplyDeregistered` whose audit fields (supply_id,
    from_status, reason, trigger, triggered_by, occurred_at) are the
    threaded inputs; trigger is always "Operator" and monitor_ref is
    absent (operator path).
  - Every source status outside the permitted set (Decommissioned)
    always raises `SupplyCannotDeregisterError` carrying the current
    status. The partition is total over `SupplyStatus`, so a future
    status value cannot silently fall through.
  - The emitted event's supply_id is `state.id`, never
    `command.supply_id` (source-of-truth id invariant).
  - Pure: same (state, command, now, triggered_by) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from cora.supply.aggregates.supply import (
    Supply,
    SupplyCannotDeregisterError,
    SupplyDeregistered,
    SupplyName,
    SupplyNotFoundError,
    SupplyStatus,
)
from cora.supply.features import deregister_supply
from cora.supply.features.deregister_supply import DeregisterSupply
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_REASON = printable_ascii_text(min_size=1, max_size=500)
_FACILITY_CODE = FacilityCode("aps")

_PERMITTED_SOURCES = (
    SupplyStatus.UNKNOWN,
    SupplyStatus.AVAILABLE,
    SupplyStatus.DEGRADED,
    SupplyStatus.UNAVAILABLE,
    SupplyStatus.RECOVERING,
)
_DISALLOWED_SOURCES = tuple(s for s in SupplyStatus if s not in frozenset(_PERMITTED_SOURCES))


def _state(*, supply_id: UUID, status: SupplyStatus) -> Supply:
    return Supply(
        id=supply_id,
        kind="LiquidNitrogen",
        name=SupplyName("2-BM LN2"),
        facility_code=_FACILITY_CODE,
        status=status,
    )


def _command(*, supply_id: UUID, reason: str) -> DeregisterSupply:
    return DeregisterSupply(supply_id=supply_id, reason=reason)


@pytest.mark.unit
@given(
    supply_id=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
    triggered_by_uuid=st.uuids(),
)
def test_deregister_with_none_state_always_raises_not_found(
    supply_id: UUID,
    reason: str,
    now: datetime,
    triggered_by_uuid: UUID,
) -> None:
    """Empty stream always raises `SupplyNotFoundError` carrying command.supply_id."""
    with pytest.raises(SupplyNotFoundError) as exc:
        deregister_supply.decide(
            state=None,
            command=_command(supply_id=supply_id, reason=reason),
            now=now,
            triggered_by=ActorId(triggered_by_uuid),
        )
    assert exc.value.supply_id == supply_id


@pytest.mark.unit
@given(
    supply_id=st.uuids(),
    source=st.sampled_from(_PERMITTED_SOURCES),
    reason=_REASON,
    now=aware_datetimes(),
    triggered_by_uuid=st.uuids(),
)
def test_deregister_from_permitted_source_emits_single_event(
    supply_id: UUID,
    source: SupplyStatus,
    reason: str,
    now: datetime,
    triggered_by_uuid: UUID,
) -> None:
    """Any permitted source emits one SupplyDeregistered with threaded fields."""
    triggered_by = ActorId(triggered_by_uuid)
    events = deregister_supply.decide(
        state=_state(supply_id=supply_id, status=source),
        command=_command(supply_id=supply_id, reason=reason),
        now=now,
        triggered_by=triggered_by,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, SupplyDeregistered)
    assert event.supply_id == supply_id
    assert event.from_status == source.value
    assert event.reason == reason
    assert event.trigger == "Operator"
    assert event.triggered_by == triggered_by
    assert event.occurred_at == now
    assert event.monitor_ref is None


@pytest.mark.unit
@given(
    supply_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    reason=_REASON,
    now=aware_datetimes(),
    triggered_by_uuid=st.uuids(),
)
def test_deregister_from_disallowed_source_always_raises_cannot_deregister(
    supply_id: UUID,
    source: SupplyStatus,
    reason: str,
    now: datetime,
    triggered_by_uuid: UUID,
) -> None:
    """Any source outside the permitted set (Decommissioned) raises, carrying status."""
    with pytest.raises(SupplyCannotDeregisterError) as exc:
        deregister_supply.decide(
            state=_state(supply_id=supply_id, status=source),
            command=_command(supply_id=supply_id, reason=reason),
            now=now,
            triggered_by=ActorId(triggered_by_uuid),
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    state_supply_id=st.uuids(),
    command_supply_id=st.uuids(),
    source=st.sampled_from(_PERMITTED_SOURCES),
    reason=_REASON,
    now=aware_datetimes(),
    triggered_by_uuid=st.uuids(),
)
def test_deregister_uses_state_id_not_command_supply_id(
    state_supply_id: UUID,
    command_supply_id: UUID,
    source: SupplyStatus,
    reason: str,
    now: datetime,
    triggered_by_uuid: UUID,
) -> None:
    """The emitted event's supply_id is state.id, not command.supply_id."""
    assume(state_supply_id != command_supply_id)
    events = deregister_supply.decide(
        state=_state(supply_id=state_supply_id, status=source),
        command=_command(supply_id=command_supply_id, reason=reason),
        now=now,
        triggered_by=ActorId(triggered_by_uuid),
    )
    assert events[0].supply_id == state_supply_id


@pytest.mark.unit
@given(
    supply_id=st.uuids(),
    source=st.sampled_from(_PERMITTED_SOURCES),
    reason=_REASON,
    now=aware_datetimes(),
    triggered_by_uuid=st.uuids(),
)
def test_deregister_is_pure_same_input_same_output(
    supply_id: UUID,
    source: SupplyStatus,
    reason: str,
    now: datetime,
    triggered_by_uuid: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _state(supply_id=supply_id, status=source)
    command = _command(supply_id=supply_id, reason=reason)
    triggered_by = ActorId(triggered_by_uuid)
    first = deregister_supply.decide(
        state=state, command=command, now=now, triggered_by=triggered_by
    )
    second = deregister_supply.decide(
        state=state, command=command, now=now, triggered_by=triggered_by
    )
    assert first == second
