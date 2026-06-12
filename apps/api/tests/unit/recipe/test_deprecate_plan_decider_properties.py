"""Property-based tests for `deprecate_plan.decide` (Recipe BC).

Complements the example-based `test_deprecate_plan_decider.py` with
universal claims across generated inputs. The decider is a pure multi-
source FSM transition

    (state, command, now) -> list[PlanDeprecated]

Load-bearing properties:

  - state=None always raises `PlanNotFoundError` carrying command.plan_id.
  - The source-state partition is total over `PlanStatus`: each of
    {Defined, Versioned} emits exactly one `PlanDeprecated`
    (plan_id=state.id, occurred_at=now); every other status raises
    `PlanCannotDeprecateError` carrying the current status, so a future
    status value cannot silently fall through.
  - The emitted event's plan_id is `state.id`, never `command.plan_id`.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.recipe.aggregates.plan import (
    Plan,
    PlanCannotDeprecateError,
    PlanDeprecated,
    PlanName,
    PlanNotFoundError,
    PlanStatus,
)
from cora.recipe.features import deprecate_plan
from cora.recipe.features.deprecate_plan import DeprecatePlan
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime

_PRACTICE_ID = UUID(int=1)
_ASSET_ID = UUID(int=2)

_DEPRECATABLE_SOURCES = (PlanStatus.DEFINED, PlanStatus.VERSIONED)
_DISALLOWED_SOURCES = tuple(s for s in PlanStatus if s not in frozenset(_DEPRECATABLE_SOURCES))


def _plan(*, plan_id: UUID, status: PlanStatus) -> Plan:
    return Plan(
        id=plan_id,
        name=PlanName("32-ID FlyScan"),
        practice_id=_PRACTICE_ID,
        asset_ids=frozenset({_ASSET_ID}),
        status=status,
    )


@pytest.mark.unit
@given(plan_id=st.uuids(), now=aware_datetimes())
def test_deprecate_with_none_state_always_raises_not_found(
    plan_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `PlanNotFoundError` carrying command.plan_id."""
    with pytest.raises(PlanNotFoundError) as exc:
        deprecate_plan.decide(state=None, command=DeprecatePlan(plan_id=plan_id), now=now)
    assert exc.value.plan_id == plan_id


@pytest.mark.unit
@given(
    plan_id=st.uuids(),
    source=st.sampled_from(_DEPRECATABLE_SOURCES),
    now=aware_datetimes(),
)
def test_deprecate_from_allowed_source_emits_single_event(
    plan_id: UUID,
    source: PlanStatus,
    now: datetime,
) -> None:
    """Each allowed source emits exactly one PlanDeprecated at now."""
    events = deprecate_plan.decide(
        state=_plan(plan_id=plan_id, status=source),
        command=DeprecatePlan(plan_id=plan_id),
        now=now,
    )
    assert events == [PlanDeprecated(plan_id=plan_id, occurred_at=now)]


@pytest.mark.unit
@given(
    plan_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_deprecate_from_disallowed_source_always_raises_cannot_deprecate(
    plan_id: UUID,
    source: PlanStatus,
    now: datetime,
) -> None:
    """Any source outside {Defined, Versioned} raises, carrying current status."""
    with pytest.raises(PlanCannotDeprecateError) as exc:
        deprecate_plan.decide(
            state=_plan(plan_id=plan_id, status=source),
            command=DeprecatePlan(plan_id=plan_id),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(state_plan_id=st.uuids(), command_plan_id=st.uuids(), now=aware_datetimes())
def test_deprecate_emits_event_with_state_id_not_command_plan_id(
    state_plan_id: UUID,
    command_plan_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's plan_id is state.id, not command.plan_id."""
    assume(state_plan_id != command_plan_id)
    events = deprecate_plan.decide(
        state=_plan(plan_id=state_plan_id, status=PlanStatus.DEFINED),
        command=DeprecatePlan(plan_id=command_plan_id),
        now=now,
    )
    assert events[0].plan_id == state_plan_id


@pytest.mark.unit
@given(plan_id=st.uuids(), now=aware_datetimes())
def test_deprecate_is_pure_same_input_same_output(plan_id: UUID, now: datetime) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _plan(plan_id=plan_id, status=PlanStatus.DEFINED)
    command = DeprecatePlan(plan_id=plan_id)
    first = deprecate_plan.decide(state=state, command=command, now=now)
    second = deprecate_plan.decide(state=state, command=command, now=now)
    assert first == second
