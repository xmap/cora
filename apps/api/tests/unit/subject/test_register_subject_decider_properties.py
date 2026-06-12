"""Property-based tests for `register_subject.decide` (Subject BC).

Complements the example-based `test_register_subject_decider.py` with
universal claims across generated inputs. The genesis decider is pure

    (state, command, now, new_id, registered_by) -> list[SubjectRegistered]

Load-bearing properties:

  - Any non-None state always raises `SubjectAlreadyExistsError`
    carrying state.id (idempotency-as-error), regardless of command.
  - On the happy path the single `SubjectRegistered` carries the
    injected ids: subject_id=new_id, name (trimmed), occurred_at=now,
    registered_by threaded.
  - Pure: same inputs return equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.shared.identity import ActorId
from cora.subject.aggregates.subject import (
    Subject,
    SubjectAlreadyExistsError,
    SubjectName,
    SubjectRegistered,
    SubjectStatus,
)
from cora.subject.features import register_subject
from cora.subject.features.register_subject import RegisterSubject
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_NAME = printable_ascii_text(min_size=1, max_size=200)
_STATUS = st.sampled_from(list(SubjectStatus))


@pytest.mark.unit
@given(
    existing_id=st.uuids(),
    existing_status=_STATUS,
    name=_NAME,
    now=aware_datetimes(),
    new_id=st.uuids(),
    registered_by_uuid=st.uuids(),
)
def test_register_on_existing_state_always_raises_already_exists(
    existing_id: UUID,
    existing_status: SubjectStatus,
    name: str,
    now: datetime,
    new_id: UUID,
    registered_by_uuid: UUID,
) -> None:
    """Any non-None state raises SubjectAlreadyExistsError carrying state.id."""
    existing = Subject(id=existing_id, name=SubjectName("prior"), status=existing_status)
    with pytest.raises(SubjectAlreadyExistsError) as exc:
        register_subject.decide(
            state=existing,
            command=RegisterSubject(name=name),
            now=now,
            new_id=new_id,
            registered_by=ActorId(registered_by_uuid),
        )
    assert exc.value.subject_id == existing_id


@pytest.mark.unit
@given(
    name=_NAME,
    now=aware_datetimes(),
    new_id=st.uuids(),
    registered_by_uuid=st.uuids(),
)
def test_register_emits_single_event_with_injected_fields(
    name: str,
    now: datetime,
    new_id: UUID,
    registered_by_uuid: UUID,
) -> None:
    """Empty stream + valid command emits one SubjectRegistered with injected ids."""
    registered_by = ActorId(registered_by_uuid)
    events = register_subject.decide(
        state=None,
        command=RegisterSubject(name=name),
        now=now,
        new_id=new_id,
        registered_by=registered_by,
    )
    assert events == [
        SubjectRegistered(
            subject_id=new_id,
            name=name,
            occurred_at=now,
            registered_by=registered_by,
        )
    ]


@pytest.mark.unit
@given(
    name=_NAME,
    now=aware_datetimes(),
    new_id=st.uuids(),
    registered_by_uuid=st.uuids(),
)
def test_register_is_pure_same_input_same_output(
    name: str,
    now: datetime,
    new_id: UUID,
    registered_by_uuid: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock/id leakage)."""
    command = RegisterSubject(name=name)
    registered_by = ActorId(registered_by_uuid)
    first = register_subject.decide(
        state=None, command=command, now=now, new_id=new_id, registered_by=registered_by
    )
    second = register_subject.decide(
        state=None, command=command, now=now, new_id=new_id, registered_by=registered_by
    )
    assert first == second
