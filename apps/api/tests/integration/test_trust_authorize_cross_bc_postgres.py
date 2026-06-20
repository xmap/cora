"""Integration test: TrustAuthorize gates handlers across BC boundaries.

Second verification pass of the post-handler-gate Trust integration.
The first pass proved TrustAuthorize gates handlers within Trust
itself. This file extends the proof across BC boundaries: a single
Trust policy gates Subject and Access commands, principal_id
propagates correctly under real authz, and per-BC `UnauthorizedError`
classes are raised at the right BC (the cross-BC log-distinguishability
convention).

Also pins the documented bootstrap workflow from
`cora/trust/authorize.py`'s docstring — the chicken-and-egg escape
hatch (start AllowAll → define policy → restart with TrustAuthorize)
is verified end-to-end so a future change that breaks it surfaces
here, not in production.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.access import UnauthorizedError as AccessUnauthorizedError
from cora.access import wire_access
from cora.access.features.deactivate_actor import DeactivateActor
from cora.access.features.register_actor import RegisterActor
from cora.infrastructure.adapters.postgres_event_store import PostgresEventStore
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import SYSTEM_HTTP_SURFACE_ID
from cora.subject import UnauthorizedError as SubjectUnauthorizedError
from cora.subject import wire_subject
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.register_subject import RegisterSubject
from cora.trust.authorize import TrustAuthorize
from cora.trust.features import define_policy
from cora.trust.features.define_policy import DefinePolicy
from tests._authz import seed_policy
from tests.integration._helpers import build_postgres_deps
from tests.unit.subject._helpers import seed_active_asset

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
# Post-3h: handlers pass nil conduit_id; gating policy matches.
_CONDUIT_ID = UUID(int=0)
_PERMITTED_PRINCIPAL = UUID("01900000-0000-7000-8000-00000000c0a1")
_OTHER_PRINCIPAL = UUID("01900000-0000-7000-8000-00000000c0a2")
_BOOTSTRAP_PRINCIPAL = UUID("01900000-0000-7000-8000-00000000c099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000000c0aa")


def _bootstrap_deps(db_pool: asyncpg.Pool, *, ids: list[UUID]) -> Kernel:
    return build_postgres_deps(db_pool, now=_NOW, ids=ids)


def _gated_deps(db_pool: asyncpg.Pool, *, policy_id: UUID, ids: list[UUID]) -> Kernel:
    event_store = PostgresEventStore(db_pool)
    return build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=ids,
        authz=TrustAuthorize(event_store, policy_id=policy_id),
        event_store=event_store,
    )


async def _seed_policy(
    db_pool: asyncpg.Pool,
    *,
    policy_id: UUID,
    permitted_commands: frozenset[str],
    name: str,
) -> None:
    """Helper: seed a Trust policy directly into the event store.

    Delegates to the shared `seed_policy` helper, preserving the
    file's permitted principal, conduit, surface, and timestamp so the
    gated handlers (which call on `SYSTEM_HTTP_SURFACE_ID`) strict-match.
    """
    await seed_policy(
        PostgresEventStore(db_pool),
        policy_id=policy_id,
        permitted_principal_ids=frozenset({_PERMITTED_PRINCIPAL}),
        permitted_commands=permitted_commands,
        conduit_id=_CONDUIT_ID,
        surface_id=SYSTEM_HTTP_SURFACE_ID,
        name=name,
        occurred_at=_NOW,
    )


# ---------- Cross-BC: Trust policy gates Subject handler ----------


@pytest.mark.integration
async def test_trust_policy_gates_subject_register_for_permitted_principal(
    db_pool: asyncpg.Pool,
) -> None:
    """A Trust policy permitting RegisterSubject lets the permitted
    principal create subjects through the wire_subject chain. Pinned
    because cross-BC gating is the whole point of having Trust as a
    separate BC: a single Policy aggregate must gate commands across
    every BC's wire chain identically."""
    policy_id = UUID("01900000-0000-7000-8000-0000000bb101")
    subject_id = UUID("01900000-0000-7000-8000-0000000bb102")
    register_event_id = UUID("01900000-0000-7000-8000-0000000bb1e2")

    await _seed_policy(
        db_pool,
        policy_id=policy_id,
        permitted_commands=frozenset({"RegisterSubject"}),
        name="GateB-PermitRegisterSubject",
    )

    gated = _gated_deps(db_pool, policy_id=policy_id, ids=[subject_id, register_event_id])
    handlers = wire_subject(gated)

    result = await handlers.register_subject(
        RegisterSubject(name="GateB-AllowedSubject"),
        principal_id=_PERMITTED_PRINCIPAL,
        correlation_id=_CORRELATION_ID,
        surface_id=SYSTEM_HTTP_SURFACE_ID,
    )
    assert result == subject_id


