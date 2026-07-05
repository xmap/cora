"""Property-based tests for `grant_ratification.decide` (Trust BC, Ratification).

Complements the example-based `ratification/test_grant_ratification_decider.py`
with universal claims across generated inputs. The decider is a pure
single-source FSM transition

    (state, command, granted_by, now) -> list[RatificationGranted]

Load-bearing properties:

  - state=None always raises `RatificationNotFoundError` carrying
    command.ratification_id.
  - The source-state partition is total over `RatificationStatus`: only
    `Requested` is grantable; every terminal status raises
    `RatificationCannotGrantError` carrying the current status (the status
    guard runs before the independence check), so a future status value
    cannot silently fall through.
  - Independence (four-eyes): on a Requested state, granted_by==requested_by
    always raises `RatificationRequesterCannotSelfRatifyError`; an independent
    principal emits exactly one `RatificationGranted` (ratification_id=state.id,
    occurred_at=now). This is the load-bearing invariant the gate provides.
  - Pure: same (state, command, granted_by, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

from cora.trust.aggregates.ratification import (
    Ratification,
    RatificationCannotGrantError,
    RatificationDenied,
    RatificationGranted,
    RatificationNotFoundError,
    RatificationRequesterCannotSelfRatifyError,
    RatificationStatus,
    evolve,
)
from cora.trust.features.grant_ratification import GrantRatification
from cora.trust.features.grant_ratification.decider import decide
from tests._strategies import aware_datetimes
from tests.unit.trust.ratification._fixtures import NOW, RATIFICATION_ID, make_requested

_GRANTABLE_SOURCES = (RatificationStatus.REQUESTED,)
_TERMINAL_SOURCES = tuple(s for s in RatificationStatus if s not in frozenset(_GRANTABLE_SOURCES))


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
@given(ratification_id=st.uuids(), granted_by=st.uuids(), now=aware_datetimes())
def test_grant_with_none_state_always_raises_not_found(
    ratification_id: UUID,
    granted_by: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises RatificationNotFoundError carrying command id."""
    with pytest.raises(RatificationNotFoundError) as exc:
        decide(
            state=None,
            command=GrantRatification(ratification_id=ratification_id),
            granted_by=granted_by,
            now=now,
        )
    assert exc.value.ratification_id == ratification_id


@pytest.mark.unit
@given(
    source=st.sampled_from(_TERMINAL_SOURCES),
    requester=st.uuids(),
    granted_by=st.uuids(),
    now=aware_datetimes(),
)
def test_grant_from_terminal_source_always_raises_cannot_grant(
    source: RatificationStatus,
    requester: UUID,
    granted_by: UUID,
    now: datetime,
) -> None:
    """Any source other than Requested raises, carrying the current status."""
    state = _state_with(status=source, requested_by=requester)
    with pytest.raises(RatificationCannotGrantError) as exc:
        decide(
            state=state,
            command=GrantRatification(ratification_id=state.id),
            granted_by=granted_by,
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(requester=st.uuids(), now=aware_datetimes())
def test_grant_by_requester_always_raises_self_sign(
    requester: UUID,
    now: datetime,
) -> None:
    """Four-eyes: on a Requested state, the requester may not grant its own request."""
    state = _state_with(status=RatificationStatus.REQUESTED, requested_by=requester)
    with pytest.raises(RatificationRequesterCannotSelfRatifyError) as exc:
        decide(
            state=state,
            command=GrantRatification(ratification_id=state.id),
            granted_by=requester,
            now=now,
        )
    assert exc.value.principal_id == requester


@pytest.mark.unit
@given(requester=st.uuids(), granted_by=st.uuids(), now=aware_datetimes())
def test_grant_by_independent_principal_emits_single_event(
    requester: UUID,
    granted_by: UUID,
    now: datetime,
) -> None:
    """An independent principal on a Requested state emits one RatificationGranted."""
    assume(requester != granted_by)
    state = _state_with(status=RatificationStatus.REQUESTED, requested_by=requester)
    events = decide(
        state=state,
        command=GrantRatification(ratification_id=state.id),
        granted_by=granted_by,
        now=now,
    )
    assert events == [RatificationGranted(ratification_id=state.id, occurred_at=now)]


@pytest.mark.unit
@given(requester=st.uuids(), granted_by=st.uuids(), now=aware_datetimes())
def test_grant_is_pure_same_input_same_output(
    requester: UUID,
    granted_by: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    assume(requester != granted_by)
    state = _state_with(status=RatificationStatus.REQUESTED, requested_by=requester)
    command = GrantRatification(ratification_id=state.id)
    first = decide(state=state, command=command, granted_by=granted_by, now=now)
    second = decide(state=state, command=command, granted_by=granted_by, now=now)
    assert first == second
