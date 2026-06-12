"""Property-based tests for `define_method.decide` (Recipe BC).

Complements the example-based `test_define_method_decider.py` with
universal claims across generated inputs. The genesis decider is pure

    (state, command, capability, now, new_id) -> list[MethodDefined]

Load-bearing properties:

  - Any non-None state always raises `MethodAlreadyExistsError`
    carrying state.id (idempotency-as-error), regardless of command.
  - A None capability always raises `CapabilityNotFoundError`
    carrying the command's capability_id (cross-BC stream missing).
  - A capability whose executor_shapes excludes METHOD always raises
    `MethodCapabilityExecutorMismatchError` carrying new_id +
    capability_id.
  - On the happy path the single `MethodDefined` carries the
    injected/passthrough fields: method_id=new_id, name, capability_id,
    needed_family_ids, occurred_at=now.
  - Pure: same inputs return equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.recipe.aggregates.capability import (
    Capability,
    CapabilityCode,
    CapabilityName,
    CapabilityNotFoundError,
    ExecutorShape,
)
from cora.recipe.aggregates.method import (
    Method,
    MethodAlreadyExistsError,
    MethodName,
)
from cora.recipe.features import define_method
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_method.decider import (
    MethodCapabilityExecutorMismatchError,
)
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_NAME = printable_ascii_text(min_size=1, max_size=200)


def _capability(
    *,
    shapes: frozenset[ExecutorShape] = frozenset({ExecutorShape.METHOD}),
    capability_id: UUID | None = None,
) -> Capability:
    """Build a Capability fixture for the cross-BC tests."""
    return Capability(
        id=capability_id or uuid4(),
        code=CapabilityCode("cora.capability.x"),
        name=CapabilityName("X"),
        executor_shapes=shapes,
    )


@pytest.mark.unit
@given(
    existing_id=st.uuids(),
    capability_uuid=st.uuids(),
    name=_NAME,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_method_on_existing_state_raises_already_exists(
    existing_id: UUID,
    capability_uuid: UUID,
    name: str,
    now: datetime,
    new_id: UUID,
) -> None:
    """Any non-None state raises MethodAlreadyExistsError carrying state.id."""
    existing = Method(
        id=existing_id,
        name=MethodName("XRF Mapping"),
        needed_family_ids=frozenset(),
    )
    cap = _capability(capability_id=capability_uuid)
    with pytest.raises(MethodAlreadyExistsError) as exc:
        define_method.decide(
            state=existing,
            command=DefineMethod(name=name, capability_id=cap.id),
            capability=cap,
            now=now,
            new_id=new_id,
        )
    assert exc.value.method_id == existing_id


@pytest.mark.unit
@given(
    capability_uuid=st.uuids(),
    name=_NAME,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_method_with_missing_capability_raises_not_found(
    capability_uuid: UUID,
    name: str,
    now: datetime,
    new_id: UUID,
) -> None:
    """A None capability raises CapabilityNotFoundError carrying capability_id."""
    with pytest.raises(CapabilityNotFoundError) as exc:
        define_method.decide(
            state=None,
            command=DefineMethod(name=name, capability_id=capability_uuid),
            capability=None,
            now=now,
            new_id=new_id,
        )
    assert exc.value.capability_id == capability_uuid


@pytest.mark.unit
@given(
    capability_uuid=st.uuids(),
    name=_NAME,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_method_with_non_method_capability_raises_executor_mismatch(
    capability_uuid: UUID,
    name: str,
    now: datetime,
    new_id: UUID,
) -> None:
    """A capability excluding METHOD raises MethodCapabilityExecutorMismatchError."""
    cap = _capability(
        shapes=frozenset({ExecutorShape.PROCEDURE}),
        capability_id=capability_uuid,
    )
    with pytest.raises(MethodCapabilityExecutorMismatchError) as exc:
        define_method.decide(
            state=None,
            command=DefineMethod(name=name, capability_id=cap.id),
            capability=cap,
            now=now,
            new_id=new_id,
        )
    assert exc.value.method_id == new_id
    assert exc.value.capability_id == capability_uuid


@pytest.mark.unit
@given(
    capability_uuid=st.uuids(),
    family_id=st.uuids(),
    name=_NAME,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_method_on_empty_stream_emits_event_with_injected_fields(
    capability_uuid: UUID,
    family_id: UUID,
    name: str,
    now: datetime,
    new_id: UUID,
) -> None:
    """Empty stream + METHOD-shaped capability emits one MethodDefined with injected fields."""
    cap = _capability(capability_id=capability_uuid)
    events = define_method.decide(
        state=None,
        command=DefineMethod(
            name=name,
            capability_id=cap.id,
            needed_family_ids=frozenset({family_id}),
        ),
        capability=cap,
        now=now,
        new_id=new_id,
    )
    assert len(events) == 1
    event = events[0]
    assert event.method_id == new_id
    assert event.name == name
    assert event.capability_id == capability_uuid
    assert set(event.needed_family_ids) == {family_id}
    assert event.occurred_at == now


@pytest.mark.unit
@given(
    capability_uuid=st.uuids(),
    family_id=st.uuids(),
    name=_NAME,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_method_with_identical_inputs_returns_equal_events(
    capability_uuid: UUID,
    family_id: UUID,
    name: str,
    now: datetime,
    new_id: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock/id leakage)."""
    cap = _capability(capability_id=capability_uuid)
    command = DefineMethod(
        name=name,
        capability_id=cap.id,
        needed_family_ids=frozenset({family_id}),
    )
    first = define_method.decide(
        state=None, command=command, capability=cap, now=now, new_id=new_id
    )
    second = define_method.decide(
        state=None, command=command, capability=cap, now=now, new_id=new_id
    )
    assert first == second
