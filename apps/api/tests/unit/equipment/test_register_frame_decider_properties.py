"""Property-based tests for `register_frame.decide` (Equipment BC).

Complements the example-based `test_register_frame_decider.py` with
universal claims across generated inputs. The genesis decider is pure

    (state, command, now, new_id) -> list[FrameRegistered]

Load-bearing properties:

  - Any non-None state always raises `FrameAlreadyExistsError`
    carrying state.id (idempotency-as-error), regardless of command.
  - On the happy path the single `FrameRegistered` carries the
    injected/passthrough fields: frame_id=new_id, name, parent_id=None,
    placement=None, supersedes=None, occurred_at=now.
  - Pure: same inputs return equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.equipment.aggregates.frame import (
    Frame,
    FrameAlreadyExistsError,
    FrameRegistered,
    FrameStatus,
)
from cora.equipment.aggregates.frame.state import FrameName
from cora.equipment.features import register_frame
from cora.equipment.features.register_frame import RegisterFrame
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_NAME = printable_ascii_text(min_size=1, max_size=200)
_FIXED_NAME = "centerline_1p35_mrad"


@pytest.mark.unit
@given(
    existing_id=st.uuids(),
    name=_NAME,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_on_existing_state_always_raises_already_exists(
    existing_id: UUID,
    name: str,
    now: datetime,
    new_id: UUID,
) -> None:
    """Any non-None state raises FrameAlreadyExistsError carrying state.id."""
    existing = Frame(
        id=existing_id,
        name=FrameName("existing"),
        parent_id=None,
        placement=None,
        status=FrameStatus.ACTIVE,
    )
    with pytest.raises(FrameAlreadyExistsError) as exc:
        register_frame.decide(
            state=existing,
            command=RegisterFrame(name=name, parent_id=None, placement=None),
            now=now,
            new_id=new_id,
        )
    assert exc.value.frame_id == existing_id


@pytest.mark.unit
@given(
    name=_NAME,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_emits_single_event_with_injected_fields(
    name: str,
    now: datetime,
    new_id: UUID,
) -> None:
    """Empty stream + root frame emits one FrameRegistered with injected fields."""
    events = register_frame.decide(
        state=None,
        command=RegisterFrame(name=name, parent_id=None, placement=None),
        now=now,
        new_id=new_id,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, FrameRegistered)
    assert event.frame_id == new_id
    assert event.name == name
    assert event.parent_id is None
    assert event.placement is None
    assert event.supersedes is None
    assert event.occurred_at == now


@pytest.mark.unit
@given(
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_is_pure_same_input_same_output(
    now: datetime,
    new_id: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock/id leakage)."""
    command = RegisterFrame(name=_FIXED_NAME, parent_id=None, placement=None)
    first = register_frame.decide(state=None, command=command, now=now, new_id=new_id)
    second = register_frame.decide(state=None, command=command, now=now, new_id=new_id)
    assert first == second
