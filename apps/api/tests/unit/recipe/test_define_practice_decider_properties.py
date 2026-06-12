"""Property-based tests for `define_practice.decide` (Recipe BC).

Complements the example-based `test_define_practice_decider.py` with
universal claims across generated inputs. The genesis decider is pure

    (state, command, now, new_id) -> list[PracticeDefined]

Load-bearing properties:

  - Any non-None state always raises `PracticeAlreadyExistsError`
    carrying state.id (idempotency-as-error), regardless of command.
  - On the happy path the single `PracticeDefined` carries the
    injected/passthrough fields: practice_id=new_id, name, method_id,
    site_id, occurred_at=now.
  - Pure: same inputs return equal events.

The full name-validation gate matrix lives in the example-based
sibling; this file does not duplicate it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.recipe.aggregates.practice import (
    Practice,
    PracticeAlreadyExistsError,
    PracticeDefined,
    PracticeName,
    PracticeStatus,
)
from cora.recipe.features import define_practice
from cora.recipe.features.define_practice import DefinePractice
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_NAME = printable_ascii_text(min_size=1, max_size=200)
_PRACTICE_STATUS = st.sampled_from(tuple(PracticeStatus))


@pytest.mark.unit
@given(
    existing_id=st.uuids(),
    existing_method_id=st.uuids(),
    existing_site_id=st.uuids(),
    existing_status=_PRACTICE_STATUS,
    name=_NAME,
    method_id=st.uuids(),
    site_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_on_existing_state_always_raises_already_exists(
    existing_id: UUID,
    existing_method_id: UUID,
    existing_site_id: UUID,
    existing_status: PracticeStatus,
    name: str,
    method_id: UUID,
    site_id: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """Any non-None state raises PracticeAlreadyExistsError carrying state.id."""
    existing = Practice(
        id=existing_id,
        name=PracticeName("X"),
        method_id=existing_method_id,
        site_id=existing_site_id,
        status=existing_status,
    )
    with pytest.raises(PracticeAlreadyExistsError) as exc:
        define_practice.decide(
            state=existing,
            command=DefinePractice(name=name, method_id=method_id, site_id=site_id),
            now=now,
            new_id=new_id,
        )
    assert exc.value.practice_id == existing_id


@pytest.mark.unit
@given(
    name=_NAME,
    method_id=st.uuids(),
    site_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_emits_single_event_with_injected_fields(
    name: str,
    method_id: UUID,
    site_id: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """Empty stream emits one PracticeDefined with injected/passthrough fields."""
    events = define_practice.decide(
        state=None,
        command=DefinePractice(name=name, method_id=method_id, site_id=site_id),
        now=now,
        new_id=new_id,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, PracticeDefined)
    assert event.practice_id == new_id
    assert event.name == name
    assert event.method_id == method_id
    assert event.site_id == site_id
    assert event.occurred_at == now


@pytest.mark.unit
@given(
    name=_NAME,
    method_id=st.uuids(),
    site_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_is_pure_same_input_same_output(
    name: str,
    method_id: UUID,
    site_id: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock/id leakage)."""
    command = DefinePractice(name=name, method_id=method_id, site_id=site_id)
    first = define_practice.decide(state=None, command=command, now=now, new_id=new_id)
    second = define_practice.decide(state=None, command=command, now=now, new_id=new_id)
    assert first == second
