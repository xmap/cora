"""Property-based tests for `submit_clearance.decide` (Safety BC).

Complements the example-based `test_submit_clearance_decider.py` with
universal claims across generated inputs. The decider is a pure
single-source FSM transition

    (state, command, now) -> list[ClearanceSubmitted]

Load-bearing properties:

  - state=None always raises `ClearanceNotFoundError` carrying
    command.clearance_id.
  - The source-state partition is total over `ClearanceStatus`: only
    `Defined` emits exactly one `ClearanceSubmitted` (clearance_id=
    state.id, occurred_at=now); every other status raises
    `ClearanceCannotSubmitError` carrying the current status, so a future
    status value cannot silently fall through.
  - The emitted event's clearance_id is `state.id`, never
    command.clearance_id.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.safety.aggregates.clearance import (
    Clearance,
    ClearanceCannotSubmitError,
    ClearanceNotFoundError,
    ClearanceStatus,
    ClearanceSubmitted,
    ClearanceTitle,
    RunBinding,
)
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateId,
    clearance_template_stream_id,
)
from cora.safety.features import submit_clearance
from cora.safety.features.submit_clearance import SubmitClearance
from cora.shared.facility_code import FacilityCode
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime

_SUBMITTABLE_SOURCES = (ClearanceStatus.DEFINED,)
_DISALLOWED_SOURCES = tuple(s for s in ClearanceStatus if s not in frozenset(_SUBMITTABLE_SOURCES))


def _clearance(*, clearance_id: UUID, status: ClearanceStatus) -> Clearance:
    return Clearance(
        id=clearance_id,
        template_id=ClearanceTemplateId(clearance_template_stream_id("aps", "ESAF")),
        facility_code=FacilityCode("aps"),
        title=ClearanceTitle("Pilot"),
        bindings=frozenset({RunBinding(run_id=uuid4())}),
        status=status,
    )


@pytest.mark.unit
@given(clearance_id=st.uuids(), now=aware_datetimes())
def test_submit_with_none_state_always_raises_not_found(
    clearance_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `ClearanceNotFoundError` carrying the id."""
    with pytest.raises(ClearanceNotFoundError) as exc:
        submit_clearance.decide(
            state=None,
            command=SubmitClearance(clearance_id=clearance_id),
            now=now,
        )
    assert exc.value.clearance_id == clearance_id


@pytest.mark.unit
@given(clearance_id=st.uuids(), now=aware_datetimes())
def test_submit_from_defined_emits_single_event(
    clearance_id: UUID,
    now: datetime,
) -> None:
    """Defined is the only submittable source; emits one ClearanceSubmitted."""
    events = submit_clearance.decide(
        state=_clearance(clearance_id=clearance_id, status=ClearanceStatus.DEFINED),
        command=SubmitClearance(clearance_id=clearance_id),
        now=now,
    )
    assert events == [ClearanceSubmitted(clearance_id=clearance_id, occurred_at=now)]


@pytest.mark.unit
@given(
    clearance_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_submit_from_disallowed_source_always_raises_cannot_submit(
    clearance_id: UUID,
    source: ClearanceStatus,
    now: datetime,
) -> None:
    """Any source other than Defined raises, carrying the current status."""
    with pytest.raises(ClearanceCannotSubmitError) as exc:
        submit_clearance.decide(
            state=_clearance(clearance_id=clearance_id, status=source),
            command=SubmitClearance(clearance_id=clearance_id),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    state_clearance_id=st.uuids(),
    command_clearance_id=st.uuids(),
    now=aware_datetimes(),
)
def test_submit_uses_state_id_not_command_clearance_id(
    state_clearance_id: UUID,
    command_clearance_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's clearance_id is state.id, not command.clearance_id."""
    assume(state_clearance_id != command_clearance_id)
    events = submit_clearance.decide(
        state=_clearance(clearance_id=state_clearance_id, status=ClearanceStatus.DEFINED),
        command=SubmitClearance(clearance_id=command_clearance_id),
        now=now,
    )
    assert events[0].clearance_id == state_clearance_id


@pytest.mark.unit
@given(clearance_id=st.uuids(), now=aware_datetimes())
def test_submit_is_pure_same_input_same_output(
    clearance_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _clearance(clearance_id=clearance_id, status=ClearanceStatus.DEFINED)
    command = SubmitClearance(clearance_id=clearance_id)
    first = submit_clearance.decide(state=state, command=command, now=now)
    second = submit_clearance.decide(state=state, command=command, now=now)
    assert first == second
