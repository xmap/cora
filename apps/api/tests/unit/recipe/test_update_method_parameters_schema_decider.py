"""Unit tests for the `update_method_parameters_schema` slice's pure decider.

The decider:
  - Raises MethodNotFoundError on empty state
  - Validates the proposed schema via validate_parameters_schema
  - No-ops (returns []) on unchanged-vs-current schema
  - Emits MethodParametersSchemaUpdated otherwise

Schema can be set, replaced, or cleared (None payload). All lifecycle states
(Defined / Versioned / Deprecated) are valid sources, since schema iteration
is independent of content lifecycle.

Mirrors `test_update_family_settings_schema_decider.py` (Equipment) shape and
assertions.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from cora.recipe.aggregates.method import (
    ExecutionPattern,
    InvalidMethodIterativeStoppingFieldError,
    InvalidMethodParametersSchemaError,
    Method,
    MethodName,
    MethodNotFoundError,
    MethodParametersSchemaUpdated,
    MethodStatus,
)
from cora.recipe.features import update_method_parameters_schema
from cora.recipe.features.update_method_parameters_schema import (
    UpdateMethodParametersSchema,
)

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _method(
    *,
    status: MethodStatus = MethodStatus.DEFINED,
    parameters_schema: dict[str, Any] | None = None,
    execution_pattern: ExecutionPattern | None = None,
) -> Method:
    return Method(
        id=uuid4(),
        name=MethodName("Continuous Rotation Tomography"),
        status=status,
        parameters_schema=parameters_schema,
        execution_pattern=execution_pattern,
    )


def _valid_schema(min_val: int = 5) -> dict[str, Any]:
    return {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {
            "energy": {
                "type": "number",
                "minimum": min_val,
                "unit": {"system": "udunits", "code": "keV"},
            }
        },
    }


def _schema_with_property(prop: str) -> dict[str, Any]:
    """A valid parameters_schema declaring a single named property."""
    return {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {prop: {"type": "number"}},
    }


@pytest.mark.unit
def test_decide_emits_event_when_setting_schema_for_first_time() -> None:
    state = _method(parameters_schema=None)
    schema = _valid_schema()
    events = update_method_parameters_schema.decide(
        state=state,
        command=UpdateMethodParametersSchema(method_id=state.id, parameters_schema=schema),
        now=_NOW,
    )
    assert events == [
        MethodParametersSchemaUpdated(
            method_id=state.id,
            parameters_schema=schema,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_emits_event_when_replacing_schema() -> None:
    state = _method(parameters_schema=_valid_schema(min_val=5))
    new_schema = _valid_schema(min_val=10)
    events = update_method_parameters_schema.decide(
        state=state,
        command=UpdateMethodParametersSchema(method_id=state.id, parameters_schema=new_schema),
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].parameters_schema == new_schema


@pytest.mark.unit
def test_decide_emits_event_when_clearing_schema() -> None:
    """Clearing via None payload IS an event (audit trail of
    'operator removed declarations on date X')."""
    state = _method(parameters_schema=_valid_schema())
    events = update_method_parameters_schema.decide(
        state=state,
        command=UpdateMethodParametersSchema(method_id=state.id, parameters_schema=None),
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].parameters_schema is None


@pytest.mark.unit
def test_decide_no_op_when_schema_unchanged() -> None:
    """Re-submitting the same schema is a no-op (no event emitted).
    Avoids audit-log noise; the value IS the audit, identical
    re-submission carries no information."""
    schema = _valid_schema()
    state = _method(parameters_schema=schema)
    events = update_method_parameters_schema.decide(
        state=state,
        command=UpdateMethodParametersSchema(method_id=state.id, parameters_schema=schema),
        now=_NOW,
    )
    assert events == []


@pytest.mark.unit
def test_decide_no_op_when_both_current_and_proposed_are_none() -> None:
    state = _method(parameters_schema=None)
    events = update_method_parameters_schema.decide(
        state=state,
        command=UpdateMethodParametersSchema(method_id=state.id, parameters_schema=None),
        now=_NOW,
    )
    assert events == []


@pytest.mark.unit
def test_decide_raises_method_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(MethodNotFoundError) as exc_info:
        update_method_parameters_schema.decide(
            state=None,
            command=UpdateMethodParametersSchema(
                method_id=target_id, parameters_schema=_valid_schema()
            ),
            now=_NOW,
        )
    assert exc_info.value.method_id == target_id


@pytest.mark.unit
def test_decide_raises_invalid_schema_for_missing_dollar_schema() -> None:
    state = _method()
    with pytest.raises(InvalidMethodParametersSchemaError):
        update_method_parameters_schema.decide(
            state=state,
            command=UpdateMethodParametersSchema(
                method_id=state.id,
                parameters_schema={"type": "object"},  # no $schema
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_raises_invalid_schema_for_forbidden_keyword() -> None:
    state = _method()
    with pytest.raises(InvalidMethodParametersSchemaError):
        update_method_parameters_schema.decide(
            state=state,
            command=UpdateMethodParametersSchema(
                method_id=state.id,
                parameters_schema={"$schema": _DRAFT, "oneOf": [{"type": "string"}]},
            ),
            now=_NOW,
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "lifecycle_status",
    [MethodStatus.DEFINED, MethodStatus.VERSIONED, MethodStatus.DEPRECATED],
)
def test_decide_accepts_schema_update_in_any_lifecycle_state(
    lifecycle_status: MethodStatus,
) -> None:
    """Schema iteration is independent of content lifecycle: schema
    can be updated even on Deprecated methods (operators may refine
    the audit-record schema after deprecation)."""
    state = _method(status=lifecycle_status)
    events = update_method_parameters_schema.decide(
        state=state,
        command=UpdateMethodParametersSchema(method_id=state.id, parameters_schema=_valid_schema()),
        now=_NOW,
    )
    assert len(events) == 1


# ---------- compute classification: ITERATIVE stopping key (L4(a)) ----------


@pytest.mark.unit
def test_decide_rejects_iterative_schema_without_stopping_key() -> None:
    """L4(a): an ITERATIVE Method's parameters_schema, once set, MUST
    declare a budget (max_iter-shape) or tolerance (tol-shape) key.
    A schema with neither is rejected (Invalid<X> family -> HTTP 400)."""
    state = _method(execution_pattern=ExecutionPattern.ITERATIVE)
    with pytest.raises(InvalidMethodIterativeStoppingFieldError) as exc_info:
        update_method_parameters_schema.decide(
            state=state,
            command=UpdateMethodParametersSchema(
                method_id=state.id, parameters_schema=_valid_schema()
            ),
            now=_NOW,
        )
    assert exc_info.value.method_id == state.id


@pytest.mark.unit
@pytest.mark.parametrize("stopping_key", ["max_iter", "num_iter", "nsteps"])
def test_decide_accepts_iterative_schema_with_budget_key(stopping_key: str) -> None:
    """A budget-shaped stopping key satisfies L4(a)."""
    state = _method(execution_pattern=ExecutionPattern.ITERATIVE)
    events = update_method_parameters_schema.decide(
        state=state,
        command=UpdateMethodParametersSchema(
            method_id=state.id, parameters_schema=_schema_with_property(stopping_key)
        ),
        now=_NOW,
    )
    assert len(events) == 1


@pytest.mark.unit
@pytest.mark.parametrize("stopping_key", ["tol", "rtol", "atol"])
def test_decide_accepts_iterative_schema_with_tolerance_key(stopping_key: str) -> None:
    """A tolerance-shaped stopping key satisfies L4(a)."""
    state = _method(execution_pattern=ExecutionPattern.ITERATIVE)
    events = update_method_parameters_schema.decide(
        state=state,
        command=UpdateMethodParametersSchema(
            method_id=state.id, parameters_schema=_schema_with_property(stopping_key)
        ),
        now=_NOW,
    )
    assert len(events) == 1


@pytest.mark.unit
@pytest.mark.parametrize(
    "pattern",
    [ExecutionPattern.BATCH, ExecutionPattern.STREAMING, None],
)
def test_decide_does_not_enforce_stopping_key_on_non_iterative(
    pattern: ExecutionPattern | None,
) -> None:
    """L4(a) is ITERATIVE-only: a BATCH or STREAMING Method, and an
    unclassified (None) Method, may declare a schema with no stopping
    key; all skip the check."""
    state = _method(execution_pattern=pattern)
    events = update_method_parameters_schema.decide(
        state=state,
        command=UpdateMethodParametersSchema(method_id=state.id, parameters_schema=_valid_schema()),
        now=_NOW,
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_iterative_with_none_schema_stays_unconstrained() -> None:
    """A freshly-defined ITERATIVE Method with no schema is in a
    transient unconstrained state: clearing/leaving the schema None
    raises nothing (L4(a) fires only when a schema is being set)."""
    state = _method(execution_pattern=ExecutionPattern.ITERATIVE, parameters_schema=None)
    events = update_method_parameters_schema.decide(
        state=state,
        command=UpdateMethodParametersSchema(method_id=state.id, parameters_schema=None),
        now=_NOW,
    )
    assert events == []
