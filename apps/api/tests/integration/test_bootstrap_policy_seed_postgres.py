"""Integration tests for the System Bootstrap Policy seed.

Covers the bootstrap authz-gap-fill: the seed migration
`20260519200000_seed_default_surfaces_and_v2_policy.sql` ships a Policy
aggregate with the well-known UUID `SYSTEM_BOOTSTRAP_POLICY_ID` that
permits `{DefinePolicy, RegisterActor}` for `SYSTEM_PRINCIPAL_ID` on the
nil conduit, bound to the seeded HTTP Surface. Production deployments
set `TRUST_POLICY_ID` to this UUID to collapse the 3-step bootstrap
dance into a 1-step env-var set.

The bootstrap policy strict-matches its bound Surface: every
authorize / evaluate call against it must present
`surface_id=SYSTEM_HTTP_SURFACE_ID` (the seeded HTTP Surface) to Allow.
The retired nil-surface policy (...0001) stays in the event log forever
(forward-only migrations) but is operationally inert: its nil-as-wildcard
evaluate fold was removed, so it strict-denies every real-surface call.

Design lock: `memory/project_bootstrap_policy_design.md` +
`memory/project_conduit_injection_design.md`.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.infrastructure.adapters.postgres_event_store import PostgresEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.ports import Allow, Deny
from cora.infrastructure.ports.event_store import ConcurrencyError
from cora.infrastructure.routing import SYSTEM_HTTP_SURFACE_ID, SYSTEM_PRINCIPAL_ID
from cora.trust._bootstrap import SYSTEM_BOOTSTRAP_POLICY_ID
from cora.trust.aggregates.policy.events import (
    PolicyDefined,
    event_type_name,
    to_payload,
)
from cora.trust.aggregates.policy.read import load_policy
from cora.trust.aggregates.policy.state import evaluate
from cora.trust.authorize import TrustAuthorize
from cora.trust.features import define_policy
from cora.trust.features.define_policy import DefinePolicy
from tests.integration._helpers import build_postgres_deps

_NIL_CONDUIT = UUID(int=0)
_NOW = datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC)


@pytest.mark.integration
async def test_bootstrap_policy_stream_exists_with_expected_payload(
    db_pool: asyncpg.Pool,
) -> None:
    """Raw-SQL check: the migration appended one PolicyDefined row with
    the locked payload shape (bound to the HTTP Surface; sorted
    permitted_principal_ids + sorted permitted_commands per
    `to_payload`)."""
    rows = await db_pool.fetch(
        """
        SELECT event_type, payload, metadata, principal_id, version
        FROM events
        WHERE stream_type = 'Policy' AND stream_id = $1
        ORDER BY version
        """,
        SYSTEM_BOOTSTRAP_POLICY_ID,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["event_type"] == "PolicyDefined"
    assert row["version"] == 1
    assert row["principal_id"] == SYSTEM_PRINCIPAL_ID

    # asyncpg returns jsonb as either str or already-decoded dict depending
    # on codec config; handle both for robustness.
    payload_raw = row["payload"]
    payload = json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw
    assert payload == {
        "policy_id": str(SYSTEM_BOOTSTRAP_POLICY_ID),
        "name": "System Bootstrap Policy V2",
        "conduit_id": str(_NIL_CONDUIT),
        "surface_id": str(SYSTEM_HTTP_SURFACE_ID),
        "permitted_principal_ids": [str(SYSTEM_PRINCIPAL_ID)],
        "permitted_commands": ["DefinePolicy", "RegisterActor"],
        "occurred_at": "2026-05-19T00:00:00+00:00",
    }

    metadata_raw = row["metadata"]
    metadata = json.loads(metadata_raw) if isinstance(metadata_raw, str) else metadata_raw
    assert metadata == {"command": "SystemBootstrap"}


@pytest.mark.integration
async def test_bootstrap_policy_folds_and_evaluates_correctly(
    db_pool: asyncpg.Pool,
) -> None:
    """The seeded event must fold cleanly via `load_policy` (no
    `from_stored` errors) and `evaluate` must return Allow / Deny
    consistently with the locked permitted-set. Allow requires the
    bound HTTP Surface; a mismatched surface strict-denies."""
    event_store = PostgresEventStore(db_pool)
    policy = await load_policy(event_store, SYSTEM_BOOTSTRAP_POLICY_ID)

    assert policy is not None
    assert policy.id == SYSTEM_BOOTSTRAP_POLICY_ID
    assert policy.conduit_id == _NIL_CONDUIT
    assert policy.surface_id == SYSTEM_HTTP_SURFACE_ID
    assert policy.permitted_principal_ids == frozenset({SYSTEM_PRINCIPAL_ID})
    assert policy.permitted_commands == frozenset({"DefinePolicy", "RegisterActor"})

    # Allow on the two permitted commands (with the bound HTTP surface).
    for command in ("DefinePolicy", "RegisterActor"):
        result = evaluate(
            policy,
            principal_id=SYSTEM_PRINCIPAL_ID,
            command_name=command,
            conduit_id=_NIL_CONDUIT,
            surface_id=SYSTEM_HTTP_SURFACE_ID,
        )
        assert isinstance(result, Allow), f"expected Allow for {command}, got {result!r}"

    # Deny on an unpermitted command.
    deny_command = evaluate(
        policy,
        principal_id=SYSTEM_PRINCIPAL_ID,
        command_name="DefineZone",
        conduit_id=_NIL_CONDUIT,
        surface_id=SYSTEM_HTTP_SURFACE_ID,
    )
    assert isinstance(deny_command, Deny)

    # Deny on an unpermitted principal.
    other_principal = UUID("01900000-0000-7000-8000-00000000beef")
    deny_principal = evaluate(
        policy,
        principal_id=other_principal,
        command_name="DefinePolicy",
        conduit_id=_NIL_CONDUIT,
        surface_id=SYSTEM_HTTP_SURFACE_ID,
    )
    assert isinstance(deny_principal, Deny)

    # Deny on a non-nil conduit.
    other_conduit = UUID("01900000-0000-7000-8000-00000000cafe")
    deny_conduit = evaluate(
        policy,
        principal_id=SYSTEM_PRINCIPAL_ID,
        command_name="DefinePolicy",
        conduit_id=other_conduit,
        surface_id=SYSTEM_HTTP_SURFACE_ID,
    )
    assert isinstance(deny_conduit, Deny)

    # Deny on a mismatched surface (strict surface matching).
    other_surface = UUID("01900000-0000-7000-8000-00000000face")
    deny_surface = evaluate(
        policy,
        principal_id=SYSTEM_PRINCIPAL_ID,
        command_name="DefinePolicy",
        conduit_id=_NIL_CONDUIT,
        surface_id=other_surface,
    )
    assert isinstance(deny_surface, Deny)
    assert "surface" in deny_surface.reason.lower()


@pytest.mark.integration
async def test_trust_authorize_against_bootstrap_policy_permits_define_policy(
    db_pool: asyncpg.Pool,
) -> None:
    """End-to-end: TrustAuthorize wired against the bootstrap policy
    permits SYSTEM_PRINCIPAL_ID to call DefinePolicy through the real
    handler. This proves the 1-step bootstrap (env var only) works.
    The call must present the bound HTTP Surface to Allow."""
    event_store = PostgresEventStore(db_pool)
    authorize = TrustAuthorize(event_store, policy_id=SYSTEM_BOOTSTRAP_POLICY_ID)

    # The two permitted commands authorize Allow (on the bound surface).
    for command in ("DefinePolicy", "RegisterActor"):
        result = await authorize.authorize(
            SYSTEM_PRINCIPAL_ID,
            command,
            _NIL_CONDUIT,
            surface_id=SYSTEM_HTTP_SURFACE_ID,
        )
        assert isinstance(result, Allow), f"expected Allow for {command}, got {result!r}"

    # An unpermitted command Denies (this is the scope-creep guardrail).
    denied = await authorize.authorize(
        SYSTEM_PRINCIPAL_ID,
        "DefineZone",
        _NIL_CONDUIT,
        surface_id=SYSTEM_HTTP_SURFACE_ID,
    )
    assert isinstance(denied, Deny)


@pytest.mark.integration
async def test_trust_authorize_against_bootstrap_policy_denies_mismatched_surface(
    db_pool: asyncpg.Pool,
) -> None:
    """The bootstrap policy strict-matches its bound HTTP Surface: a
    call arriving on a different surface is denied even for the
    permitted principal + command."""
    event_store = PostgresEventStore(db_pool)
    authorize = TrustAuthorize(event_store, policy_id=SYSTEM_BOOTSTRAP_POLICY_ID)

    other_surface = UUID("01900000-0000-7000-8000-00000000face")
    result = await authorize.authorize(
        SYSTEM_PRINCIPAL_ID,
        "DefinePolicy",
        _NIL_CONDUIT,
        surface_id=other_surface,
    )
    assert isinstance(result, Deny)
    assert "surface" in result.reason.lower()


@pytest.mark.integration
async def test_bootstrap_policy_can_define_a_real_policy_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """The whole point of the bootstrap seed: a fresh deployment can
    immediately define a real admin Policy without the 3-step dance.
    We simulate that here, gating define_policy through
    TrustAuthorize-against-seed, then writing a new Policy as
    SYSTEM_PRINCIPAL_ID."""
    event_store = PostgresEventStore(db_pool)
    authorize = TrustAuthorize(event_store, policy_id=SYSTEM_BOOTSTRAP_POLICY_ID)

    new_policy_id = UUID("01900000-0000-7000-8000-000000000b01")
    new_event_id = UUID("01900000-0000-7000-8000-000000000b02")
    correlation_id = UUID("01900000-0000-7000-8000-000000000b03")
    admin_principal = UUID("01900000-0000-7000-8000-000000000b04")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[new_policy_id, new_event_id],
        event_store=event_store,
        authz=authorize,
    )

    # Under the bootstrap policy, SYSTEM_PRINCIPAL_ID is the only
    # principal allowed to call DefinePolicy. This succeeds when the
    # call arrives on the bound HTTP Surface.
    returned_id = await define_policy.bind(deps)(
        DefinePolicy(
            name="Real Admin Policy",
            conduit_id=_NIL_CONDUIT,
            permitted_principal_ids=frozenset({admin_principal}),
            permitted_commands=frozenset({"DefinePolicy", "RegisterActor", "DefineZone"}),
            surface_id=SYSTEM_HTTP_SURFACE_ID,
        ),
        principal_id=SYSTEM_PRINCIPAL_ID,
        correlation_id=correlation_id,
        surface_id=SYSTEM_HTTP_SURFACE_ID,
    )
    assert returned_id == new_policy_id

    # The new policy is loadable and has the expected shape.
    loaded = await load_policy(event_store, new_policy_id)
    assert loaded is not None
    assert loaded.name.value == "Real Admin Policy"
    assert loaded.permitted_principal_ids == frozenset({admin_principal})
    assert loaded.surface_id == SYSTEM_HTTP_SURFACE_ID


@pytest.mark.integration
async def test_bootstrap_policy_denies_non_system_principal(
    db_pool: asyncpg.Pool,
) -> None:
    """Scope-creep guard from the other direction: a
    random principal cannot use the bootstrap policy to define
    policies. Only SYSTEM_PRINCIPAL_ID can. Operators wanting a
    different admin must first register an Actor as SYSTEM, then
    promote a real Policy permitting that Actor."""
    event_store = PostgresEventStore(db_pool)
    authorize = TrustAuthorize(event_store, policy_id=SYSTEM_BOOTSTRAP_POLICY_ID)
    rando = UUID("01900000-0000-7000-8000-000000000c01")

    result = await authorize.authorize(
        rando,
        "DefinePolicy",
        _NIL_CONDUIT,
        surface_id=SYSTEM_HTTP_SURFACE_ID,
    )
    assert isinstance(result, Deny)


@pytest.mark.integration
async def test_bootstrap_policy_id_is_a_fixed_constant() -> None:
    """The bootstrap UUID must be a code constant, not
    a Settings value. This test pins the exact UUID so a typo or
    refactor that changes it breaks loudly."""
    assert UUID("00000000-0000-0000-0000-000000000002") == SYSTEM_BOOTSTRAP_POLICY_ID


@pytest.mark.integration
async def test_bootstrap_policy_permitted_commands_match_real_handler_command_names() -> None:
    """Gate-review F7 (WI1 mitigation): pin that the command-name
    strings baked into the seed migration's payload match the actual
    `_COMMAND_NAME` constants in the handler modules. If
    `register_actor.handler._COMMAND_NAME` ever renames from
    "RegisterActor" without a compensating new migration, this test
    breaks loudly instead of the bootstrap workflow silently denying
    every fresh deployment's first API call."""
    from cora.access.features.register_actor.handler import (
        _COMMAND_NAME as REGISTER_ACTOR_COMMAND_NAME,  # pyright: ignore[reportPrivateUsage]
    )
    from cora.trust.features.define_policy.handler import (
        _COMMAND_NAME as DEFINE_POLICY_COMMAND_NAME,  # pyright: ignore[reportPrivateUsage]
    )

    seeded = {"DefinePolicy", "RegisterActor"}
    assert REGISTER_ACTOR_COMMAND_NAME in seeded
    assert DEFINE_POLICY_COMMAND_NAME in seeded


