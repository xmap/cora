"""Decider tests for the `request_ratification` slice (genesis)."""

import pytest

from cora.trust.aggregates.ratification import (
    CONSEQUENCE_CLASS_MAX_LENGTH,
    InvalidConsequenceClassError,
    RatificationAlreadyExistsError,
    RatificationRequested,
)
from cora.trust.features.request_ratification import RequestRatification
from cora.trust.features.request_ratification.decider import decide
from tests.unit.trust.ratification._fixtures import (
    COMMAND_NAME,
    CONSEQUENCE_CLASS,
    NOW,
    OTHER_PRINCIPAL_ID,
    RATIFICATION_ID,
    REQUESTER_ID,
    TARGET_REF,
    make_requested,
)

_BASE_CMD = RequestRatification(
    ratification_id=RATIFICATION_ID,
    target_action_id=TARGET_REF,
    command_name=COMMAND_NAME,
    consequence_class=CONSEQUENCE_CLASS,
)


@pytest.mark.unit
def test_genesis_emits_ratification_requested() -> None:
    events = decide(state=None, command=_BASE_CMD, requested_by=REQUESTER_ID, now=NOW)
    assert len(events) == 1
    [e] = events
    assert isinstance(e, RatificationRequested)
    assert e.ratification_id == RATIFICATION_ID
    assert e.target_action_id == TARGET_REF
    assert e.command_name == COMMAND_NAME
    assert e.consequence_class == CONSEQUENCE_CLASS
    assert e.requested_by == REQUESTER_ID
    assert e.occurred_at == NOW


@pytest.mark.unit
def test_requester_is_the_threaded_principal_not_a_command_field() -> None:
    # requested_by comes from the handler-threaded principal, so the same command
    # records whoever issues it (unspoofable). Two principals -> two requesters.
    [e1] = decide(state=None, command=_BASE_CMD, requested_by=REQUESTER_ID, now=NOW)
    [e2] = decide(state=None, command=_BASE_CMD, requested_by=OTHER_PRINCIPAL_ID, now=NOW)
    assert e1.requested_by == REQUESTER_ID
    assert e2.requested_by == OTHER_PRINCIPAL_ID


@pytest.mark.unit
def test_collision_raises_already_exists() -> None:
    with pytest.raises(RatificationAlreadyExistsError):
        decide(state=make_requested(), command=_BASE_CMD, requested_by=REQUESTER_ID, now=NOW)


@pytest.mark.unit
def test_blank_consequence_class_raises() -> None:
    cmd = RequestRatification(
        ratification_id=RATIFICATION_ID,
        target_action_id=TARGET_REF,
        command_name=COMMAND_NAME,
        consequence_class="   ",
    )
    with pytest.raises(InvalidConsequenceClassError):
        decide(state=None, command=cmd, requested_by=REQUESTER_ID, now=NOW)


@pytest.mark.unit
def test_overlong_consequence_class_raises() -> None:
    cmd = RequestRatification(
        ratification_id=RATIFICATION_ID,
        target_action_id=TARGET_REF,
        command_name=COMMAND_NAME,
        consequence_class="x" * (CONSEQUENCE_CLASS_MAX_LENGTH + 1),
    )
    with pytest.raises(InvalidConsequenceClassError):
        decide(state=None, command=cmd, requested_by=REQUESTER_ID, now=NOW)


@pytest.mark.unit
def test_consequence_class_trimmed_on_event() -> None:
    cmd = RequestRatification(
        ratification_id=RATIFICATION_ID,
        target_action_id=TARGET_REF,
        command_name=COMMAND_NAME,
        consequence_class="  irreversible  ",
    )
    [e] = decide(state=None, command=cmd, requested_by=REQUESTER_ID, now=NOW)
    assert e.consequence_class == "irreversible"
