"""Property-based tests for `deny_ratification.decide` (Trust BC, Ratification).

Complements the example-based `ratification/test_deny_ratification_decider.py`
with universal claims across generated inputs. The decider is a pure
single-source FSM transition with a mandatory reason

    (state, command, denied_by, now) -> list[RatificationDenied]

Load-bearing properties:

  - state=None always raises `RatificationNotFoundError` carrying
    command.ratification_id.
  - The source-state partition is total over `RatificationStatus`: only
    `Requested` is deniable; every terminal status raises
    `RatificationCannotDenyError` carrying the current status (the status
    guard runs before the independence check), so a future status value
    cannot silently fall through.
  - Independence (four-eyes): on a Requested state, denied_by==requested_by
    always raises `RatificationRequesterCannotSelfRatifyError`.
  - Reason validation runs after the independence check: an independent
    principal with a blank or over-REASON_MAX_LENGTH reason raises
    `InvalidRatificationReasonError`; a valid reason emits exactly one
    `RatificationDenied` (ratification_id=state.id, reason trimmed,
    occurred_at=now).
  - Pure: same (state, command, denied_by, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.trust.aggregates.ratification import (
    InvalidRatificationReasonError,
    Ratification,
    RatificationCannotDenyError,
    RatificationDenied,
    RatificationGranted,
    RatificationNotFoundError,
    RatificationRequesterCannotSelfRatifyError,
    RatificationStatus,
    evolve,
)
from cora.trust.features.deny_ratification import DenyRatification
from cora.trust.features.deny_ratification.decider import decide
from tests._strategies import aware_datetimes, printable_ascii_text
from tests.unit.trust.ratification._fixtures import NOW, RATIFICATION_ID, make_requested

_REASON = printable_ascii_text(min_size=1, max_size=REASON_MAX_LENGTH)

_DENIABLE_SOURCES = (RatificationStatus.REQUESTED,)
_TERMINAL_SOURCES = tuple(s for s in RatificationStatus if s not in frozenset(_DENIABLE_SOURCES))


def _state_with(*, status: RatificationStatus, requested_by: UUID) -> Ratification:
    """Build a Ratification in the requested status, seeded by requested_by."""
    requested = make_requested(requested_by=requested_by)
    match status:
        case RatificationStatus.REQUESTED:
            return requested
        case RatificationStatus.GRANTED:
            return evolve(
                requested,
                RatificationGranted(ratification_id=RATIFICATION_ID, occurred_at=NOW),
            )
        case RatificationStatus.DENIED:
            return evolve(
                requested,
                RatificationDenied(
                    ratification_id=RATIFICATION_ID, reason="prior denial", occurred_at=NOW
                ),
            )


@pytest.mark.unit
@given(ratification_id=st.uuids(), reason=_REASON, denied_by=st.uuids(), now=aware_datetimes())
def test_deny_with_none_state_always_raises_not_found(
    ratification_id: UUID,
    reason: str,
    denied_by: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises RatificationNotFoundError carrying command id."""
    with pytest.raises(RatificationNotFoundError) as exc:
        decide(
            state=None,
            command=DenyRatification(ratification_id=ratification_id, reason=reason),
            denied_by=denied_by,
            now=now,
        )
    assert exc.value.ratification_id == ratification_id


@pytest.mark.unit
@given(
    source=st.sampled_from(_TERMINAL_SOURCES),
    requester=st.uuids(),
    reason=_REASON,
    denied_by=st.uuids(),
    now=aware_datetimes(),
)
def test_deny_from_terminal_source_always_raises_cannot_deny(
    source: RatificationStatus,
    requester: UUID,
    reason: str,
    denied_by: UUID,
    now: datetime,
) -> None:
    """Any source other than Requested raises, carrying the current status."""
    state = _state_with(status=source, requested_by=requester)
    with pytest.raises(RatificationCannotDenyError) as exc:
        decide(
            state=state,
            command=DenyRatification(ratification_id=state.id, reason=reason),
            denied_by=denied_by,
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(requester=st.uuids(), reason=_REASON, now=aware_datetimes())
def test_deny_by_requester_always_raises_self_sign(
    requester: UUID,
    reason: str,
    now: datetime,
) -> None:
    """Four-eyes: on a Requested state, the requester may not deny its own request."""
    state = _state_with(status=RatificationStatus.REQUESTED, requested_by=requester)
    with pytest.raises(RatificationRequesterCannotSelfRatifyError) as exc:
        decide(
            state=state,
            command=DenyRatification(ratification_id=state.id, reason=reason),
            denied_by=requester,
            now=now,
        )
    assert exc.value.principal_id == requester


@pytest.mark.unit
@given(
    requester=st.uuids(),
    denied_by=st.uuids(),
    blank=st.text(alphabet=" \t\n", max_size=8),
    now=aware_datetimes(),
)
def test_deny_blank_reason_always_raises_invalid_reason(
    requester: UUID,
    denied_by: UUID,
    blank: str,
    now: datetime,
) -> None:
    """An independent principal with a whitespace-only reason raises."""
    assume(requester != denied_by)
    state = _state_with(status=RatificationStatus.REQUESTED, requested_by=requester)
    with pytest.raises(InvalidRatificationReasonError):
        decide(
            state=state,
            command=DenyRatification(ratification_id=state.id, reason=blank),
            denied_by=denied_by,
            now=now,
        )


@pytest.mark.unit
@given(
    requester=st.uuids(),
    denied_by=st.uuids(),
    overlong=st.integers(min_value=REASON_MAX_LENGTH + 1, max_value=REASON_MAX_LENGTH + 200),
    now=aware_datetimes(),
)
def test_deny_overlong_reason_always_raises_invalid_reason(
    requester: UUID,
    denied_by: UUID,
    overlong: int,
    now: datetime,
) -> None:
    """A reason longer than the max after trim raises."""
    assume(requester != denied_by)
    state = _state_with(status=RatificationStatus.REQUESTED, requested_by=requester)
    with pytest.raises(InvalidRatificationReasonError):
        decide(
            state=state,
            command=DenyRatification(ratification_id=state.id, reason="x" * overlong),
            denied_by=denied_by,
            now=now,
        )


@pytest.mark.unit
@given(requester=st.uuids(), denied_by=st.uuids(), reason=_REASON, now=aware_datetimes())
def test_deny_by_independent_principal_emits_single_event_with_trimmed_reason(
    requester: UUID,
    denied_by: UUID,
    reason: str,
    now: datetime,
) -> None:
    """An independent principal with a valid reason emits one RatificationDenied (trimmed)."""
    assume(requester != denied_by)
    state = _state_with(status=RatificationStatus.REQUESTED, requested_by=requester)
    events = decide(
        state=state,
        command=DenyRatification(ratification_id=state.id, reason=f"  {reason}  "),
        denied_by=denied_by,
        now=now,
    )
    assert events == [RatificationDenied(ratification_id=state.id, reason=reason, occurred_at=now)]


@pytest.mark.unit
@given(requester=st.uuids(), denied_by=st.uuids(), reason=_REASON, now=aware_datetimes())
def test_deny_is_pure_same_input_same_output(
    requester: UUID,
    denied_by: UUID,
    reason: str,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    assume(requester != denied_by)
    state = _state_with(status=RatificationStatus.REQUESTED, requested_by=requester)
    command = DenyRatification(ratification_id=state.id, reason=reason)
    first = decide(state=state, command=command, denied_by=denied_by, now=now)
    second = decide(state=state, command=command, denied_by=denied_by, now=now)
    assert first == second
