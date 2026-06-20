"""Unit tests for the `list_permissions` query handler.

Confirms enumeration returns the sorted permitted command set when
principal + conduit are eligible, returns empty list when either
check fails, always sets `incomplete=False` at v1, and short-
circuits on caller-authz deny.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.ports import Allow, AuthzResult, Deny
from cora.trust import TrustHandlers, UnauthorizedError, wire_trust
from cora.trust.features import list_permissions
from cora.trust.features.list_permissions import ListPermissions
from tests._authz import seed_policy
from tests.unit._helpers import build_deps


class _AllowListPermissionsDenyOthers:
    """Authorize stub: allow `ListPermissions`, deny `ListPermissionsOfOthers`.

    Models the bootstrap policy's posture for gate-review F2: the
    on-behalf gate must fire when `evaluated_principal_id != caller`.
    """

    async def authorize(
        self,
        principal_id: UUID,
        command_name: str,
        conduit_id: UUID,
        surface_id: UUID = UUID(int=0),  # noqa: B008
    ) -> AuthzResult:
        _ = (principal_id, conduit_id)
        if command_name == "ListPermissionsOfOthers":
            return Deny(reason="on-behalf not permitted")
        return Allow()


_NOW = datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC)
_POLICY_ID = UUID("01900000-0000-7000-8000-000000000701")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CONDUIT_ID = UUID("01900000-0000-7000-8000-00000000aaaa")
_OTHER_CONDUIT = UUID("01900000-0000-7000-8000-00000000bbbb")
_ALLOWED_PRINCIPAL = UUID("01900000-0000-7000-8000-000000000a01")
_OTHER_PRINCIPAL = UUID("01900000-0000-7000-8000-000000000a02")


async def _seed_policy(
    store: InMemoryEventStore,
    *,
    policy_id: UUID = _POLICY_ID,
    conduit_id: UUID = _CONDUIT_ID,
    principals: frozenset[UUID] = frozenset({_ALLOWED_PRINCIPAL}),
    commands: frozenset[str] = frozenset({"RegisterActor", "DefinePolicy", "DefineZone"}),
) -> None:
    await seed_policy(
        store,
        policy_id=policy_id,
        permitted_principal_ids=principals,
        permitted_commands=commands,
        conduit_id=conduit_id,
        occurred_at=_NOW,
    )


def _query(
    *,
    policy_id: UUID = _POLICY_ID,
    evaluated_principal_id: UUID = _ALLOWED_PRINCIPAL,
    evaluated_conduit_id: UUID = _CONDUIT_ID,
) -> ListPermissions:
    return ListPermissions(
        policy_id=policy_id,
        evaluated_principal_id=evaluated_principal_id,
        evaluated_conduit_id=evaluated_conduit_id,
    )


@pytest.mark.unit
async def test_handler_returns_none_when_policy_does_not_exist() -> None:
    deps = build_deps(ids=[uuid4() for _ in range(8)], now=_NOW)
    handler = list_permissions.bind(deps)

    result = await handler(
        _query(policy_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_returns_sorted_commands_when_eligible() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[uuid4() for _ in range(8)], now=_NOW, event_store=store)
    await _seed_policy(store)
    handler = list_permissions.bind(deps)

    result = await handler(
        _query(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is not None
    # Sorted alphabetically
    assert result.permitted_commands == ["DefinePolicy", "DefineZone", "RegisterActor"]
    assert result.incomplete is False


@pytest.mark.unit
async def test_handler_returns_empty_list_when_principal_not_in_permitted_set() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[uuid4() for _ in range(8)], now=_NOW, event_store=store)
    await _seed_policy(store)
    handler = list_permissions.bind(deps)

    result = await handler(
        _query(evaluated_principal_id=_OTHER_PRINCIPAL),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is not None
    assert result.permitted_commands == []
    assert result.incomplete is False


@pytest.mark.unit
async def test_handler_returns_empty_list_when_conduit_does_not_match() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[uuid4() for _ in range(8)], now=_NOW, event_store=store)
    await _seed_policy(store)
    handler = list_permissions.bind(deps)

    result = await handler(
        _query(evaluated_conduit_id=_OTHER_CONDUIT),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is not None
    assert result.permitted_commands == []
    assert result.incomplete is False


@pytest.mark.unit
async def test_handler_returns_empty_list_when_both_checks_fail() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[uuid4() for _ in range(8)], now=_NOW, event_store=store)
    await _seed_policy(store)
    handler = list_permissions.bind(deps)

    result = await handler(
        _query(evaluated_principal_id=_OTHER_PRINCIPAL, evaluated_conduit_id=_OTHER_CONDUIT),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is not None
    assert result.permitted_commands == []


@pytest.mark.unit
async def test_incomplete_field_always_false_at_v1() -> None:
    """Anti-hook: `incomplete` is required from day 1 even though
    it's always False today. Future ABAC will flip it on for some
    inputs; tests should pin the v1 invariant explicitly."""
    store = InMemoryEventStore()
    deps = build_deps(ids=[uuid4() for _ in range(8)], now=_NOW, event_store=store)
    await _seed_policy(store)
    handler = list_permissions.bind(deps)

    # All branches: eligible, principal-mismatch, conduit-mismatch.
    for q in (
        _query(),
        _query(evaluated_principal_id=_OTHER_PRINCIPAL),
        _query(evaluated_conduit_id=_OTHER_CONDUIT),
    ):
        result = await handler(q, principal_id=_PRINCIPAL_ID, correlation_id=_CORRELATION_ID)
        assert result is not None
        assert result.incomplete is False


@pytest.mark.unit
async def test_handler_raises_unauthorized_when_caller_authz_denies() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[uuid4() for _ in range(8)], now=_NOW, event_store=store, deny=True)
    await _seed_policy(store)
    handler = list_permissions.bind(deps)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            _query(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_short_circuits_before_loading_when_authz_denies() -> None:
    deps = build_deps(ids=[uuid4() for _ in range(8)], now=_NOW, deny=True)
    handler = list_permissions.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            _query(policy_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_on_behalf_query_denied_when_caller_lacks_list_permissions_of_others() -> None:
    """Gate-review F2: when evaluated_principal_id != principal_id,
    the handler runs a SECOND authorize call against
    ListPermissionsOfOthers. Bootstrap-shaped authz allows
    ListPermissions but denies ListPermissionsOfOthers → on-behalf
    queries fail-closed."""
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[uuid4() for _ in range(8)],
        now=_NOW,
        event_store=store,
        authz=_AllowListPermissionsDenyOthers(),
    )
    await _seed_policy(store)
    handler = list_permissions.bind(deps)

    # Caller is _PRINCIPAL_ID; subject is _ALLOWED_PRINCIPAL (different).
    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            _query(evaluated_principal_id=_ALLOWED_PRINCIPAL),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert "on-behalf" in exc_info.value.reason.lower()


@pytest.mark.unit
async def test_self_query_allowed_even_when_list_permissions_of_others_denied() -> None:
    """Gate-review F2 inverse: self-queries (evaluated_principal_id ==
    caller) bypass the on-behalf gate. The slice remains useful for
    the most common case ('what can I do?') under the strictest
    policy posture."""
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[uuid4() for _ in range(8)],
        now=_NOW,
        event_store=store,
        authz=_AllowListPermissionsDenyOthers(),
    )
    await _seed_policy(store, principals=frozenset({_PRINCIPAL_ID}))
    handler = list_permissions.bind(deps)

    # Caller queries about themselves → no second gate fired.
    result = await handler(
        _query(evaluated_principal_id=_PRINCIPAL_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is not None
    assert "RegisterActor" in result.permitted_commands


@pytest.mark.unit
def test_wire_trust_includes_list_permissions() -> None:
    deps = build_deps(ids=[uuid4() for _ in range(8)], now=_NOW)
    handlers = wire_trust(deps)
    assert isinstance(handlers, TrustHandlers)
    assert callable(handlers.list_permissions)


@pytest.mark.unit
async def test_wired_handler_runs_through_full_composition() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[uuid4() for _ in range(8)], now=_NOW, event_store=store)
    await _seed_policy(store)
    handlers = wire_trust(deps)

    result = await handlers.list_permissions(
        _query(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is not None
    assert "RegisterActor" in result.permitted_commands
