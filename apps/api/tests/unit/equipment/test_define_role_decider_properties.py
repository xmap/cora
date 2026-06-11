"""Property-based tests for `define_role.decide` (Equipment BC).

Universal claims across generated inputs:

  - state=None + valid command emits a single RoleDefined with the
    injected new_id / now and disjoint affordance sets.
  - state=Role always raises RoleAlreadyExistsError, regardless of
    command.
  - Overlapping required/optional Affordance sets always raise
    RoleAffordanceOverlapError.
  - Pure: same (state, command, now, new_id) returns the same events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.equipment.aggregates.family import Affordance
from cora.equipment.aggregates.role import (
    ROLE_DOCSTRING_MAX_LENGTH,
    ROLE_NAME_MAX_LENGTH,
    Role,
    RoleAffordanceOverlapError,
    RoleAlreadyExistsError,
    RoleDefined,
    RoleId,
    RoleName,
    SignalType,
)
from cora.equipment.features import define_role
from cora.equipment.features.define_role import DefineRole
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_NAME = printable_ascii_text(min_size=1, max_size=ROLE_NAME_MAX_LENGTH)
_DOC = printable_ascii_text(min_size=1, max_size=ROLE_DOCSTRING_MAX_LENGTH)
_AFFORDANCES = st.frozensets(st.sampled_from(list(Affordance)), max_size=4)
_SIGNAL_LABEL = printable_ascii_text(min_size=1, max_size=50)
_SIGNAL_SET = st.frozensets(_SIGNAL_LABEL, max_size=3)


def _command(
    *,
    name: str,
    docstring: str,
    required: frozenset[Affordance],
    optional: frozenset[Affordance],
    produces: frozenset[str],
    consumes: frozenset[str],
) -> DefineRole:
    return DefineRole(
        name=name,
        docstring=docstring,
        required_affordances=required,
        optional_affordances=optional,
        produces=produces,
        consumes=consumes,
    )


def _role(role_id: UUID) -> Role:
    return Role(id=RoleId(role_id), name=RoleName("X"), docstring="x")


@pytest.mark.unit
@given(
    name=_NAME,
    docstring=_DOC,
    required=_AFFORDANCES,
    optional=_AFFORDANCES,
    produces=_SIGNAL_SET,
    consumes=_SIGNAL_SET,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_role_disjoint_inputs_emit_one_event_with_injected_fields(
    name: str,
    docstring: str,
    required: frozenset[Affordance],
    optional: frozenset[Affordance],
    produces: frozenset[str],
    consumes: frozenset[str],
    now: datetime,
    new_id: UUID,
) -> None:
    """Empty stream + disjoint Affordance sets + valid command -> single RoleDefined."""
    disjoint_optional = optional - required
    command = _command(
        name=name,
        docstring=docstring,
        required=required,
        optional=disjoint_optional,
        produces=produces,
        consumes=consumes,
    )
    events = define_role.decide(state=None, command=command, now=now, new_id=new_id)
    assert events == [
        RoleDefined(
            role_id=new_id,
            name=name.strip(),
            docstring=docstring.strip(),
            occurred_at=now,
            required_affordances=required,
            optional_affordances=disjoint_optional,
            produces=frozenset(SignalType(s.strip()) for s in produces),
            consumes=frozenset(SignalType(s.strip()) for s in consumes),
        )
    ]


@pytest.mark.unit
@given(
    existing_id=st.uuids(),
    name=_NAME,
    docstring=_DOC,
    required=_AFFORDANCES,
    optional=_AFFORDANCES,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_role_on_existing_state_always_raises_already_exists(
    existing_id: UUID,
    name: str,
    docstring: str,
    required: frozenset[Affordance],
    optional: frozenset[Affordance],
    now: datetime,
    new_id: UUID,
) -> None:
    """Any non-None state -> RoleAlreadyExistsError, regardless of command."""
    command = _command(
        name=name,
        docstring=docstring,
        required=required,
        optional=optional - required,
        produces=frozenset(),
        consumes=frozenset(),
    )
    with pytest.raises(RoleAlreadyExistsError) as exc:
        define_role.decide(state=_role(existing_id), command=command, now=now, new_id=new_id)
    assert exc.value.role_id == RoleId(existing_id)


@pytest.mark.unit
@given(
    overlap=st.sampled_from(list(Affordance)),
    name=_NAME,
    docstring=_DOC,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_role_with_overlapping_affordances_always_raises(
    overlap: Affordance,
    name: str,
    docstring: str,
    now: datetime,
    new_id: UUID,
) -> None:
    """Any single Affordance appearing in BOTH sets -> RoleAffordanceOverlapError."""
    command = _command(
        name=name,
        docstring=docstring,
        required=frozenset({overlap}),
        optional=frozenset({overlap}),
        produces=frozenset(),
        consumes=frozenset(),
    )
    with pytest.raises(RoleAffordanceOverlapError) as exc:
        define_role.decide(state=None, command=command, now=now, new_id=new_id)
    assert overlap in exc.value.overlap


@pytest.mark.unit
@given(
    name=_NAME,
    docstring=_DOC,
    required=_AFFORDANCES,
    optional=_AFFORDANCES,
    produces=_SIGNAL_SET,
    consumes=_SIGNAL_SET,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_role_is_pure_same_input_same_output(
    name: str,
    docstring: str,
    required: frozenset[Affordance],
    optional: frozenset[Affordance],
    produces: frozenset[str],
    consumes: frozenset[str],
    now: datetime,
    new_id: UUID,
) -> None:
    """Two calls with identical args return identical events (no clock leakage)."""
    command = _command(
        name=name,
        docstring=docstring,
        required=required,
        optional=optional - required,
        produces=produces,
        consumes=consumes,
    )
    first = define_role.decide(state=None, command=command, now=now, new_id=new_id)
    second = define_role.decide(state=None, command=command, now=now, new_id=new_id)
    assert first == second
