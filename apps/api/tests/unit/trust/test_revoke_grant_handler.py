"""Application-handler unit tests for the `revoke_grant` slice.

Pins the handler-level concerns: authz invocation, event-store append at the
loaded version, the silently-idempotent noop path (revoking an absent principal
appends nothing), and PolicyNotFoundError on a missing Policy stream. Pure-
decider behavior is exercised in `policy/test_revoke_grant_decider.py` +
`test_revoke_grant_decider_properties.py`.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.trust import UnauthorizedError
from cora.trust.aggregates.policy import (
    PolicyDefined,
    PolicyNotFoundError,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.trust.features import revoke_grant
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 5, 27, 12, 0, 0, tzinfo=UTC)
_POLICY_ID = UUID("01900000-0000-7000-8000-00000000f001")
_CONDUIT_ID = UUID("01900000-0000-7000-8000-00000000f002")
_SURFACE_ID = UUID("01900000-0000-7000-8000-00000000f003")
_PRINCIPAL_IN = UUID("01900000-0000-7000-8000-00000000f0a1")
_PRINCIPAL_ABSENT = UUID("01900000-0000-7000-8000-00000000f0a2")
_INVOKER = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_EVENT_ID = UUID("01900000-0000-7000-8000-00000000f101")


async def _seed_policy(store: InMemoryEventStore) -> None:
    """Append a PolicyDefined at version 0 so the stream folds to a real Policy."""
    event = PolicyDefined(
        policy_id=_POLICY_ID,
        name="Beam-team",
        conduit_id=_CONDUIT_ID,
        permitted_principal_ids=(_PRINCIPAL_IN,),
        permitted_commands=("RegisterActor",),
        occurred_at=_NOW,
        surface_id=_SURFACE_ID,
    )
    await store.append(
        stream_type="Policy",
        stream_id=_POLICY_ID,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.occurred_at,
                event_id=UUID(int=1),
                command_name="DefinePolicy",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_INVOKER,
            )
        ],
    )


@pytest.mark.unit
async def test_revoke_grant_handler_appends_grant_revoked() -> None:
    store = InMemoryEventStore()
    await _seed_policy(store)
    deps = build_deps(ids=[_EVENT_ID], now=_NOW, event_store=store)
    handler = revoke_grant.bind(deps)

    await handler(
        revoke_grant.RevokePolicyGrant(
            policy_id=_POLICY_ID, permitted_principal_id=_PRINCIPAL_IN, reason="access review"
        ),
        principal_id=_INVOKER,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Policy", _POLICY_ID)
    assert version == 2
    assert events[-1].event_type == "PolicyGrantRevoked"
    assert events[-1].payload["principal_id"] == str(_PRINCIPAL_IN)
    assert events[-1].payload["revoked_by"] == str(_INVOKER)
    assert events[-1].payload["reason"] == "access review"
    folded = fold([from_stored(s) for s in events])
    assert folded is not None
    assert _PRINCIPAL_IN not in folded.permitted_principal_ids


@pytest.mark.unit
async def test_revoke_grant_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_policy(store)
    deps = build_deps(ids=[_EVENT_ID], now=_NOW, event_store=store, deny=True)
    handler = revoke_grant.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            revoke_grant.RevokePolicyGrant(
                policy_id=_POLICY_ID, permitted_principal_id=_PRINCIPAL_IN, reason="access review"
            ),
            principal_id=_INVOKER,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_revoke_grant_handler_noop_appends_nothing_for_absent_principal() -> None:
    store = InMemoryEventStore()
    await _seed_policy(store)
    deps = build_deps(ids=[_EVENT_ID], now=_NOW, event_store=store)
    handler = revoke_grant.bind(deps)

    await handler(
        revoke_grant.RevokePolicyGrant(
            policy_id=_POLICY_ID, permitted_principal_id=_PRINCIPAL_ABSENT, reason="access review"
        ),
        principal_id=_INVOKER,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Policy", _POLICY_ID)
    assert version == 1
    assert not any(e.event_type == "PolicyGrantRevoked" for e in events)


@pytest.mark.unit
async def test_revoke_grant_handler_raises_not_found_when_policy_absent() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_EVENT_ID], now=_NOW, event_store=store)
    handler = revoke_grant.bind(deps)

    with pytest.raises(PolicyNotFoundError):
        await handler(
            revoke_grant.RevokePolicyGrant(
                policy_id=_POLICY_ID, permitted_principal_id=_PRINCIPAL_IN, reason="access review"
            ),
            principal_id=_INVOKER,
            correlation_id=_CORRELATION_ID,
        )
