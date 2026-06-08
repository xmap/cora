"""Pure-decider tests for `supersede_caution` slice.

Pins the cross-aggregate two-stream output shape:
  - parent_events == [CautionSuperseded(parent.id, superseded_by_caution_id=new_id)]
  - child_events == [CautionRegistered(caution_id=new_id,
                                       parent_id=parent.id, ...)]
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from cora.caution.aggregates.caution import (
    AssetTarget,
    Caution,
    CautionCannotSupersedeError,
    CautionCategory,
    CautionRegistered,
    CautionSeverity,
    CautionStatus,
    CautionSuperseded,
    CautionText,
    CautionWorkaround,
    InvalidCautionExpiresAtError,
    InvalidCautionSupersedeTargetError,
    InvalidCautionTextError,
    InvalidCautionWorkaroundError,
    ProcedureTarget,
)
from cora.caution.features import supersede_caution
from cora.caution.features.supersede_caution import (
    CautionSupersessionContext,
    SupersedeCaution,
)
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_ASSET_ID = UUID("01900000-0000-7000-8000-000000010001")
_AUTHOR_ID = ActorId(UUID("01900000-0000-7000-8000-000000010002"))


def _parent(
    *,
    status: CautionStatus = CautionStatus.ACTIVE,
    target: AssetTarget | ProcedureTarget | None = None,
) -> Caution:
    return Caution(
        id=uuid4(),
        target=target if target is not None else AssetTarget(asset_id=_ASSET_ID),
        category=CautionCategory.WEAR,
        severity=CautionSeverity.CAUTION,
        text=CautionText("original text"),
        workaround=CautionWorkaround("original workaround"),
        authored_by=_AUTHOR_ID,
        status=status,
    )


def _command(
    parent_id: UUID,
    *,
    target: AssetTarget | ProcedureTarget | None = None,
    text: str = "updated text",
    workaround: str = "updated workaround",
    expires_at: datetime | None = None,
) -> SupersedeCaution:
    return SupersedeCaution(
        parent_id=parent_id,
        target=target if target is not None else AssetTarget(asset_id=_ASSET_ID),
        category=CautionCategory.WEAR,
        severity=CautionSeverity.CAUTION,
        text=text,
        workaround=workaround,
        expires_at=expires_at,
    )


@pytest.mark.unit
def test_decide_emits_parent_superseded_and_child_registered() -> None:
    parent = _parent()
    new_id = uuid4()
    ctx = CautionSupersessionContext(parent=parent, parent_version=3)
    cmd = _command(parent.id, text="amended text", workaround="amended workaround")

    result = supersede_caution.decide(
        state=None,
        command=cmd,
        context=ctx,
        now=_NOW,
        new_id=new_id,
        authored_by=_AUTHOR_ID,
    )

    assert len(result.parent_events) == 1
    assert isinstance(result.parent_events[0], CautionSuperseded)
    assert result.parent_events[0].caution_id == parent.id
    assert result.parent_events[0].superseded_by_caution_id == new_id
    assert result.parent_events[0].occurred_at == _NOW

    assert len(result.child_events) == 1
    assert isinstance(result.child_events[0], CautionRegistered)
    assert result.child_events[0].caution_id == new_id
    assert result.child_events[0].parent_id == parent.id
    assert result.child_events[0].text == "amended text"
    assert result.child_events[0].workaround == "amended workaround"
    assert result.child_events[0].target == AssetTarget(asset_id=_ASSET_ID)


@pytest.mark.unit
def test_decide_child_target_is_required_to_match_parent_target() -> None:
    parent = _parent(target=AssetTarget(asset_id=_ASSET_ID))
    other_asset = uuid4()
    ctx = CautionSupersessionContext(parent=parent, parent_version=1)
    cmd = _command(parent.id, target=AssetTarget(asset_id=other_asset))
    with pytest.raises(InvalidCautionSupersedeTargetError):
        supersede_caution.decide(
            state=None,
            command=cmd,
            context=ctx,
            now=_NOW,
            new_id=uuid4(),
            authored_by=_AUTHOR_ID,
        )


@pytest.mark.unit
def test_decide_rejects_cross_kind_target_mismatch() -> None:
    parent = _parent(target=AssetTarget(asset_id=_ASSET_ID))
    ctx = CautionSupersessionContext(parent=parent, parent_version=1)
    cmd = _command(parent.id, target=ProcedureTarget(procedure_id=uuid4()))
    with pytest.raises(InvalidCautionSupersedeTargetError):
        supersede_caution.decide(
            state=None,
            command=cmd,
            context=ctx,
            now=_NOW,
            new_id=uuid4(),
            authored_by=_AUTHOR_ID,
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "status",
    [CautionStatus.SUPERSEDED, CautionStatus.RETIRED],
)
def test_decide_rejects_when_parent_not_active(status: CautionStatus) -> None:
    parent = _parent(status=status)
    ctx = CautionSupersessionContext(parent=parent, parent_version=1)
    cmd = _command(parent.id)
    with pytest.raises(CautionCannotSupersedeError):
        supersede_caution.decide(
            state=None,
            command=cmd,
            context=ctx,
            now=_NOW,
            new_id=uuid4(),
            authored_by=_AUTHOR_ID,
        )


@pytest.mark.unit
def test_decide_rejects_empty_child_text() -> None:
    parent = _parent()
    ctx = CautionSupersessionContext(parent=parent, parent_version=1)
    cmd = _command(parent.id, text="   ")
    with pytest.raises(InvalidCautionTextError):
        supersede_caution.decide(
            state=None,
            command=cmd,
            context=ctx,
            now=_NOW,
            new_id=uuid4(),
            authored_by=_AUTHOR_ID,
        )


@pytest.mark.unit
def test_decide_rejects_empty_child_workaround() -> None:
    """Anti-hook #1: workaround REQUIRED on the child too."""
    parent = _parent()
    ctx = CautionSupersessionContext(parent=parent, parent_version=1)
    cmd = _command(parent.id, workaround="   ")
    with pytest.raises(InvalidCautionWorkaroundError):
        supersede_caution.decide(
            state=None,
            command=cmd,
            context=ctx,
            now=_NOW,
            new_id=uuid4(),
            authored_by=_AUTHOR_ID,
        )


