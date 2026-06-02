"""Unit tests for the `deprecate_model` application handler.

Update-style handler (mirrors version_model and deprecate_family):
load + fold + decide + append. Not idempotency-wrapped; domain-
idempotent via `ModelCannotDeprecateError` on retry from `Deprecated`.

Tests cover the happy path (returns None + appends one
ModelDeprecated event), the auth deny path, the
ModelNotFoundError on a missing stream, and the
ModelCannotDeprecateError on re-deprecation.

The Deprecated path drives the slice itself to land the Model in
Deprecated state, then invokes the handler a second time and expects
ModelCannotDeprecateError (strict-not-idempotent).
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.equipment import EquipmentHandlers, UnauthorizedError, wire_equipment
from cora.equipment.aggregates.model import (
    Manufacturer,
    ManufacturerName,
    ModelCannotDeprecateError,
    ModelNotFoundError,
)
from cora.equipment.features import define_model, deprecate_model
from cora.equipment.features.define_model import DefineModel
from cora.equipment.features.deprecate_model import DeprecateModel
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
_MODEL_ID = UUID("01900000-0000-7000-8000-00000007ad11")
_DEFINED_EVENT_ID = UUID("01900000-0000-7000-8000-00000007ad12")
_DEPRECATED_EVENT_ID = UUID("01900000-0000-7000-8000-00000007ad13")
_EXTRA_EVENT_ID = UUID("01900000-0000-7000-8000-00000007ad14")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_FAMILY_A_ID = UUID("01900000-0000-7000-8000-00000000fad1")

_REASON = "Vendor end-of-life 2026-Q3"


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    """Thin wrapper preserving this file's ID list + clock."""
    return _build_deps_shared(
        ids=[_MODEL_ID, _DEFINED_EVENT_ID, _DEPRECATED_EVENT_ID, _EXTRA_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


def _patch_known_families(
    monkeypatch: pytest.MonkeyPatch,
    family_ids: list[UUID],
) -> None:
    """Patch `list_all_family_ids` as imported into the define_model handler.

    `deprecate_model` does NOT call `list_all_family_ids`, but the
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
        declared_families=frozenset({_FAMILY_A_ID}),
    )


async def _seed_model(deps: Kernel) -> None:
    """Define a Model via the public handler so the stream is initialized."""
    await define_model.bind(deps)(
        _define_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.unit
async def test_handler_returns_none_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_known_families(monkeypatch, [_FAMILY_A_ID])
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    await _seed_model(deps)

    result = await deprecate_model.bind(deps)(
        DeprecateModel(model_id=_MODEL_ID, reason=_REASON),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_model_deprecated_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_known_families(monkeypatch, [_FAMILY_A_ID])
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    await _seed_model(deps)

    await deprecate_model.bind(deps)(
        DeprecateModel(model_id=_MODEL_ID, reason=_REASON),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Model", _MODEL_ID)
    assert version == 2
    assert [e.event_type for e in events] == ["ModelDefined", "ModelDeprecated"]
    deprecated = events[1]
    assert deprecated.event_id == _DEPRECATED_EVENT_ID
    assert deprecated.metadata == {"command": "DeprecateModel"}
    assert deprecated.payload["model_id"] == str(_MODEL_ID)
    assert deprecated.payload["reason"] == _REASON


@pytest.mark.unit
async def test_handler_raises_model_not_found_when_model_does_not_exist() -> None:
    deps = _build_deps()
    handler = deprecate_model.bind(deps)

    with pytest.raises(ModelNotFoundError):
        await handler(
            DeprecateModel(model_id=_MODEL_ID, reason=_REASON),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_deprecate_when_already_deprecated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Strict-not-idempotent: re-deprecating raises."""
    _patch_known_families(monkeypatch, [_FAMILY_A_ID])
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    await _seed_model(deps)

    handler = deprecate_model.bind(deps)
    await handler(
        DeprecateModel(model_id=_MODEL_ID, reason=_REASON),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    with pytest.raises(ModelCannotDeprecateError):
        await handler(
            DeprecateModel(model_id=_MODEL_ID, reason=_REASON),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_known_families(monkeypatch, [_FAMILY_A_ID])
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    await _seed_model(deps)

    deny_deps = _build_deps(event_store=store, deny=True)
    with pytest.raises(UnauthorizedError) as exc_info:
        await deprecate_model.bind(deny_deps)(
            DeprecateModel(model_id=_MODEL_ID, reason=_REASON),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    _patch_known_families(monkeypatch, [_FAMILY_A_ID])
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    await _seed_model(deps)

    await deprecate_model.bind(deps)(
        DeprecateModel(model_id=_MODEL_ID, reason=_REASON),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Model", _MODEL_ID)
    assert events[1].causation_id == causation


@pytest.mark.unit
def test_wire_equipment_includes_deprecate_model() -> None:
    deps = _build_deps()
    handlers = wire_equipment(deps)
    assert isinstance(handlers, EquipmentHandlers)
    assert callable(handlers.deprecate_model)
