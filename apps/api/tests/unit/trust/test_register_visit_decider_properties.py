"""Property-based tests for `register_visit.decide` (Trust BC, Visit aggregate).

Complements the example-based `visit/test_register_visit_decider.py` with
universal claims across generated inputs. The decider is a pure gated
genesis

    (state, command, context, now) -> list[VisitRegistered]

with a caller-supplied `command.visit_id` (no injected `new_id`): a BSS
subscriber mints deterministic UUIDs, so the genesis id rides on the
command rather than being generated inside the decider.

Load-bearing properties:

  - Any non-None state always raises `VisitAlreadyExistsError` carrying
    state.id (idempotency-as-error), regardless of command / context.
  - The happy path (no parent, valid period) emits exactly one
    `VisitRegistered` threading the command fields through:
    visit_id=command.visit_id, policy_id, surface_id, type.value,
    planned_start_at, planned_end_at, parent_id, external_refs, and
    occurred_at=now.
  - The emitted event's visit_id is `command.visit_id`, never state.id
    (state must be None to reach the happy path).
  - A clean partOf gate: parent present on the same Surface passes and
    threads parent_id through. The full gate matrix (missing parent,
    mismatched surface, inverted period) is pinned by the example test.
  - Pure: same (state, command, context, now) returns equal events.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.trust.aggregates.visit import (
    Visit,
    VisitAlreadyExistsError,
    VisitRegistered,
    VisitStatus,
    VisitType,
)
from cora.trust.features.register_visit import RegisterVisit
from cora.trust.features.register_visit.context import RegisterVisitContext
from cora.trust.features.register_visit.decider import decide
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from cora.shared.identifier import Identifier

_PLANNED_START = datetime(2026, 5, 27, 12, 0, 0, tzinfo=UTC)
_PLANNED_END = _PLANNED_START + timedelta(hours=8)
_POLICY_ID = UUID(int=2)
_SURFACE_ID = UUID(int=3)

_NO_PARENT_CTX = RegisterVisitContext(parent_visit=None)


def _state(
    *,
    visit_id: UUID,
    status: VisitStatus,
    surface_id: UUID = _SURFACE_ID,
) -> Visit:
    return Visit(
        id=visit_id,
        policy_id=_POLICY_ID,
        surface_id=surface_id,
        type=VisitType.USER,
        planned_start_at=_PLANNED_START,
        planned_end_at=_PLANNED_END,
        status=status,
    )


def _command(
    *,
    visit_id: UUID,
    policy_id: UUID,
    surface_id: UUID,
    parent_id: UUID | None = None,
    external_refs: frozenset[Identifier] = frozenset(),
) -> RegisterVisit:
    return RegisterVisit(
        visit_id=visit_id,
        policy_id=policy_id,
        surface_id=surface_id,
        type=VisitType.USER,
        planned_start_at=_PLANNED_START,
        planned_end_at=_PLANNED_END,
        parent_id=parent_id,
        external_refs=external_refs,
    )


def _parent_on(*, parent_id: UUID, surface_id: UUID) -> Visit:
    return _state(visit_id=parent_id, status=VisitStatus.PLANNED, surface_id=surface_id)


@pytest.mark.unit
@given(
    existing_id=st.uuids(),
    existing_status=st.sampled_from(list(VisitStatus)),
    visit_id=st.uuids(),
    policy_id=st.uuids(),
    surface_id=st.uuids(),
    now=aware_datetimes(),
)
def test_register_on_existing_state_always_raises_already_exists(
    existing_id: UUID,
    existing_status: VisitStatus,
    visit_id: UUID,
    policy_id: UUID,
    surface_id: UUID,
    now: datetime,
) -> None:
    """Any non-None state raises VisitAlreadyExistsError carrying state.id."""
    existing = _state(visit_id=existing_id, status=existing_status)
    with pytest.raises(VisitAlreadyExistsError) as exc:
        decide(
            state=existing,
            command=_command(visit_id=visit_id, policy_id=policy_id, surface_id=surface_id),
            context=_NO_PARENT_CTX,
            now=now,
        )
    assert exc.value.visit_id == existing_id


@pytest.mark.unit
@given(
    visit_id=st.uuids(),
    policy_id=st.uuids(),
    surface_id=st.uuids(),
    now=aware_datetimes(),
)
def test_register_happy_path_emits_single_visit_registered_with_threaded_fields(
    visit_id: UUID,
    policy_id: UUID,
    surface_id: UUID,
    now: datetime,
) -> None:
    """The happy path emits one VisitRegistered threading command fields + occurred_at=now."""
    events = decide(
        state=None,
        command=_command(visit_id=visit_id, policy_id=policy_id, surface_id=surface_id),
        context=_NO_PARENT_CTX,
        now=now,
    )
    assert len(events) == 1
    [event] = events
    assert isinstance(event, VisitRegistered)
    assert event.visit_id == visit_id
    assert event.policy_id == policy_id
    assert event.surface_id == surface_id
    assert event.type == VisitType.USER.value
    assert event.planned_start_at == _PLANNED_START
    assert event.planned_end_at == _PLANNED_END
    assert event.occurred_at == now
    assert event.parent_id is None
    assert event.external_refs == frozenset()


@pytest.mark.unit
@given(
    visit_id=st.uuids(),
    policy_id=st.uuids(),
    surface_id=st.uuids(),
    ref_value=printable_ascii_text(min_size=1, max_size=64),
    now=aware_datetimes(),
)
def test_register_happy_path_threads_external_refs(
    visit_id: UUID,
    policy_id: UUID,
    surface_id: UUID,
    ref_value: str,
    now: datetime,
) -> None:
    """external_refs on the command are threaded verbatim onto the event."""
    from cora.shared.identifier import Identifier

    refs = frozenset({Identifier(scheme="proposal", value=ref_value)})
    events = decide(
        state=None,
        command=_command(
            visit_id=visit_id,
            policy_id=policy_id,
            surface_id=surface_id,
            external_refs=refs,
        ),
        context=_NO_PARENT_CTX,
        now=now,
    )
    assert events[0].external_refs == refs


@pytest.mark.unit
@given(
    visit_id=st.uuids(),
    policy_id=st.uuids(),
    surface_id=st.uuids(),
    parent_id=st.uuids(),
    now=aware_datetimes(),
)
def test_register_with_parent_on_same_surface_threads_parent_id(
    visit_id: UUID,
    policy_id: UUID,
    surface_id: UUID,
    parent_id: UUID,
    now: datetime,
) -> None:
    """Parent present on the same Surface passes the partOf gate and threads parent_id."""
    ctx = RegisterVisitContext(parent_visit=_parent_on(parent_id=parent_id, surface_id=surface_id))
    events = decide(
        state=None,
        command=_command(
            visit_id=visit_id,
            policy_id=policy_id,
            surface_id=surface_id,
            parent_id=parent_id,
        ),
        context=ctx,
        now=now,
    )
    assert len(events) == 1
    assert events[0].parent_id == parent_id


@pytest.mark.unit
@given(
    visit_id=st.uuids(),
    policy_id=st.uuids(),
    surface_id=st.uuids(),
    now=aware_datetimes(),
)
def test_register_is_pure_same_input_same_output(
    visit_id: UUID,
    policy_id: UUID,
    surface_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    command = _command(visit_id=visit_id, policy_id=policy_id, surface_id=surface_id)
    first = decide(state=None, command=command, context=_NO_PARENT_CTX, now=now)
    second = decide(state=None, command=command, context=_NO_PARENT_CTX, now=now)
    assert first == second
