"""Property-based tests for `update_plan_default_parameters.decide` (Recipe BC).

Complements the example-based `test_update_plan_default_parameters_decider.py`
with universal claims across generated inputs. This is a cross-aggregate
decider: the handler loads the owning Method and passes its
`parameters_schema` in via `PlanDefaultParametersContext`, keeping the
decider pure.

    (state, command, context, now) -> list[PlanDefaultParametersUpdated]

Load-bearing properties:

  - Empty state always raises `PlanNotFoundError` carrying the command's
    plan_id, before any merge or schema work.
  - A merged result violating the Method's parameters_schema always
    raises `InvalidPlanDefaultParametersError`.
  - STRICT-when-None: a None schema plus a non-empty patch always raises
    `InvalidPlanDefaultParametersError` whose reason names the missing
    contract.
  - A first-keys patch that conforms emits exactly one
    `PlanDefaultParametersUpdated` keyed on state.id with the FULL
    post-merge dict and occurred_at=now.
  - A merge that equals the current default_parameters no-ops (returns []).
  - Defaults updates are orthogonal to lifecycle: any PlanStatus emits.
  - Pure: same inputs return equal results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.recipe.aggregates.plan import (
    InvalidPlanDefaultParametersError,
    Plan,
    PlanDefaultParametersUpdated,
    PlanName,
    PlanNotFoundError,
    PlanStatus,
)
from cora.recipe.features import update_plan_default_parameters
from cora.recipe.features.update_plan_default_parameters import (
    UpdatePlanDefaultParameters,
)
from cora.recipe.features.update_plan_default_parameters.context import (
    PlanDefaultParametersContext,
)
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_DRAFT = "https://json-schema.org/draft/2020-12/schema"
_LIFECYCLE_STATES = (PlanStatus.DEFINED, PlanStatus.VERSIONED, PlanStatus.DEPRECATED)


def _plan(
    *,
    plan_id: UUID,
    default_parameters: dict[str, Any] | None = None,
    status: PlanStatus = PlanStatus.DEFINED,
) -> Plan:
    return Plan(
        id=plan_id,
        name=PlanName("32-ID FlyScan"),
        practice_id=plan_id,
        asset_ids=frozenset({plan_id}),
        status=status,
        method_id=plan_id,
        default_parameters=default_parameters if default_parameters is not None else {},
    )


def _schema() -> dict[str, Any]:
    return {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {
            "energy": {
                "type": "number",
                "minimum": 5,
                "maximum": 50,
                "unit": {"system": "udunits", "code": "keV"},
            },
            "exposure": {
                "type": "integer",
                "minimum": 1,
                "unit": {"system": "udunits", "code": "ms"},
            },
        },
    }


def _context(schema: dict[str, Any] | None) -> PlanDefaultParametersContext:
    return PlanDefaultParametersContext(method_parameters_schema=schema)


@pytest.mark.unit
@given(plan_id=st.uuids(), now=aware_datetimes())
def test_decide_empty_state_always_raises_plan_not_found(
    plan_id: UUID,
    now: datetime,
) -> None:
    """No prior events: PlanNotFoundError carrying the command's plan_id."""
    with pytest.raises(PlanNotFoundError) as exc:
        update_plan_default_parameters.decide(
            state=None,
            command=UpdatePlanDefaultParameters(
                plan_id=plan_id, default_parameters_patch={"energy": 12.0}
            ),
            context=_context(_schema()),
            now=now,
        )
    assert exc.value.plan_id == plan_id


@pytest.mark.unit
@given(
    plan_id=st.uuids(),
    energy=st.floats(min_value=51.0, max_value=1000.0),
    now=aware_datetimes(),
)
def test_decide_schema_violation_always_raises_invalid_defaults(
    plan_id: UUID,
    energy: float,
    now: datetime,
) -> None:
    """A merged value above the schema maximum raises InvalidPlanDefaultParametersError."""
    state = _plan(plan_id=plan_id)
    with pytest.raises(InvalidPlanDefaultParametersError):
        update_plan_default_parameters.decide(
            state=state,
            command=UpdatePlanDefaultParameters(
                plan_id=plan_id, default_parameters_patch={"energy": energy}
            ),
            context=_context(_schema()),
            now=now,
        )


