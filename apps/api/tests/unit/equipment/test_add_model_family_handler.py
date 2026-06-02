"""Unit tests for the `add_model_family` application handler.

Update-style handler (mirrors `add_asset_family` and `version_model`):
load + fold + decide + append. Not idempotency-wrapped.

Cross-BC concern: the referenced `family_id` must resolve to a
registered Family via `list_all_family_ids`. The unit harness has no
Postgres pool, so we monkeypatch the symbol imported into the
handler module to a fixed accept-all stub (mirrors the
`define_model` handler test pattern). The seeding `define_model`
call is also monkeypatched against the same stub for the same
reason.

The Deprecated path seeds a `ModelDeprecated` event directly onto
the in-memory store (no `deprecate_model` slice is exercised in
this test file), then invokes the handler and expects
`ModelCannotAddFamilyError`.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.equipment import EquipmentHandlers, UnauthorizedError, wire_equipment
from cora.equipment.aggregates.family import FamilyNotFoundError
from cora.equipment.aggregates.model import (
    Manufacturer,
    ManufacturerName,
    ModelCannotAddFamilyError,
    ModelDeprecated,
    ModelFamilyAlreadyPresentError,
    ModelNotFoundError,
    event_type_name,
    to_payload,
)
from cora.equipment.features import add_model_family, define_model
from cora.equipment.features.add_model_family import AddModelFamily
from cora.equipment.features.define_model import DefineModel
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
_MODEL_ID = UUID("01900000-0000-7000-8000-00000007ac11")
_DEFINED_EVENT_ID = UUID("01900000-0000-7000-8000-00000007ac12")
_ADDED_EVENT_ID = UUID("01900000-0000-7000-8000-00000007ac13")
_DEPRECATED_EVENT_ID = UUID("01900000-0000-7000-8000-00000007ac14")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_FAMILY_A_ID = UUID("01900000-0000-7000-8000-00000000fb01")
_FAMILY_B_ID = UUID("01900000-0000-7000-8000-00000000fb02")
_FAMILY_MISSING_ID = UUID("01900000-0000-7000-8000-00000000fb99")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    """Thin wrapper preserving this file's ID list + clock."""
    return _build_deps_shared(
        ids=[_MODEL_ID, _DEFINED_EVENT_ID, _ADDED_EVENT_ID, _DEPRECATED_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


def _patch_known_families(
    monkeypatch: pytest.MonkeyPatch,
    family_ids: list[UUID],
) -> None:
    """Patch `list_all_family_ids` in both handler modules that look it up.

    The seeding `define_model` call AND the slice under test
    (`add_model_family`) each import `list_all_family_ids` by name at module
    load. Patching the binding in each handler's namespace ensures both
    paths see the stub.
    """

    async def _fake_list_family_ids(_pool: object) -> list[UUID]:
        return list(family_ids)

    monkeypatch.setattr(
        "cora.equipment.features.define_model.handler.list_all_family_ids",
        _fake_list_family_ids,
    )
    monkeypatch.setattr(
        "cora.equipment.features.add_model_family.handler.list_all_family_ids",
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
    """Define a Model via the public handler so the stream is initialized
    in `Defined` status with `_FAMILY_A_ID` declared."""
    await define_model.bind(deps)(
        _define_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _seed_deprecated_model(deps: Kernel, store: InMemoryEventStore) -> None:
    """Append a `ModelDeprecated` event directly so the model lands in
    `Deprecated` status without going through a `deprecate_model` slice
    in this test file."""
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
async def test_handler_returns_none_and_appends_event_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_known_families(monkeypatch, [_FAMILY_A_ID, _FAMILY_B_ID])
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    await _seed_model(deps)

    result = await add_model_family.bind(deps)(
        AddModelFamily(model_id=_MODEL_ID, family_id=_FAMILY_B_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None

    events, version = await store.load("Model", _MODEL_ID)
    assert version == 2
    assert [e.event_type for e in events] == ["ModelDefined", "ModelFamilyAdded"]
    added = events[1]
    assert added.event_id == _ADDED_EVENT_ID
    assert added.metadata == {"command": "AddModelFamily"}
    assert added.payload["model_id"] == str(_MODEL_ID)
    assert added.payload["family_id"] == str(_FAMILY_B_ID)
    assert added.payload["occurred_at"] == _NOW.isoformat()


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
        await add_model_family.bind(deny_deps)(
            AddModelFamily(model_id=_MODEL_ID, family_id=_FAMILY_B_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_raises_family_not_found_for_unregistered_family(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cross-BC precondition: the family_id must resolve via
    `list_all_family_ids`; an unregistered id raises `FamilyNotFoundError`
    before the decider is reached."""
    _patch_known_families(monkeypatch, [_FAMILY_A_ID, _FAMILY_B_ID])
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    await _seed_model(deps)

    with pytest.raises(FamilyNotFoundError) as exc_info:
        await add_model_family.bind(deps)(
            AddModelFamily(model_id=_MODEL_ID, family_id=_FAMILY_MISSING_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.family_id == _FAMILY_MISSING_ID


@pytest.mark.unit
async def test_handler_raises_model_not_found_when_stream_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unseeded model stream surfaces ModelNotFoundError. The
    cross-BC lookup passes (family is known); the decider rejects
    because state is None."""
    _patch_known_families(monkeypatch, [_FAMILY_A_ID])
    deps = _build_deps()

    with pytest.raises(ModelNotFoundError) as exc_info:
        await add_model_family.bind(deps)(
            AddModelFamily(model_id=_MODEL_ID, family_id=_FAMILY_A_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.model_id == _MODEL_ID


@pytest.mark.unit
async def test_handler_raises_already_present_on_duplicate_family(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Re-adding a family already in declared_families surfaces
    ModelFamilyAlreadyPresentError (strict-not-idempotent)."""
    _patch_known_families(monkeypatch, [_FAMILY_A_ID])
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    await _seed_model(deps)

    with pytest.raises(ModelFamilyAlreadyPresentError) as exc_info:
        await add_model_family.bind(deps)(
            # _FAMILY_A_ID is already declared at define_model time.
            AddModelFamily(model_id=_MODEL_ID, family_id=_FAMILY_A_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.model_id == _MODEL_ID
    assert exc_info.value.family_id == _FAMILY_A_ID


@pytest.mark.unit
async def test_handler_raises_cannot_add_family_when_deprecated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deprecated Models cannot accept new family declarations."""
    _patch_known_families(monkeypatch, [_FAMILY_A_ID, _FAMILY_B_ID])
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    await _seed_deprecated_model(deps, store)

    with pytest.raises(ModelCannotAddFamilyError):
        await add_model_family.bind(deps)(
            AddModelFamily(model_id=_MODEL_ID, family_id=_FAMILY_B_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
def test_wire_equipment_includes_add_model_family() -> None:
    deps = _build_deps()
    handlers = wire_equipment(deps)
    assert isinstance(handlers, EquipmentHandlers)
    assert callable(handlers.add_model_family)