@pytest.mark.integration
async def test_trust_policy_gates_subject_register_denies_other_principal(
    db_pool: asyncpg.Pool,
) -> None:
    """Non-permitted principal calling register_subject under TrustAuthorize
    raises Subject's `UnauthorizedError` (not Trust's or Access's). Pins
    the per-BC distinct-class convention end-to-end: each BC's handler
    chain raises its own application-error class so log filters /
    aggregator queries can distinguish 403s by source BC."""
    policy_id = UUID("01900000-0000-7000-8000-0000000bb201")
    spare_a = UUID("01900000-0000-7000-8000-0000000bb202")
    spare_b = UUID("01900000-0000-7000-8000-0000000bb2e2")

    await _seed_policy(
        db_pool,
        policy_id=policy_id,
        permitted_commands=frozenset({"RegisterSubject"}),
        name="GateB-DenyOtherForSubject",
    )

    gated = _gated_deps(db_pool, policy_id=policy_id, ids=[spare_a, spare_b])
    handlers = wire_subject(gated)

    with pytest.raises(SubjectUnauthorizedError) as exc_info:
        await handlers.register_subject(
            RegisterSubject(name="GateB-DeniedSubject"),
            principal_id=_OTHER_PRINCIPAL,
            correlation_id=_CORRELATION_ID,
            # Matching surface so the deny is on principal, not surface.
            surface_id=SYSTEM_HTTP_SURFACE_ID,
        )
    assert str(_OTHER_PRINCIPAL) in exc_info.value.reason


@pytest.mark.integration
async def test_trust_policy_gates_subject_update_style_command(
    db_pool: asyncpg.Pool,
) -> None:
    """Update-style commands (via
    make_subject_update_handler) must also gate through TrustAuthorize.
    Pinned because the factory wraps a different IO loop than create-
    style handlers, and the authz call site lives inside that loop —
    a refactor that drops the call would break authz silently."""
    # Setup: define a policy permitting both RegisterSubject and MountSubject.
    policy_id = UUID("01900000-0000-7000-8000-0000000bb301")
    subject_id = UUID("01900000-0000-7000-8000-0000000bb302")
    register_event_id = UUID("01900000-0000-7000-8000-0000000bb3e2")
    mount_event_id = UUID("01900000-0000-7000-8000-0000000bb3e3")

    await _seed_policy(
        db_pool,
        policy_id=policy_id,
        permitted_commands=frozenset({"RegisterSubject", "MountSubject"}),
        name="GateB-PermitRegisterAndMount",
    )

    gated = _gated_deps(
        db_pool,
        policy_id=policy_id,
        ids=[subject_id, register_event_id, mount_event_id],
    )
    handlers = wire_subject(gated)

    # Register first (also exercises gating on a create-style command).
    await handlers.register_subject(
        RegisterSubject(name="GateB-MountTarget"),
        principal_id=_PERMITTED_PRINCIPAL,
        correlation_id=_CORRELATION_ID,
        surface_id=SYSTEM_HTTP_SURFACE_ID,
    )

    # Now mount under TrustAuthorize via the make_subject_update_handler chain.
    asset_id = await seed_active_asset(gated.event_store, now=_NOW, correlation_id=_CORRELATION_ID)
    await handlers.mount_subject(
        MountSubject(subject_id=subject_id, asset_id=asset_id, reason=""),
        principal_id=_PERMITTED_PRINCIPAL,
        correlation_id=_CORRELATION_ID,
        surface_id=SYSTEM_HTTP_SURFACE_ID,
    )

    # Other principal cannot mount even though they could try.
    other_subject_id = UUID("01900000-0000-7000-8000-0000000bb303")
    other_register_event_id = UUID("01900000-0000-7000-8000-0000000bb3e4")
    other_mount_event_id = UUID("01900000-0000-7000-8000-0000000bb3e5")
    other_gated = _gated_deps(
        db_pool,
        policy_id=policy_id,
        ids=[other_subject_id, other_register_event_id, other_mount_event_id],
    )
    other_handlers = wire_subject(other_gated)

    # First register that subject (under permitted principal so the
    # subject exists for the mount denial check).
    await other_handlers.register_subject(
        RegisterSubject(name="GateB-OtherMountTarget"),
        principal_id=_PERMITTED_PRINCIPAL,
        correlation_id=_CORRELATION_ID,
        surface_id=SYSTEM_HTTP_SURFACE_ID,
    )

    with pytest.raises(SubjectUnauthorizedError):
        await other_handlers.mount_subject(
            MountSubject(subject_id=other_subject_id, asset_id=asset_id, reason=""),
            principal_id=_OTHER_PRINCIPAL,
            correlation_id=_CORRELATION_ID,
            # Matching surface so the deny is on principal, not surface.
            surface_id=SYSTEM_HTTP_SURFACE_ID,
        )


# ---------- Cross-BC: Trust policy gates Access handler ----------


