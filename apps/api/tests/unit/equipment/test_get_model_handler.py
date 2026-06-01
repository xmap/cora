"""Unit tests for the `get_model` query handler.

Mirrors `test_get_family_handler.py`. Round-trips through the write
side (define + add_model_family + get) verify that fold-on-read
correctly returns the registered Model state. Read slices don't emit
events, so the assertions focus on (1) authorize wiring (2) the
load + fold spine and (3) None-on-miss semantics. Unlike Family,
no `ModelView` wrapper exists: the Model summary projection does
not carry per-FSM-transition timestamps, so the handler returns
`Model | None` directly.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment import EquipmentHandlers, UnauthorizedError, wire_equipment
from cora.equipment.aggregates.model import (
    Manufacturer,
    ManufacturerName,
    Model,
    ModelName,
    ModelStatus,
    PartNumber,
)
from cora.equipment.features import add_model_family, define_model, get_model
from cora.equipment.features.add_model_family import AddModelFamily
from cora.equipment.features.define_model import DefineModel
from cora.equipment.features.get_model import GetModel
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import DenyAllAuthorize as _DenyAllAuthorize
from tests.unit._helpers import RecordingAuthorize as _RecordingAuthorize
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000007ab1")
_EVENT_ID = UUID("01900000-0000-7000-8000-000000007be1")
_ADD_EVENT_ID = UUID("01900000-0000-7000-8000-000000007be2")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_FAMILY_A_ID = UUID("01900000-0000-7000-8000-00000000fa01")
_FAMILY_B_ID = UUID("01900000-0000-7000-8000-00000000fa02")


def _build_deps(event_store: InMemoryEventStore | None = None) -> Kernel:
    """Thin wrapper preserving this file's ID list + clock."""
    return _build_deps_shared(
        ids=[_NEW_ID, _EVENT_ID, _ADD_EVENT_ID],
        now=_NOW,
        event_store=event_store,
    )


def _patch_known_families(
    monkeypatch: pytest.MonkeyPatch,
    family_ids: list[UUID],
    *,
    targets: tuple[str, ...] = (
        "cora.equipment.features.define_model.handler.list_family_ids",
        "cora.equipment.features.add_model_family.handler.list_family_ids",
    ),
) -> None:
    """Stub `list_family_ids` as imported into upstream command handlers.

    `get_model` itself does NOT call `list_family_ids`; the stub is
    needed only for the upstream `define_model` and `add_model_family`
    calls that seed the stream this test reads back.
    """

    async def _fake_list_family_ids(_pool: object) -> list[UUID]:
        return list(family_ids)

    for target in targets:
        monkeypatch.setattr(target, _fake_list_family_ids)


@pytest.mark.unit
async def test_handler_returns_model_for_known_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Round-trip: define + get."""
    _patch_known_families(monkeypatch, [_FAMILY_A_ID])
    deps = _build_deps()
    await define_model.bind(deps)(
        DefineModel(
            name="Aerotech ANT130-L",
            manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
            part_number="ANT130-L",
            declared_families=frozenset({_FAMILY_A_ID}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    handler = get_model.bind(deps)
    model = await handler(
        GetModel(model_id=_NEW_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert model == Model(
        id=_NEW_ID,
        name=ModelName("Aerotech ANT130-L"),
        manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
        part_number=PartNumber("ANT130-L"),
        declared_families=frozenset({_FAMILY_A_ID}),
        status=ModelStatus.DEFINED,
        version=None,
    )


@pytest.mark.unit
async def test_handler_reflects_targeted_mutation_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """fold-on-read returns the post-mutation state: define + add a
    second family yields a 2-element `declared_families` frozenset."""
    _patch_known_families(monkeypatch, [_FAMILY_A_ID, _FAMILY_B_ID])
    deps = _build_deps()
    await define_model.bind(deps)(
        DefineModel(
            name="Aerotech ANT130-L",
            manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
            part_number="ANT130-L",
            declared_families=frozenset({_FAMILY_A_ID}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_model_family.bind(deps)(
        AddModelFamily(model_id=_NEW_ID, family_id=_FAMILY_B_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    handler = get_model.bind(deps)
    model = await handler(
        GetModel(model_id=_NEW_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert model is not None
    assert model.declared_families == frozenset({_FAMILY_A_ID, _FAMILY_B_ID})
    assert model.status is ModelStatus.DEFINED


@pytest.mark.unit
async def test_handler_returns_none_for_unknown_id() -> None:
    """Missing stream folds to None; the handler does NOT raise
    `ModelNotFoundError` here (transition / mutation handlers do; read
    handlers leave the not-found mapping to the route / tool layer)."""
    deps = _build_deps()
    handler = get_model.bind(deps)
    model = await handler(
        GetModel(model_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert model is None


@pytest.mark.unit
async def test_handler_authorizes_with_query_name_and_default_conduit() -> None:
    """Query handlers DO call authorize. Pinned because the eventual
    TrustAuthorize swap is mechanical per handler ,  the call site has
    to exist."""
    tracking = _RecordingAuthorize()
    deps = _build_deps_shared(
        ids=[_NEW_ID, _EVENT_ID],
        now=_NOW,
        authz=tracking,
    )

    handler = get_model.bind(deps)
    await handler(
        GetModel(model_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert tracking.calls == [(_PRINCIPAL_ID, "GetModel", UUID(int=0), UUID(int=0))]


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = _build_deps_shared(
        ids=[_NEW_ID, _EVENT_ID],
        now=_NOW,
        authz=_DenyAllAuthorize(),
    )

    handler = get_model.bind(deps)
    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            GetModel(model_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
def test_wire_equipment_includes_get_model() -> None:
    deps = _build_deps()
    handlers = wire_equipment(deps)
    assert isinstance(handlers, EquipmentHandlers)
    assert callable(handlers.get_model)
    assert callable(handlers.define_model)
