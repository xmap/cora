"""Decider tests for the `register_visit` slice (genesis)."""

from dataclasses import replace
from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from cora.shared.identifier import Identifier
from cora.trust.aggregates.visit import (
    InvalidVisitPlannedPeriodError,
    Visit,
    VisitAlreadyExistsError,
    VisitParentMismatchedSurfaceError,
    VisitParentNotFoundError,
    VisitRegistered,
    VisitStatus,
    VisitType,
)
from cora.trust.features.register_visit import RegisterVisit
from cora.trust.features.register_visit.context import RegisterVisitContext
from cora.trust.features.register_visit.decider import decide
from tests.unit.trust.visit._fixtures import (
    NOW,
    PLANNED_END,
    PLANNED_START,
    POLICY_ID,
    SURFACE_ID,
    VISIT_ID,
    make_visit,
)

_BASE_CMD = RegisterVisit(
    visit_id=VISIT_ID,
    policy_id=POLICY_ID,
    surface_id=SURFACE_ID,
    type=VisitType.USER,
    planned_start_at=PLANNED_START,
    planned_end_at=PLANNED_END,
)

_NO_PARENT_CTX = RegisterVisitContext(parent_visit=None)


def _parent_on(surface_id: UUID, parent_id: UUID | None = None) -> Visit:
    """Build a parent Visit fixture on a given Surface (Planned status)."""
    parent = make_visit(VisitStatus.PLANNED)
    return replace(
        parent, id=parent_id if parent_id is not None else uuid4(), surface_id=surface_id
    )


@pytest.mark.unit
def test_genesis_emits_visit_registered() -> None:
    events = decide(state=None, command=_BASE_CMD, context=_NO_PARENT_CTX, now=NOW)
    assert len(events) == 1
    [e] = events
    assert isinstance(e, VisitRegistered)
    assert e.visit_id == VISIT_ID
    assert e.policy_id == POLICY_ID
    assert e.surface_id == SURFACE_ID
    assert e.type == VisitType.USER.value
    assert e.planned_start_at == PLANNED_START
    assert e.planned_end_at == PLANNED_END
    assert e.occurred_at == NOW
    assert e.parent_id is None
    assert e.external_refs == frozenset()


@pytest.mark.unit
def test_genesis_carries_external_refs_through_to_event() -> None:
    ref = Identifier(scheme="proposal", value="12345")
    events = decide(
        state=None,
        command=replace(_BASE_CMD, external_refs=frozenset({ref})),
        context=_NO_PARENT_CTX,
        now=NOW,
    )
    assert events[0].external_refs == frozenset({ref})


@pytest.mark.unit
def test_genesis_carries_parent_id() -> None:
    parent_id = uuid4()
    parent = _parent_on(SURFACE_ID, parent_id=parent_id)
    ctx = RegisterVisitContext(parent_visit=parent)
    events = decide(
        state=None,
        command=replace(_BASE_CMD, parent_id=parent_id),
        context=ctx,
        now=NOW,
    )
    assert events[0].parent_id == parent_id


@pytest.mark.unit
def test_genesis_rejects_existing_state() -> None:
    existing: Visit = make_visit(VisitStatus.PLANNED)
    with pytest.raises(VisitAlreadyExistsError) as exc_info:
        decide(state=existing, command=_BASE_CMD, context=_NO_PARENT_CTX, now=NOW)
    assert exc_info.value.visit_id == existing.id


@pytest.mark.unit
def test_genesis_rejects_planned_end_equal_to_start() -> None:
    with pytest.raises(InvalidVisitPlannedPeriodError):
        decide(
            state=None,
            command=replace(_BASE_CMD, planned_end_at=PLANNED_START),
            context=_NO_PARENT_CTX,
            now=NOW,
        )


@pytest.mark.unit
def test_genesis_rejects_planned_end_before_start() -> None:
    with pytest.raises(InvalidVisitPlannedPeriodError):
        decide(
            state=None,
            command=replace(_BASE_CMD, planned_end_at=PLANNED_START - timedelta(hours=1)),
            context=_NO_PARENT_CTX,
            now=NOW,
        )


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    cmd = replace(_BASE_CMD)  # explicit copy to validate purity, not aliasing
    first = decide(state=None, command=cmd, context=_NO_PARENT_CTX, now=NOW)
    second = decide(state=None, command=cmd, context=_NO_PARENT_CTX, now=NOW)
    assert first == second


@pytest.mark.unit
def test_partof_requested_but_parent_missing_raises() -> None:
    parent_id = uuid4()
    ctx_missing = RegisterVisitContext(parent_visit=None)
    with pytest.raises(VisitParentNotFoundError) as exc_info:
        decide(
            state=None,
            command=replace(_BASE_CMD, parent_id=parent_id),
            context=ctx_missing,
            now=NOW,
        )
    assert exc_info.value.parent_id == parent_id


@pytest.mark.unit
def test_partof_parent_on_different_surface_raises() -> None:
    parent_id = uuid4()
    other_surface = uuid4()
    parent = _parent_on(other_surface, parent_id=parent_id)
    ctx = RegisterVisitContext(parent_visit=parent)
    with pytest.raises(VisitParentMismatchedSurfaceError) as exc_info:
        decide(
            state=None,
            command=replace(_BASE_CMD, parent_id=parent_id),
            context=ctx,
            now=NOW,
        )
    assert exc_info.value.child_surface_id == SURFACE_ID
    assert exc_info.value.parent_surface_id == other_surface


@pytest.mark.unit
def test_partof_parent_on_same_surface_passes() -> None:
    parent_id = uuid4()
    parent = _parent_on(SURFACE_ID, parent_id=parent_id)
    ctx = RegisterVisitContext(parent_visit=parent)
    events = decide(
        state=None,
        command=replace(_BASE_CMD, parent_id=parent_id),
        context=ctx,
        now=NOW,
    )
    assert events[0].parent_id == parent_id
