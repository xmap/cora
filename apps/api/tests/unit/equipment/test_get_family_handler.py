"""Unit tests for the `get_family` query handler.

Mirrors `test_get_subject_handler.py` / `test_get_actor_handler.py`.
Round-trips through the write side (define → get) verify that
fold-on-read correctly returns the registered Family.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment import EquipmentHandlers, UnauthorizedError, wire_equipment
from cora.equipment.aggregates.family import (
    Family,
    FamilyName,
    FamilyStatus,
    family_stream_id,
)
from cora.equipment.features import define_family, get_family
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.get_family import GetFamily
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import DenyAllAuthorize as _DenyAllAuthorize
from tests.unit._helpers import RecordingAuthorize as _RecordingAuthorize
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
# The Family stream id is derived from the name; the generator supplies
# only the per-event id.
_DERIVED_ID = family_stream_id(FamilyName("Tomography"))
_EVENT_ID = UUID("01900000-0000-7000-8000-000000006be1")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(event_store: InMemoryEventStore | None = None) -> Kernel:
    """Thin wrapper preserving this file's ID list + clock."""
    return _build_deps_shared(
        ids=[_EVENT_ID],
        now=_NOW,
        event_store=event_store,
    )


@pytest.mark.unit
async def test_handler_returns_capability_for_known_id() -> None:
    """Round-trip: define + get."""
    deps = _build_deps()
    await define_family.bind(deps)(
        DefineFamily(name="Tomography", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    handler = get_family.bind(deps)
    view = await handler(
        GetFamily(family_id=_DERIVED_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is not None
    assert view.family == Family(
        id=_DERIVED_ID,
        name=FamilyName("Tomography"),
        status=FamilyStatus.DEFINED,
    )
    # In-memory deps have no pool -> projection-sourced timestamps absent.
    assert view.timestamps is None


@pytest.mark.unit
async def test_handler_returns_none_for_unknown_id() -> None:
    deps = _build_deps()
    handler = get_family.bind(deps)
    view = await handler(
        GetFamily(family_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert view is None


@pytest.mark.unit
async def test_handler_authorizes_with_query_name_and_default_conduit() -> None:
    """Query handlers DO call authorize. Pinned because the
    eventual TrustAuthorize swap is mechanical per handler — the call
    site has to exist."""
    tracking = _RecordingAuthorize()
    deps = _build_deps_shared(
        ids=[_EVENT_ID],
        now=_NOW,
        authz=tracking,
    )

    handler = get_family.bind(deps)
    await handler(
        GetFamily(family_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert tracking.calls == [(_PRINCIPAL_ID, "GetFamily", UUID(int=0), UUID(int=0))]


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = _build_deps_shared(
        ids=[_EVENT_ID],
        now=_NOW,
        authz=_DenyAllAuthorize(),
    )

    handler = get_family.bind(deps)
    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            GetFamily(family_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
def test_wire_equipment_includes_get_family() -> None:
    deps = _build_deps()
    handlers = wire_equipment(deps)
    assert isinstance(handlers, EquipmentHandlers)
    assert callable(handlers.get_family)
    assert callable(handlers.define_family)
