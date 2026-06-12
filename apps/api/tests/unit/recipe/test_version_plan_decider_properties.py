"""Property-based tests for `version_plan.decide` (Recipe BC).

Complements the example-based `test_version_plan_decider.py` with
universal claims across generated inputs. The decider is a pure
multi-source FSM transition

    (state, command, now) -> list[PlanVersioned]

with source set `Defined | Versioned -> Versioned`; only Deprecated
is rejected.

Load-bearing properties:

  - state=None always raises `PlanNotFoundError` carrying command.plan_id.
  - The source-state partition is total over `PlanStatus`: every
    versionable status (Defined, Versioned) emits exactly one
    `PlanVersioned` (plan_id=state.id, occurred_at=now); every other
    status raises `PlanCannotVersionError` carrying the current status,
    so a future status value cannot silently fall through.
  - The emitted event's plan_id is `state.id`, never `command.plan_id`.
  - The trimmed version tag is threaded onto the emitted event.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.recipe.aggregates.plan import (
    Plan,
    PlanCannotVersionError,
    PlanName,
    PlanNotFoundError,
    PlanStatus,
    PlanVersioned,
)
from cora.recipe.features import version_plan
from cora.recipe.features.version_plan import VersionPlan
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime

_VALID_VERSION_TAG = "v2"

_VERSIONABLE_SOURCES = (PlanStatus.DEFINED, PlanStatus.VERSIONED)
_DISALLOWED_SOURCES = tuple(s for s in PlanStatus if s not in frozenset(_VERSIONABLE_SOURCES))


def _plan(*, plan_id: UUID, status: PlanStatus) -> Plan:
    return Plan(
        id=plan_id,
        name=PlanName("32-ID FlyScan"),
        practice_id=UUID(int=1),
        asset_ids=frozenset({UUID(int=2)}),
        status=status,
    )


@pytest.mark.unit
@given(plan_id=st.uuids(), now=aware_datetimes())
def test_version_with_none_state_always_raises_not_found(
    plan_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `PlanNotFoundError` carrying command.plan_id."""
    with pytest.raises(PlanNotFoundError) as exc:
        version_plan.decide(
            state=None,
            command=VersionPlan(plan_id=plan_id, version_tag=_VALID_VERSION_TAG),
            now=now,
        )
    assert exc.value.plan_id == plan_id


@pytest.mark.unit
@given(
    plan_id=st.uuids(),
    source=st.sampled_from(_VERSIONABLE_SOURCES),
    now=aware_datetimes(),
)
def test_version_from_allowed_source_emits_single_event(
    plan_id: UUID,
    source: PlanStatus,
    now: datetime,
) -> None:
    """Every versionable source emits exactly one PlanVersioned at now."""
    events = version_plan.decide(
        state=_plan(plan_id=plan_id, status=source),
        command=VersionPlan(plan_id=plan_id, version_tag=_VALID_VERSION_TAG),
        now=now,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, PlanVersioned)
    assert event.plan_id == plan_id
    assert event.occurred_at == now
    assert event.content_hash is not None


@pytest.mark.unit
@given(
    plan_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_version_from_disallowed_source_always_raises_cannot_version(
    plan_id: UUID,
    source: PlanStatus,
    now: datetime,
) -> None:
    """Any source other than Defined/Versioned raises, carrying the current status."""
    with pytest.raises(PlanCannotVersionError) as exc:
        version_plan.decide(
            state=_plan(plan_id=plan_id, status=source),
            command=VersionPlan(plan_id=plan_id, version_tag=_VALID_VERSION_TAG),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(state_plan_id=st.uuids(), command_plan_id=st.uuids(), now=aware_datetimes())
def test_version_emits_event_with_state_id_not_command_plan_id(
    state_plan_id: UUID,
    command_plan_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's plan_id is state.id, not command.plan_id."""
    assume(state_plan_id != command_plan_id)
    events = version_plan.decide(
        state=_plan(plan_id=state_plan_id, status=PlanStatus.DEFINED),
        command=VersionPlan(plan_id=command_plan_id, version_tag=_VALID_VERSION_TAG),
        now=now,
    )
    assert events[0].plan_id == state_plan_id


@pytest.mark.unit
@given(
    plan_id=st.uuids(),
    source=st.sampled_from(_VERSIONABLE_SOURCES),
    now=aware_datetimes(),
)
def test_version_emits_event_with_trimmed_tag(
    plan_id: UUID,
    source: PlanStatus,
    now: datetime,
) -> None:
    """The trimmed version tag is threaded onto the emitted event."""
    events = version_plan.decide(
        state=_plan(plan_id=plan_id, status=source),
        command=VersionPlan(plan_id=plan_id, version_tag=f"  {_VALID_VERSION_TAG}  "),
        now=now,
    )
    assert events[0].version_tag == _VALID_VERSION_TAG


@pytest.mark.unit
@given(plan_id=st.uuids(), now=aware_datetimes())
def test_version_is_pure_same_input_same_output(
    plan_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _plan(plan_id=plan_id, status=PlanStatus.DEFINED)
    command = VersionPlan(plan_id=plan_id, version_tag=_VALID_VERSION_TAG)
    first = version_plan.decide(state=state, command=command, now=now)
    second = version_plan.decide(state=state, command=command, now=now)
    assert first == second
