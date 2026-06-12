"""Property-based tests for `supersede_caution.decide` (Caution BC).

Complements the example-based `test_supersede_caution_decider.py` with
universal claims across generated inputs. This is the cross-aggregate
supersession decider returning `SupersessionEvents` (parent + child
streams) for the atomic two-stream `append_streams` write.

    (state, command, context, now, new_id, authored_by) -> SupersessionEvents

Load-bearing properties:

  - An Active parent with a target-preserving child emits exactly one
    `CautionSuperseded` on the parent stream (linking to new_id) and one
    `CautionRegistered` child (caution_id=new_id, parent_id=parent.id,
    target=parent.target, occurred_at=now).
  - A non-Active parent (`{Superseded, Retired}`) always raises
    `CautionCannotSupersedeError` carrying the current status.
  - A child whose target differs from the parent's always raises
    `InvalidCautionSupersedeTargetError`.
  - Pure: same inputs return equal results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

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
    InvalidCautionSupersedeTargetError,
)
from cora.caution.features import supersede_caution
from cora.caution.features.supersede_caution import SupersedeCaution
from cora.caution.features.supersede_caution.context import CautionSupersessionContext
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_TEXT = printable_ascii_text(min_size=1, max_size=2000)
_WORKAROUND = printable_ascii_text(min_size=1, max_size=2000)
_NON_ACTIVE_SOURCES = (CautionStatus.SUPERSEDED, CautionStatus.RETIRED)


def _parent(*, caution_id: UUID, target_uuid: UUID, status: CautionStatus) -> Caution:
    return Caution(
        id=caution_id,
        target=AssetTarget(asset_id=target_uuid),
        category=CautionCategory.WEAR,
        severity=CautionSeverity.NOTICE,
        text=CautionText("hexapod stalls below 0.5 mm/s"),
        workaround=CautionWorkaround("ramp velocity above 0.5 before homing"),
        authored_by=ActorId(UUID(int=9)),
        status=status,
    )


def _command(*, parent_id: UUID, target_uuid: UUID, text: str, workaround: str) -> SupersedeCaution:
    return SupersedeCaution(
        parent_id=parent_id,
        target=AssetTarget(asset_id=target_uuid),
        category=CautionCategory.WEAR,
        severity=CautionSeverity.CAUTION,
        text=text,
        workaround=workaround,
    )


@pytest.mark.unit
@given(
    parent_id=st.uuids(),
    target_uuid=st.uuids(),
    text=_TEXT,
    workaround=_WORKAROUND,
    now=aware_datetimes(),
    new_id=st.uuids(),
    authored_by_uuid=st.uuids(),
)
def test_supersede_active_parent_emits_parent_and_child_events(
    parent_id: UUID,
    target_uuid: UUID,
    text: str,
    workaround: str,
    now: datetime,
    new_id: UUID,
    authored_by_uuid: UUID,
) -> None:
    """Active parent + target-preserving child emits the parent + child events."""
    authored_by = ActorId(authored_by_uuid)
    parent = _parent(caution_id=parent_id, target_uuid=target_uuid, status=CautionStatus.ACTIVE)
    result = supersede_caution.decide(
        state=None,
        command=_command(
            parent_id=parent_id, target_uuid=target_uuid, text=text, workaround=workaround
        ),
        context=CautionSupersessionContext(parent=parent, parent_version=0),
        now=now,
        new_id=new_id,
        authored_by=authored_by,
    )
    assert result.parent_events == [
        CautionSuperseded(caution_id=parent_id, superseded_by_caution_id=new_id, occurred_at=now)
    ]
    assert len(result.child_events) == 1
    child = result.child_events[0]
    assert isinstance(child, CautionRegistered)
    assert child.caution_id == new_id
    assert child.parent_id == parent_id
    assert child.target == AssetTarget(asset_id=target_uuid)
    assert child.authored_by == authored_by
    assert child.occurred_at == now


@pytest.mark.unit
@given(
    parent_id=st.uuids(),
    target_uuid=st.uuids(),
    source=st.sampled_from(_NON_ACTIVE_SOURCES),
    text=_TEXT,
    workaround=_WORKAROUND,
    now=aware_datetimes(),
    new_id=st.uuids(),
    authored_by_uuid=st.uuids(),
)
def test_supersede_non_active_parent_always_raises_cannot_supersede(
    parent_id: UUID,
    target_uuid: UUID,
    source: CautionStatus,
    text: str,
    workaround: str,
    now: datetime,
    new_id: UUID,
    authored_by_uuid: UUID,
) -> None:
    """A Superseded or Retired parent refuses supersession, carrying the status."""
    parent = _parent(caution_id=parent_id, target_uuid=target_uuid, status=source)
    with pytest.raises(CautionCannotSupersedeError) as exc:
        supersede_caution.decide(
            state=None,
            command=_command(
                parent_id=parent_id, target_uuid=target_uuid, text=text, workaround=workaround
            ),
            context=CautionSupersessionContext(parent=parent, parent_version=0),
            now=now,
            new_id=new_id,
            authored_by=ActorId(authored_by_uuid),
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    parent_id=st.uuids(),
    parent_target_uuid=st.uuids(),
    child_target_uuid=st.uuids(),
    text=_TEXT,
    workaround=_WORKAROUND,
    now=aware_datetimes(),
    new_id=st.uuids(),
    authored_by_uuid=st.uuids(),
)
def test_supersede_target_mismatch_always_raises_invalid_target(
    parent_id: UUID,
    parent_target_uuid: UUID,
    child_target_uuid: UUID,
    text: str,
    workaround: str,
    now: datetime,
    new_id: UUID,
    authored_by_uuid: UUID,
) -> None:
    """A child target differing from the parent's raises InvalidCautionSupersedeTargetError."""
    assume(parent_target_uuid != child_target_uuid)
    parent = _parent(
        caution_id=parent_id, target_uuid=parent_target_uuid, status=CautionStatus.ACTIVE
    )
    with pytest.raises(InvalidCautionSupersedeTargetError):
        supersede_caution.decide(
            state=None,
            command=_command(
                parent_id=parent_id, target_uuid=child_target_uuid, text=text, workaround=workaround
            ),
            context=CautionSupersessionContext(parent=parent, parent_version=0),
            now=now,
            new_id=new_id,
            authored_by=ActorId(authored_by_uuid),
        )


@pytest.mark.unit
@given(
    parent_id=st.uuids(),
    target_uuid=st.uuids(),
    text=_TEXT,
    workaround=_WORKAROUND,
    now=aware_datetimes(),
    new_id=st.uuids(),
    authored_by_uuid=st.uuids(),
)
def test_supersede_is_pure_same_input_same_output(
    parent_id: UUID,
    target_uuid: UUID,
    text: str,
    workaround: str,
    now: datetime,
    new_id: UUID,
    authored_by_uuid: UUID,
) -> None:
    """Two calls with identical args return equal results (no clock/id leakage)."""
    parent = _parent(caution_id=parent_id, target_uuid=target_uuid, status=CautionStatus.ACTIVE)
    command = _command(
        parent_id=parent_id, target_uuid=target_uuid, text=text, workaround=workaround
    )
    context = CautionSupersessionContext(parent=parent, parent_version=0)
    authored_by = ActorId(authored_by_uuid)
    first = supersede_caution.decide(
        state=None,
        command=command,
        context=context,
        now=now,
        new_id=new_id,
        authored_by=authored_by,
    )
    second = supersede_caution.decide(
        state=None,
        command=command,
        context=context,
        now=now,
        new_id=new_id,
        authored_by=authored_by,
    )
    assert first == second
