"""Shared helpers for tests that exercise the real `TrustAuthorize` gate.

Before this module, the "seed a `PolicyDefined` then run real authz"
setup was copy-pasted as a per-file `_seed_policy` across the contract
and trust tiers (one near-identical 30-line copy in each of ~10 files).
This consolidates the event-building into one place. Two append shapes
exist because the tiers differ:

  - unit / integration: `await seed_policy(store, ...)` against a bare
    event store (the policy stream is appended directly).
  - contract: `seed_policy_into_app(app, ...)` (sync) against a running
    app's in-memory store, plus `trust_authorize_client(...)` which
    spins up `create_app()` with `TRUST_POLICY_ID` wired and seeds in
    one step, yielding the live `TestClient`.

The policy shape is CORA's flat allowlist: `permitted_principal_ids` x
`permitted_commands`, additionally gated by `conduit_id` + `surface_id`
(both strict-matched by `evaluate`). Contract calls arrive on
`SYSTEM_HTTP_SURFACE_ID`, so that is the contract default surface; the
unit `TrustAuthorize` tests use the nil surface, matching the
nil-sentinel a 3-arg `authorize(...)` passes. Handlers pass
`conduit_id = NIL_SENTINEL_ID` today, so the gating policy uses the same.

Keep new policy-seeding tests on these helpers rather than hand-rolling
another `_seed_policy`; that copy-paste is exactly what this replaces.
"""
# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false
# `app.state.deps.event_store` is typed `Any` by FastAPI's state
# machinery; the white-box seed accepts that and casts at use.

import asyncio
from collections.abc import Generator, Iterable
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.ports import EventStore, NewEvent
from cora.infrastructure.routing import NIL_SENTINEL_ID, SYSTEM_HTTP_SURFACE_ID
from cora.trust.aggregates.policy.events import (
    PolicyDefined,
    event_type_name,
    to_payload,
)

# A throwaway test policy id for callers that do not care about a
# specific value. Tests that assert on the id pass their own.
DEFAULT_TEST_POLICY_ID = UUID("01900000-0000-7000-8000-0000000000a0")


def make_policy_event(
    *,
    policy_id: UUID,
    permitted_principal_ids: Iterable[UUID],
    permitted_commands: Iterable[str],
    conduit_id: UUID = NIL_SENTINEL_ID,
    surface_id: UUID = NIL_SENTINEL_ID,
    name: str = "Test-policy",
    occurred_at: datetime | None = None,
) -> NewEvent:
    """Build one envelope-wrapped `PolicyDefined` for a permissive (or
    narrow) test policy. Shared by every tier; the tier-specific append
    is done by the callers below."""
    event = PolicyDefined(
        policy_id=policy_id,
        name=name,
        conduit_id=conduit_id,
        permitted_principal_ids=tuple(permitted_principal_ids),
        permitted_commands=tuple(permitted_commands),
        occurred_at=occurred_at if occurred_at is not None else datetime.now(tz=UTC),
        surface_id=surface_id,
    )
    return to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=event.occurred_at,
        event_id=uuid4(),
        command_name="DefinePolicy",
        correlation_id=uuid4(),
        principal_id=uuid4(),
    )


async def seed_policy(
    store: EventStore,
    *,
    policy_id: UUID,
    permitted_principal_ids: Iterable[UUID],
    permitted_commands: Iterable[str],
    conduit_id: UUID = NIL_SENTINEL_ID,
    surface_id: UUID = NIL_SENTINEL_ID,
    name: str = "Test-policy",
    occurred_at: datetime | None = None,
) -> None:
    """Append a `PolicyDefined` directly to a bare event store
    (unit / integration tiers)."""
    await store.append(
        "Policy",
        policy_id,
        expected_version=0,
        events=[
            make_policy_event(
                policy_id=policy_id,
                permitted_principal_ids=permitted_principal_ids,
                permitted_commands=permitted_commands,
                conduit_id=conduit_id,
                surface_id=surface_id,
                name=name,
                occurred_at=occurred_at,
            )
        ],
    )


def seed_policy_into_app(
    app: FastAPI,
    *,
    policy_id: UUID,
    permitted_principal_ids: Iterable[UUID],
    permitted_commands: Iterable[str],
    conduit_id: UUID = NIL_SENTINEL_ID,
    surface_id: UUID = SYSTEM_HTTP_SURFACE_ID,
    name: str = "Test-policy",
) -> None:
    """Seed a `PolicyDefined` into a running app's in-memory store
    (contract tier). Bypasses the API because `TrustAuthorize` is already
    gating every command at this point (the bootstrap chicken-and-egg
    documented in `TrustAuthorize`). Defaults the surface to
    `SYSTEM_HTTP_SURFACE_ID` so REST `TestClient` calls strict-match."""
    asyncio.run(
        app.state.deps.event_store.append(
            "Policy",
            policy_id,
            0,
            [
                make_policy_event(
                    policy_id=policy_id,
                    permitted_principal_ids=permitted_principal_ids,
                    permitted_commands=permitted_commands,
                    conduit_id=conduit_id,
                    surface_id=surface_id,
                    name=name,
                )
            ],
        )
    )


@contextmanager
def trust_authorize_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    permitted_principal_ids: Iterable[UUID],
    permitted_commands: Iterable[str],
    policy_id: UUID = DEFAULT_TEST_POLICY_ID,
    surface_id: UUID = SYSTEM_HTTP_SURFACE_ID,
) -> Generator[TestClient]:
    """Spin up `create_app()` with `TrustAuthorize` wired against a
    freshly seeded permissive policy, and yield the live `TestClient`.

    The seeded policy permits the given principals to issue the given
    commands; every other principal (including the `SYSTEM_PRINCIPAL_ID`
    fallback when no `X-Principal-Id` header is sent) gets Deny. Sets
    `APP_ENV=test` + `TRUST_POLICY_ID` before constructing the app.
    """
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("TRUST_POLICY_ID", str(policy_id))

    client = TestClient(create_app())
    client.__enter__()  # start lifespan; app.state.deps now populated
    try:
        seed_policy_into_app(
            cast("FastAPI", client.app),
            policy_id=policy_id,
            permitted_principal_ids=permitted_principal_ids,
            permitted_commands=permitted_commands,
            surface_id=surface_id,
        )
        yield client
    finally:
        client.__exit__(None, None, None)
