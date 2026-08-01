"""Unit tests for the `deprecate_method` slice's pure decider.

Multi-source-state guard: `Defined | Versioned -> Deprecated`. Same
source-set as version_method but the target is terminal.
Re-deprecating raises (strict-not-idempotent). Mirrors
`test_deprecate_family_decider.py` (Equipment 5f-2).
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.recipe.aggregates.method import (
    Method,
    MethodCannotDeprecateError,
    MethodDeprecated,
    MethodName,
    MethodNotFoundError,
    MethodStatus,
)
from cora.recipe.features import deprecate_method
from cora.recipe.features.deprecate_method import DeprecateMethod
from cora.shared.deprecation import DeprecationReason

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _method(
    *,
    status: MethodStatus = MethodStatus.DEFINED,
    version: str | None = None,
) -> Method:
    return Method(
        id=uuid4(),
        name=MethodName("XRF Mapping"),
        needed_family_ids=frozenset(),
        status=status,
        version=version,
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "source",
    [MethodStatus.DEFINED, MethodStatus.VERSIONED],
)
def test_decide_emits_method_deprecated_for_each_allowed_source_status(
    source: MethodStatus,
) -> None:
    state = _method(status=source)
    events = deprecate_method.decide(
        state=state,
        command=DeprecateMethod(reason=DeprecationReason.SUPERSEDED, method_id=state.id),
        now=_NOW,
    )
    assert events == [MethodDeprecated(reason="Superseded", method_id=state.id, occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_raises_method_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(MethodNotFoundError) as exc_info:
        deprecate_method.decide(
            state=None,
            command=DeprecateMethod(reason=DeprecationReason.SUPERSEDED, method_id=target_id),
            now=_NOW,
        )
    assert exc_info.value.method_id == target_id


@pytest.mark.unit
def test_decide_raises_cannot_deprecate_when_already_deprecated() -> None:
    """Strict-not-idempotent."""
    state = _method(status=MethodStatus.DEPRECATED)
    with pytest.raises(MethodCannotDeprecateError) as exc_info:
        deprecate_method.decide(
            state=state,
            command=DeprecateMethod(reason=DeprecationReason.SUPERSEDED, method_id=state.id),
            now=_NOW,
        )
    assert exc_info.value.method_id == state.id
    assert exc_info.value.current_status is MethodStatus.DEPRECATED


@pytest.mark.unit
def test_decide_error_message_lists_both_allowed_source_statuses() -> None:
    state = _method(status=MethodStatus.DEPRECATED)
    with pytest.raises(MethodCannotDeprecateError) as exc_info:
        deprecate_method.decide(
            state=state,
            command=DeprecateMethod(reason=DeprecationReason.SUPERSEDED, method_id=state.id),
            now=_NOW,
        )
    msg = str(exc_info.value)
    assert "Defined" in msg
    assert "Versioned" in msg


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _method()
    command = DeprecateMethod(reason=DeprecationReason.SUPERSEDED, method_id=state.id)
    first = deprecate_method.decide(state=state, command=command, now=_NOW)
    second = deprecate_method.decide(state=state, command=command, now=_NOW)
    assert first == second
