"""Unit tests for the `define_policy` application handler."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.routing import SYSTEM_HTTP_SURFACE_ID
from cora.trust import TrustHandlers, UnauthorizedError, wire_trust
from cora.trust.aggregates.policy import InvalidPolicyNameError
from cora.trust.features import define_policy
from cora.trust.features.define_policy import DefinePolicy
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000000401")
_EVENT_ID = UUID("01900000-0000-7000-8000-0000000004e1")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CONDUIT_ID = UUID("01900000-0000-7000-8000-00000000aaaa")
_ALLOWED_PRINCIPAL = UUID("01900000-0000-7000-8000-000000000a01")


def _command(name: str = "Beam-team") -> DefinePolicy:
    return DefinePolicy(
        name=name,
        conduit_id=_CONDUIT_ID,
        permitted_principal_ids=frozenset({_ALLOWED_PRINCIPAL}),
        permitted_commands=frozenset({"RegisterActor"}),
        surface_id=SYSTEM_HTTP_SURFACE_ID,
    )


@pytest.mark.unit
async def test_handler_returns_generated_policy_id() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
    handler = define_policy.bind(deps)

    result = await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert result == _NEW_ID


@pytest.mark.unit
async def test_handler_appends_policy_defined_event_to_store() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_policy.bind(deps)

    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Policy", _NEW_ID)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "PolicyDefined"
    assert stored.schema_version == 1
    assert stored.payload == {
        "policy_id": str(_NEW_ID),
        "name": "Beam-team",
        "conduit_id": str(_CONDUIT_ID),
        "surface_id": str(SYSTEM_HTTP_SURFACE_ID),
        "permitted_principal_ids": [str(_ALLOWED_PRINCIPAL)],
        "permitted_commands": ["RegisterActor"],
        "occurred_at": _NOW.isoformat(),
    }
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.event_id == _EVENT_ID
    assert stored.metadata == {"command": "DefinePolicy"}
    assert stored.occurred_at == _NOW


@pytest.mark.unit
async def test_handler_trims_policy_name_via_value_object() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_policy.bind(deps)

    await handler(
        _command(name="  Beam-team  "),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Policy", _NEW_ID)
    assert events[0].payload["name"] == "Beam-team"


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, deny=True)
    handler = define_policy.bind(deps)

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
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store, deny=True)
    handler = define_policy.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, version = await store.load("Policy", _NEW_ID)
    assert events == []
    assert version == 0


@pytest.mark.unit
async def test_handler_propagates_invalid_policy_name_error() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
    handler = define_policy.bind(deps)

    with pytest.raises(InvalidPolicyNameError):
        await handler(
            _command(name="   "),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_does_not_append_when_decider_rejects() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_policy.bind(deps)

    with pytest.raises(InvalidPolicyNameError):
        await handler(
            _command(name=""),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, version = await store.load("Policy", _NEW_ID)
    assert events == []
    assert version == 0


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_policy.bind(deps)

    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Policy", _NEW_ID)
    assert events[0].causation_id == causation


@pytest.mark.unit
def test_wire_trust_returns_handlers_bundle_with_define_policy() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
    handlers = wire_trust(deps)
    assert isinstance(handlers, TrustHandlers)
    assert callable(handlers.define_policy)
    # define_zone + define_conduit still wired (regression guard for 3a/3b)
    assert callable(handlers.define_zone)
    assert callable(handlers.define_conduit)


@pytest.mark.unit
async def test_wired_handler_propagates_causation_id_through_full_composition() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handlers = wire_trust(deps)

    await handlers.define_policy(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Policy", _NEW_ID)
    assert events[0].causation_id == causation
