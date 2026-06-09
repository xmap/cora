"""Property-based tests for `observe_enclosure_status.decide` (Enclosure BC).

Mirrors the Access / Trust / Federation / Supply decider-PBT pattern
and the sibling `test_register_enclosure_decider_properties.py` shape.
Universal claims across generated inputs:

  - state=None always raises `EnclosureNotFoundError`, regardless of
    command shape.
  - state.lifecycle=Decommissioned always raises
    `EnclosureCannotObserveWhileDecommissionedError`, regardless of
    the requested permit-status target.
  - trigger=Operator always raises `MonitorTriggerNotPermittedError`
    (closes the D6.L2 operator-assert-Permitted backdoor at the
    command-tier guard; pins Risk #3 from the locked design).
  - Identical-status observation (state.permit_status == new_status)
    returns `[]` (L-EV-2 status-change-only invariant; load-bearing
    divergence from the Supply precedent).
  - Status-change observation under trigger=Monitor + lifecycle=Active
    emits exactly one `EnclosurePermitObserved` whose `enclosure_id` is
    `state.id` (NOT command.enclosure_id; pins the source-of-truth id
    invariant) with from_status/to_status/reason/trigger/triggered_by/
    occurred_at threaded through unchanged.
  - Pure: same (state, command, now, triggered_by) returns equal events.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.enclosure.aggregates._value_types import EnclosureId
from cora.enclosure.aggregates.enclosure import (
    Enclosure,
    EnclosureCannotObserveWhileDecommissionedError,
    EnclosureLifecycle,
    EnclosureName,
    EnclosureNotFoundError,
    EnclosurePermitObserved,
    EnclosurePermitStatus,
    MonitorRef,
    MonitorTriggerNotPermittedError,
)
from cora.enclosure.features import observe_enclosure_status
from cora.enclosure.features.observe_enclosure_status import ObserveEnclosureStatus
from cora.shared.identity import ActorId, MonitorSourceId
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from uuid import UUID


_REASON = printable_ascii_text(min_size=1, max_size=500)
_PERMIT_STATUS = st.sampled_from(list(EnclosurePermitStatus))
_LIFECYCLE = st.sampled_from(list(EnclosureLifecycle))

_FIXED_REGISTERED_AT = datetime(2026, 1, 1, tzinfo=UTC)


def _monitor_ref() -> MonitorRef:
    return MonitorRef(source_kind="EpicsPv", source_id="2BMA:PSS:permit")


def _state(
    *,
    enclosure_id: UUID,
    containing_asset_id: UUID,
    registered_by: UUID,
    permit_status: EnclosurePermitStatus,
    lifecycle: EnclosureLifecycle = EnclosureLifecycle.ACTIVE,
) -> Enclosure:
    decommissioned_at = (
        datetime(2026, 2, 1, tzinfo=UTC) if lifecycle is EnclosureLifecycle.DECOMMISSIONED else None
    )
    decommissioned_by = (
        ActorId(registered_by) if lifecycle is EnclosureLifecycle.DECOMMISSIONED else None
    )
    return Enclosure(
        id=EnclosureId(enclosure_id),
        name=EnclosureName("2-BM Hutch A"),
        containing_asset_id=containing_asset_id,
        permit_status=permit_status,
        lifecycle=lifecycle,
        registered_at=_FIXED_REGISTERED_AT,
        registered_by=ActorId(registered_by),
        decommissioned_at=decommissioned_at,
        decommissioned_by=decommissioned_by,
    )


def _command(
    *,
    enclosure_id: UUID,
    new_status: EnclosurePermitStatus,
    monitor_source_uuid: UUID,
    reason: str = "PSS interlock chain healthy",
    trigger: str = "Monitor",
) -> ObserveEnclosureStatus:
    return ObserveEnclosureStatus(
        enclosure_id=EnclosureId(enclosure_id),
        new_status=new_status,
        monitor_ref=_monitor_ref(),
        monitor_source_id=MonitorSourceId(monitor_source_uuid),
        reason=reason,
        trigger=trigger,
    )


@pytest.mark.unit
@given(
    enclosure_id=st.uuids(),
    new_status=_PERMIT_STATUS,
    monitor_source_uuid=st.uuids(),
    now=aware_datetimes(),
    triggered_by_uuid=st.uuids(),
)
def test_observe_with_none_state_always_raises_not_found(
    enclosure_id: UUID,
    new_status: EnclosurePermitStatus,
    monitor_source_uuid: UUID,
    now: datetime,
    triggered_by_uuid: UUID,
) -> None:
    """Empty stream always raises `EnclosureNotFoundError`."""
    with pytest.raises(EnclosureNotFoundError) as exc:
        observe_enclosure_status.decide(
            state=None,
            command=_command(
                enclosure_id=enclosure_id,
                new_status=new_status,
                monitor_source_uuid=monitor_source_uuid,
            ),
            now=now,
            triggered_by=MonitorSourceId(triggered_by_uuid),
        )
    assert exc.value.enclosure_id == enclosure_id


@pytest.mark.unit
@given(
    enclosure_id=st.uuids(),
    containing_asset_id=st.uuids(),
    registered_by=st.uuids(),
    source_permit=_PERMIT_STATUS,
    target_permit=_PERMIT_STATUS,
    monitor_source_uuid=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
    triggered_by_uuid=st.uuids(),
)
def test_observe_decommissioned_lifecycle_always_raises_cannot_observe(
    enclosure_id: UUID,
    containing_asset_id: UUID,
    registered_by: UUID,
    source_permit: EnclosurePermitStatus,
    target_permit: EnclosurePermitStatus,
    monitor_source_uuid: UUID,
    reason: str,
    now: datetime,
    triggered_by_uuid: UUID,
) -> None:
    """Decommissioned lifecycle rejects every observation regardless of target."""
    state = _state(
        enclosure_id=enclosure_id,
        containing_asset_id=containing_asset_id,
        registered_by=registered_by,
        permit_status=source_permit,
        lifecycle=EnclosureLifecycle.DECOMMISSIONED,
    )
    with pytest.raises(EnclosureCannotObserveWhileDecommissionedError) as exc:
        observe_enclosure_status.decide(
            state=state,
            command=_command(
                enclosure_id=enclosure_id,
                new_status=target_permit,
                monitor_source_uuid=monitor_source_uuid,
                reason=reason,
            ),
            now=now,
            triggered_by=MonitorSourceId(triggered_by_uuid),
        )
    assert exc.value.enclosure_id == enclosure_id
    assert exc.value.current_lifecycle is EnclosureLifecycle.DECOMMISSIONED


@pytest.mark.unit
@given(
    enclosure_id=st.uuids(),
    containing_asset_id=st.uuids(),
    registered_by=st.uuids(),
    source_permit=_PERMIT_STATUS,
    target_permit=_PERMIT_STATUS,
    monitor_source_uuid=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
    triggered_by_uuid=st.uuids(),
)
def test_observe_with_operator_trigger_always_raises_not_permitted(
    enclosure_id: UUID,
    containing_asset_id: UUID,
    registered_by: UUID,
    source_permit: EnclosurePermitStatus,
    target_permit: EnclosurePermitStatus,
    monitor_source_uuid: UUID,
    reason: str,
    now: datetime,
    triggered_by_uuid: UUID,
) -> None:
    """Operator-trigger observation always rejects (D6.L2 backdoor closure)."""
    state = _state(
        enclosure_id=enclosure_id,
        containing_asset_id=containing_asset_id,
        registered_by=registered_by,
        permit_status=source_permit,
    )
    with pytest.raises(MonitorTriggerNotPermittedError):
        observe_enclosure_status.decide(
            state=state,
            command=_command(
                enclosure_id=enclosure_id,
                new_status=target_permit,
                monitor_source_uuid=monitor_source_uuid,
                reason=reason,
                trigger="Operator",
            ),
            now=now,
            triggered_by=MonitorSourceId(triggered_by_uuid),
        )


@pytest.mark.unit
@given(
    enclosure_id=st.uuids(),
    containing_asset_id=st.uuids(),
    registered_by=st.uuids(),
    permit_status=_PERMIT_STATUS,
    monitor_source_uuid=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
    triggered_by_uuid=st.uuids(),
)
def test_observe_identical_status_returns_empty_event_list(
    enclosure_id: UUID,
    containing_asset_id: UUID,
    registered_by: UUID,
    permit_status: EnclosurePermitStatus,
    monitor_source_uuid: UUID,
    reason: str,
    now: datetime,
    triggered_by_uuid: UUID,
) -> None:
    """L-EV-2 status-change-only: identical-status observation is a no-op."""
    state = _state(
        enclosure_id=enclosure_id,
        containing_asset_id=containing_asset_id,
        registered_by=registered_by,
        permit_status=permit_status,
    )
    events = observe_enclosure_status.decide(
        state=state,
        command=_command(
            enclosure_id=enclosure_id,
            new_status=permit_status,
            monitor_source_uuid=monitor_source_uuid,
            reason=reason,
        ),
        now=now,
        triggered_by=MonitorSourceId(triggered_by_uuid),
    )
    assert events == []


@pytest.mark.unit
@given(
    state_enclosure_id=st.uuids(),
    command_enclosure_id=st.uuids(),
    containing_asset_id=st.uuids(),
    registered_by=st.uuids(),
    source_permit=_PERMIT_STATUS,
    target_permit=_PERMIT_STATUS,
    monitor_source_uuid=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
    triggered_by_uuid=st.uuids(),
)
def test_observe_status_change_emits_single_event_with_state_id(
    state_enclosure_id: UUID,
    command_enclosure_id: UUID,
    containing_asset_id: UUID,
    registered_by: UUID,
    source_permit: EnclosurePermitStatus,
    target_permit: EnclosurePermitStatus,
    monitor_source_uuid: UUID,
    reason: str,
    now: datetime,
    triggered_by_uuid: UUID,
) -> None:
    """Status-change observation emits one event with state.id (not command.enclosure_id)."""
    assume(source_permit is not target_permit)
    state = _state(
        enclosure_id=state_enclosure_id,
        containing_asset_id=containing_asset_id,
        registered_by=registered_by,
        permit_status=source_permit,
    )
    triggered_by = MonitorSourceId(triggered_by_uuid)
    events = observe_enclosure_status.decide(
        state=state,
        command=_command(
            enclosure_id=command_enclosure_id,
            new_status=target_permit,
            monitor_source_uuid=monitor_source_uuid,
            reason=reason,
        ),
        now=now,
        triggered_by=triggered_by,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, EnclosurePermitObserved)
    assert event.enclosure_id == state_enclosure_id
    assert event.from_status == source_permit.value
    assert event.to_status == target_permit.value
    assert event.reason == reason
    assert event.trigger == "Monitor"
    assert event.triggered_by == triggered_by
    assert event.occurred_at == now
    assert event.monitor_ref == "EpicsPv:2BMA:PSS:permit"


@pytest.mark.unit
@given(
    enclosure_id=st.uuids(),
    containing_asset_id=st.uuids(),
    registered_by=st.uuids(),
    source_permit=_PERMIT_STATUS,
    target_permit=_PERMIT_STATUS,
    monitor_source_uuid=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
    triggered_by_uuid=st.uuids(),
)
def test_observe_is_pure_same_input_same_output(
    enclosure_id: UUID,
    containing_asset_id: UUID,
    registered_by: UUID,
    source_permit: EnclosurePermitStatus,
    target_permit: EnclosurePermitStatus,
    monitor_source_uuid: UUID,
    reason: str,
    now: datetime,
    triggered_by_uuid: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    assume(source_permit is not target_permit)
    state = _state(
        enclosure_id=enclosure_id,
        containing_asset_id=containing_asset_id,
        registered_by=registered_by,
        permit_status=source_permit,
    )
    command = _command(
        enclosure_id=enclosure_id,
        new_status=target_permit,
        monitor_source_uuid=monitor_source_uuid,
        reason=reason,
    )
    triggered_by = MonitorSourceId(triggered_by_uuid)
    first = observe_enclosure_status.decide(
        state=state, command=command, now=now, triggered_by=triggered_by
    )
    second = observe_enclosure_status.decide(
        state=state, command=command, now=now, triggered_by=triggered_by
    )
    assert first == second
