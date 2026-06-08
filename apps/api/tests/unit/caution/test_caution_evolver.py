"""Caution evolver: replay events to reconstruct state."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.caution.aggregates.caution import (
    AssetTarget,
    Caution,
    CautionCategory,
    CautionRegistered,
    CautionRetired,
    CautionSeverity,
    CautionStatus,
    CautionSuperseded,
    CautionTag,
    CautionText,
    CautionWorkaround,
    ProcedureTarget,
    evolve,
    fold,
)
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_CAUTION_ID = UUID("01900000-0000-7000-8000-00000000d001")
_AUTHOR_ID = ActorId(UUID("01900000-0000-7000-8000-00000000d002"))
_ASSET_ID = UUID("01900000-0000-7000-8000-00000000d003")
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-00000000d004")


def _genesis(
    *,
    target: AssetTarget | ProcedureTarget | None = None,
    parent_id: UUID | None = None,
) -> CautionRegistered:
    return CautionRegistered(
        caution_id=_CAUTION_ID,
        target=target if target is not None else AssetTarget(asset_id=_ASSET_ID),
        category="Wear",
        severity="Caution",
        text="hexapod stalls below 0.5 mm/s",
        workaround="run at 0.6 mm/s",
        tags=frozenset({"low-speed-stall"}),
        authored_by=_AUTHOR_ID,
        expires_at=None,
        propagate_to_children=False,
        parent_id=parent_id,
        occurred_at=_NOW,
    )


# ---------- fold genesis ----------


@pytest.mark.unit
def test_fold_empty_stream_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_genesis_lands_in_active() -> None:
    state = fold([_genesis()])
    assert state == Caution(
        id=_CAUTION_ID,
        target=AssetTarget(asset_id=_ASSET_ID),
        category=CautionCategory.WEAR,
        severity=CautionSeverity.CAUTION,
        text=CautionText("hexapod stalls below 0.5 mm/s"),
        workaround=CautionWorkaround("run at 0.6 mm/s"),
        authored_by=_AUTHOR_ID,
        tags=frozenset({CautionTag("low-speed-stall")}),
        expires_at=None,
        propagate_to_children=False,
        status=CautionStatus.ACTIVE,
        parent_id=None,
    )


@pytest.mark.unit
def test_fold_genesis_with_procedure_target() -> None:
    state = fold([_genesis(target=ProcedureTarget(procedure_id=_PROCEDURE_ID))])
    assert state is not None
    assert state.target == ProcedureTarget(procedure_id=_PROCEDURE_ID)


@pytest.mark.unit
def test_fold_genesis_with_parent_id() -> None:
    parent_id = UUID("01900000-0000-7000-8000-00000000dabc")
    state = fold([_genesis(parent_id=parent_id)])
    assert state is not None
    assert state.parent_id == parent_id
    assert state.status == CautionStatus.ACTIVE


# ---------- supersede arm ----------


@pytest.mark.unit
def test_fold_genesis_then_superseded_transitions_to_superseded() -> None:
    child_id = UUID("01900000-0000-7000-8000-00000000d100")
    state = fold(
        [
            _genesis(),
            CautionSuperseded(
                caution_id=_CAUTION_ID,
                superseded_by_caution_id=child_id,
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.status == CautionStatus.SUPERSEDED
    assert state.superseded_by_caution_id == child_id
    # Identity + target preserved.
    assert state.id == _CAUTION_ID
    assert state.target == AssetTarget(asset_id=_ASSET_ID)


# ---------- retire arm ----------


@pytest.mark.unit
@pytest.mark.parametrize("reason", ["Resolved", "NoLongerApplies", "WrongTarget"])
def test_fold_genesis_then_retired_transitions_to_retired(reason: str) -> None:
    state = fold(
        [
            _genesis(),
            CautionRetired(
                caution_id=_CAUTION_ID,
                reason=reason,
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.status == CautionStatus.RETIRED
    assert state.retired_reason is not None
    assert state.retired_reason.value == reason


# ---------- transitions on empty state ----------


@pytest.mark.unit
def test_evolve_superseded_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="CautionSuperseded cannot be applied to empty state"):
        evolve(
            None,
            CautionSuperseded(
                caution_id=_CAUTION_ID,
                superseded_by_caution_id=_CAUTION_ID,
                occurred_at=_NOW,
            ),
        )


@pytest.mark.unit
def test_evolve_retired_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="CautionRetired cannot be applied to empty state"):
        evolve(
            None,
            CautionRetired(
                caution_id=_CAUTION_ID,
                reason="Resolved",
                occurred_at=_NOW,
            ),
        )


# ---------- evolver immutability ----------


@pytest.mark.unit
def test_evolver_returns_new_state_does_not_mutate_input() -> None:
    initial = fold([_genesis()])
    assert initial is not None
    transitioned = evolve(
        initial,
        CautionRetired(
            caution_id=_CAUTION_ID,
            reason="Resolved",
            occurred_at=_NOW,
        ),
    )
    assert initial.status == CautionStatus.ACTIVE
    assert transitioned.status == CautionStatus.RETIRED
    assert transitioned is not initial