@pytest.mark.integration
async def test_concurrent_writes_against_bootstrap_stream_fail_loud(
    db_pool: asyncpg.Pool,
) -> None:
    """Adversarial: if any non-migration code tried to append to the
    bootstrap policy's stream (for example an operator running define_policy
    with `_POLICY_ID = SYSTEM_BOOTSTRAP_POLICY_ID` by accident), the
    `expected_version=0` optimistic concurrency check should reject
    it because version 1 is already there. This protects the seed
    from accidental overwrite via the normal handler path."""
    event_store = PostgresEventStore(db_pool)

    bogus_event = PolicyDefined(
        policy_id=SYSTEM_BOOTSTRAP_POLICY_ID,
        name="Accidental Overwrite Attempt",
        conduit_id=_NIL_CONDUIT,
        permitted_principal_ids=(UUID("01900000-0000-7000-8000-000000000d01"),),
        permitted_commands=("DefineEverything",),
        occurred_at=_NOW,
        surface_id=SYSTEM_HTTP_SURFACE_ID,
    )
    new_event = to_new_event(
        event_type=event_type_name(bogus_event),
        payload=to_payload(bogus_event),
        occurred_at=bogus_event.occurred_at,
        event_id=UUID("01900000-0000-7000-8000-000000000d02"),
        command_name="DefinePolicy",
        correlation_id=UUID("01900000-0000-7000-8000-000000000d03"),
        causation_id=None,
        principal_id=UUID("01900000-0000-7000-8000-000000000d04"),
    )

    with pytest.raises(ConcurrencyError):
        await event_store.append(
            stream_type="Policy",
            stream_id=SYSTEM_BOOTSTRAP_POLICY_ID,
            expected_version=0,  # caller thinks the stream is fresh; it isn't
            events=[new_event],
        )
