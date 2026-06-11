"""Unit tests for the `define_role` slice's pure decider."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.family import Affordance
from cora.equipment.aggregates.role import (
    InvalidRoleDocstringError,
    InvalidRoleNameError,
    InvalidSignalTypeError,
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

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)


def _basic_command(**overrides: object) -> DefineRole:
    defaults: dict[str, object] = {
        "name": "Imager",
        "docstring": "Acquires 2D image frames on exposure or trigger.",
        "required_affordances": frozenset({Affordance.IMAGEABLE}),
        "optional_affordances": frozenset({Affordance.BINNABLE}),
        "produces": frozenset({"Image"}),
        "consumes": frozenset({"TriggerIn"}),
    }
    defaults.update(overrides)
    return DefineRole(**defaults)  # type: ignore[arg-type]


@pytest.mark.unit
def test_decide_emits_role_defined_when_stream_is_empty() -> None:
    new_id = uuid4()
    events = define_role.decide(
        state=None,
        command=_basic_command(),
        now=_NOW,
        new_id=new_id,
    )
    assert events == [
        RoleDefined(
            role_id=new_id,
            name="Imager",
            docstring="Acquires 2D image frames on exposure or trigger.",
            occurred_at=_NOW,
            required_affordances=frozenset({Affordance.IMAGEABLE}),
            optional_affordances=frozenset({Affordance.BINNABLE}),
            produces=frozenset({SignalType("Image")}),
            consumes=frozenset({SignalType("TriggerIn")}),
        )
    ]


@pytest.mark.unit
def test_decide_trims_name_via_value_object() -> None:
    new_id = uuid4()
    events = define_role.decide(
        state=None,
        command=_basic_command(name="  Imager  "),
        now=_NOW,
        new_id=new_id,
    )
    assert events[0].name == "Imager"


@pytest.mark.unit
def test_decide_trims_docstring() -> None:
    events = define_role.decide(
        state=None,
        command=_basic_command(docstring="  Acquires frames.  "),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].docstring == "Acquires frames."


@pytest.mark.unit
def test_decide_rejects_invalid_name() -> None:
    with pytest.raises(InvalidRoleNameError):
        define_role.decide(
            state=None,
            command=_basic_command(name=""),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_rejects_empty_docstring() -> None:
    with pytest.raises(InvalidRoleDocstringError):
        define_role.decide(
            state=None,
            command=_basic_command(docstring="   "),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_rejects_too_long_docstring() -> None:
    with pytest.raises(InvalidRoleDocstringError):
        define_role.decide(
            state=None,
            command=_basic_command(docstring="x" * 2001),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_rejects_overlapping_affordance_sets() -> None:
    new_id = uuid4()
    with pytest.raises(RoleAffordanceOverlapError) as exc_info:
        define_role.decide(
            state=None,
            command=_basic_command(
                required_affordances=frozenset({Affordance.IMAGEABLE, Affordance.BINNABLE}),
                optional_affordances=frozenset({Affordance.BINNABLE}),
            ),
            now=_NOW,
            new_id=new_id,
        )
    assert exc_info.value.role_id == new_id
    assert exc_info.value.overlap == frozenset({Affordance.BINNABLE})


@pytest.mark.unit
def test_decide_rejects_empty_signal_type() -> None:
    with pytest.raises(InvalidSignalTypeError):
        define_role.decide(
            state=None,
            command=_basic_command(produces=frozenset({""})),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_rejects_too_long_signal_type() -> None:
    with pytest.raises(InvalidSignalTypeError):
        define_role.decide(
            state=None,
            command=_basic_command(consumes=frozenset({"x" * 51})),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_normalizes_signal_types_with_trim() -> None:
    events = define_role.decide(
        state=None,
        command=_basic_command(
            produces=frozenset({"  Image  ", "Frame"}),
            consumes=frozenset[str](),
        ),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].produces == frozenset({SignalType("Image"), SignalType("Frame")})


@pytest.mark.unit
def test_decide_accepts_empty_required_and_optional_affordances() -> None:
    events = define_role.decide(
        state=None,
        command=_basic_command(
            required_affordances=frozenset[Affordance](),
            optional_affordances=frozenset[Affordance](),
        ),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].required_affordances == frozenset()
    assert events[0].optional_affordances == frozenset()


@pytest.mark.unit
def test_decide_rejects_existing_state() -> None:
    existing = Role(
        id=RoleId(uuid4()),
        name=RoleName("Imager"),
        docstring="x",
    )
    with pytest.raises(RoleAlreadyExistsError) as exc_info:
        define_role.decide(
            state=existing,
            command=_basic_command(name="Other"),
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.role_id == existing.id


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    new_id = uuid4()
    command = _basic_command()
    first = define_role.decide(state=None, command=command, now=_NOW, new_id=new_id)
    second = define_role.decide(state=None, command=command, now=_NOW, new_id=new_id)
    assert first == second
