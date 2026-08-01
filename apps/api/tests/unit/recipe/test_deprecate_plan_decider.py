"""Unit tests for the `deprecate_plan` slice's pure decider.

Mirror of `test_deprecate_practice_decider.py` /
`test_deprecate_method_decider.py`. Multi-source guard
`Defined | Versioned -> Deprecated`. Re-deprecating raises.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

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
from cora.shared.deprecation import DeprecationReason

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _plan(
    *,
    status: PlanStatus = PlanStatus.DEFINED,
    version: str | None = None,
) -> Plan:
    return Plan(
        id=uuid4(),
        name=PlanName("32-ID FlyScan"),
        practice_id=uuid4(),
        asset_ids=frozenset({uuid4()}),
        status=status,
        version=version,
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "source",
    [PlanStatus.DEFINED, PlanStatus.VERSIONED],
)
def test_decide_emits_plan_deprecated_for_each_allowed_source_status(
    source: PlanStatus,
) -> None:
    state = _plan(status=source)
    events = deprecate_plan.decide(
        state=state,
        command=DeprecatePlan(reason=DeprecationReason.SUPERSEDED, plan_id=state.id),
        now=_NOW,
    )
    assert events == [PlanDeprecated(reason="Superseded", plan_id=state.id, occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_raises_plan_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(PlanNotFoundError) as exc_info:
        deprecate_plan.decide(
            state=None,
            command=DeprecatePlan(reason=DeprecationReason.SUPERSEDED, plan_id=target_id),
            now=_NOW,
        )
    assert exc_info.value.plan_id == target_id


@pytest.mark.unit
def test_decide_raises_cannot_deprecate_when_already_deprecated() -> None:
    """Strict-not-idempotent."""
    state = _plan(status=PlanStatus.DEPRECATED)
    with pytest.raises(PlanCannotDeprecateError) as exc_info:
        deprecate_plan.decide(
            state=state,
            command=DeprecatePlan(reason=DeprecationReason.SUPERSEDED, plan_id=state.id),
            now=_NOW,
        )
    assert exc_info.value.plan_id == state.id
    assert exc_info.value.current_status is PlanStatus.DEPRECATED


@pytest.mark.unit
def test_decide_error_message_lists_both_allowed_source_statuses() -> None:
    state = _plan(status=PlanStatus.DEPRECATED)
    with pytest.raises(PlanCannotDeprecateError) as exc_info:
        deprecate_plan.decide(
            state=state,
            command=DeprecatePlan(reason=DeprecationReason.SUPERSEDED, plan_id=state.id),
            now=_NOW,
        )
    msg = str(exc_info.value)
    assert "Defined" in msg
    assert "Versioned" in msg


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _plan()
    command = DeprecatePlan(reason=DeprecationReason.SUPERSEDED, plan_id=state.id)
    first = deprecate_plan.decide(state=state, command=command, now=_NOW)
    second = deprecate_plan.decide(state=state, command=command, now=_NOW)
    assert first == second
