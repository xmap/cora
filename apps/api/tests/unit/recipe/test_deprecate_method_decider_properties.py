"""Property-based tests for `deprecate_method.decide` (Recipe BC).

Complements the example-based `test_deprecate_method_decider.py` with
universal claims across generated inputs. The decider is a pure multi-
source FSM terminal

    (state, command, now) -> list[MethodDeprecated]

with source-set `Defined | Versioned -> Deprecated` (re-deprecating an
already-Deprecated method raises, strict-not-idempotent).

Load-bearing properties:

  - state=None always raises `MethodNotFoundError` carrying
    command.method_id.
  - The source-state partition is total over `MethodStatus`: every
    status in {Defined, Versioned} emits exactly one `MethodDeprecated`
    (method_id=state.id, occurred_at=now); every other status raises
    `MethodCannotDeprecateError` carrying the current status, so a
    future status value cannot silently fall through.
  - The emitted event's method_id is `state.id`, never
    `command.method_id`.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

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
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_DEPRECATABLE_SOURCES = (MethodStatus.DEFINED, MethodStatus.VERSIONED)
_DISALLOWED_SOURCES = tuple(s for s in MethodStatus if s not in frozenset(_DEPRECATABLE_SOURCES))


def _method(*, method_id: UUID, status: MethodStatus) -> Method:
    return Method(
        id=method_id,
        name=MethodName("XRF Mapping"),
        needed_family_ids=frozenset(),
        status=status,
    )


@pytest.mark.unit
@given(method_id=st.uuids(), now=aware_datetimes())
def test_deprecate_with_none_state_always_raises_not_found(
    method_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `MethodNotFoundError` carrying command.method_id."""
    with pytest.raises(MethodNotFoundError) as exc:
        deprecate_method.decide(
            state=None,
            command=DeprecateMethod(method_id=method_id),
            now=now,
        )
    assert exc.value.method_id == method_id


@pytest.mark.unit
@given(
    method_id=st.uuids(),
    source=st.sampled_from(_DEPRECATABLE_SOURCES),
    now=aware_datetimes(),
)
def test_deprecate_from_allowed_source_emits_single_event(
    method_id: UUID,
    source: MethodStatus,
    now: datetime,
) -> None:
    """Every allowed source emits exactly one MethodDeprecated at now."""
    events = deprecate_method.decide(
        state=_method(method_id=method_id, status=source),
        command=DeprecateMethod(method_id=method_id),
        now=now,
    )
    assert events == [MethodDeprecated(method_id=method_id, occurred_at=now)]


@pytest.mark.unit
@given(
    method_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_deprecate_from_disallowed_source_always_raises_cannot_deprecate(
    method_id: UUID,
    source: MethodStatus,
    now: datetime,
) -> None:
    """Any source outside the allowed set raises, carrying the current status."""
    with pytest.raises(MethodCannotDeprecateError) as exc:
        deprecate_method.decide(
            state=_method(method_id=method_id, status=source),
            command=DeprecateMethod(method_id=method_id),
            now=now,
        )
    assert exc.value.current_status is source
    assert exc.value.method_id == method_id


@pytest.mark.unit
@given(state_method_id=st.uuids(), command_method_id=st.uuids(), now=aware_datetimes())
def test_deprecate_emits_event_with_state_id_not_command_id(
    state_method_id: UUID,
    command_method_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's method_id is state.id, not command.method_id."""
    assume(state_method_id != command_method_id)
    events = deprecate_method.decide(
        state=_method(method_id=state_method_id, status=MethodStatus.DEFINED),
        command=DeprecateMethod(method_id=command_method_id),
        now=now,
    )
    assert events[0].method_id == state_method_id


@pytest.mark.unit
@given(method_id=st.uuids(), now=aware_datetimes())
def test_deprecate_is_pure_same_input_returns_equal_output(
    method_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _method(method_id=method_id, status=MethodStatus.DEFINED)
    command = DeprecateMethod(method_id=method_id)
    first = deprecate_method.decide(state=state, command=command, now=now)
    second = deprecate_method.decide(state=state, command=command, now=now)
    assert first == second
