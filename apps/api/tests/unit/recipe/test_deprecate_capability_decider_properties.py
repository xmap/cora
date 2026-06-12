"""Property-based tests for `deprecate_capability.decide` (Recipe BC).

Complements the example-based `test_deprecate_capability_decider.py` with
universal claims across generated inputs. The decider is a pure
multi-source FSM transition

    (state, command, now) -> list[CapabilityDeprecated]

Load-bearing properties:

  - state=None always raises `CapabilityNotFoundError` carrying
    command.capability_id.
  - The source-state partition is total over `CapabilityStatus`: only
    `Defined` and `Versioned` emit exactly one `CapabilityDeprecated`
    (capability_id=state.id, occurred_at=now); every other status raises
    `CapabilityCannotDeprecateError` carrying the current status, so a
    future status value cannot silently fall through.
  - The emitted event's capability_id is `state.id`, never
    `command.capability_id`.
  - The optional `replaced_by_capability_id` pointer threads from the
    command onto the emitted event unchanged.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

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

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

from tests._strategies import aware_datetimes

_DEPRECATABLE_SOURCES = (CapabilityStatus.DEFINED, CapabilityStatus.VERSIONED)
_DISALLOWED_SOURCES = tuple(
    s for s in CapabilityStatus if s not in frozenset(_DEPRECATABLE_SOURCES)
)


def _state(*, capability_id: UUID, status: CapabilityStatus) -> Capability:
    return Capability(
        id=capability_id,
        code=CapabilityCode("cora.capability.x"),
        name=CapabilityName("X"),
        status=status,
        executor_shapes=frozenset({ExecutorShape.METHOD}),
    )


@pytest.mark.unit
@given(capability_id=st.uuids(), now=aware_datetimes())
def test_deprecate_with_none_state_always_raises_not_found(
    capability_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `CapabilityNotFoundError` carrying command id."""
    with pytest.raises(CapabilityNotFoundError) as exc:
        decide(
            state=None,
            command=DeprecateCapability(capability_id=capability_id),
            now=now,
        )
    assert exc.value.capability_id == capability_id


@pytest.mark.unit
@given(
    capability_id=st.uuids(),
    source=st.sampled_from(_DEPRECATABLE_SOURCES),
    now=aware_datetimes(),
)
def test_deprecate_from_deprecatable_source_emits_single_event(
    capability_id: UUID,
    source: CapabilityStatus,
    now: datetime,
) -> None:
    """Defined and Versioned are the deprecatable sources; each emits one event."""
    events = decide(
        state=_state(capability_id=capability_id, status=source),
        command=DeprecateCapability(capability_id=capability_id),
        now=now,
    )
    assert events == [
        CapabilityDeprecated(
            capability_id=capability_id,
            occurred_at=now,
            replaced_by_capability_id=None,
        )
    ]


@pytest.mark.unit
@given(
    capability_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_deprecate_from_disallowed_source_always_raises_cannot_deprecate(
    capability_id: UUID,
    source: CapabilityStatus,
    now: datetime,
) -> None:
    """Any source outside {Defined, Versioned} raises, carrying the current status."""
    with pytest.raises(CapabilityCannotDeprecateError) as exc:
        decide(
            state=_state(capability_id=capability_id, status=source),
            command=DeprecateCapability(capability_id=capability_id),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(state_id=st.uuids(), command_id=st.uuids(), now=aware_datetimes())
def test_deprecate_emits_event_with_state_id_not_command_id(
    state_id: UUID,
    command_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's capability_id is state.id, not command.capability_id."""
    assume(state_id != command_id)
    events = decide(
        state=_state(capability_id=state_id, status=CapabilityStatus.DEFINED),
        command=DeprecateCapability(capability_id=command_id),
        now=now,
    )
    assert events[0].capability_id == state_id


@pytest.mark.unit
@given(capability_id=st.uuids(), successor_id=st.uuids(), now=aware_datetimes())
def test_deprecate_emits_event_threading_replaced_by_pointer(
    capability_id: UUID,
    successor_id: UUID,
    now: datetime,
) -> None:
    """A supplied replaced_by_capability_id threads onto the emitted event."""
    events = decide(
        state=_state(capability_id=capability_id, status=CapabilityStatus.VERSIONED),
        command=DeprecateCapability(
            capability_id=capability_id,
            replaced_by_capability_id=successor_id,
        ),
        now=now,
    )
    assert events[0].replaced_by_capability_id == successor_id


@pytest.mark.unit
@given(capability_id=st.uuids(), now=aware_datetimes())
def test_deprecate_is_pure_same_input_same_output(
    capability_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _state(capability_id=capability_id, status=CapabilityStatus.DEFINED)
    command = DeprecateCapability(capability_id=capability_id)
    first = decide(state=state, command=command, now=now)
    second = decide(state=state, command=command, now=now)
    assert first == second
