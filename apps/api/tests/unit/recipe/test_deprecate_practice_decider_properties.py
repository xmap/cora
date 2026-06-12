"""Property-based tests for `deprecate_practice.decide` (Recipe BC).

Complements the example-based `test_deprecate_practice_decider.py` with
universal claims across generated inputs. The decider is a pure
multi-source FSM terminal

    (state, command, now) -> list[PracticeDeprecated]

Load-bearing properties:

  - state=None always raises `PracticeNotFoundError` carrying
    command.practice_id.
  - The source-state partition is total over `PracticeStatus`: only
    `Defined` and `Versioned` emit exactly one `PracticeDeprecated`
    (practice_id=state.id, occurred_at=now); every other status raises
    `PracticeCannotDeprecateError` carrying the current status, so a
    future status value cannot silently fall through.
  - The emitted event's practice_id is `state.id`, never
    `command.practice_id`.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.recipe.aggregates.practice import (
    Practice,
    PracticeCannotDeprecateError,
    PracticeDeprecated,
    PracticeName,
    PracticeNotFoundError,
    PracticeStatus,
)
from cora.recipe.features import deprecate_practice
from cora.recipe.features.deprecate_practice import DeprecatePractice
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime

_METHOD_ID = UUID(int=1)
_SITE_ID = UUID(int=2)

_DEPRECATABLE_SOURCES = (PracticeStatus.DEFINED, PracticeStatus.VERSIONED)
_DISALLOWED_SOURCES = tuple(s for s in PracticeStatus if s not in frozenset(_DEPRECATABLE_SOURCES))


def _practice(*, practice_id: UUID, status: PracticeStatus) -> Practice:
    return Practice(
        id=practice_id,
        name=PracticeName("APS Standard Tomography"),
        method_id=_METHOD_ID,
        site_id=_SITE_ID,
        status=status,
    )


@pytest.mark.unit
@given(practice_id=st.uuids(), now=aware_datetimes())
def test_deprecate_with_none_state_always_raises_not_found(
    practice_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `PracticeNotFoundError` carrying the command id."""
    with pytest.raises(PracticeNotFoundError) as exc:
        deprecate_practice.decide(
            state=None,
            command=DeprecatePractice(practice_id=practice_id),
            now=now,
        )
    assert exc.value.practice_id == practice_id


@pytest.mark.unit
@given(
    practice_id=st.uuids(),
    source=st.sampled_from(_DEPRECATABLE_SOURCES),
    now=aware_datetimes(),
)
def test_deprecate_from_allowed_source_emits_single_event(
    practice_id: UUID,
    source: PracticeStatus,
    now: datetime,
) -> None:
    """Defined and Versioned both emit exactly one PracticeDeprecated."""
    events = deprecate_practice.decide(
        state=_practice(practice_id=practice_id, status=source),
        command=DeprecatePractice(practice_id=practice_id),
        now=now,
    )
    assert events == [PracticeDeprecated(practice_id=practice_id, occurred_at=now)]


@pytest.mark.unit
@given(
    practice_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_deprecate_from_disallowed_source_always_raises_cannot_deprecate(
    practice_id: UUID,
    source: PracticeStatus,
    now: datetime,
) -> None:
    """Any source outside the deprecatable set raises, carrying current status."""
    with pytest.raises(PracticeCannotDeprecateError) as exc:
        deprecate_practice.decide(
            state=_practice(practice_id=practice_id, status=source),
            command=DeprecatePractice(practice_id=practice_id),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    state_practice_id=st.uuids(),
    command_practice_id=st.uuids(),
    source=st.sampled_from(_DEPRECATABLE_SOURCES),
    now=aware_datetimes(),
)
def test_deprecate_emits_event_with_state_id_not_command_id(
    state_practice_id: UUID,
    command_practice_id: UUID,
    source: PracticeStatus,
    now: datetime,
) -> None:
    """The emitted event's practice_id is state.id, not command.practice_id."""
    assume(state_practice_id != command_practice_id)
    events = deprecate_practice.decide(
        state=_practice(practice_id=state_practice_id, status=source),
        command=DeprecatePractice(practice_id=command_practice_id),
        now=now,
    )
    assert events[0].practice_id == state_practice_id


@pytest.mark.unit
@given(
    practice_id=st.uuids(),
    source=st.sampled_from(_DEPRECATABLE_SOURCES),
    now=aware_datetimes(),
)
def test_deprecate_is_pure_same_input_returns_equal_output(
    practice_id: UUID,
    source: PracticeStatus,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _practice(practice_id=practice_id, status=source)
    command = DeprecatePractice(practice_id=practice_id)
    first = deprecate_practice.decide(state=state, command=command, now=now)
    second = deprecate_practice.decide(state=state, command=command, now=now)
    assert first == second
