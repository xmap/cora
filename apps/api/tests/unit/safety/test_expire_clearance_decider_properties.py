"""Property-based tests for `expire_clearance.decide` (Safety BC).

Complements the example-based `test_expire_clearance_decider.py` with
universal claims across generated inputs. The decider is a pure
single-source FSM terminal

    (state, command, now) -> list[ClearanceExpired]

Load-bearing properties:

  - state=None always raises `ClearanceNotFoundError` carrying
    command.clearance_id.
  - The source-state partition is total over `ClearanceStatus`: only
    `Active` emits exactly one `ClearanceExpired` (clearance_id=state.id,
    occurred_at=now); every other status raises
    `ClearanceCannotExpireError` carrying the current status, so a future
    status value cannot silently fall through.
  - The emitted event's clearance_id is `state.id`, never
    `command.clearance_id`.
  - Pure: same (state, command, now) returns equal events.

The full gate matrix (reason trimming, empty/too-long rejection) is
pinned by the example test; this file does not duplicate it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.safety.aggregates.clearance import (
    Clearance,
    ClearanceCannotExpireError,
    ClearanceExpired,
    ClearanceNotFoundError,
    ClearanceStatus,
    ClearanceTitle,
    RunBinding,
)
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateId,
    clearance_template_stream_id,
)
from cora.safety.features import expire_clearance
from cora.safety.features.expire_clearance import ExpireClearance
from cora.shared.facility_code import FacilityCode

if TYPE_CHECKING:
    from datetime import datetime

from tests._strategies import aware_datetimes, printable_ascii_text

_REASON = "validity window elapsed"

_EXPIRABLE_SOURCES = (ClearanceStatus.ACTIVE,)
_DISALLOWED_SOURCES = tuple(s for s in ClearanceStatus if s not in frozenset(_EXPIRABLE_SOURCES))


def _clearance(*, clearance_id: UUID, status: ClearanceStatus) -> Clearance:
    return Clearance(
        id=clearance_id,
        template_id=ClearanceTemplateId(clearance_template_stream_id("aps", "ESAF")),
        facility_code=FacilityCode("aps"),
        title=ClearanceTitle("Pilot"),
        bindings=frozenset({RunBinding(run_id=UUID(int=2))}),
        status=status,
    )


@pytest.mark.unit
@given(clearance_id=st.uuids(), now=aware_datetimes())
def test_expire_with_none_state_always_raises_not_found(
    clearance_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `ClearanceNotFoundError` carrying command id."""
    with pytest.raises(ClearanceNotFoundError) as exc:
        expire_clearance.decide(
            state=None,
            command=ExpireClearance(clearance_id=clearance_id, reason=_REASON),
            now=now,
        )
    assert exc.value.clearance_id == clearance_id


@pytest.mark.unit
@given(
    clearance_id=st.uuids(),
    reason=printable_ascii_text(max_size=64),
    now=aware_datetimes(),
)
def test_expire_from_active_emits_single_event(
    clearance_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """Active is the only expirable source; emits one ClearanceExpired."""
    events = expire_clearance.decide(
        state=_clearance(clearance_id=clearance_id, status=ClearanceStatus.ACTIVE),
        command=ExpireClearance(clearance_id=clearance_id, reason=reason),
        now=now,
    )
    assert events == [ClearanceExpired(clearance_id=clearance_id, reason=reason, occurred_at=now)]


@pytest.mark.unit
@given(
    clearance_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_expire_from_disallowed_source_always_raises_cannot_expire(
    clearance_id: UUID,
    source: ClearanceStatus,
    now: datetime,
) -> None:
    """Any source other than Active raises, carrying the current status."""
    with pytest.raises(ClearanceCannotExpireError) as exc:
        expire_clearance.decide(
            state=_clearance(clearance_id=clearance_id, status=source),
            command=ExpireClearance(clearance_id=clearance_id, reason=_REASON),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(state_id=st.uuids(), command_id=st.uuids(), now=aware_datetimes())
def test_expire_uses_state_id_not_command_clearance_id(
    state_id: UUID,
    command_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's clearance_id is state.id, not command.clearance_id."""
    assume(state_id != command_id)
    events = expire_clearance.decide(
        state=_clearance(clearance_id=state_id, status=ClearanceStatus.ACTIVE),
        command=ExpireClearance(clearance_id=command_id, reason=_REASON),
        now=now,
    )
    assert events[0].clearance_id == state_id


@pytest.mark.unit
@given(clearance_id=st.uuids(), now=aware_datetimes())
def test_expire_is_pure_same_input_same_output(
    clearance_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _clearance(clearance_id=clearance_id, status=ClearanceStatus.ACTIVE)
    command = ExpireClearance(clearance_id=clearance_id, reason=_REASON)
    first = expire_clearance.decide(state=state, command=command, now=now)
    second = expire_clearance.decide(state=state, command=command, now=now)
    assert first == second
