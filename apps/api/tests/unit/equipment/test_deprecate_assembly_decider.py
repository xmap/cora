"""Unit tests for the `deprecate_assembly` slice's pure decider."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates._value_types import RoleId
from cora.equipment.aggregates.assembly import (
    Assembly,
    AssemblyCannotDeprecateError,
    AssemblyDeprecated,
    AssemblyName,
    AssemblyNotFoundError,
    AssemblyStatus,
)
from cora.equipment.features import deprecate_assembly
from cora.equipment.features.deprecate_assembly import DeprecateAssembly

_NOW = datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC)


def _state(
    assembly_id: object,
    *,
    status: AssemblyStatus = AssemblyStatus.DEFINED,
) -> Assembly:
    return Assembly(
        id=assembly_id,  # type: ignore[arg-type]
        name=AssemblyName("Existing"),
        presents_as=frozenset({RoleId(uuid4())}),
        status=status,
    )


@pytest.mark.unit
def test_decide_emits_assembly_deprecated_from_defined_state() -> None:
    assembly_id = uuid4()
    state = _state(assembly_id, status=AssemblyStatus.DEFINED)
    events = deprecate_assembly.decide(
        state=state,
        command=DeprecateAssembly(
            assembly_id=assembly_id,
            reason="superseded by Detector-rev3",
        ),
        now=_NOW,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, AssemblyDeprecated)
    assert event.assembly_id == assembly_id
    assert event.reason == "superseded by Detector-rev3"
    assert event.occurred_at == _NOW


@pytest.mark.unit
def test_decide_emits_assembly_deprecated_from_versioned_state() -> None:
    """Multi-source FSM: Versioned -> Deprecated is also valid."""
    assembly_id = uuid4()
    state = _state(assembly_id, status=AssemblyStatus.VERSIONED)
    events = deprecate_assembly.decide(
        state=state,
        command=DeprecateAssembly(assembly_id=assembly_id, reason="r"),
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].assembly_id == assembly_id


@pytest.mark.unit
def test_decide_rejects_none_state_with_assembly_not_found() -> None:
    target_id = uuid4()
    with pytest.raises(AssemblyNotFoundError) as exc_info:
        deprecate_assembly.decide(
            state=None,
            command=DeprecateAssembly(assembly_id=target_id, reason="r"),
            now=_NOW,
        )
    assert exc_info.value.assembly_id == target_id


@pytest.mark.unit
def test_decide_rejects_deprecated_state_with_cannot_deprecate() -> None:
    """Strict-not-idempotent: re-deprecating raises."""
    assembly_id = uuid4()
    state = _state(assembly_id, status=AssemblyStatus.DEPRECATED)
    with pytest.raises(AssemblyCannotDeprecateError) as exc_info:
        deprecate_assembly.decide(
            state=state,
            command=DeprecateAssembly(assembly_id=assembly_id, reason="r"),
            now=_NOW,
        )
    assert exc_info.value.assembly_id == assembly_id
    assert "Deprecated" in exc_info.value.reason


@pytest.mark.unit
def test_decide_is_pure_same_inputs_yield_same_events() -> None:
    assembly_id = uuid4()
    state = _state(assembly_id)
    command = DeprecateAssembly(assembly_id=assembly_id, reason="end-of-life")
    events_a = deprecate_assembly.decide(state, command, now=_NOW)
    events_b = deprecate_assembly.decide(state, command, now=_NOW)
    assert events_a == events_b
