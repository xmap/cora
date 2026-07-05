"""Property-based tests for `request_ratification.decide` (Trust BC, Ratification).

Complements the example-based `ratification/test_request_ratification_decider.py`
with universal claims across generated inputs. The decider is a pure gated
genesis

    (state, command, requested_by, now) -> list[RatificationRequested]

with a caller-supplied `command.ratification_id` (no injected `new_id`): a
subscriber mints deterministic UUIDs, so the genesis id rides on the command.
`requested_by` is threaded in by the handler from the envelope principal.

Load-bearing properties:

  - state=None + valid input emits exactly one RatificationRequested threading
    the command fields through, with requested_by=the threaded principal and
    occurred_at=now.
  - Any non-None state always raises `RatificationAlreadyExistsError` carrying
    command.ratification_id (idempotency-as-error), regardless of command.
  - A blank or over-100 consequence_class raises `InvalidConsequenceClassError`.
  - consequence_class is trimmed on the emitted event.
  - Pure: same (state, command, requested_by, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

from cora.trust.aggregates.ratification import (
    CONSEQUENCE_CLASS_MAX_LENGTH,
    InvalidConsequenceClassError,
    RatificationAlreadyExistsError,
    RatificationRequested,
)
from cora.trust.features.request_ratification import RequestRatification
from cora.trust.features.request_ratification.decider import decide
from tests._strategies import aware_datetimes, printable_ascii_text
from tests.unit.trust.ratification._fixtures import make_requested

_COMMAND_NAME = printable_ascii_text(min_size=1, max_size=64)
_CONSEQUENCE_CLASS = printable_ascii_text(min_size=1, max_size=CONSEQUENCE_CLASS_MAX_LENGTH)


def _command(
    *,
    ratification_id: UUID,
    target_action_id: UUID,
    command_name: str,
    consequence_class: str,
) -> RequestRatification:
    return RequestRatification(
        ratification_id=ratification_id,
        target_action_id=target_action_id,
        command_name=command_name,
        consequence_class=consequence_class,
    )


@pytest.mark.unit
@given(
    ratification_id=st.uuids(),
    target_action_id=st.uuids(),
    command_name=_COMMAND_NAME,
    consequence_class=_CONSEQUENCE_CLASS,
    requested_by=st.uuids(),
    now=aware_datetimes(),
)
def test_request_happy_path_emits_single_requested_with_threaded_fields(
    ratification_id: UUID,
    target_action_id: UUID,
    command_name: str,
    consequence_class: str,
    requested_by: UUID,
    now: datetime,
) -> None:
    """state=None emits one RatificationRequested threading command fields + requested_by."""
    events = decide(
        state=None,
        command=_command(
            ratification_id=ratification_id,
            target_action_id=target_action_id,
            command_name=command_name,
            consequence_class=consequence_class,
        ),
        requested_by=requested_by,
        now=now,
    )
    assert events == [
        RatificationRequested(
            ratification_id=ratification_id,
            target_action_id=target_action_id,
            command_name=command_name,
            consequence_class=consequence_class,
            requested_by=requested_by,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    ratification_id=st.uuids(),
    target_action_id=st.uuids(),
    command_name=_COMMAND_NAME,
    consequence_class=_CONSEQUENCE_CLASS,
    requested_by=st.uuids(),
    now=aware_datetimes(),
)
def test_request_on_existing_state_always_raises_already_exists(
    ratification_id: UUID,
    target_action_id: UUID,
    command_name: str,
    consequence_class: str,
    requested_by: UUID,
    now: datetime,
) -> None:
    """Any non-None state raises RatificationAlreadyExistsError carrying command id."""
    with pytest.raises(RatificationAlreadyExistsError) as exc:
        decide(
            state=make_requested(),
            command=_command(
                ratification_id=ratification_id,
                target_action_id=target_action_id,
                command_name=command_name,
                consequence_class=consequence_class,
            ),
            requested_by=requested_by,
            now=now,
        )
    assert exc.value.ratification_id == ratification_id


@pytest.mark.unit
@given(
    ratification_id=st.uuids(),
    target_action_id=st.uuids(),
    command_name=_COMMAND_NAME,
    blank=st.text(alphabet=" \t\n", max_size=8),
    requested_by=st.uuids(),
    now=aware_datetimes(),
)
def test_request_blank_consequence_class_always_raises(
    ratification_id: UUID,
    target_action_id: UUID,
    command_name: str,
    blank: str,
    requested_by: UUID,
    now: datetime,
) -> None:
    """A whitespace-only consequence_class raises InvalidConsequenceClassError."""
    with pytest.raises(InvalidConsequenceClassError):
        decide(
            state=None,
            command=_command(
                ratification_id=ratification_id,
                target_action_id=target_action_id,
                command_name=command_name,
                consequence_class=blank,
            ),
            requested_by=requested_by,
            now=now,
        )


@pytest.mark.unit
@given(
    ratification_id=st.uuids(),
    target_action_id=st.uuids(),
    command_name=_COMMAND_NAME,
    overlong=st.integers(min_value=CONSEQUENCE_CLASS_MAX_LENGTH + 1, max_value=500),
    requested_by=st.uuids(),
    now=aware_datetimes(),
)
def test_request_overlong_consequence_class_always_raises(
    ratification_id: UUID,
    target_action_id: UUID,
    command_name: str,
    overlong: int,
    requested_by: UUID,
    now: datetime,
) -> None:
    """A consequence_class longer than the max after trim raises."""
    with pytest.raises(InvalidConsequenceClassError):
        decide(
            state=None,
            command=_command(
                ratification_id=ratification_id,
                target_action_id=target_action_id,
                command_name=command_name,
                consequence_class="x" * overlong,
            ),
            requested_by=requested_by,
            now=now,
        )


@pytest.mark.unit
@given(
    ratification_id=st.uuids(),
    target_action_id=st.uuids(),
    command_name=_COMMAND_NAME,
    consequence_class=_CONSEQUENCE_CLASS,
    requested_by=st.uuids(),
    now=aware_datetimes(),
)
def test_request_trims_consequence_class_on_event(
    ratification_id: UUID,
    target_action_id: UUID,
    command_name: str,
    consequence_class: str,
    requested_by: UUID,
    now: datetime,
) -> None:
    """Surrounding whitespace on consequence_class is stripped on the event."""
    events = decide(
        state=None,
        command=_command(
            ratification_id=ratification_id,
            target_action_id=target_action_id,
            command_name=command_name,
            consequence_class=f"  {consequence_class}  ",
        ),
        requested_by=requested_by,
        now=now,
    )
    assert events[0].consequence_class == consequence_class


@pytest.mark.unit
@given(
    ratification_id=st.uuids(),
    target_action_id=st.uuids(),
    command_name=_COMMAND_NAME,
    consequence_class=_CONSEQUENCE_CLASS,
    requested_by=st.uuids(),
    now=aware_datetimes(),
)
def test_request_is_pure_same_input_same_output(
    ratification_id: UUID,
    target_action_id: UUID,
    command_name: str,
    consequence_class: str,
    requested_by: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    command = _command(
        ratification_id=ratification_id,
        target_action_id=target_action_id,
        command_name=command_name,
        consequence_class=consequence_class,
    )
    first = decide(state=None, command=command, requested_by=requested_by, now=now)
    second = decide(state=None, command=command, requested_by=requested_by, now=now)
    assert first == second
