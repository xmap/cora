"""Unit tests for the `remove_model_family` application handler.

Update-style handler (mirrors `remove_asset_family` and `version_model`):
load + fold + decide + append. Not idempotency-wrapped.

Unlike `add_model_family`, this slice performs NO cross-BC Family
lookup: removal only requires `family_id` to be present in
`declared_families`. The Family may have been deprecated or deleted
from the Family registry and removal still proceeds.

The seeding `define_model` call DOES still resolve `list_family_ids`
cross-BC; the unit harness has no Postgres pool, so we monkeypatch
that symbol on the `define_model` handler module to a fixed accept-
all stub so the seed succeeds. The slice under test imports nothing
from `list_family_ids`.

The Deprecated path seeds a `ModelDeprecated` event directly onto
the in-memory store (no `deprecate_model` slice is exercised in
this test file), then invokes the handler and expects
`ModelCannotVersionError`.
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
    ModelFamilyNotPresentError,
    ModelNotFoundError,
    event_type_name,
    to_payload,
)
from cora.equipment.features import define_model, remove_model_family
from cora.equipment.features.define_model import DefineModel
from cora.equipment.features.remove_model_family import RemoveModelFamily
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
_MODEL_ID = UUID("01900000-0000-7000-8000-00000007ad11")
_DEFINED_EVENT_ID = UUID("01900000-0000-7000-8000-00000007ad12")
_REMOVED_EVENT_ID = UUID("01900000-0000-7000-8000-00000007ad13")
_DEPRECATED_EVENT_ID = UUID("01900000-0000-7000-8000-00000007ad14")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_FAMILY_A_ID = UUID("01900000-0000-7000-8000-00000000fc01")
_FAMILY_ABSENT_ID = UUID("01900000-0000-7000-8000-00000000fc99")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    """Thin wrapper preserving this file's ID list + clock."""
    return _build_deps_shared(
        ids=[_MODEL_ID, _DEFINED_EVENT_ID, _REMOVED_EVENT_ID, _DEPRECATED_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


def _patch_seed_known_families(
    monkeypatch: pytest.MonkeyPatch,
    family_ids: list[UUID],
) -> None:
    """Patch `list_family_ids` only on the `define_model` handler.

    The slice under test (`remove_model_family`) does NOT perform a
    cross-BC family lookup, so only the seeding `define_model` call
    needs the stub.
    """

    async def _fake_list_family_ids(_pool: object) -> list[UUID]:
        return list(family_ids)

    monkeypatch.setattr(
        "cora.equipment.features.define_model.handler.list_family_ids",
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
    _patch_seed_known_families(monkeypatch, [_FAMILY_A_ID])
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    await _seed_model(deps)

    result = await remove_model_family.bind(deps)(
        RemoveModelFamily(model_id=_MODEL_ID, family_id=_FAMILY_A_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None

    events, version = await store.load("Model", _MODEL_ID)
    assert version == 2
    assert [e.event_type for e in events] == ["ModelDefined", "ModelFamilyRemoved"]
    removed = events[1]
    assert removed.event_id == _REMOVED_EVENT_ID
    assert removed.metadata == {"command": "RemoveModelFamily"}
    assert removed.payload["model_id"] == str(_MODEL_ID)
    assert removed.payload["family_id"] == str(_FAMILY_A_ID)
    assert removed.payload["occurred_at"] == _NOW.isoformat()


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_seed_known_families(monkeypatch, [_FAMILY_A_ID])
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    await _seed_model(deps)

    deny_deps = _build_deps(event_store=store, deny=True)
    with pytest.raises(UnauthorizedError) as exc_info:
        await remove_model_family.bind(deny_deps)(
            RemoveModelFamily(model_id=_MODEL_ID, family_id=_FAMILY_A_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_raises_model_not_found_when_stream_is_missing() -> None:
    """An unseeded model stream surfaces ModelNotFoundError. No cross-BC
    lookup runs; the decider rejects because state is None."""
    deps = _build_deps()

    with pytest.raises(ModelNotFoundError) as exc_info:
        await remove_model_family.bind(deps)(
            RemoveModelFamily(model_id=_MODEL_ID, family_id=_FAMILY_A_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.model_id == _MODEL_ID


@pytest.mark.unit
async def test_handler_raises_not_present_on_absent_family(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Removing a family not in declared_families surfaces
    ModelFamilyNotPresentError (strict-not-idempotent). No cross-BC
    lookup runs."""
    _patch_seed_known_families(monkeypatch, [_FAMILY_A_ID])
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    await _seed_model(deps)

    with pytest.raises(ModelFamilyNotPresentError) as exc_info:
        await remove_model_family.bind(deps)(
            # _FAMILY_ABSENT_ID was never declared at define_model time.
            RemoveModelFamily(model_id=_MODEL_ID, family_id=_FAMILY_ABSENT_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.model_id == _MODEL_ID
    assert exc_info.value.family_id == _FAMILY_ABSENT_ID


@pytest.mark.unit
async def test_handler_raises_cannot_version_when_deprecated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deprecated Models cannot accept family removals."""
    _patch_seed_known_families(monkeypatch, [_FAMILY_A_ID])
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    await _seed_deprecated_model(deps, store)

    with pytest.raises(ModelCannotVersionError):
        await remove_model_family.bind(deps)(
            RemoveModelFamily(model_id=_MODEL_ID, family_id=_FAMILY_A_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
def test_wire_equipment_includes_remove_model_family() -> None:
    deps = _build_deps()
    handlers = wire_equipment(deps)
    assert isinstance(handlers, EquipmentHandlers)
    assert callable(handlers.remove_model_family)