@pytest.mark.unit
@given(
    plan_id=st.uuids(),
    key=printable_ascii_text(max_size=16),
    value=printable_ascii_text(max_size=16),
    now=aware_datetimes(),
)
def test_decide_none_schema_with_non_empty_patch_raises_invalid_defaults(
    plan_id: UUID,
    key: str,
    value: str,
    now: datetime,
) -> None:
    """STRICT-when-None: a non-empty patch against a None schema is rejected."""
    state = _plan(plan_id=plan_id)
    with pytest.raises(InvalidPlanDefaultParametersError) as exc:
        update_plan_default_parameters.decide(
            state=state,
            command=UpdatePlanDefaultParameters(
                plan_id=plan_id, default_parameters_patch={key: value}
            ),
            context=_context(None),
            now=now,
        )
    assert "Method declares no parameters_schema" in exc.value.reason


@pytest.mark.unit
@given(
    plan_id=st.uuids(),
    energy=st.floats(min_value=5.0, max_value=50.0),
    now=aware_datetimes(),
)
def test_decide_conforming_first_keys_emits_event_with_post_merge_payload(
    plan_id: UUID,
    energy: float,
    now: datetime,
) -> None:
    """A conforming first-keys patch emits one event keyed on state.id at now."""
    state = _plan(plan_id=plan_id)
    events = update_plan_default_parameters.decide(
        state=state,
        command=UpdatePlanDefaultParameters(
            plan_id=plan_id, default_parameters_patch={"energy": energy}
        ),
        context=_context(_schema()),
        now=now,
    )
    assert events == [
        PlanDefaultParametersUpdated(
            plan_id=state.id,
            default_parameters={"energy": energy},
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    plan_id=st.uuids(),
    energy=st.floats(min_value=5.0, max_value=50.0),
    now=aware_datetimes(),
)
def test_decide_unchanged_merge_returns_empty(
    plan_id: UUID,
    energy: float,
    now: datetime,
) -> None:
    """Re-submitting the current value merges to an identical dict: no event."""
    state = _plan(plan_id=plan_id, default_parameters={"energy": energy})
    events = update_plan_default_parameters.decide(
        state=state,
        command=UpdatePlanDefaultParameters(
            plan_id=plan_id, default_parameters_patch={"energy": energy}
        ),
        context=_context(_schema()),
        now=now,
    )
    assert events == []


@pytest.mark.unit
@given(
    plan_id=st.uuids(),
    status=st.sampled_from(_LIFECYCLE_STATES),
    energy=st.floats(min_value=5.0, max_value=50.0),
    now=aware_datetimes(),
)
def test_decide_any_lifecycle_state_emits_event(
    plan_id: UUID,
    status: PlanStatus,
    energy: float,
    now: datetime,
) -> None:
    """Defaults updates are orthogonal to lifecycle: even Deprecated emits."""
    state = _plan(plan_id=plan_id, status=status)
    events = update_plan_default_parameters.decide(
        state=state,
        command=UpdatePlanDefaultParameters(
            plan_id=plan_id, default_parameters_patch={"energy": energy}
        ),
        context=_context(_schema()),
        now=now,
    )
    assert len(events) == 1


@pytest.mark.unit
@given(
    plan_id=st.uuids(),
    energy=st.floats(min_value=5.0, max_value=50.0),
    now=aware_datetimes(),
)
def test_decide_is_pure_same_input_returns_equal_output(
    plan_id: UUID,
    energy: float,
    now: datetime,
) -> None:
    """Two calls with identical args return equal results (no clock leakage)."""
    state = _plan(plan_id=plan_id)
    command = UpdatePlanDefaultParameters(
        plan_id=plan_id, default_parameters_patch={"energy": energy}
    )
    context = _context(_schema())
    first = update_plan_default_parameters.decide(
        state=state, command=command, context=context, now=now
    )
    second = update_plan_default_parameters.decide(
        state=state, command=command, context=context, now=now
    )
    assert first == second
