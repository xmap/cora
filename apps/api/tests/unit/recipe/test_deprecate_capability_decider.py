"""Unit tests for the `deprecate_capability` slice's pure decider."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.recipe.aggregates.capability import (
    Capability,
    CapabilityCannotDeprecateError,
    CapabilityCode,
    CapabilityDeprecated,
    CapabilityName,
    CapabilityNotFoundError,
    CapabilityStatus,
    ExecutorShape,
)
from cora.recipe.features.deprecate_capability import DeprecateCapability, decide
from cora.shared.deprecation import DeprecationReason

_NOW = datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC)


def _state(status: CapabilityStatus = CapabilityStatus.DEFINED) -> Capability:
    return Capability(
        id=uuid4(),
        code=CapabilityCode("cora.capability.x"),
        name=CapabilityName("X"),
        status=status,
        executor_shapes=frozenset({ExecutorShape.METHOD}),
    )


@pytest.mark.unit
def test_decide_deprecates_from_defined() -> None:
    state = _state(CapabilityStatus.DEFINED)
    events = decide(
        state=state,
        command=DeprecateCapability(reason=DeprecationReason.SUPERSEDED, capability_id=state.id),
        now=_NOW,
    )
    assert len(events) == 1
    assert isinstance(events[0], CapabilityDeprecated)
    assert events[0].replaced_by_capability_id is None


@pytest.mark.unit
def test_decide_deprecates_from_versioned() -> None:
    state = _state(CapabilityStatus.VERSIONED)
    events = decide(
        state=state,
        command=DeprecateCapability(reason=DeprecationReason.SUPERSEDED, capability_id=state.id),
        now=_NOW,
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_with_replaced_by_pointer() -> None:
    state = _state()
    successor = uuid4()
    events = decide(
        state=state,
        command=DeprecateCapability(
            reason=DeprecationReason.SUPERSEDED,
            capability_id=state.id,
            replaced_by_capability_id=successor,
        ),
        now=_NOW,
    )
    assert events[0].replaced_by_capability_id == successor


@pytest.mark.unit
def test_decide_raises_not_found_when_state_is_none() -> None:
    cap_id = uuid4()
    with pytest.raises(CapabilityNotFoundError) as exc:
        decide(
            state=None,
            command=DeprecateCapability(reason=DeprecationReason.SUPERSEDED, capability_id=cap_id),
            now=_NOW,
        )
    assert exc.value.capability_id == cap_id


@pytest.mark.unit
def test_decide_raises_cannot_deprecate_when_already_deprecated() -> None:
    """Strict-not-idempotent: re-deprecating raises."""
    state = _state(CapabilityStatus.DEPRECATED)
    with pytest.raises(CapabilityCannotDeprecateError) as exc:
        decide(
            state=state,
            command=DeprecateCapability(
                reason=DeprecationReason.SUPERSEDED, capability_id=state.id
            ),
            now=_NOW,
        )
    assert exc.value.current_status == CapabilityStatus.DEPRECATED
