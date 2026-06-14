"""Unit tests for the `evaluate_policy` query handler."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.ports import (
    Allow,
    Deny,
)
from cora.infrastructure.routing import SYSTEM_HTTP_SURFACE_ID
from cora.trust import TrustHandlers, UnauthorizedError, wire_trust
from cora.trust.aggregates.policy.events import (
    PolicyDefined,
    event_type_name,
    to_payload,
)
from cora.trust.features import evaluate_policy
from cora.trust.features.evaluate_policy import EvaluatePolicy
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_POLICY_ID = UUID("01900000-0000-7000-8000-000000000501")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CONDUIT_ID = UUID("01900000-0000-7000-8000-00000000aaaa")
_OTHER_CONDUIT = UUID("01900000-0000-7000-8000-00000000bbbb")
_ALLOWED_PRINCIPAL = UUID("01900000-0000-7000-8000-000000000a01")
_OTHER_PRINCIPAL = UUID("01900000-0000-7000-8000-000000000a02")
_SURFACE = SYSTEM_HTTP_SURFACE_ID
_OTHER_SURFACE = UUID("01900000-0000-7000-8000-00000000face")


async def _seed_policy(
    store: InMemoryEventStore,
    *,
    policy_id: UUID = _POLICY_ID,
    conduit_id: UUID = _CONDUIT_ID,
    principals: frozenset[UUID] = frozenset({_ALLOWED_PRINCIPAL}),
    commands: frozenset[str] = frozenset({"RegisterActor"}),
    surface_id: UUID = _SURFACE,
) -> None:
    """Seed the event store with a single PolicyDefined event.

    Bypasses define_policy so the test exercises only evaluate_policy's
    load-and-evaluate path (define_policy has its own unit tests). The
    policy binds the HTTP Surface so `evaluate` (strict surface match)
    can Allow a query carrying the same surface.
    """
    event = PolicyDefined(
        policy_id=policy_id,
        name="Test-policy",
        conduit_id=conduit_id,
        permitted_principal_ids=tuple(principals),
        permitted_commands=tuple(commands),
        occurred_at=_NOW,
        surface_id=surface_id,
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=event.occurred_at,
        event_id=uuid4(),
        command_name="DefinePolicy",
        correlation_id=uuid4(),
        principal_id=uuid4(),
    )
    await store.append("Policy", policy_id, expected_version=0, events=[new_event])


def _query(
    *,
    policy_id: UUID = _POLICY_ID,
    evaluated_principal_id: UUID = _ALLOWED_PRINCIPAL,
    evaluated_command_name: str = "RegisterActor",
    evaluated_conduit_id: UUID = _CONDUIT_ID,
    evaluated_surface_id: UUID = _SURFACE,
) -> EvaluatePolicy:
    return EvaluatePolicy(
        policy_id=policy_id,
        evaluated_principal_id=evaluated_principal_id,
        evaluated_command_name=evaluated_command_name,
        evaluated_conduit_id=evaluated_conduit_id,
        evaluated_surface_id=evaluated_surface_id,
    )


@pytest.mark.unit
async def test_handler_returns_none_when_policy_does_not_exist() -> None:
    """Missing policy → handler returns None (route layer maps to 404)."""
    deps = build_deps(ids=[uuid4() for _ in range(8)], now=_NOW)
    handler = evaluate_policy.bind(deps)

    result = await handler(
        _query(policy_id=uuid4()),  # nothing seeded for this id
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_returns_allow_when_subject_matches_policy() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[uuid4() for _ in range(8)], now=_NOW, event_store=store)
    await _seed_policy(store)
    handler = evaluate_policy.bind(deps)

    result = await handler(
        _query(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert isinstance(result, Allow)


@pytest.mark.unit
async def test_handler_returns_deny_when_principal_not_permitted() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[uuid4() for _ in range(8)], now=_NOW, event_store=store)
    await _seed_policy(store)
    handler = evaluate_policy.bind(deps)

    result = await handler(
        _query(evaluated_principal_id=_OTHER_PRINCIPAL),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert isinstance(result, Deny)
    assert "principal" in result.reason.lower()


@pytest.mark.unit
async def test_handler_returns_deny_when_command_not_permitted() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[uuid4() for _ in range(8)], now=_NOW, event_store=store)
    await _seed_policy(store)
    handler = evaluate_policy.bind(deps)

    result = await handler(
        _query(evaluated_command_name="DropDatabase"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert isinstance(result, Deny)
    assert "command" in result.reason.lower()


@pytest.mark.unit
async def test_handler_returns_deny_when_conduit_does_not_match() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[uuid4() for _ in range(8)], now=_NOW, event_store=store)
    await _seed_policy(store)
    handler = evaluate_policy.bind(deps)

    result = await handler(
        _query(evaluated_conduit_id=_OTHER_CONDUIT),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert isinstance(result, Deny)
    assert "conduit" in result.reason.lower()


@pytest.mark.unit
async def test_handler_returns_deny_when_surface_does_not_match() -> None:
    """Strict surface matching: the seeded policy binds the HTTP Surface,
    so a query carrying a different evaluated surface denies even when
    principal, command, and conduit all match."""
    store = InMemoryEventStore()
    deps = build_deps(ids=[uuid4() for _ in range(8)], now=_NOW, event_store=store)
    await _seed_policy(store)
    handler = evaluate_policy.bind(deps)

    result = await handler(
        _query(evaluated_surface_id=_OTHER_SURFACE),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert isinstance(result, Deny)
    assert "surface" in result.reason.lower()


@pytest.mark.unit
async def test_handler_raises_unauthorized_when_caller_authz_denies() -> None:
    """Caller-level authz denial raises UnauthorizedError BEFORE the
    Policy is loaded — the caller isn't allowed to even ask the
    question. Distinct from a Deny result, which IS a successful query
    that returned 'no'."""
    store = InMemoryEventStore()
    deps = build_deps(ids=[uuid4() for _ in range(8)], now=_NOW, event_store=store, deny=True)
    await _seed_policy(store)
    handler = evaluate_policy.bind(deps)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            _query(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_does_not_load_policy_when_caller_authz_denies() -> None:
    """If the caller can't ask, the handler should short-circuit before
    hitting the event store. The policy doesn't exist for this query's
    policy_id; under the no-deny path the handler would return None,
    but here it must raise UnauthorizedError instead."""
    deps = build_deps(ids=[uuid4() for _ in range(8)], now=_NOW, deny=True)  # no policy seeded
    handler = evaluate_policy.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            _query(policy_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_passes_subject_fields_through_to_evaluate() -> None:
    """Sanity check: the handler delegates query.subject_* fields to
    the pure evaluate function — not the caller's principal_id."""
    store = InMemoryEventStore()
    deps = build_deps(ids=[uuid4() for _ in range(8)], now=_NOW, event_store=store)
    await _seed_policy(store)
    handler = evaluate_policy.bind(deps)

    # Caller is _PRINCIPAL_ID (NOT in permitted set);
    # subject is _ALLOWED_PRINCIPAL (IS in permitted set).
    # Result must be Allow, proving the handler used evaluated_principal_id
    # not principal_id.
    result = await handler(
        _query(evaluated_principal_id=_ALLOWED_PRINCIPAL),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert isinstance(result, Allow)


@pytest.mark.unit
def test_wire_trust_returns_handlers_bundle_with_evaluate_policy() -> None:
    deps = build_deps(ids=[uuid4() for _ in range(8)], now=_NOW)
    handlers = wire_trust(deps)
    assert isinstance(handlers, TrustHandlers)
    assert callable(handlers.evaluate_policy)
    # All 3a/3b/3c slices still wired (regression guard)
    assert callable(handlers.define_zone)
    assert callable(handlers.define_conduit)
    assert callable(handlers.define_policy)


@pytest.mark.unit
async def test_wired_handler_evaluates_through_full_composition() -> None:
    """End-to-end check that evaluate_policy survives the `with_tracing` wrap in wire.py.

    No idempotency wrap on queries.
    """
    store = InMemoryEventStore()
    deps = build_deps(ids=[uuid4() for _ in range(8)], now=_NOW, event_store=store)
    await _seed_policy(store)
    handlers = wire_trust(deps)

    result = await handlers.evaluate_policy(
        _query(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert isinstance(result, Allow)
