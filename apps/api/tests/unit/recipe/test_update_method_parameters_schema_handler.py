"""Unit tests for the `update_method_parameters_schema` application handler.

Mirrors `test_version_method_handler.py` shape.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from cora.recipe import RecipeHandlers, UnauthorizedError, wire_recipe
from cora.recipe.aggregates.method import (
    ExecutionPattern,
    InvalidMethodParametersSchemaError,
    MethodNotFoundError,
)
from cora.recipe.features import define_method, update_method_parameters_schema
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.update_method_parameters_schema import UpdateMethodParametersSchema
from tests.unit._helpers import build_deps, seed_capability

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_METHOD_ID = UUID("01900000-0000-7000-8000-00000000bd01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-00000000bd0c")
_DEFINED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000bd02")
_SCHEMA_EVENT_ID = UUID("01900000-0000-7000-8000-00000000bd03")
_SCHEMA_EVENT_ID_2 = UUID("01900000-0000-7000-8000-00000000bd04")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")

_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _valid_schema(min_val: int = 5) -> dict[str, Any]:
    return {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {
            "energy": {
                "type": "number",
                "minimum": min_val,
                "unit": {"system": "udunits", "code": "keV"},
            }
        },
    }


async def _define_method_helper(deps: Kernel) -> UUID:
    """Seed bound Capability + invoke define_method."""
    await seed_capability(deps.event_store, _CAPABILITY_ID)
    return await define_method.bind(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            name="XRF Mapping",
            capability_id=_CAPABILITY_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.unit
async def test_handler_returns_none_on_success() -> None:
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[_METHOD_ID, _DEFINED_EVENT_ID, _SCHEMA_EVENT_ID, _SCHEMA_EVENT_ID_2],
        now=_NOW,
        event_store=store,
    )
    method_id = await _define_method_helper(deps)

    result = await update_method_parameters_schema.bind(deps)(
        UpdateMethodParametersSchema(method_id=method_id, parameters_schema=_valid_schema()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_method_parameters_schema_updated_event() -> None:
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[_METHOD_ID, _DEFINED_EVENT_ID, _SCHEMA_EVENT_ID, _SCHEMA_EVENT_ID_2],
        now=_NOW,
        event_store=store,
    )
    method_id = await _define_method_helper(deps)
    schema = _valid_schema()

    await update_method_parameters_schema.bind(deps)(
        UpdateMethodParametersSchema(method_id=method_id, parameters_schema=schema),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Method", method_id)
    assert version == 2
    assert [e.event_type for e in events] == ["MethodDefined", "MethodParametersSchemaUpdated"]
    schema_event = events[1]
    assert schema_event.event_id == _SCHEMA_EVENT_ID
    assert schema_event.metadata == {"command": "UpdateMethodParametersSchema"}
    assert schema_event.payload["parameters_schema"] == schema


@pytest.mark.unit
async def test_handler_no_op_on_unchanged_schema_does_not_append() -> None:
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[_METHOD_ID, _DEFINED_EVENT_ID, _SCHEMA_EVENT_ID, _SCHEMA_EVENT_ID_2],
        now=_NOW,
        event_store=store,
    )
    method_id = await _define_method_helper(deps)
    handler = update_method_parameters_schema.bind(deps)
    schema = _valid_schema()

    await handler(
        UpdateMethodParametersSchema(method_id=method_id, parameters_schema=schema),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await handler(
        UpdateMethodParametersSchema(method_id=method_id, parameters_schema=schema),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Method", method_id)
    assert version == 2  # define + 1 schema-update; second call no-op
    assert [e.event_type for e in events] == ["MethodDefined", "MethodParametersSchemaUpdated"]


@pytest.mark.unit
async def test_handler_supports_setting_then_clearing_schema() -> None:
    """Set, then clear: two events emitted; final state has parameters_schema=None
    (and projection's parameters_schema_present flips back to FALSE)."""
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[_METHOD_ID, _DEFINED_EVENT_ID, _SCHEMA_EVENT_ID, _SCHEMA_EVENT_ID_2],
        now=_NOW,
        event_store=store,
    )
    method_id = await _define_method_helper(deps)
    handler = update_method_parameters_schema.bind(deps)

    await handler(
        UpdateMethodParametersSchema(method_id=method_id, parameters_schema=_valid_schema()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await handler(
        UpdateMethodParametersSchema(method_id=method_id, parameters_schema=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Method", method_id)
    assert version == 3
    assert events[1].payload["parameters_schema"] == _valid_schema()
    assert events[2].payload["parameters_schema"] is None


@pytest.mark.unit
async def test_handler_raises_method_not_found_when_method_does_not_exist() -> None:
    deps = build_deps(
        ids=[_METHOD_ID, _DEFINED_EVENT_ID, _SCHEMA_EVENT_ID, _SCHEMA_EVENT_ID_2], now=_NOW
    )
    handler = update_method_parameters_schema.bind(deps)

    with pytest.raises(MethodNotFoundError):
        await handler(
            UpdateMethodParametersSchema(method_id=_METHOD_ID, parameters_schema=_valid_schema()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_invalid_schema_for_missing_dollar_schema() -> None:
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[_METHOD_ID, _DEFINED_EVENT_ID, _SCHEMA_EVENT_ID, _SCHEMA_EVENT_ID_2],
        now=_NOW,
        event_store=store,
    )
    method_id = await _define_method_helper(deps)

    with pytest.raises(InvalidMethodParametersSchemaError):
        await update_method_parameters_schema.bind(deps)(
            UpdateMethodParametersSchema(
                method_id=method_id,
                parameters_schema={"type": "object"},  # no $schema
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[_METHOD_ID, _DEFINED_EVENT_ID, _SCHEMA_EVENT_ID, _SCHEMA_EVENT_ID_2],
        now=_NOW,
        event_store=store,
    )
    method_id = await _define_method_helper(deps)

    deny_deps = build_deps(
        ids=[_METHOD_ID, _DEFINED_EVENT_ID, _SCHEMA_EVENT_ID, _SCHEMA_EVENT_ID_2],
        now=_NOW,
        event_store=store,
        deny=True,
    )
    with pytest.raises(UnauthorizedError) as exc_info:
        await update_method_parameters_schema.bind(deny_deps)(
            UpdateMethodParametersSchema(method_id=method_id, parameters_schema=_valid_schema()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[_METHOD_ID, _DEFINED_EVENT_ID, _SCHEMA_EVENT_ID, _SCHEMA_EVENT_ID_2],
        now=_NOW,
        event_store=store,
    )
    method_id = await _define_method_helper(deps)

    await update_method_parameters_schema.bind(deps)(
        UpdateMethodParametersSchema(method_id=method_id, parameters_schema=_valid_schema()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Method", method_id)
    assert events[1].causation_id == causation


@pytest.mark.unit
def test_wire_recipe_includes_update_method_parameters_schema() -> None:
    deps = build_deps(
        ids=[_METHOD_ID, _DEFINED_EVENT_ID, _SCHEMA_EVENT_ID, _SCHEMA_EVENT_ID_2], now=_NOW
    )
    handlers = wire_recipe(deps)
    assert isinstance(handlers, RecipeHandlers)
    assert callable(handlers.update_method_parameters_schema)
