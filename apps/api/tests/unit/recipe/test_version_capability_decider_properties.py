"""Property-based tests for `version_capability.decide` (Recipe BC).

Complements the example-based `test_version_capability_decider.py`
with universal claims across generated inputs. The decider is a pure
multi-source transition

    (state, command, now) -> list[CapabilityVersioned]

with sources `Defined | Versioned -> Versioned`.

Load-bearing properties:

  - state=None always raises `CapabilityNotFoundError` carrying
    command.capability_id.
  - The source-state partition is total over `CapabilityStatus`: both
    `Defined` and `Versioned` emit exactly one `CapabilityVersioned`
    (capability_id=state.id, occurred_at=now); every other status
    raises `CapabilityCannotVersionError` carrying the current status,
    so a future status value cannot silently fall through.
  - The emitted event's capability_id is `state.id`, never
    command.capability_id, and the trimmed version_tag is threaded
    from the command.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.equipment.aggregates.family import Affordance
from cora.recipe.aggregates.capability import (
    Capability,
    CapabilityCannotVersionError,
    CapabilityCode,
    CapabilityName,
    CapabilityNotFoundError,
    CapabilityStatus,
    CapabilityVersioned,
    ExecutorShape,
)
from cora.recipe.features import version_capability
from cora.recipe.features.version_capability import VersionCapability
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_VERSION_TAG = "v2"

_VERSIONABLE_SOURCES = (CapabilityStatus.DEFINED, CapabilityStatus.VERSIONED)
_DISALLOWED_SOURCES = tuple(s for s in CapabilityStatus if s not in frozenset(_VERSIONABLE_SOURCES))


def _state(*, capability_id: UUID, status: CapabilityStatus) -> Capability:
    return Capability(
        id=capability_id,
        code=CapabilityCode("cora.capability.x"),
        name=CapabilityName("X"),
        status=status,
        executor_shapes=frozenset({ExecutorShape.METHOD}),
    )


def _cmd(*, capability_id: UUID, version_tag: str = _VERSION_TAG) -> VersionCapability:
    return VersionCapability(
        capability_id=capability_id,
        version_tag=version_tag,
        required_affordances=frozenset({Affordance.ROTATABLE}),
        executor_shapes=frozenset({ExecutorShape.METHOD}),
    )


@pytest.mark.unit
@given(capability_id=st.uuids(), now=aware_datetimes())
def test_version_with_none_state_always_raises_not_found(
    capability_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `CapabilityNotFoundError` carrying command.capability_id."""
    with pytest.raises(CapabilityNotFoundError) as exc:
        version_capability.decide(
            state=None,
            command=_cmd(capability_id=capability_id),
            now=now,
        )
    assert exc.value.capability_id == capability_id


@pytest.mark.unit
@given(
    capability_id=st.uuids(),
    source=st.sampled_from(_VERSIONABLE_SOURCES),
    now=aware_datetimes(),
)
def test_version_from_versionable_source_emits_single_event(
    capability_id: UUID,
    source: CapabilityStatus,
    now: datetime,
) -> None:
    """Both Defined and Versioned are versionable sources; each emits one event."""
    events = version_capability.decide(
        state=_state(capability_id=capability_id, status=source),
        command=_cmd(capability_id=capability_id),
        now=now,
    )
    assert events == [
        CapabilityVersioned(
            capability_id=capability_id,
            version_tag=_VERSION_TAG,
            description=None,
            required_affordances=frozenset({Affordance.ROTATABLE}),
            executor_shapes=frozenset({ExecutorShape.METHOD}),
            parameters_schema=None,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    capability_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_version_from_disallowed_source_always_raises_cannot_version(
    capability_id: UUID,
    source: CapabilityStatus,
    now: datetime,
) -> None:
    """Any source other than Defined or Versioned raises, carrying the current status."""
    with pytest.raises(CapabilityCannotVersionError) as exc:
        version_capability.decide(
            state=_state(capability_id=capability_id, status=source),
            command=_cmd(capability_id=capability_id),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(state_id=st.uuids(), command_id=st.uuids(), now=aware_datetimes())
def test_version_emits_event_with_state_id_not_command_id(
    state_id: UUID,
    command_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's capability_id is state.id, not command.capability_id."""
    assume(state_id != command_id)
    events = version_capability.decide(
        state=_state(capability_id=state_id, status=CapabilityStatus.DEFINED),
        command=_cmd(capability_id=command_id),
        now=now,
    )
    assert events[0].capability_id == state_id


@pytest.mark.unit
@given(capability_id=st.uuids(), now=aware_datetimes())
def test_version_emits_event_with_now_as_occurred_at(
    capability_id: UUID,
    now: datetime,
) -> None:
    """The emitted event carries the injected clock value as occurred_at."""
    events = version_capability.decide(
        state=_state(capability_id=capability_id, status=CapabilityStatus.VERSIONED),
        command=_cmd(capability_id=capability_id),
        now=now,
    )
    assert events[0].occurred_at == now


@pytest.mark.unit
@given(capability_id=st.uuids(), now=aware_datetimes())
def test_version_is_pure_same_input_same_output(
    capability_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _state(capability_id=capability_id, status=CapabilityStatus.DEFINED)
    command = _cmd(capability_id=capability_id)
    first = version_capability.decide(state=state, command=command, now=now)
    second = version_capability.decide(state=state, command=command, now=now)
    assert first == second