@pytest.mark.integration
async def test_trust_policy_gates_access_handler_with_distinct_error_class(
    db_pool: asyncpg.Pool,
) -> None:
    """Access handler raises Access's `UnauthorizedError` (not Subject's
    or Trust's). Same distinct-class convention as the Subject test
    above, but for Access — confirming the convention holds across
    BCs even when they share the same cross-BC `Authorize` adapter."""
    policy_id = UUID("01900000-0000-7000-8000-0000000bb401")
    actor_id = UUID("01900000-0000-7000-8000-0000000bb402")
    register_event_id = UUID("01900000-0000-7000-8000-0000000bb4e2")
    spare_event_id = UUID("01900000-0000-7000-8000-0000000bb4e3")

    # Permit RegisterActor only (so DeactivateActor will be denied).
    await _seed_policy(
        db_pool,
        policy_id=policy_id,
        permitted_commands=frozenset({"RegisterActor"}),
        name="GateB-PermitRegisterActorOnly",
    )

    gated = _gated_deps(
        db_pool,
        policy_id=policy_id,
        ids=[actor_id, register_event_id, spare_event_id],
    )
    handlers = wire_access(gated)

    # Permitted principal can register an actor.
    await handlers.register_actor(
        RegisterActor(name="GateB-PermittedActor"),
        principal_id=_PERMITTED_PRINCIPAL,
        correlation_id=_CORRELATION_ID,
        surface_id=SYSTEM_HTTP_SURFACE_ID,
    )

    # But cannot deactivate (DeactivateActor not in permitted_commands) —
    # raises ACCESS's UnauthorizedError, not Subject's.
    with pytest.raises(AccessUnauthorizedError) as exc_info:
        await handlers.deactivate_actor(
            DeactivateActor(actor_id=actor_id),
            principal_id=_PERMITTED_PRINCIPAL,
            correlation_id=_CORRELATION_ID,
            # Matching surface so the deny is on command, not surface.
            surface_id=SYSTEM_HTTP_SURFACE_ID,
        )
    assert "DeactivateActor" in exc_info.value.reason

    # Cross-check: the raised class is NOT Subject's UnauthorizedError.
    # (Both have identical shape but distinct identity per the cross-BC
    # log-distinguishability convention.)
    assert not isinstance(exc_info.value, SubjectUnauthorizedError)


# ---------- Bootstrap workflow ----------


@pytest.mark.integration
async def test_documented_bootstrap_workflow_produces_working_authz(
    db_pool: asyncpg.Pool,
) -> None:
    """Pin the bootstrap workflow documented in `cora/trust/authorize.py`.

    The documented sequence:

        1. Start with `trust_policy_id` unset (AllowAllAuthorize).
        2. Define a permissive policy via the API; record the id.
        3. Restart with `trust_policy_id` = that id.

    This test walks through every step against real Postgres to prove
    the documented escape hatch from the chicken-and-egg actually
    works. Without this the docstring would be unverified guidance —
    a future change that broke it (for example removing AllowAllAuthorize
    as the default, or changing how Settings selects the adapter)
    would only surface in production.
    """
    policy_id = UUID("01900000-0000-7000-8000-0000000bb501")
    policy_event_id = UUID("01900000-0000-7000-8000-0000000bb5e1")
    subject_id_step3 = UUID("01900000-0000-7000-8000-0000000bb502")
    register_event_id_step3 = UUID("01900000-0000-7000-8000-0000000bb5e2")

    # Step 1: Start with AllowAllAuthorize. Confirm a wide-open
    # define_policy call succeeds — without this escape hatch you
    # could never bootstrap.
    bootstrap = _bootstrap_deps(db_pool, ids=[policy_id, policy_event_id])
    returned_policy_id = await define_policy.bind(bootstrap)(
        DefinePolicy(
            name="GateB-BootstrapPolicy",
            conduit_id=_CONDUIT_ID,
            # Permissive enough to keep working post-restart.
            permitted_principal_ids=frozenset({_PERMITTED_PRINCIPAL}),
            permitted_commands=frozenset({"RegisterSubject"}),
            surface_id=SYSTEM_HTTP_SURFACE_ID,
        ),
        principal_id=_BOOTSTRAP_PRINCIPAL,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_policy_id == policy_id

    # Step 2 (operator step): records the policy_id and updates env.
    # Simulated here by passing the id into the next deps build.

    # Step 3: "Restart" with TrustAuthorize wired against the
    # bootstrap policy. The authz adapter loads from the SAME
    # event store the bootstrap step wrote to (hard contract: the
    # workflow assumes one event store across the restart).
    restarted = _gated_deps(
        db_pool,
        policy_id=policy_id,
        ids=[subject_id_step3, register_event_id_step3],
    )
    handlers = wire_subject(restarted)

    # Permitted principal can now operate under TrustAuthorize.
    result = await handlers.register_subject(
        RegisterSubject(name="GateB-PostBootstrapSubject"),
        principal_id=_PERMITTED_PRINCIPAL,
        correlation_id=_CORRELATION_ID,
        surface_id=SYSTEM_HTTP_SURFACE_ID,
    )
    assert result == subject_id_step3
