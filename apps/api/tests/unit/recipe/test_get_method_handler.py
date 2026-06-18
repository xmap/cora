"""Unit tests for the `get_method` query handler.

Mirrors `test_get_family_handler.py`. Round-trips through the
write side (define → get) verify fold-on-read returns the registered
Method with the right needed_family_ids frozenset.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.recipe import RecipeHandlers, UnauthorizedError, wire_recipe
from cora.recipe.aggregates.method import (
    ExecutionPattern,
    Method,
    MethodName,
    MethodStatus,
)
from cora.recipe.features import define_method, get_method
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.get_method import GetMethod
from tests.unit._helpers import RecordingAuthorize, build_deps, seed_capability

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000000ac01")
_EVENT_ID = UUID("01900000-0000-7000-8000-00000000ac02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CAP1 = UUID("01900000-0000-7000-8000-000000000111")
_CAP2 = UUID("01900000-0000-7000-8000-000000000222")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-00000000ac0c")


@pytest.mark.unit
async def test_handler_returns_method_for_known_id() -> None:
    """Round-trip: define + get."""
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
    await seed_capability(deps.event_store, _CAPABILITY_ID)
    await define_method.bind(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            name="XRF Fly Mapping",
            capability_id=_CAPABILITY_ID,
            needed_family_ids=frozenset({_CAP1, _CAP2}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    handler = get_method.bind(deps)
    view = await handler(
        GetMethod(method_id=_NEW_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is not None
    assert view.method == Method(
        id=_NEW_ID,
        name=MethodName("XRF Fly Mapping"),
        needed_family_ids=frozenset({_CAP1, _CAP2}),
        capability_id=_CAPABILITY_ID,
        status=MethodStatus.DEFINED,
        execution_pattern=ExecutionPattern.BATCH,
    )
    # In-memory deps have no pool, so projection-sourced timestamps are
    # absent (Path C handler behavior; Postgres integration suite
    # exercises the populated path).
    assert view.timestamps is None


@pytest.mark.unit
async def test_handler_returns_method_with_empty_needed_family_ids() -> None:
    """Procedural Methods (no equipment requirement) round-trip
    through fold-on-read with empty frozenset preserved."""
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
    await seed_capability(deps.event_store, _CAPABILITY_ID)
    await define_method.bind(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            name="Sample Cleaning",
            capability_id=_CAPABILITY_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    handler = get_method.bind(deps)
    view = await handler(
        GetMethod(method_id=_NEW_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is not None
    assert view.method.needed_family_ids == frozenset()


@pytest.mark.unit
async def test_handler_returns_none_for_unknown_id() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
    handler = get_method.bind(deps)
    view = await handler(
        GetMethod(method_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert view is None


@pytest.mark.unit
async def test_handler_authorizes_with_query_name_and_default_conduit() -> None:
    tracking = RecordingAuthorize()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, authz=tracking)

    handler = get_method.bind(deps)
    await handler(
        GetMethod(method_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert tracking.calls == [(_PRINCIPAL_ID, "GetMethod", UUID(int=0), UUID(int=0))]


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = build_deps(ids=[_NEW_ID], now=_NOW, deny=True)

    handler = get_method.bind(deps)
    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            GetMethod(method_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
def test_wire_recipe_includes_get_method() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
    handlers = wire_recipe(deps)
    assert isinstance(handlers, RecipeHandlers)
    assert callable(handlers.get_method)
