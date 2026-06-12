"""Property-based tests for `define_family.decide` (Equipment BC).

Complements the example-based `test_define_family_decider.py` with
universal claims across generated inputs. The genesis decider is pure

    (state, command, now, new_id) -> list[FamilyDefined]

Load-bearing properties:

  - Any non-None state always raises `FamilyAlreadyExistsError`
    carrying state.id (idempotency-as-error), regardless of command.
  - On the happy path the single `FamilyDefined` carries the
    injected/passthrough fields: family_id=new_id, name (trimmed),
    affordances threaded from the command, occurred_at=now.
  - Pure: same inputs return equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.equipment.aggregates.family import (
    Affordance,
    Family,
    FamilyAlreadyExistsError,
    FamilyDefined,
    FamilyName,
)
from cora.equipment.features import define_family
from cora.equipment.features.define_family import DefineFamily
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_NAME = printable_ascii_text(min_size=1, max_size=200)
_AFFORDANCES = st.sets(st.sampled_from(tuple(Affordance))).map(frozenset)


def _command(*, name: str, affordances: frozenset[Affordance]) -> DefineFamily:
    return DefineFamily(name=name, affordances=affordances)


@pytest.mark.unit
@given(
    existing_id=st.uuids(),
    name=_NAME,
    affordances=_AFFORDANCES,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_on_existing_state_always_raises_already_exists(
    existing_id: UUID,
    name: str,
    affordances: frozenset[Affordance],
    now: datetime,
    new_id: UUID,
) -> None:
    """Any non-None state raises FamilyAlreadyExistsError carrying state.id."""
    existing = Family(id=existing_id, name=FamilyName("Tomography"))
    with pytest.raises(FamilyAlreadyExistsError) as exc:
        define_family.decide(
            state=existing,
            command=_command(name=name, affordances=affordances),
            now=now,
            new_id=new_id,
        )
    assert exc.value.family_id == existing_id


@pytest.mark.unit
@given(
    name=_NAME,
    affordances=_AFFORDANCES,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_emits_single_event_with_injected_fields(
    name: str,
    affordances: frozenset[Affordance],
    now: datetime,
    new_id: UUID,
) -> None:
    """Empty stream emits one FamilyDefined carrying the injected fields."""
    events = define_family.decide(
        state=None,
        command=_command(name=name, affordances=affordances),
        now=now,
        new_id=new_id,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, FamilyDefined)
    assert event.family_id == new_id
    assert event.name == name
    assert event.affordances == affordances
    assert event.occurred_at == now


@pytest.mark.unit
@given(
    name=_NAME,
    affordances=_AFFORDANCES,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_emits_event_with_affordances_threaded_from_command(
    name: str,
    affordances: frozenset[Affordance],
    now: datetime,
    new_id: UUID,
) -> None:
    """The emitted affordance set equals the command's affordance set verbatim."""
    events = define_family.decide(
        state=None,
        command=_command(name=name, affordances=affordances),
        now=now,
        new_id=new_id,
    )
    assert events[0].affordances == affordances


@pytest.mark.unit
@given(
    name=_NAME,
    affordances=_AFFORDANCES,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_is_pure_same_input_same_output(
    name: str,
    affordances: frozenset[Affordance],
    now: datetime,
    new_id: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock/id leakage)."""
    command = _command(name=name, affordances=affordances)
    first = define_family.decide(state=None, command=command, now=now, new_id=new_id)
    second = define_family.decide(state=None, command=command, now=now, new_id=new_id)
    assert first == second
