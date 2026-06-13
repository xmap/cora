"""Unit tests for the `define_model` application handler.

Mirrors the `define_family` handler test's shape (same Handler
protocol, same authorize + event-store wiring, same Kernel deps).
The Model-specific addition is the cross-BC `list_all_family_ids`
precondition: the handler resolves every element of
`command.declared_family_ids` against the Family read repo before
invoking the decider, and raises `FamilyNotFoundError` on miss.

`list_all_family_ids` reads from `proj_equipment_family_summary` and
returns `[]` when `pool is None` (the in-memory test default).
Tests that need a populated Family set monkeypatch the symbol
imported into `define_model.handler` rather than seeding a real
projection.

The Model stream id is derived from the vendor key (manufacturer +
part number), so the handler pops a random fallback id on every path
(used only for the unknown-pending-confirmation placeholder) and then
the per-event id. Real-key tests assert the derived id; the placeholder
test asserts the random fallback.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.equipment import UnauthorizedError
from cora.equipment.aggregates.family import FamilyNotFoundError
from cora.equipment.aggregates.model import (
    Manufacturer,
    ManufacturerName,
    PartNumber,
    model_stream_id,
)
from cora.equipment.features import define_model
from cora.equipment.features.define_model import DefineModel
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
# Real-key Models derive their stream id; the random id is popped but
# unused, so it stands in as the fallback slot ahead of the event id.
_FALLBACK_ID = UUID("01900000-0000-7000-8000-000000007ab1")
_EVENT_ID = UUID("01900000-0000-7000-8000-000000007be1")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_FAMILY_A_ID = UUID("01900000-0000-7000-8000-00000000fa01")
_FAMILY_B_ID = UUID("01900000-0000-7000-8000-00000000fa02")
_FAMILY_MISSING_ID = UUID("01900000-0000-7000-8000-00000000fa99")

_DERIVED_ID = model_stream_id(
    Manufacturer(name=ManufacturerName("Aerotech")),
    PartNumber("ANT130-L"),
    new_id=UUID(int=0),
)


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    """Thin wrapper preserving this file's ID list + clock."""
    return _build_deps_shared(
        ids=[_FALLBACK_ID, _EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


def _patch_known_families(
    monkeypatch: pytest.MonkeyPatch,
    family_ids: list[UUID],
) -> None:
    """Patch `list_all_family_ids` as imported into the handler module.

    The handler does `from cora.equipment.aggregates.family import
    list_family_ids` at module load, so monkeypatching the source
    function leaves the bound name in the handler stale. We patch the
    name in the handler module's namespace, which is the binding the
    handler actually calls.
    """

    async def _fake_list_family_ids(_pool: object) -> list[UUID]:
        return list(family_ids)

    monkeypatch.setattr(
        "cora.equipment.features.define_model.handler.list_all_family_ids",
        _fake_list_family_ids,
    )


def _command(
    declared_family_ids: frozenset[UUID],
    *,
    part_number: str = "ANT130-L",
) -> DefineModel:
    return DefineModel(
        name="Aerotech ANT130-L",
        manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
        part_number=part_number,
        declared_family_ids=declared_family_ids,
    )


@pytest.mark.unit
async def test_handler_returns_derived_model_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_known_families(monkeypatch, [_FAMILY_A_ID])
    deps = _build_deps()
    handler = define_model.bind(deps)

    result = await handler(
        _command(frozenset({_FAMILY_A_ID})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert result == _DERIVED_ID


@pytest.mark.unit
async def test_handler_placeholder_part_number_uses_random_fallback_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Model recorded with the unknown-pending-confirmation placeholder
    cannot derive a stable id, so the handler falls back to the random
    id rather than colliding distinct unconfirmed Models."""
    _patch_known_families(monkeypatch, [_FAMILY_A_ID])
    deps = _build_deps()
    handler = define_model.bind(deps)

    result = await handler(
        _command(frozenset({_FAMILY_A_ID}), part_number="unknown-pending-confirmation"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert result == _FALLBACK_ID


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_known_families(monkeypatch, [_FAMILY_A_ID])
    deps = _build_deps(deny=True)
    handler = define_model.bind(deps)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            _command(frozenset({_FAMILY_A_ID})),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_does_not_append_when_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_known_families(monkeypatch, [_FAMILY_A_ID])
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store, deny=True)
    handler = define_model.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            _command(frozenset({_FAMILY_A_ID})),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, version = await store.load("Model", _DERIVED_ID)
    assert events == []
    assert version == 0


@pytest.mark.unit
async def test_handler_raises_family_not_found_for_unregistered_family(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cross-BC precondition: declared_family_ids containing an id that
    doesn't resolve via `list_all_family_ids` raises `FamilyNotFoundError`."""
    _patch_known_families(monkeypatch, [_FAMILY_A_ID])
    deps = _build_deps()
    handler = define_model.bind(deps)

    with pytest.raises(FamilyNotFoundError):
        await handler(
            _command(frozenset({_FAMILY_A_ID, _FAMILY_MISSING_ID})),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_proceeds_when_all_declared_family_ids_resolve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every declared family resolves against the fake lookup, so the
    handler reaches the decider and returns the derived id."""
    _patch_known_families(monkeypatch, [_FAMILY_A_ID, _FAMILY_B_ID])
    deps = _build_deps()
    handler = define_model.bind(deps)

    result = await handler(
        _command(frozenset({_FAMILY_A_ID, _FAMILY_B_ID})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert result == _DERIVED_ID


@pytest.mark.unit
async def test_handler_appends_model_defined_event_to_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After success, the event store receives stream_type='Model',
    expected_version=0, and exactly one NewEvent of type 'ModelDefined'."""
    _patch_known_families(monkeypatch, [_FAMILY_A_ID])
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_model.bind(deps)

    await handler(
        _command(frozenset({_FAMILY_A_ID})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Model", _DERIVED_ID)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "ModelDefined"
    assert stored.schema_version == 1
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.event_id == _EVENT_ID
    assert stored.metadata == {"command": "DefineModel"}
    assert stored.occurred_at == _NOW
    assert stored.payload["model_id"] == str(_DERIVED_ID)
    assert stored.payload["name"] == "Aerotech ANT130-L"
    assert stored.payload["part_number"] == "ANT130-L"
    assert stored.payload["declared_family_ids"] == [str(_FAMILY_A_ID)]
