"""Tests for Visit state, value objects, and domain errors."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from cora.shared.identifier import Identifier
from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.trust.aggregates.visit import (
    InvalidVisitPlannedPeriodError,
    InvalidVisitReasonError,
    Visit,
    VisitAlreadyExistsError,
    VisitCannotHoldError,
    VisitNotFoundError,
    VisitStatus,
    VisitType,
)

_NOW = datetime(2026, 5, 27, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_visit_status_enum_has_eight_values() -> None:
    """8-state FSM lock per [[project_visit_aggregate_design]]."""
    assert {s.value for s in VisitStatus} == {
        "Planned",
        "Arrived",
        "InProgress",
        "OnHold",
        "Completed",
        "Cancelled",
        "Aborted",
        "Voided",
    }


@pytest.mark.unit
def test_visit_type_enum_has_five_closed_values() -> None:
    """VisitType is closed: {user, commissioning, maintenance, calibration, staff}."""
    assert {t.value for t in VisitType} == {
        "user",
        "commissioning",
        "maintenance",
        "calibration",
        "staff",
    }


@pytest.mark.unit
def test_visit_default_status_is_planned() -> None:
    """Genesis state is Planned (decider doesn't pass status; defaults apply)."""
    v = Visit(
        id=uuid4(),
        policy_id=uuid4(),
        surface_id=uuid4(),
        type=VisitType.USER,
        planned_start_at=_NOW,
        planned_end_at=_NOW + timedelta(hours=1),
    )
    assert v.status == VisitStatus.PLANNED
    assert v.last_status_reason is None
    assert v.external_refs == frozenset()
    assert v.parent_id is None


@pytest.mark.unit
def test_visit_carries_external_refs_as_frozenset() -> None:
    """Identifier hosting matches Campaign/Run precedent (frozenset on state)."""
    ref = Identifier(scheme="proposal", value="12345")
    v = Visit(
        id=uuid4(),
        policy_id=uuid4(),
        surface_id=uuid4(),
        type=VisitType.USER,
        planned_start_at=_NOW,
        planned_end_at=_NOW + timedelta(hours=1),
        external_refs=frozenset({ref}),
    )
    assert v.external_refs == frozenset({ref})


@pytest.mark.unit
def test_invalid_planned_period_error_carries_both_timestamps() -> None:
    start = _NOW
    end = _NOW - timedelta(hours=1)
    err = InvalidVisitPlannedPeriodError(planned_start_at=start, planned_end_at=end)
    assert err.planned_start_at == start
    assert err.planned_end_at == end


@pytest.mark.unit
def test_invalid_reason_error_carries_value() -> None:
    err = InvalidVisitReasonError("   ")
    assert err.value == "   "
    assert str(REASON_MAX_LENGTH) in str(err)


@pytest.mark.unit
def test_visit_already_exists_error_carries_id() -> None:
    vid = uuid4()
    err = VisitAlreadyExistsError(vid)
    assert err.visit_id == vid
    assert str(vid) in str(err)


@pytest.mark.unit
def test_visit_not_found_error_carries_id() -> None:
    vid = uuid4()
    err = VisitNotFoundError(vid)
    assert err.visit_id == vid


@pytest.mark.unit
def test_visit_cannot_hold_error_carries_full_diagnostic() -> None:
    vid = uuid4()
    err = VisitCannotHoldError(
        visit_id=vid,
        current_status=VisitStatus.COMPLETED,
        permitted_sources=(VisitStatus.IN_PROGRESS,),
    )
    assert err.visit_id == vid
    assert err.current_status == VisitStatus.COMPLETED
    assert err.permitted_sources == (VisitStatus.IN_PROGRESS,)
    assert "hold" in str(err)
    assert "Completed" in str(err)
    assert "InProgress" in str(err)
