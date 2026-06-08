"""Clearance evolver: replay events to reconstruct state."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.safety.aggregates.clearance import (
    ClearanceActivated,
    ClearanceApproved,
    ClearanceKind,
    ClearanceRegistered,
    ClearanceRejected,
    ClearanceReviewStarted,
    ClearanceReviewStepAppended,
    ClearanceStatus,
    ClearanceSubmitted,
    SubjectBinding,
    evolve,
    fold,
)
from cora.safety.aggregates.clearance.hazard_classification import RiskBand
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_CLEARANCE_ID = UUID("01900000-0000-7000-8000-000000011002")


def _genesis_event(*, with_optional: bool = False) -> ClearanceRegistered:
    sid = uuid4()
    return ClearanceRegistered(
        clearance_id=_CLEARANCE_ID,
        kind="ESAF",
        facility_asset_id=uuid4(),
        title="Pilot",
        bindings=({"kind": "Subject", "id": str(sid)},),
        declarations=(
            {
                "target": {"kind": "Subject", "id": str(sid)},
                "classifications": [{"kind": "RiskBand", "band": "Yellow"}],
                "mitigations": [],
                "notes": None,
            },
        ),
        risk_band="Yellow" if with_optional else None,
        external_id="ESAF-12345" if with_optional else None,
        valid_from=_NOW if with_optional else None,
        valid_until=None,
        parent_id=None,
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_fold_empty_stream_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_genesis_only_lands_in_defined() -> None:
    state = fold([_genesis_event()])
    assert state is not None
    assert state.id == _CLEARANCE_ID
    assert state.kind == ClearanceKind.ESAF
    assert state.status == ClearanceStatus.DEFINED


@pytest.mark.unit
def test_fold_genesis_reconstructs_typed_bindings() -> None:
    state = fold([_genesis_event()])
    assert state is not None
    assert len(state.bindings) == 1
    binding = next(iter(state.bindings))
    assert isinstance(binding, SubjectBinding)


@pytest.mark.unit
def test_fold_genesis_with_optional_fields() -> None:
    state = fold([_genesis_event(with_optional=True)])
    assert state is not None
    assert state.risk_band == RiskBand.YELLOW
    assert state.external_id == "ESAF-12345"
    assert state.valid_from == _NOW


@pytest.mark.unit
def test_evolver_returns_new_state_does_not_mutate_input() -> None:
    """The genesis arm is non-mutating."""
    state1 = evolve(None, _genesis_event())
    state2 = evolve(None, _genesis_event())
    # Each call returns a fresh frozen instance
    assert state1 is not state2
    assert state1.id == state2.id


@pytest.mark.unit
def test_fold_reconstructs_declarations() -> None:
    state = fold([_genesis_event()])
    assert state is not None
    assert len(state.declarations) == 1
    decl = next(iter(state.declarations))
    assert RiskBand.YELLOW in decl.classifications


# ---------- non-genesis arms (11a-b) ----------
#
# Each FSM-closure event is folded onto a Defined state and the resulting
# status / chain / validity-window invariants are pinned. These guard
# against silent re-introduction of the dropped `last_reviewed_by`
# state field (the Clearance dataclass no longer carries it; an evolver
# fold that tries to set it would fail to construct the dataclass).


def _submitted(occurred_at: datetime = _NOW) -> ClearanceSubmitted:
    return ClearanceSubmitted(clearance_id=_CLEARANCE_ID, occurred_at=occurred_at)


def _review_started(role: str = "BeamlineScientist") -> ClearanceReviewStarted:
    return ClearanceReviewStarted(
        clearance_id=_CLEARANCE_ID,
        first_reviewer_role=role,
        occurred_at=_NOW,
    )


def _step_appended(
    step_index: int = 0,
    *,
    decision: str = "Approved",
    decided_at: datetime = _NOW,
) -> ClearanceReviewStepAppended:
    return ClearanceReviewStepAppended(
        clearance_id=_CLEARANCE_ID,
        step_index=step_index,
        role="ESH",
        decided_by=ActorId(uuid4()),
        decision=decision,
        decided_at=decided_at,
        notes=None,
        occurred_at=_NOW,
    )


def _approved(
    *,
    valid_from: datetime | None = None,
    valid_until: datetime | None = None,
) -> ClearanceApproved:
    return ClearanceApproved(
        clearance_id=_CLEARANCE_ID,
        valid_from=valid_from,
        valid_until=valid_until,
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_fold_submitted_lands_in_submitted() -> None:
    state = fold([_genesis_event(), _submitted()])
    assert state is not None
    assert state.status == ClearanceStatus.SUBMITTED


@pytest.mark.unit
def test_fold_review_started_lands_in_under_review() -> None:
    state = fold([_genesis_event(), _submitted(), _review_started()])
    assert state is not None
    assert state.status == ClearanceStatus.UNDER_REVIEW


@pytest.mark.unit
def test_fold_review_step_appended_grows_chain_without_status_change() -> None:
    state = fold([_genesis_event(), _submitted(), _review_started(), _step_appended(step_index=0)])
    assert state is not None
    assert state.status == ClearanceStatus.UNDER_REVIEW
    assert len(state.review_steps) == 1
    assert state.review_steps[0].decision == "Approved"


@pytest.mark.unit
def test_fold_multi_step_chain_preserves_order() -> None:
    state = fold(
        [
            _genesis_event(),
            _submitted(),
            _review_started(),
            _step_appended(step_index=0, decision="Approved"),
            _step_appended(step_index=1, decision="RequestedChanges"),
            _step_appended(step_index=2, decision="Approved"),
        ]
    )
    assert state is not None
    assert [s.decision for s in state.review_steps] == [
        "Approved",
        "RequestedChanges",
        "Approved",
    ]
    assert [s.step_index for s in state.review_steps] == [0, 1, 2]


@pytest.mark.unit
def test_fold_approved_lands_in_approved_without_validity_overrides() -> None:
    """Approved with valid_from/valid_until = None preserves prior values."""
    state = fold(
        [
            _genesis_event(with_optional=True),  # genesis carries valid_from=_NOW
            _submitted(),
            _review_started(),
            _step_appended(),
            _approved(),
        ]
    )
    assert state is not None
    assert state.status == ClearanceStatus.APPROVED
    assert state.valid_from == _NOW  # preserved from genesis
    assert state.valid_until is None


@pytest.mark.unit
def test_fold_approved_overrides_validity_window_when_provided() -> None:
    new_from = datetime(2026, 6, 1, tzinfo=UTC)
    new_until = datetime(2026, 9, 1, tzinfo=UTC)
    state = fold(
        [
            _genesis_event(),
            _submitted(),
            _review_started(),
            _step_appended(),
            _approved(valid_from=new_from, valid_until=new_until),
        ]
    )
    assert state is not None
    assert state.status == ClearanceStatus.APPROVED
    assert state.valid_from == new_from
    assert state.valid_until == new_until


@pytest.mark.unit
def test_fold_rejected_lands_in_rejected() -> None:
    state = fold(
        [
            _genesis_event(),
            _submitted(),
            _review_started(),
            ClearanceRejected(
                clearance_id=_CLEARANCE_ID,
                reason="ESRB found insufficient PPE specification",
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.status == ClearanceStatus.REJECTED


@pytest.mark.unit
def test_fold_full_walk_to_active() -> None:
    state = fold(
        [
            _genesis_event(),
            _submitted(),
            _review_started(),
            _step_appended(),
            _approved(),
            ClearanceActivated(clearance_id=_CLEARANCE_ID, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status == ClearanceStatus.ACTIVE


@pytest.mark.unit
@pytest.mark.parametrize(
    "transition_event",
    [
        ClearanceSubmitted(clearance_id=_CLEARANCE_ID, occurred_at=_NOW),
        ClearanceReviewStarted(
            clearance_id=_CLEARANCE_ID,
            first_reviewer_role="ESH",
            occurred_at=_NOW,
        ),
        ClearanceReviewStepAppended(
            clearance_id=_CLEARANCE_ID,
            step_index=0,
            role="ESH",
            decided_by=ActorId(UUID("01900000-0000-7000-8000-000000099999")),
            decision="Approved",
            decided_at=_NOW,
            notes=None,
            occurred_at=_NOW,
        ),
        ClearanceApproved(
            clearance_id=_CLEARANCE_ID,
            valid_from=None,
            valid_until=None,
            occurred_at=_NOW,
        ),
        ClearanceRejected(clearance_id=_CLEARANCE_ID, reason="bad", occurred_at=_NOW),
        ClearanceActivated(clearance_id=_CLEARANCE_ID, occurred_at=_NOW),
    ],
)
def test_transition_events_on_empty_state_raise(transition_event: object) -> None:
    """Every transition arm refuses to fold on empty state via require_state."""
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(None, transition_event)  # pyright: ignore[reportArgumentType]


@pytest.mark.unit
def test_fold_approved_state_carries_no_reviewer_id_field() -> None:
    """Pin the dropped state field: `Clearance` aggregate no longer carries
    `last_reviewed_by`. Approving actor lives on the event envelope
    (StoredEvent.principal_id) and is sourced by the projection, not the
    aggregate fold.
    """
    state = fold(
        [
            _genesis_event(),
            _submitted(),
            _review_started(),
            _step_appended(),
            _approved(),
        ]
    )
    assert state is not None
    # The field is dropped at the dataclass level; hasattr returns False.
    assert not hasattr(state, "last_reviewed_by")
