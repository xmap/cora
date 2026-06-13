"""Unit tests for the `version_model` application handler.

Update-style handler (mirrors version_family): load + fold + decide +
append. Not idempotency-wrapped. No cross-BC family lookup at version
time (per the design memo Lock: incremental edits go through
add_model_family). Tests cover auth deny, multi-source guard, the
Deprecated rejection, the ModelNotFoundError on a missing stream, and
the appended event payload shape.

The Deprecated path seeds a `ModelDeprecated` event directly onto the
in-memory store (no `deprecate_model` slice exists yet), then invokes
the version handler and expects `ModelCannotVersionError`.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.equipment import EquipmentHandlers, UnauthorizedError, wire_equipment
from cora.equipment.aggregates.model import (
    Manufacturer,
    ManufacturerName,
    ModelCannotVersionError,
    ModelDeprecated,
    ModelNotFoundError,
    PartNumber,
    event_type_name,
    model_stream_id,
    to_payload,
)
from cora.equipment.features import define_model, version_model
from cora.equipment.features.define_model import DefineModel
from cora.equipment.features.version_model import VersionModel
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
# The seed Model derives its stream id from the vendor key; the random
# id define_model pops first is unused but still occupies the queue slot.
_MODEL_FALLBACK_ID = UUID("01900000-0000-7000-8000-00000007ab11")
_MODEL_ID = model_stream_id(
    Manufacturer(name=ManufacturerName("Aerotech")),
    PartNumber("ANT130-L"),
    new_id=UUID(int=0),
)
_DEFINED_EVENT_ID = UUID("01900000-0000-7000-8000-00000007ab12")
_VERSIONED_EVENT_ID = UUID("01900000-0000-7000-8000-00000007ab13")
_DEPRECATED_EVENT_ID = UUID("01900000-0000-7000-8000-00000007ab14")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_FAMILY_A_ID = UUID("01900000-0000-7000-8000-00000000fa01")
_FAMILY_B_ID = UUID("01900000-0000-7000-8000-00000000fa02")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    """Thin wrapper preserving this file's ID list + clock."""
    return _build_deps_shared(
        ids=[
            _MODEL_FALLBACK_ID,
            _DEFINED_EVENT_ID,
            _VERSIONED_EVENT_ID,
            _DEPRECATED_EVENT_ID,
        ],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


def _patch_known_families(
    monkeypatch: pytest.MonkeyPatch,
    family_ids: list[UUID],
) -> None:
    """Patch `list_all_family_ids` as imported into the define_model handler.

    `version_model` does NOT call `list_all_family_ids`, but the
    seeding call to `define_model` does. We stub it accept-all so the
    seed succeeds in the in-memory harness.
    """

    async def _fake_list_family_ids(_pool: object) -> list[UUID]:
        return list(family_ids)

    monkeypatch.setattr(
        "cora.equipment.features.define_model.handler.list_all_family_ids",
        _fake_list_family_ids,
    )


def _define_command() -> DefineModel:
    return DefineModel(
        name="Aerotech ANT130-L",
        manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
        part_number="ANT130-L",
        declared_family_ids=frozenset({_FAMILY_A_ID}),
    )


def _version_command(
    *,
    name: str = "Aerotech ANT130-L rev-B",
    part_number: str = "ANT130-L-B",
    version_tag: str = "v2",
    declared_family_ids: frozenset[UUID] | None = None,
) -> VersionModel:
    return VersionModel(
        model_id=_MODEL_ID,
        name=name,
        manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
        part_number=part_number,
        declared_family_ids=declared_family_ids
        if declared_family_ids is not None
        else frozenset({_FAMILY_A_ID, _FAMILY_B_ID}),
        version_tag=version_tag,
    )


async def _seed_model(deps: Kernel) -> None:
    """Define a Model via the public handler so the stream is initialized."""
    await define_model.bind(deps)(
        _define_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _seed_deprecated_model(deps: Kernel, store: InMemoryEventStore) -> None:
    """Append a `ModelDeprecated` event directly so the model lands in
    Deprecated state without going through a `deprecate_model` slice
    (which does not exist yet)."""
    await _seed_model(deps)
    deprecated = ModelDeprecated(
        model_id=_MODEL_ID,
        reason="superseded by next-gen part",
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=event_type_name(deprecated),
        payload=to_payload(deprecated),
        occurred_at=deprecated.occurred_at,
        event_id=_DEPRECATED_EVENT_ID,
        command_name="DeprecateModel",
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=_PRINCIPAL_ID,
    )
    await store.append(
        stream_type="Model",
        stream_id=_MODEL_ID,
        expected_version=1,
        events=[new_event],
    )


@pytest.mark.unit
async def test_handler_returns_none_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_known_families(monkeypatch, [_FAMILY_A_ID, _FAMILY_B_ID])
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    await _seed_model(deps)

    result = await version_model.bind(deps)(
        _version_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_model_versioned_event_with_replacement_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_known_families(monkeypatch, [_FAMILY_A_ID, _FAMILY_B_ID])
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    await _seed_model(deps)

    await version_model.bind(deps)(
        _version_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Model", _MODEL_ID)
    assert version == 2
    assert [e.event_type for e in events] == ["ModelDefined", "ModelVersioned"]
    versioned = events[1]
    assert versioned.event_id == _VERSIONED_EVENT_ID
    assert versioned.metadata == {"command": "VersionModel"}
    assert versioned.payload["model_id"] == str(_MODEL_ID)
    assert versioned.payload["name"] == "Aerotech ANT130-L rev-B"
    assert versioned.payload["part_number"] == "ANT130-L-B"
    assert versioned.payload["version_tag"] == "v2"
    assert versioned.payload["declared_family_ids"] == sorted(
        [str(_FAMILY_A_ID), str(_FAMILY_B_ID)]
    )
    assert versioned.payload["manufacturer"] == {"name": "Aerotech"}


@pytest.mark.unit
async def test_handler_raises_model_not_found_when_model_does_not_exist() -> None:
    deps = _build_deps()
    handler = version_model.bind(deps)

    with pytest.raises(ModelNotFoundError):
        await handler(
            _version_command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_version_when_deprecated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_known_families(monkeypatch, [_FAMILY_A_ID])
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    await _seed_deprecated_model(deps, store)

    with pytest.raises(ModelCannotVersionError):
        await version_model.bind(deps)(
            _version_command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_known_families(monkeypatch, [_FAMILY_A_ID, _FAMILY_B_ID])
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    await _seed_model(deps)

    deny_deps = _build_deps(event_store=store, deny=True)
    with pytest.raises(UnauthorizedError) as exc_info:
        await version_model.bind(deny_deps)(
            _version_command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
def test_wire_equipment_includes_version_model() -> None:
    deps = _build_deps()
    handlers = wire_equipment(deps)
    assert isinstance(handlers, EquipmentHandlers)
    assert callable(handlers.version_model)
