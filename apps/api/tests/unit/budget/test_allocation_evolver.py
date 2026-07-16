"""Evolver tests for the Allocation aggregate."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from cora.budget.aggregates.allocation.events import (
    AllocationActivated,
    AllocationCeilingAmended,
    AllocationGranted,
    AllocationSealed,
    AllocationVoided,
)
from cora.budget.aggregates.allocation.evolver import fold
from cora.budget.aggregates.allocation.state import AllocationStatus
from cora.shared.identity import ActorId

_T0 = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)
_T1 = _T0 + timedelta(minutes=10)
_T2 = _T0 + timedelta(minutes=20)
_T3 = _T0 + timedelta(minutes=30)

_GRANTED_BY = ActorId(UUID("01900000-0000-7000-8000-000000000011"))
_ACTIVATED_BY = ActorId(UUID("01900000-0000-7000-8000-000000000022"))
_SEALED_BY = ActorId(UUID("01900000-0000-7000-8000-000000000033"))
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-000000000044")


def _genesis(
    *,
    allocation_id: UUID | None = None,
    campaign_id: UUID | None = None,
) -> AllocationGranted:
    return AllocationGranted(
        allocation_id=allocation_id or uuid4(),
        ceiling_usd=25000.0,
        campaign_id=campaign_id,
        note="FY26 imaging award",
        granted_by=_GRANTED_BY,
        occurred_at=_T0,
    )


@pytest.mark.unit
def test_empty_stream_folds_to_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_genesis_folds_to_granted_state() -> None:
    e = _genesis(campaign_id=_CAMPAIGN_ID)
    state = fold([e])
    assert state is not None
    assert state.id == e.allocation_id
    assert state.status is AllocationStatus.GRANTED
    assert state.ceiling_usd == 25000.0
    assert state.note.value == "FY26 imaging award"
    assert state.campaign_id == _CAMPAIGN_ID
    assert state.granted_at == _T0
    assert state.granted_by == _GRANTED_BY
    assert state.activated_at is None
    assert state.activated_by is None
    assert state.sealed_at is None
    assert state.sealed_by is None
    assert state.spent_usd_at_seal is None
    assert state.end_reason is None


@pytest.mark.unit
def test_genesis_without_campaign_folds_unbound_envelope() -> None:
    state = fold([_genesis()])
    assert state is not None
    assert state.campaign_id is None


@pytest.mark.unit
def test_activated_folds_to_active_with_window_start() -> None:
    allocation_id = uuid4()
    e1 = _genesis(allocation_id=allocation_id)
    e2 = AllocationActivated(
        allocation_id=allocation_id, activated_by=_ACTIVATED_BY, occurred_at=_T1
    )
    state = fold([e1, e2])
    assert state is not None
    assert state.status is AllocationStatus.ACTIVE
    assert state.activated_at == _T1
    assert state.activated_by == _ACTIVATED_BY
    assert state.granted_at == _T0
    assert state.granted_by == _GRANTED_BY


@pytest.mark.unit
def test_ceiling_amended_overwrites_ceiling_and_keeps_status() -> None:
    """PUT semantics fold: the amended ceiling replaces the prior one
    while every other field (status included) carries forward."""
    allocation_id = uuid4()
    e1 = _genesis(allocation_id=allocation_id)
    e2 = AllocationActivated(
        allocation_id=allocation_id, activated_by=_ACTIVATED_BY, occurred_at=_T1
    )
    e3 = AllocationCeilingAmended(allocation_id=allocation_id, ceiling_usd=18000.0, occurred_at=_T2)
    state = fold([e1, e2, e3])
    assert state is not None
    assert state.ceiling_usd == 18000.0
    assert state.status is AllocationStatus.ACTIVE
    assert state.activated_at == _T1


@pytest.mark.unit
def test_ceiling_amended_while_granted_keeps_dormant_status() -> None:
    allocation_id = uuid4()
    e1 = _genesis(allocation_id=allocation_id)
    e2 = AllocationCeilingAmended(allocation_id=allocation_id, ceiling_usd=30000.0, occurred_at=_T1)
    state = fold([e1, e2])
    assert state is not None
    assert state.ceiling_usd == 30000.0
    assert state.status is AllocationStatus.GRANTED


@pytest.mark.unit
def test_sealed_folds_terminal_with_spend_snapshot_and_reason() -> None:
    allocation_id = uuid4()
    e1 = _genesis(allocation_id=allocation_id)
    e2 = AllocationActivated(
        allocation_id=allocation_id, activated_by=_ACTIVATED_BY, occurred_at=_T1
    )
    e3 = AllocationSealed(
        allocation_id=allocation_id,
        spent_usd=812.4,
        reason="Campaign closed early",
        sealed_by=_SEALED_BY,
        occurred_at=_T2,
    )
    state = fold([e1, e2, e3])
    assert state is not None
    assert state.status is AllocationStatus.SEALED
    assert state.sealed_at == _T2
    assert state.sealed_by == _SEALED_BY
    assert state.spent_usd_at_seal == 812.4
    assert state.end_reason == "Campaign closed early"
    assert state.activated_at == _T1


@pytest.mark.unit
def test_sealed_without_reason_folds_with_none_end_reason() -> None:
    """A routine end-of-window seal carries no note; the snapshot alone
    closes the books."""
    allocation_id = uuid4()
    e1 = _genesis(allocation_id=allocation_id)
    e2 = AllocationActivated(
        allocation_id=allocation_id, activated_by=_ACTIVATED_BY, occurred_at=_T1
    )
    e3 = AllocationSealed(
        allocation_id=allocation_id,
        spent_usd=0.0,
        reason=None,
        sealed_by=_SEALED_BY,
        occurred_at=_T3,
    )
    state = fold([e1, e2, e3])
    assert state is not None
    assert state.status is AllocationStatus.SEALED
    assert state.spent_usd_at_seal == 0.0
    assert state.end_reason is None


@pytest.mark.unit
def test_voided_folds_terminal_with_end_reason_and_no_snapshot() -> None:
    allocation_id = uuid4()
    e1 = _genesis(allocation_id=allocation_id)
    e2 = AllocationVoided(
        allocation_id=allocation_id,
        reason="Granted against the wrong cycle",
        occurred_at=_T1,
    )
    state = fold([e1, e2])
    assert state is not None
    assert state.status is AllocationStatus.VOIDED
    assert state.end_reason == "Granted against the wrong cycle"
    assert state.spent_usd_at_seal is None
    assert state.sealed_at is None


@pytest.mark.unit
def test_voided_from_active_keeps_window_start() -> None:
    """Voiding an already-opened window preserves activated_at: the
    audit trail keeps the fact the window existed."""
    allocation_id = uuid4()
    e1 = _genesis(allocation_id=allocation_id)
    e2 = AllocationActivated(
        allocation_id=allocation_id, activated_by=_ACTIVATED_BY, occurred_at=_T1
    )
    e3 = AllocationVoided(allocation_id=allocation_id, reason="Wrong beamline", occurred_at=_T2)
    state = fold([e1, e2, e3])
    assert state is not None
    assert state.status is AllocationStatus.VOIDED
    assert state.activated_at == _T1


@pytest.mark.unit
def test_activated_applied_to_empty_state_raises() -> None:
    """The shared `require_state` helper raises on transition-before-genesis."""
    e = AllocationActivated(allocation_id=uuid4(), activated_by=_ACTIVATED_BY, occurred_at=_T0)
    with pytest.raises(ValueError, match="AllocationActivated"):
        fold([e])


@pytest.mark.unit
def test_sealed_applied_to_empty_state_raises() -> None:
    e = AllocationSealed(
        allocation_id=uuid4(),
        spent_usd=1.0,
        reason=None,
        sealed_by=_SEALED_BY,
        occurred_at=_T0,
    )
    with pytest.raises(ValueError, match="AllocationSealed"):
        fold([e])
