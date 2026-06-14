"""Property-based tests for `decommission_enclosure.decide` (Enclosure BC).

Mirrors the Federation `decommission_facility` decider-PBT pattern.
Universal claims across generated inputs:

  - state=None always raises EnclosureNotFoundError.
  - state.lifecycle=Decommissioned always raises
    EnclosureCannotDecommissionError.
  - state.lifecycle=Active + valid reason emits exactly one
    EnclosureDecommissioned with the injected now / triggered_by and
    the command's trimmed reason.
  - Pure: same (state, command, now, triggered_by) returns the same
    events.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.enclosure.aggregates._value_types import EnclosureId, EnclosureReason
from cora.enclosure.aggregates.enclosure import (
    Enclosure,
    EnclosureCannotDecommissionError,
    EnclosureLifecycle,
    EnclosureName,
    EnclosureNotFoundError,
    EnclosurePermitStatus,
)
from cora.enclosure.features import decommission_enclosure
from cora.enclosure.features.decommission_enclosure import DecommissionEnclosure
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from uuid import UUID


_REGISTERED_AT = datetime(2026, 6, 8, 12, 0, 0, tzinfo=UTC)
_REASON = printable_ascii_text(min_size=1, max_size=200)
_FACILITY_CODE = FacilityCode("aps")


def _enclosure(
    enclosure_id: UUID,
    actor_id: UUID,
    *,
    lifecycle: EnclosureLifecycle,
) -> Enclosure:
    return Enclosure(
        id=EnclosureId(enclosure_id),
        name=EnclosureName("2-BM Hutch A"),
        facility_code=_FACILITY_CODE,
        permit_status=EnclosurePermitStatus.UNKNOWN,
        lifecycle=lifecycle,
        registered_at=_REGISTERED_AT,
        registered_by=ActorId(actor_id),
        decommissioned_at=None if lifecycle is EnclosureLifecycle.ACTIVE else _REGISTERED_AT,
        decommissioned_by=None if lifecycle is EnclosureLifecycle.ACTIVE else ActorId(actor_id),
    )


@pytest.mark.unit
@given(
    enclosure_id=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
    actor_id=st.uuids(),
)
def test_decommission_enclosure_on_none_state_always_raises_not_found(
    enclosure_id: UUID,
    reason: str,
    now: datetime,
    actor_id: UUID,
) -> None:
    """state=None -> EnclosureNotFoundError, regardless of command."""
    command = DecommissionEnclosure(
        enclosure_id=EnclosureId(enclosure_id),
        reason=reason,
    )
    with pytest.raises(EnclosureNotFoundError) as exc:
        decommission_enclosure.decide(
            state=None,
            command=command,
            now=now,
            triggered_by=ActorId(actor_id),
        )
    assert exc.value.enclosure_id == enclosure_id


@pytest.mark.unit
@given(
    enclosure_id=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
    actor_id=st.uuids(),
)
def test_decommission_enclosure_on_decommissioned_state_always_raises_cannot(
    enclosure_id: UUID,
    reason: str,
    now: datetime,
    actor_id: UUID,
) -> None:
    """state.lifecycle=Decommissioned -> EnclosureCannotDecommissionError, always."""
    state = _enclosure(
        enclosure_id,
        actor_id,
        lifecycle=EnclosureLifecycle.DECOMMISSIONED,
    )
    command = DecommissionEnclosure(
        enclosure_id=EnclosureId(enclosure_id),
        reason=reason,
    )
    with pytest.raises(EnclosureCannotDecommissionError) as exc:
        decommission_enclosure.decide(
            state=state,
            command=command,
            now=now,
            triggered_by=ActorId(actor_id),
        )
    assert exc.value.enclosure_id == enclosure_id


@pytest.mark.unit
@given(
    enclosure_id=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
    actor_id=st.uuids(),
)
def test_decommission_enclosure_on_active_state_emits_single_event(
    enclosure_id: UUID,
    reason: str,
    now: datetime,
    actor_id: UUID,
) -> None:
    """state.lifecycle=Active -> single EnclosureDecommissioned with injected fields."""
    state = _enclosure(
        enclosure_id,
        actor_id,
        lifecycle=EnclosureLifecycle.ACTIVE,
    )
    command = DecommissionEnclosure(
        enclosure_id=EnclosureId(enclosure_id),
        reason=reason,
    )
    events = decommission_enclosure.decide(
        state=state,
        command=command,
        now=now,
        triggered_by=ActorId(actor_id),
    )
    assert len(events) == 1
    event = events[0]
    assert event.enclosure_id == enclosure_id
    assert event.triggered_by == actor_id
    assert event.occurred_at == now
    assert event.reason == EnclosureReason(reason).value


@pytest.mark.unit
@given(
    enclosure_id=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
    actor_id=st.uuids(),
)
def test_decommission_enclosure_is_pure_same_input_same_output(
    enclosure_id: UUID,
    reason: str,
    now: datetime,
    actor_id: UUID,
) -> None:
    """Two calls with identical args return identical events."""
    state = _enclosure(
        enclosure_id,
        actor_id,
        lifecycle=EnclosureLifecycle.ACTIVE,
    )
    command = DecommissionEnclosure(
        enclosure_id=EnclosureId(enclosure_id),
        reason=reason,
    )
    first = decommission_enclosure.decide(
        state=state, command=command, now=now, triggered_by=ActorId(actor_id)
    )
    second = decommission_enclosure.decide(
        state=state, command=command, now=now, triggered_by=ActorId(actor_id)
    )
    assert first == second
