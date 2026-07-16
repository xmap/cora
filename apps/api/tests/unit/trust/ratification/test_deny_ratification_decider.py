"""Decider tests for the `deny_ratification` slice (Requested -> Denied).

Same independence (four-eyes) invariant as grant, plus mandatory reason
validation.
"""

import pytest

from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.trust.aggregates.ratification import (
    InvalidRatificationReasonError,
    RatificationCannotDenyError,
    RatificationDenied,
    RatificationGranted,
    RatificationNotFoundError,
    RatificationRequesterCannotSelfRatifyError,
    evolve,
)
from cora.trust.features.deny_ratification import DenyRatification
from cora.trust.features.deny_ratification.decider import decide
from tests.unit.trust.ratification._fixtures import (
    NOW,
    OTHER_PRINCIPAL_ID,
    RATIFICATION_ID,
    REQUESTER_ID,
    make_requested,
)

_CMD = DenyRatification(ratification_id=RATIFICATION_ID, reason="unsafe first-of-kind action")


@pytest.mark.unit
def test_independent_principal_denies_with_reason() -> None:
    events = decide(state=make_requested(), command=_CMD, denied_by=OTHER_PRINCIPAL_ID, now=NOW)
    assert len(events) == 1
    [e] = events
    assert isinstance(e, RatificationDenied)
    assert e.ratification_id == RATIFICATION_ID
    assert e.reason == "unsafe first-of-kind action"
    assert e.occurred_at == NOW


@pytest.mark.unit
def test_requester_cannot_self_deny() -> None:
    with pytest.raises(RatificationRequesterCannotSelfRatifyError):
        decide(state=make_requested(), command=_CMD, denied_by=REQUESTER_ID, now=NOW)


@pytest.mark.unit
def test_not_found_raises() -> None:
    with pytest.raises(RatificationNotFoundError):
        decide(state=None, command=_CMD, denied_by=OTHER_PRINCIPAL_ID, now=NOW)


@pytest.mark.unit
def test_deny_from_terminal_raises_cannot_deny() -> None:
    granted = evolve(
        make_requested(), RatificationGranted(ratification_id=RATIFICATION_ID, occurred_at=NOW)
    )
    with pytest.raises(RatificationCannotDenyError):
        decide(state=granted, command=_CMD, denied_by=OTHER_PRINCIPAL_ID, now=NOW)


@pytest.mark.unit
def test_blank_reason_raises() -> None:
    cmd = DenyRatification(ratification_id=RATIFICATION_ID, reason="   ")
    with pytest.raises(InvalidRatificationReasonError):
        decide(state=make_requested(), command=cmd, denied_by=OTHER_PRINCIPAL_ID, now=NOW)


@pytest.mark.unit
def test_overlong_reason_raises() -> None:
    cmd = DenyRatification(ratification_id=RATIFICATION_ID, reason="x" * (REASON_MAX_LENGTH + 1))
    with pytest.raises(InvalidRatificationReasonError):
        decide(state=make_requested(), command=cmd, denied_by=OTHER_PRINCIPAL_ID, now=NOW)


@pytest.mark.unit
def test_reason_trimmed_on_event() -> None:
    cmd = DenyRatification(ratification_id=RATIFICATION_ID, reason="  no  ")
    [e] = decide(state=make_requested(), command=cmd, denied_by=OTHER_PRINCIPAL_ID, now=NOW)
    assert e.reason == "no"
