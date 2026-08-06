"""EventStorePrincipalLivenessLookup resolves the three liveness values.

The adapter is the authorization gate's only view of `Actor.active`, so
each of the three values needs a test that reaches it through a real
Actor stream. `AlwaysLivePrincipalLivenessLookup` can only ever produce
`Active`, so a test wired to the stub would prove nothing about any of
the cases that matter.

The round trip at the end is the one that pins the pairing this adapter
exists for: an operator can switch a principal off AND back on, the same
way `suspend_agent` / `resume_agent` already work for an agent.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.access.adapters import EventStorePrincipalLivenessLookup
from cora.access.aggregates.actor import ActorKind
from cora.access.features import (
    deactivate_actor,
    forget_actor,
    reactivate_actor,
    register_actor,
)
from cora.access.features.deactivate_actor import DeactivateActor
from cora.access.features.forget_actor import ForgetActor
from cora.access.features.reactivate_actor import ReactivateActor
from cora.access.features.register_actor import RegisterActor
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import PrincipalLiveness
from tests.unit._helpers import build_deps, make_profile_store

_NOW = datetime(2026, 5, 9, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000000001")
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-0000000000e1")
_DEACTIVATE_EVENT_ID = UUID("01900000-0000-7000-8000-0000000000e2")
_REACTIVATE_EVENT_ID = UUID("01900000-0000-7000-8000-0000000000e3")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_UNKNOWN_ID = UUID("01900000-0000-7000-8000-0000000000ff")

_IDS = [_NEW_ID, _REGISTER_EVENT_ID, _DEACTIVATE_EVENT_ID, _REACTIVATE_EVENT_ID]


async def _register_actor(deps: Kernel) -> UUID:
    register = register_actor.bind(deps, profile_store=make_profile_store())
    return await register(
        RegisterActor(name="Doga"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _deactivate(deps: Kernel, actor_id: UUID) -> None:
    await deactivate_actor.bind(deps)(
        DeactivateActor(actor_id=actor_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.unit
async def test_registered_actor_resolves_active() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=_IDS, now=_NOW, event_store=store)
    actor_id = await _register_actor(deps)

    lookup = EventStorePrincipalLivenessLookup(store)

    assert await lookup.liveness_of(actor_id) is PrincipalLiveness.ACTIVE


@pytest.mark.unit
async def test_principal_with_no_stream_resolves_unregistered() -> None:
    """A missing stream means never registered, NOT a failed lookup.

    The gate needs these apart: the remedy for one is `register_actor`
    and for the other it is retrying the read, and collapsing them into
    a bare False would make a denial unactionable.
    """
    store = InMemoryEventStore()

    lookup = EventStorePrincipalLivenessLookup(store)

    assert await lookup.liveness_of(_UNKNOWN_ID) is PrincipalLiveness.UNREGISTERED


@pytest.mark.unit
async def test_deactivated_actor_resolves_deactivated() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=_IDS, now=_NOW, event_store=store)
    actor_id = await _register_actor(deps)
    await _deactivate(deps, actor_id)

    lookup = EventStorePrincipalLivenessLookup(store)

    assert await lookup.liveness_of(actor_id) is PrincipalLiveness.DEACTIVATED


@pytest.mark.unit
async def test_reactivated_actor_resolves_active_again() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=_IDS, now=_NOW, event_store=store)
    actor_id = await _register_actor(deps)
    await _deactivate(deps, actor_id)
    await reactivate_actor.bind(deps)(
        ReactivateActor(actor_id=actor_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    lookup = EventStorePrincipalLivenessLookup(store)

    assert await lookup.liveness_of(actor_id) is PrincipalLiveness.ACTIVE


@pytest.mark.unit
async def test_forgotten_profile_leaves_liveness_active() -> None:
    """PII erasure is not deactivation.

    `ActorProfileForgotten` scrubs the profile row and leaves aggregate
    state alone, so a forgotten actor stays permitted. Pinning it here
    keeps a future evolver change from silently turning an erasure
    request into a lockout, which would be a lockout nobody could
    diagnose because the two acts look unrelated.
    """
    store = InMemoryEventStore()
    deps = build_deps(ids=_IDS, now=_NOW, event_store=store)
    actor_id = await _register_actor(deps)
    await forget_actor.bind(deps)(
        ForgetActor(actor_id=actor_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    lookup = EventStorePrincipalLivenessLookup(store)

    assert await lookup.liveness_of(actor_id) is PrincipalLiveness.ACTIVE


@pytest.mark.unit
async def test_agent_kind_actor_resolves_active_like_a_human() -> None:
    """The claim the whole conjunct rests on, exercised rather than asserted.

    `Conjunct.LIVENESS` classifies EVERY_PRINCIPAL because `Agent.id ==
    Actor.id`: `define_agent` writes the agent's Actor in the same
    cross-BC transaction, so one `Actor.active` describes both kinds. If
    that co-write ever stopped, every agent would resolve UNREGISTERED
    and be denied the moment enforcement turned on, and no test that
    registers only humans would notice.

    Written through the Actor stream directly rather than through
    `define_agent`, because the Agent BC's genesis path is not importable
    from an Access unit test; what is pinned here is that the adapter
    treats an agent-kind Actor exactly as it treats a human one.
    """
    store = InMemoryEventStore()
    agent_actor_id = UUID("01900000-0000-7000-8000-0000000000a9")

    await store.append(
        stream_type="Actor",
        stream_id=agent_actor_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type="ActorRegisteredV2",
                payload={
                    "actor_id": str(agent_actor_id),
                    "occurred_at": _NOW.isoformat(),
                    "kind": ActorKind.AGENT.value,
                },
                occurred_at=_NOW,
                event_id=UUID("01900000-0000-7000-8000-0000000000f1"),
                command_name="DefineAgent",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )

    lookup = EventStorePrincipalLivenessLookup(store)

    assert await lookup.liveness_of(agent_actor_id) is PrincipalLiveness.ACTIVE
