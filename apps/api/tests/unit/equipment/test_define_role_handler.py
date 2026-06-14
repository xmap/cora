"""Unit tests for the `define_role` application handler."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.equipment import EquipmentHandlers, UnauthorizedError, wire_equipment
from cora.equipment.aggregates.family import Affordance
from cora.equipment.aggregates.role import (
    SEED_ROLE_DETECTOR_ID,
    InvalidRoleNameError,
)
from cora.equipment.features import define_role
from cora.equipment.features.define_role import DefineRole
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
# Per role_stream_id(RoleName("Detector")) = uuid5(_ROLE_NAMESPACE, "detector")
# = SEED_ROLE_DETECTOR_ID. The handler derives the stream_id deterministically,
# so a "Detector" command and the SEED constant collide on the same stream.
_NEW_ID = SEED_ROLE_DETECTOR_ID
_EVENT_ID = UUID("01900000-0000-7000-8000-000000007be1")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        # Handler no longer pulls a stream id from IdGenerator; only the
        # event_id is allocated from deps.id_generator.new_id().
        ids=[_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


def _command() -> DefineRole:
    return DefineRole(
        name="Detector",
        docstring="Acquires 2D image frames on exposure or trigger.",
        required_affordances=frozenset({Affordance.IMAGEABLE}),
        optional_affordances=frozenset({Affordance.BINNABLE}),
        produces=frozenset({"Image"}),
        consumes=frozenset({"TriggerIn"}),
    )


@pytest.mark.unit
async def test_handler_returns_generated_role_id() -> None:
    deps = _build_deps()
    handler = define_role.bind(deps)

    result = await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert result == _NEW_ID


@pytest.mark.unit
async def test_handler_appends_role_defined_event_to_store() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_role.bind(deps)

    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Role", _NEW_ID)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "RoleDefined"
    assert stored.schema_version == 1
    assert stored.payload == {
        "role_id": str(_NEW_ID),
        "name": "Detector",
        "docstring": "Acquires 2D image frames on exposure or trigger.",
        "occurred_at": _NOW.isoformat(),
        "required_affordances": ["Imageable"],
        "optional_affordances": ["Binnable"],
        "produces": ["Image"],
        "consumes": ["TriggerIn"],
    }
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.event_id == _EVENT_ID
    assert stored.metadata == {"command": "DefineRole"}
    assert stored.occurred_at == _NOW


@pytest.mark.unit
async def test_handler_trims_role_name_via_value_object() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_role.bind(deps)

    await handler(
        DefineRole(
            name="  Detector  ",
            docstring="x",
            required_affordances=frozenset(),
            optional_affordances=frozenset(),
            produces=frozenset(),
            consumes=frozenset(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Role", _NEW_ID)
    assert events[0].payload["name"] == "Detector"


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = _build_deps(deny=True)
    handler = define_role.bind(deps)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_does_not_append_when_denied() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store, deny=True)
    handler = define_role.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, version = await store.load("Role", _NEW_ID)
    assert events == []
    assert version == 0


@pytest.mark.unit
async def test_handler_propagates_invalid_role_name_error() -> None:
    deps = _build_deps()
    handler = define_role.bind(deps)

    with pytest.raises(InvalidRoleNameError):
        await handler(
            DefineRole(
                name="   ",
                docstring="x",
                required_affordances=frozenset(),
                optional_affordances=frozenset(),
                produces=frozenset(),
                consumes=frozenset(),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_role.bind(deps)

    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Role", _NEW_ID)
    assert events[0].causation_id == causation


@pytest.mark.unit
def test_wire_equipment_exposes_define_role_handler() -> None:
    deps = _build_deps()
    handlers = wire_equipment(deps)
    assert isinstance(handlers, EquipmentHandlers)
    assert callable(handlers.define_role)


@pytest.mark.unit
async def test_wired_handler_propagates_causation_id_through_full_composition() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handlers = wire_equipment(deps)

    await handlers.define_role(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Role", _NEW_ID)
    assert events[0].causation_id == causation
