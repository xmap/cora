"""Decider tests for the `grant_ratification` slice (Requested -> Granted).

The centerpiece is the independence (four-eyes) invariant: the grantor must
differ from the requester, and the check is kind-blind (bare principal ids).
"""

import pytest

from cora.trust.aggregates.ratification import (
    RatificationCannotGrantError,
    RatificationGranted,
    RatificationNotFoundError,
    RatificationRequesterCannotSelfRatifyError,
    RatificationStatus,
    evolve,
)
from cora.trust.features.grant_ratification import GrantRatification
from cora.trust.features.grant_ratification.decider import decide
from tests.unit.trust.ratification._fixtures import (
    NOW,
    OTHER_PRINCIPAL_ID,
    RATIFICATION_ID,
    REQUESTER_ID,
    make_requested,
)

_CMD = GrantRatification(ratification_id=RATIFICATION_ID)


@pytest.mark.unit
def test_independent_principal_grants() -> None:
    events = decide(state=make_requested(), command=_CMD, granted_by=OTHER_PRINCIPAL_ID, now=NOW)
    assert len(events) == 1
    [e] = events
    assert isinstance(e, RatificationGranted)
    assert e.ratification_id == RATIFICATION_ID
    assert e.occurred_at == NOW


@pytest.mark.unit
def test_requester_cannot_self_sign() -> None:
    # The four-eyes invariant: the requester may not grant its own request.
    with pytest.raises(RatificationRequesterCannotSelfRatifyError):
        decide(state=make_requested(), command=_CMD, granted_by=REQUESTER_ID, now=NOW)


@pytest.mark.unit
def test_grant_is_kind_blind() -> None:
    # The decider compares bare principal ids; there is no actor-kind branch. Two
    # different independent principals both grant identically.
    [e] = decide(state=make_requested(), command=_CMD, granted_by=OTHER_PRINCIPAL_ID, now=NOW)
    assert isinstance(e, RatificationGranted)


@pytest.mark.unit
def test_not_found_raises() -> None:
    with pytest.raises(RatificationNotFoundError):
        decide(state=None, command=_CMD, granted_by=OTHER_PRINCIPAL_ID, now=NOW)


@pytest.mark.unit
def test_grant_from_granted_raises_cannot_grant() -> None:
    granted = evolve(
        make_requested(), RatificationGranted(ratification_id=RATIFICATION_ID, occurred_at=NOW)
    )
    assert granted.status is RatificationStatus.GRANTED
    with pytest.raises(RatificationCannotGrantError):
        decide(state=granted, command=_CMD, granted_by=OTHER_PRINCIPAL_ID, now=NOW)
