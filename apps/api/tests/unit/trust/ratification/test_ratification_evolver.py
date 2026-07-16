"""Evolver tests for the Ratification aggregate (3-state FSM)."""

import pytest

from cora.trust.aggregates.ratification import (
    Ratification,
    RatificationDenied,
    RatificationGranted,
    RatificationRequested,
    RatificationStatus,
    evolve,
    fold,
)
from tests.unit.trust.ratification._fixtures import (
    COMMAND_NAME,
    CONSEQUENCE_CLASS,
    NOW,
    RATIFICATION_ID,
    REQUESTER_ID,
    TARGET_REF,
)

_REQUESTED = RatificationRequested(
    ratification_id=RATIFICATION_ID,
    target_action_id=TARGET_REF,
    command_name=COMMAND_NAME,
    consequence_class=CONSEQUENCE_CLASS,
    requested_by=REQUESTER_ID,
    occurred_at=NOW,
)


@pytest.mark.unit
def test_genesis_builds_requested_state() -> None:
    state = evolve(None, _REQUESTED)
    assert isinstance(state, Ratification)
    assert state.id == RATIFICATION_ID
    assert state.target_action_id == TARGET_REF
    assert state.command_name == COMMAND_NAME
    assert state.consequence_class == CONSEQUENCE_CLASS
    assert state.requested_by == REQUESTER_ID
    assert state.status is RatificationStatus.REQUESTED
    assert state.last_reason is None


@pytest.mark.unit
def test_granted_transitions_to_granted() -> None:
    state = fold(
        [_REQUESTED, RatificationGranted(ratification_id=RATIFICATION_ID, occurred_at=NOW)]
    )
    assert state is not None
    assert state.status is RatificationStatus.GRANTED
    assert state.last_reason is None


@pytest.mark.unit
def test_denied_transitions_to_denied_with_reason() -> None:
    state = fold(
        [
            _REQUESTED,
            RatificationDenied(
                ratification_id=RATIFICATION_ID, reason="too risky", occurred_at=NOW
            ),
        ]
    )
    assert state is not None
    assert state.status is RatificationStatus.DENIED
    assert state.last_reason == "too risky"


@pytest.mark.unit
def test_genesis_ignores_prior_state() -> None:
    prior = evolve(None, _REQUESTED)
    # A second genesis event replaces rather than merges (genesis ignores state).
    rebuilt = evolve(prior, _REQUESTED)
    assert rebuilt.status is RatificationStatus.REQUESTED


@pytest.mark.unit
def test_fold_empty_is_none() -> None:
    assert fold([]) is None
