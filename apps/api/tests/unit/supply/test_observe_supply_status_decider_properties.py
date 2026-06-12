"""Property-based tests for `observe_supply_status.decide` (Supply BC).

Complements the example-based `test_observe_supply_status_decider.py`
with universal claims across generated inputs. This is the Monitor-
driven inbound port; the decider routes by `command.new_status` and is
pure

    (state, command, now, triggered_by) -> list[<transition event>]

Load-bearing properties:

  - state=None always raises `SupplyNotFoundError`, for any new_status.
  - Monitor-forbidden targets (Available, Decommissioned, Unknown)
    always raise `MonitorTriggerNotPermittedError` from any source.
  - For each Monitor-permitted target the source-state partition is
    total: a permitted source emits exactly one event of the matching
    class with trigger="Monitor", the injected `MonitorSourceId`, and a
    serialized `monitor_ref`; a disallowed source raises the matching
    `SupplyCannot<Verb>Error`.
  - The emitted event's supply_id is `state.id`, never command.supply_id.
  - Pure: same inputs return equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.shared.facility_code import FacilityCode
from cora.shared.identity import MonitorSourceId
from cora.supply.aggregates.supply import (
    MonitorRef,
    MonitorTriggerNotPermittedError,
    Supply,
    SupplyCannotDegradeError,
    SupplyCannotMarkRecoveringError,
    SupplyCannotMarkUnavailableError,
    SupplyDegraded,
    SupplyMarkedRecovering,
    SupplyMarkedUnavailable,
    SupplyName,
    SupplyNotFoundError,
    SupplyStatus,
)
from cora.supply.features import observe_supply_status
from cora.supply.features.observe_supply_status import ObserveSupplyStatus
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_REASON = printable_ascii_text(min_size=1, max_size=500)
_MONITOR_KIND = printable_ascii_text(min_size=1, max_size=50)
_MONITOR_ID = printable_ascii_text(min_size=1, max_size=200)
_ALL_STATUSES = st.sampled_from(list(SupplyStatus))
_FACILITY_CODE = FacilityCode("aps")

_FORBIDDEN_TARGETS = (
    SupplyStatus.AVAILABLE,
    SupplyStatus.DECOMMISSIONED,
    SupplyStatus.UNKNOWN,
)
_DEGRADABLE_SOURCES = (
    SupplyStatus.UNKNOWN,
    SupplyStatus.AVAILABLE,
    SupplyStatus.RECOVERING,
)
_UNAVAILABLE_SOURCES = (
    SupplyStatus.UNKNOWN,
    SupplyStatus.AVAILABLE,
    SupplyStatus.DEGRADED,
    SupplyStatus.RECOVERING,
)
_RECOVERING_SOURCES = (SupplyStatus.UNAVAILABLE,)


def _not_in(permitted: tuple[SupplyStatus, ...]) -> tuple[SupplyStatus, ...]:
    return tuple(s for s in SupplyStatus if s not in frozenset(permitted))


def _state(*, supply_id: UUID, status: SupplyStatus) -> Supply:
    return Supply(
        id=supply_id,
        kind="PhotonBeam",
        name=SupplyName("beam"),
        facility_code=_FACILITY_CODE,
        status=status,
    )


def _command(
    *,
    supply_id: UUID,
    new_status: SupplyStatus,
    source_kind: str,
    source_id: str,
    monitor_source_uuid: UUID,
    reason: str,
) -> ObserveSupplyStatus:
    return ObserveSupplyStatus(
        supply_id=supply_id,
        new_status=new_status,
        monitor_ref=MonitorRef(source_kind=source_kind, source_id=source_id),
        monitor_source_id=MonitorSourceId(monitor_source_uuid),
        reason=reason,
    )


@pytest.mark.unit
@given(
    supply_id=st.uuids(),
    new_status=_ALL_STATUSES,
    source_kind=_MONITOR_KIND,
    source_id=_MONITOR_ID,
    monitor_source_uuid=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
    triggered_by_uuid=st.uuids(),
)
def test_observe_with_none_state_always_raises_not_found(
    supply_id: UUID,
    new_status: SupplyStatus,
    source_kind: str,
    source_id: str,
    monitor_source_uuid: UUID,
    reason: str,
    now: datetime,
    triggered_by_uuid: UUID,
) -> None:
    """Empty stream always raises SupplyNotFoundError, for any new_status."""
    with pytest.raises(SupplyNotFoundError):
        observe_supply_status.decide(
            state=None,
            command=_command(
                supply_id=supply_id,
                new_status=new_status,
                source_kind=source_kind,
                source_id=source_id,
                monitor_source_uuid=monitor_source_uuid,
                reason=reason,
            ),
            now=now,
            triggered_by=MonitorSourceId(triggered_by_uuid),
        )


@pytest.mark.unit
@given(
    supply_id=st.uuids(),
    source=_ALL_STATUSES,
    forbidden_target=st.sampled_from(_FORBIDDEN_TARGETS),
    source_kind=_MONITOR_KIND,
    source_id=_MONITOR_ID,
    monitor_source_uuid=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
    triggered_by_uuid=st.uuids(),
)
def test_observe_forbidden_target_always_raises_not_permitted(
    supply_id: UUID,
    source: SupplyStatus,
    forbidden_target: SupplyStatus,
    source_kind: str,
    source_id: str,
    monitor_source_uuid: UUID,
    reason: str,
    now: datetime,
    triggered_by_uuid: UUID,
) -> None:
    """Available / Decommissioned / Unknown targets are Monitor-forbidden from any source."""
    with pytest.raises(MonitorTriggerNotPermittedError) as exc:
        observe_supply_status.decide(
            state=_state(supply_id=supply_id, status=source),
            command=_command(
                supply_id=supply_id,
                new_status=forbidden_target,
                source_kind=source_kind,
                source_id=source_id,
                monitor_source_uuid=monitor_source_uuid,
                reason=reason,
            ),
            now=now,
            triggered_by=MonitorSourceId(triggered_by_uuid),
        )
    assert exc.value.requested_status is forbidden_target


@pytest.mark.unit
@given(
    supply_id=st.uuids(),
    source=st.sampled_from(_DEGRADABLE_SOURCES),
    source_kind=_MONITOR_KIND,
    source_id=_MONITOR_ID,
    monitor_source_uuid=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
    triggered_by_uuid=st.uuids(),
)
def test_observe_degraded_from_permitted_source_emits_single_event(
    supply_id: UUID,
    source: SupplyStatus,
    source_kind: str,
    source_id: str,
    monitor_source_uuid: UUID,
    reason: str,
    now: datetime,
    triggered_by_uuid: UUID,
) -> None:
    """Degraded target from a permitted source emits one Monitor SupplyDegraded."""
    triggered_by = MonitorSourceId(triggered_by_uuid)
    events = observe_supply_status.decide(
        state=_state(supply_id=supply_id, status=source),
        command=_command(
            supply_id=supply_id,
            new_status=SupplyStatus.DEGRADED,
            source_kind=source_kind,
            source_id=source_id,
            monitor_source_uuid=monitor_source_uuid,
            reason=reason,
        ),
        now=now,
        triggered_by=triggered_by,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, SupplyDegraded)
    assert event.supply_id == supply_id
    assert event.from_status == source.value
    assert event.reason == reason
    assert event.trigger == "Monitor"
    assert event.triggered_by == triggered_by
    assert event.occurred_at == now
    assert event.monitor_ref == f"{source_kind}:{source_id}"


@pytest.mark.unit
@given(
    supply_id=st.uuids(),
    source=st.sampled_from(_not_in(_DEGRADABLE_SOURCES)),
    source_kind=_MONITOR_KIND,
    source_id=_MONITOR_ID,
    monitor_source_uuid=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
    triggered_by_uuid=st.uuids(),
)
def test_observe_degraded_from_disallowed_source_raises_cannot_degrade(
    supply_id: UUID,
    source: SupplyStatus,
    source_kind: str,
    source_id: str,
    monitor_source_uuid: UUID,
    reason: str,
    now: datetime,
    triggered_by_uuid: UUID,
) -> None:
    """Degraded target from a disallowed source raises SupplyCannotDegradeError."""
    with pytest.raises(SupplyCannotDegradeError):
        observe_supply_status.decide(
            state=_state(supply_id=supply_id, status=source),
            command=_command(
                supply_id=supply_id,
                new_status=SupplyStatus.DEGRADED,
                source_kind=source_kind,
                source_id=source_id,
                monitor_source_uuid=monitor_source_uuid,
                reason=reason,
            ),
            now=now,
            triggered_by=MonitorSourceId(triggered_by_uuid),
        )


@pytest.mark.unit
@given(
    supply_id=st.uuids(),
    source=st.sampled_from(_UNAVAILABLE_SOURCES),
    source_kind=_MONITOR_KIND,
    source_id=_MONITOR_ID,
    monitor_source_uuid=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
    triggered_by_uuid=st.uuids(),
)
def test_observe_unavailable_from_permitted_source_emits_single_event(
    supply_id: UUID,
    source: SupplyStatus,
    source_kind: str,
    source_id: str,
    monitor_source_uuid: UUID,
    reason: str,
    now: datetime,
    triggered_by_uuid: UUID,
) -> None:
    """Unavailable target from a permitted source emits one Monitor SupplyMarkedUnavailable."""
    triggered_by = MonitorSourceId(triggered_by_uuid)
    events = observe_supply_status.decide(
        state=_state(supply_id=supply_id, status=source),
        command=_command(
            supply_id=supply_id,
            new_status=SupplyStatus.UNAVAILABLE,
            source_kind=source_kind,
            source_id=source_id,
            monitor_source_uuid=monitor_source_uuid,
            reason=reason,
        ),
        now=now,
        triggered_by=triggered_by,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, SupplyMarkedUnavailable)
    assert event.supply_id == supply_id
    assert event.from_status == source.value
    assert event.trigger == "Monitor"
    assert event.triggered_by == triggered_by
    assert event.monitor_ref == f"{source_kind}:{source_id}"


@pytest.mark.unit
@given(
    supply_id=st.uuids(),
    source=st.sampled_from(_not_in(_UNAVAILABLE_SOURCES)),
    source_kind=_MONITOR_KIND,
    source_id=_MONITOR_ID,
    monitor_source_uuid=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
    triggered_by_uuid=st.uuids(),
)
def test_observe_unavailable_from_disallowed_source_raises_cannot_mark_unavailable(
    supply_id: UUID,
    source: SupplyStatus,
    source_kind: str,
    source_id: str,
    monitor_source_uuid: UUID,
    reason: str,
    now: datetime,
    triggered_by_uuid: UUID,
) -> None:
    """Unavailable target from a disallowed source raises SupplyCannotMarkUnavailableError."""
    with pytest.raises(SupplyCannotMarkUnavailableError):
        observe_supply_status.decide(
            state=_state(supply_id=supply_id, status=source),
            command=_command(
                supply_id=supply_id,
                new_status=SupplyStatus.UNAVAILABLE,
                source_kind=source_kind,
                source_id=source_id,
                monitor_source_uuid=monitor_source_uuid,
                reason=reason,
            ),
            now=now,
            triggered_by=MonitorSourceId(triggered_by_uuid),
        )


@pytest.mark.unit
@given(
    state_supply_id=st.uuids(),
    command_supply_id=st.uuids(),
    source_kind=_MONITOR_KIND,
    source_id=_MONITOR_ID,
    monitor_source_uuid=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
    triggered_by_uuid=st.uuids(),
)
def test_observe_recovering_from_unavailable_emits_with_state_id(
    state_supply_id: UUID,
    command_supply_id: UUID,
    source_kind: str,
    source_id: str,
    monitor_source_uuid: UUID,
    reason: str,
    now: datetime,
    triggered_by_uuid: UUID,
) -> None:
    """Recovering from Unavailable emits one event carrying state.id, not command.supply_id."""
    assume(state_supply_id != command_supply_id)
    triggered_by = MonitorSourceId(triggered_by_uuid)
    events = observe_supply_status.decide(
        state=_state(supply_id=state_supply_id, status=SupplyStatus.UNAVAILABLE),
        command=_command(
            supply_id=command_supply_id,
            new_status=SupplyStatus.RECOVERING,
            source_kind=source_kind,
            source_id=source_id,
            monitor_source_uuid=monitor_source_uuid,
            reason=reason,
        ),
        now=now,
        triggered_by=triggered_by,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, SupplyMarkedRecovering)
    assert event.supply_id == state_supply_id
    assert event.trigger == "Monitor"
    assert event.triggered_by == triggered_by


@pytest.mark.unit
@given(
    supply_id=st.uuids(),
    source=st.sampled_from(_not_in(_RECOVERING_SOURCES)),
    source_kind=_MONITOR_KIND,
    source_id=_MONITOR_ID,
    monitor_source_uuid=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
    triggered_by_uuid=st.uuids(),
)
def test_observe_recovering_from_disallowed_source_raises_cannot_mark_recovering(
    supply_id: UUID,
    source: SupplyStatus,
    source_kind: str,
    source_id: str,
    monitor_source_uuid: UUID,
    reason: str,
    now: datetime,
    triggered_by_uuid: UUID,
) -> None:
    """Recovering target from any source other than Unavailable raises."""
    with pytest.raises(SupplyCannotMarkRecoveringError):
        observe_supply_status.decide(
            state=_state(supply_id=supply_id, status=source),
            command=_command(
                supply_id=supply_id,
                new_status=SupplyStatus.RECOVERING,
                source_kind=source_kind,
                source_id=source_id,
                monitor_source_uuid=monitor_source_uuid,
                reason=reason,
            ),
            now=now,
            triggered_by=MonitorSourceId(triggered_by_uuid),
        )


@pytest.mark.unit
@given(
    supply_id=st.uuids(),
    source=st.sampled_from(_DEGRADABLE_SOURCES),
    source_kind=_MONITOR_KIND,
    source_id=_MONITOR_ID,
    monitor_source_uuid=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
    triggered_by_uuid=st.uuids(),
)
def test_observe_is_pure_same_input_same_output(
    supply_id: UUID,
    source: SupplyStatus,
    source_kind: str,
    source_id: str,
    monitor_source_uuid: UUID,
    reason: str,
    now: datetime,
    triggered_by_uuid: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _state(supply_id=supply_id, status=source)
    command = _command(
        supply_id=supply_id,
        new_status=SupplyStatus.DEGRADED,
        source_kind=source_kind,
        source_id=source_id,
        monitor_source_uuid=monitor_source_uuid,
        reason=reason,
    )
    triggered_by = MonitorSourceId(triggered_by_uuid)
    first = observe_supply_status.decide(
        state=state, command=command, now=now, triggered_by=triggered_by
    )
    second = observe_supply_status.decide(
        state=state, command=command, now=now, triggered_by=triggered_by
    )
    assert first == second
