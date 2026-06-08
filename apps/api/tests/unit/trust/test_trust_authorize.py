"""Unit tests for the `TrustAuthorize` adapter.

Exercises the adapter against `InMemoryEventStore` with a seeded
PolicyDefined event. The adapter is the production path that gates
every cross-BC command through a single configured Policy.

Traversal observation emission: when the adapter is constructed with
a `TraversalStore`, every Allow / Deny decision writes one
ConduitTraversal observation row scoped to the target Conduit's
traversals logbook.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.ports import (
    Allow,
    Deny,
    FakeClock,
    FixedIdGenerator,
)
from cora.shared.logbook import LogbookFieldSpec, LogbookSchema
from cora.trust.aggregates.conduit import (
    LOGBOOK_KIND_TRAVERSALS,
    ConduitDefined,
    ConduitLogbookClosed,
    ConduitLogbookOpened,
)
from cora.trust.aggregates.conduit import (
    event_type_name as conduit_event_type_name,
)
from cora.trust.aggregates.conduit import (
    to_payload as conduit_to_payload,
)
from cora.trust.aggregates.conduit.entries import InMemoryTraversalStore
from cora.trust.aggregates.policy.events import (
    PolicyDefined,
    event_type_name,
    to_payload,
)
from cora.trust.authorize import TrustAuthorize

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_POLICY_ID = UUID("01900000-0000-7000-8000-000000000601")
# Post-3h: handlers pass `UUID(int=0)` (nil sentinel) as conduit_id by
# default; the gating policy must use the same conduit_id to match.
_CONDUIT_ID = UUID(int=0)
_OTHER_CONDUIT_ID = UUID("01900000-0000-7000-8000-00000000aaaa")
_ALLOWED_PRINCIPAL = UUID("01900000-0000-7000-8000-000000000a01")
_OTHER_PRINCIPAL = UUID("01900000-0000-7000-8000-000000000a02")


async def _seed_policy(
    store: InMemoryEventStore,
    *,
    policy_id: UUID = _POLICY_ID,
    conduit_id: UUID = _CONDUIT_ID,
    principals: frozenset[UUID] = frozenset({_ALLOWED_PRINCIPAL}),
    commands: frozenset[str] = frozenset({"RegisterActor"}),
) -> None:
    event = PolicyDefined(
        policy_id=policy_id,
        name="Test-policy",
        conduit_id=conduit_id,
        permitted_principal_ids=tuple(principals),
        permitted_commands=tuple(commands),
        occurred_at=_NOW,
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


@pytest.mark.unit
async def test_returns_allow_when_subject_matches_configured_policy() -> None:
    store = InMemoryEventStore()
    await _seed_policy(store)
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID)

    result = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", UUID(int=0))
    assert isinstance(result, Allow)


@pytest.mark.unit
async def test_returns_deny_when_principal_not_permitted() -> None:
    store = InMemoryEventStore()
    await _seed_policy(store)
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID)

    result = await authorize.authorize(_OTHER_PRINCIPAL, "RegisterActor", UUID(int=0))
    assert isinstance(result, Deny)
    assert "principal" in result.reason.lower()


@pytest.mark.unit
async def test_returns_deny_when_command_not_permitted() -> None:
    store = InMemoryEventStore()
    await _seed_policy(store)
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID)

    result = await authorize.authorize(_ALLOWED_PRINCIPAL, "DropDatabase", UUID(int=0))
    assert isinstance(result, Deny)
    assert "command" in result.reason.lower()


@pytest.mark.unit
async def test_returns_deny_when_configured_policy_does_not_exist() -> None:
    """Fail-closed: configured policy missing from event store → Deny.
    Pinned because a future change to permissive-on-missing would be a
    significant security regression and must be deliberate."""
    store = InMemoryEventStore()  # nothing seeded
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID)

    result = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", UUID(int=0))
    assert isinstance(result, Deny)
    assert "not found" in result.reason.lower()
    assert str(_POLICY_ID) in result.reason


@pytest.mark.unit
async def test_denies_when_caller_conduit_id_does_not_match_policy() -> None:
    """TrustAuthorize forwards the caller's conduit_id to `evaluate`.

    A policy bound to one conduit denies calls on another. Pinned
    because this is the whole point of 3h — without it the
    conduit_id parameter on the port shape would be cosmetic.
    (3g had it ignored; 3g's no-op test was replaced by this one.)
    """
    store = InMemoryEventStore()
    # Policy governs `_OTHER_CONDUIT_ID`, NOT the nil conduit handlers
    # currently pass.
    await _seed_policy(store, conduit_id=_OTHER_CONDUIT_ID)
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID)

    # Caller passes the nil conduit_id → mismatch → Deny even though
    # principal + command are permitted.
    denied_nil = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", UUID(int=0))
    assert isinstance(denied_nil, Deny)
    assert "conduit" in denied_nil.reason.lower()

    # Caller passes a third, unrelated conduit_id → also Deny.
    third_conduit = UUID("01900000-0000-7000-8000-00000000bbbb")
    denied_other = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", third_conduit)
    assert isinstance(denied_other, Deny)
    assert "conduit" in denied_other.reason.lower()

    # Caller passes the policy's own conduit_id → Allow (sanity check
    # that conduit-matching is what gates, not some other invariant).
    allowed = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", _OTHER_CONDUIT_ID)
    assert isinstance(allowed, Allow)


@pytest.mark.unit
async def test_loads_policy_on_each_call_no_caching() -> None:
    """Pin the no-caching contract for TrustAuthorize policy loads.

    Changing the policy in the store between calls is reflected on
    the very next call. (Future caching + LISTEN/NOTIFY invalidation
    would change this; should be a deliberate change.)

    Reseeding is awkward here (PolicyDefined is genesis-only); instead
    we verify the load happens by deleting the seeded event and
    showing the next call returns Deny rather than the previously-
    loaded Allow.
    """
    store = InMemoryEventStore()
    await _seed_policy(store)
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID)

    first = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", UUID(int=0))
    assert isinstance(first, Allow)

    # Drop the policy (white-box: InMemoryEventStore exposes its dict).
    store._streams.pop(("Policy", _POLICY_ID))  # type: ignore[attr-defined]  # pyright: ignore[reportUnknownMemberType]

    second = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", UUID(int=0))
    assert isinstance(second, Deny)
    assert "not found" in second.reason.lower()


# ---------- Traversal observation emission ----------


_OBS_EVENT_ID = UUID("01900000-0000-7000-8000-000000000711")
_OBS_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)
_TARGET_CONDUIT_ID = UUID("01900000-0000-7000-8000-000000000c01")
_TRAVERSALS_LOGBOOK_ID = UUID("01900000-0000-7000-8000-000000000c02")


async def _seed_conduit_with_open_traversals_logbook(
    store: InMemoryEventStore,
    *,
    conduit_id: UUID = _TARGET_CONDUIT_ID,
    logbook_id: UUID = _TRAVERSALS_LOGBOOK_ID,
) -> None:
    """Seed a Conduit + an open traversals logbook directly into the store."""
    defined = ConduitDefined(
        conduit_id=conduit_id,
        name="Test conduit",
        source_zone_id=uuid4(),
        target_zone_id=uuid4(),
        occurred_at=_OBS_NOW,
    )
    opened = ConduitLogbookOpened(
        conduit_id=conduit_id,
        logbook_id=logbook_id,
        kind=LOGBOOK_KIND_TRAVERSALS,
        schema=LogbookSchema(fields={"x": LogbookFieldSpec(type="string")}),
        occurred_at=_OBS_NOW,
    )
    new_events = [
        to_new_event(
            event_type=conduit_event_type_name(e),
            payload=conduit_to_payload(e),
            occurred_at=e.occurred_at,
            event_id=uuid4(),
            command_name="DefineConduit",
            correlation_id=uuid4(),
            principal_id=uuid4(),
        )
        for e in (defined, opened)
    ]
    await store.append("Conduit", conduit_id, expected_version=0, events=new_events)


@pytest.mark.unit
async def test_init_rejects_traversals_store_without_clock_and_id_generator() -> None:
    """Wiring guard: missing clock or id_generator surfaces at startup."""
    store = InMemoryEventStore()
    with pytest.raises(ValueError, match="requires both clock and id_generator"):
        TrustAuthorize(
            store,
            policy_id=_POLICY_ID,
            traversals_store=InMemoryTraversalStore(),
            # clock + id_generator deliberately omitted
        )


@pytest.mark.unit
async def test_skips_traversal_emission_when_traversals_store_is_unset() -> None:
    """Backward-compat: TrustAuthorize with no traversals_store works
    exactly like it did before the traversals store landed: pure authz, no side effects."""
    store = InMemoryEventStore()
    await _seed_policy(store)
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID)
    result = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", UUID(int=0))
    assert isinstance(result, Allow)


@pytest.mark.unit
async def test_emits_traversal_on_allow_when_conduit_has_open_logbook() -> None:
    store = InMemoryEventStore()
    await _seed_policy(store, conduit_id=_TARGET_CONDUIT_ID)
    await _seed_conduit_with_open_traversals_logbook(store)

    traversals = InMemoryTraversalStore()
    authorize = TrustAuthorize(
        store,
        policy_id=_POLICY_ID,
        traversals_store=traversals,
        clock=FakeClock(_OBS_NOW),
        id_generator=FixedIdGenerator([_OBS_EVENT_ID]),
    )

    result = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", _TARGET_CONDUIT_ID)
    assert isinstance(result, Allow)

    rows = traversals.all()
    assert len(rows) == 1
    row = rows[0]
    assert row.event_id == _OBS_EVENT_ID
    assert row.conduit_id == _TARGET_CONDUIT_ID
    assert row.logbook_id == _TRAVERSALS_LOGBOOK_ID
    assert row.actor_id == _ALLOWED_PRINCIPAL
    assert row.command_name == "RegisterActor"
    assert row.decision == "Allow"
    assert row.reason is None
    assert row.occurred_at == _OBS_NOW


@pytest.mark.unit
async def test_emits_traversal_on_deny_with_reason_attached() -> None:
    store = InMemoryEventStore()
    await _seed_policy(store, conduit_id=_TARGET_CONDUIT_ID)
    await _seed_conduit_with_open_traversals_logbook(store)

    traversals = InMemoryTraversalStore()
    authorize = TrustAuthorize(
        store,
        policy_id=_POLICY_ID,
        traversals_store=traversals,
        clock=FakeClock(_OBS_NOW),
        id_generator=FixedIdGenerator([_OBS_EVENT_ID]),
    )

    result = await authorize.authorize(_OTHER_PRINCIPAL, "RegisterActor", _TARGET_CONDUIT_ID)
    assert isinstance(result, Deny)

    rows = traversals.all()
    assert len(rows) == 1
    row = rows[0]
    assert row.decision == "Deny"
    assert row.reason is not None
    assert "principal" in row.reason.lower()


@pytest.mark.unit
async def test_skips_traversal_emission_when_conduit_does_not_exist() -> None:
    """Best-effort: missing Conduit logs a warning but doesn't fail
    the authz call. Today's handlers pass UUID(int=0) sentinel which
    has no Conduit aggregate behind it, so until conduit-routing
    lands, most commands won't have traversals emitted."""
    store = InMemoryEventStore()
    await _seed_policy(store)
    # No Conduit seeded.

    traversals = InMemoryTraversalStore()
    authorize = TrustAuthorize(
        store,
        policy_id=_POLICY_ID,
        traversals_store=traversals,
        clock=FakeClock(_OBS_NOW),
        id_generator=FixedIdGenerator([_OBS_EVENT_ID]),
    )

    result = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", UUID(int=0))
    assert isinstance(result, Allow)
    # No traversal recorded because the target Conduit doesn't exist.
    assert traversals.all() == []


@pytest.mark.unit
async def test_skips_traversal_when_traversals_logbook_was_closed() -> None:
    """If the traversals logbook has been closed, the logbook-id
    resolver returns None and emission is skipped."""
    store = InMemoryEventStore()
    await _seed_policy(store, conduit_id=_TARGET_CONDUIT_ID)
    await _seed_conduit_with_open_traversals_logbook(store)

    # Append a ConduitLogbookClosed for the same logbook.
    closed = ConduitLogbookClosed(
        conduit_id=_TARGET_CONDUIT_ID,
        logbook_id=_TRAVERSALS_LOGBOOK_ID,
        occurred_at=_OBS_NOW,
    )
    closed_envelope = to_new_event(
        event_type=conduit_event_type_name(closed),
        payload=conduit_to_payload(closed),
        occurred_at=closed.occurred_at,
        event_id=uuid4(),
        command_name="CloseConduitChannel",
        correlation_id=uuid4(),
        principal_id=uuid4(),
    )
    await store.append(
        "Conduit",
        _TARGET_CONDUIT_ID,
        expected_version=2,
        events=[closed_envelope],
    )

    traversals = InMemoryTraversalStore()
    authorize = TrustAuthorize(
        store,
        policy_id=_POLICY_ID,
        traversals_store=traversals,
        clock=FakeClock(_OBS_NOW),
        id_generator=FixedIdGenerator([_OBS_EVENT_ID]),
    )

    result = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", _TARGET_CONDUIT_ID)
    assert isinstance(result, Allow)
    assert traversals.all() == []
