"""Property-based tests for `activate_clearance.decide` (Safety BC).

Complements the example-based `test_activate_clearance_decider.py` with
universal claims across generated inputs. The decider is a pure
single-source FSM transition

    (state, command, now) -> list[ClearanceActivated]

Load-bearing properties:

  - state=None always raises `ClearanceNotFoundError` carrying
    command.clearance_id.
  - The source-state partition is total over `ClearanceStatus`: only
    `Approved` emits exactly one `ClearanceActivated` (clearance_id=
    state.id, occurred_at=now); every other status raises
    `ClearanceCannotActivateError` carrying the current status, so a
    future status value cannot silently fall through.
  - The emitted event's clearance_id is `state.id`, never
    `command.clearance_id`.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.safety.aggregates.clearance import (
    Clearance,
    ClearanceActivated,
    ClearanceCannotActivateError,
    ClearanceNotFoundError,
    ClearanceStatus,
    ClearanceTitle,
    RunBinding,
)
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateId,
    clearance_template_stream_id,
)
from cora.safety.features import activate_clearance
from cora.safety.features.activate_clearance import ActivateClearance
from cora.shared.facility_code import FacilityCode
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime

_TEMPLATE_ID = ClearanceTemplateId(clearance_template_stream_id("aps", "ESAF"))
_FACILITY_CODE = FacilityCode("aps")
_TITLE = ClearanceTitle("Pilot")
_RUN_ID = UUID(int=1)

_ACTIVATABLE_SOURCES = (ClearanceStatus.APPROVED,)
_DISALLOWED_SOURCES = tuple(s for s in ClearanceStatus if s not in frozenset(_ACTIVATABLE_SOURCES))


def _clearance(*, clearance_id: UUID, status: ClearanceStatus) -> Clearance:
    return Clearance(
        id=clearance_id,
        template_id=_TEMPLATE_ID,
        facility_code=_FACILITY_CODE,
        title=_TITLE,
        bindings=frozenset({RunBinding(run_id=_RUN_ID)}),
        status=status,
    )


@pytest.mark.unit
@given(clearance_id=st.uuids(), now=aware_datetimes())
def test_activate_with_none_state_always_raises_not_found(
    clearance_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `ClearanceNotFoundError` carrying command id."""
    with pytest.raises(ClearanceNotFoundError) as exc:
        activate_clearance.decide(
            state=None,
            command=ActivateClearance(clearance_id=clearance_id),
            now=now,
        )
    assert exc.value.clearance_id == clearance_id


@pytest.mark.unit
@given(clearance_id=st.uuids(), now=aware_datetimes())
def test_activate_from_approved_emits_single_event(
    clearance_id: UUID,
    now: datetime,
) -> None:
    """Approved is the only activatable source; emits one ClearanceActivated."""
    events = activate_clearance.decide(
        state=_clearance(clearance_id=clearance_id, status=ClearanceStatus.APPROVED),
        command=ActivateClearance(clearance_id=clearance_id),
        now=now,
    )
    assert events == [ClearanceActivated(clearance_id=clearance_id, occurred_at=now)]


@pytest.mark.unit
@given(
    clearance_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_activate_from_disallowed_source_always_raises_cannot_activate(
    clearance_id: UUID,
    source: ClearanceStatus,
    now: datetime,
) -> None:
    """Any source other than Approved raises, carrying the current status."""
    with pytest.raises(ClearanceCannotActivateError) as exc:
        activate_clearance.decide(
            state=_clearance(clearance_id=clearance_id, status=source),
            command=ActivateClearance(clearance_id=clearance_id),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(state_id=st.uuids(), command_id=st.uuids(), now=aware_datetimes())
def test_activate_uses_state_id_not_command_id(
    state_id: UUID,
    command_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's clearance_id is state.id, not command.clearance_id."""
    assume(state_id != command_id)
    events = activate_clearance.decide(
        state=_clearance(clearance_id=state_id, status=ClearanceStatus.APPROVED),
        command=ActivateClearance(clearance_id=command_id),
        now=now,
    )
    assert events[0].clearance_id == state_id


@pytest.mark.unit
@given(clearance_id=st.uuids(), now=aware_datetimes())
def test_activate_is_pure_same_input_same_output(
    clearance_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _clearance(clearance_id=clearance_id, status=ClearanceStatus.APPROVED)
    command = ActivateClearance(clearance_id=clearance_id)
    first = activate_clearance.decide(state=state, command=command, now=now)
    second = activate_clearance.decide(state=state, command=command, now=now)
    assert first == second