@pytest.mark.unit
def test_decide_rejects_past_expires_at() -> None:
    parent = _parent()
    ctx = CautionSupersessionContext(parent=parent, parent_version=1)
    past = _NOW - timedelta(days=1)
    cmd = _command(parent.id, expires_at=past)
    with pytest.raises(InvalidCautionExpiresAtError):
        supersede_caution.decide(
            state=None,
            command=cmd,
            context=ctx,
            now=_NOW,
            new_id=uuid4(),
            authored_by=_AUTHOR_ID,
        )


@pytest.mark.unit
def test_decide_carries_future_expires_at_on_child() -> None:
    parent = _parent()
    ctx = CautionSupersessionContext(parent=parent, parent_version=1)
    future = _NOW + timedelta(days=30)
    cmd = _command(parent.id, expires_at=future)
    result = supersede_caution.decide(
        state=None,
        command=cmd,
        context=ctx,
        now=_NOW,
        new_id=uuid4(),
        authored_by=_AUTHOR_ID,
    )
    assert result.child_events[0].expires_at == future


@pytest.mark.unit
def test_decide_state_arg_is_ignored() -> None:
    """The child is genesis: any non-None `state` is silently ignored
    (the parent's state is what matters; comes from context)."""
    parent = _parent()
    ctx = CautionSupersessionContext(parent=parent, parent_version=1)
    cmd = _command(parent.id)
    # Pass a non-None state -- should NOT raise CautionAlreadyExists.
    fake_state = _parent()
    result = supersede_caution.decide(
        state=fake_state,
        command=cmd,
        context=ctx,
        now=_NOW,
        new_id=uuid4(),
        authored_by=_AUTHOR_ID,
    )
    assert len(result.parent_events) == 1
    assert len(result.child_events) == 1
