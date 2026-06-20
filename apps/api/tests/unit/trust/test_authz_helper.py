"""Tests for the shared authz seed helper (`tests/_authz.py`).

The helper is test infrastructure, but it seeds real `PolicyDefined`
events and is relied on by ~10 contract/unit files, so a regression in
it would fail those obscurely. These pin the async `seed_policy` shape
directly against `TrustAuthorize`; the contract `trust_authorize_client`
shape is exercised by the refactored contract endpoint tests.
"""

from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.ports import Allow, Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID, SYSTEM_HTTP_SURFACE_ID
from cora.trust.authorize import TrustAuthorize
from tests._authz import seed_policy

_POLICY_ID = UUID("01900000-0000-7000-8000-0000000000c1")
_PRINCIPAL = UUID("01900000-0000-7000-8000-0000000000c2")


@pytest.mark.unit
async def test_seed_policy_allows_permitted_principal_and_command() -> None:
    store = InMemoryEventStore()
    await seed_policy(
        store,
        policy_id=_POLICY_ID,
        permitted_principal_ids={_PRINCIPAL},
        permitted_commands={"RegisterActor"},
    )
    authz = TrustAuthorize(store, policy_id=_POLICY_ID)

    result = await authz.authorize(_PRINCIPAL, "RegisterActor", UUID(int=0))
    assert isinstance(result, Allow)


@pytest.mark.unit
async def test_seed_policy_denies_unpermitted_principal() -> None:
    store = InMemoryEventStore()
    await seed_policy(
        store,
        policy_id=_POLICY_ID,
        permitted_principal_ids={_PRINCIPAL},
        permitted_commands={"RegisterActor"},
    )
    authz = TrustAuthorize(store, policy_id=_POLICY_ID)

    result = await authz.authorize(uuid4(), "RegisterActor", UUID(int=0))
    assert isinstance(result, Deny)


@pytest.mark.unit
async def test_seed_policy_denies_unpermitted_command() -> None:
    store = InMemoryEventStore()
    await seed_policy(
        store,
        policy_id=_POLICY_ID,
        permitted_principal_ids={_PRINCIPAL},
        permitted_commands={"RegisterActor"},
    )
    authz = TrustAuthorize(store, policy_id=_POLICY_ID)

    result = await authz.authorize(_PRINCIPAL, "DropDatabase", UUID(int=0))
    assert isinstance(result, Deny)


@pytest.mark.unit
async def test_seed_policy_surface_id_is_strict_matched() -> None:
    """A policy seeded on the HTTP surface allows a call arriving on that
    surface and denies one on the nil surface. Pins that the helper's
    surface_id is load-bearing: the contract default SYSTEM_HTTP_SURFACE_ID
    exists so REST calls strict-match, and a regression in it would
    otherwise surface only through the slower contract suite."""
    store = InMemoryEventStore()
    await seed_policy(
        store,
        policy_id=_POLICY_ID,
        permitted_principal_ids={_PRINCIPAL},
        permitted_commands={"RegisterActor"},
        surface_id=SYSTEM_HTTP_SURFACE_ID,
    )
    authz = TrustAuthorize(store, policy_id=_POLICY_ID)

    on_http = await authz.authorize(
        _PRINCIPAL, "RegisterActor", UUID(int=0), SYSTEM_HTTP_SURFACE_ID
    )
    assert isinstance(on_http, Allow)

    on_nil = await authz.authorize(_PRINCIPAL, "RegisterActor", UUID(int=0), NIL_SENTINEL_ID)
    assert isinstance(on_nil, Deny)
