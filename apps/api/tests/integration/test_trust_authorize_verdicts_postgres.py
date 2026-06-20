"""End-to-end integration test: Verdict entries against real Postgres.

The first concrete entry type, exercised end-to-end:
  1. Define a Conduit (writes ConduitDefined + ConduitLogbookOpened to
     the events table on the Conduit's stream)
  2. Wire TrustAuthorize with a real PostgresVerdictStore
  3. Issue an Allow + a Deny against the Conduit
  4. Read back from entries_conduit_verdicts and verify the
     two rows landed with the right shape (typed columns survive
     jsonb-free round-trip; logbook_id matches the logbook opened
     in step 1)

Also exercises:
  - Idempotency: a retry with the same event_id is a no-op
  - The full upstream chain (ConduitDefined → ConduitLogbookOpened →
    TrustAuthorize lookup → entry write) lands transactionally
    correct against Postgres
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.infrastructure.adapters.postgres_event_store import PostgresEventStore
from cora.infrastructure.ports import (
    Allow,
    Deny,
    FakeClock,
    FixedIdGenerator,
)
from cora.trust.aggregates.conduit.entries import (
    PostgresVerdictStore,
    Verdict,
)
from cora.trust.authorize import TrustAuthorize
from cora.trust.features import define_conduit
from cora.trust.features.define_conduit import DefineConduit
from tests._authz import seed_policy
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-00000000c001")
_DENIED_PRINCIPAL = UUID("01900000-0000-7000-8000-00000000c002")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000000c003")
_SOURCE_ZONE = UUID("01900000-0000-7000-8000-00000000c0aa")
_TARGET_ZONE = UUID("01900000-0000-7000-8000-00000000c0bb")


async def _read_traversals(db_pool: asyncpg.Pool, conduit_id: UUID) -> list[asyncpg.Record]:
    async with db_pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT event_id, conduit_id, logbook_id, actor_id, command_name,
                   decision, reason, correlation_id, causation_id, occurred_at
            FROM entries_conduit_verdicts
            WHERE conduit_id = $1
            ORDER BY occurred_at, event_id
            """,
            conduit_id,
        )


@pytest.mark.integration
async def test_trust_authorize_persists_traversals_against_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """End-to-end: define a Conduit + Policy, wire TrustAuthorize with
    a real PostgresVerdictStore, exercise Allow + Deny, verify rows."""
    # Fresh ids for this test run (avoids collisions across reruns
    # against a shared template DB).
    conduit_id = UUID("01900000-0000-7000-8000-000000067a01")
    verdict_logbook_id = UUID("01900000-0000-7000-8000-000000067a02")
    define_conduit_event_id = UUID("01900000-0000-7000-8000-000000067a03")
    logbook_opened_event_id = UUID("01900000-0000-7000-8000-000000067a04")
    policy_id = UUID("01900000-0000-7000-8000-000000067a05")
    allow_entry_id = UUID("01900000-0000-7000-8000-000000067a07")
    deny_entry_id = UUID("01900000-0000-7000-8000-000000067a08")

    event_store = PostgresEventStore(db_pool)
    verdict_store = PostgresVerdictStore(db_pool)
    define_conduit_deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            conduit_id,
            verdict_logbook_id,
            define_conduit_event_id,
            logbook_opened_event_id,
        ],
        event_store=event_store,
    )

    # 1. Define the Conduit (writes ConduitDefined + ConduitLogbookOpened).
    returned_id = await define_conduit.bind(define_conduit_deps)(
        DefineConduit(
            name="Detector-to-Storage",
            source_zone_id=_SOURCE_ZONE,
            target_zone_id=_TARGET_ZONE,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_id == conduit_id

    # 2. Seed a Policy that gates `RegisterActor` for `_PRINCIPAL_ID`
    #    on this Conduit (so TrustAuthorize Allow/Deny is meaningful).
    await seed_policy(
        event_store,
        policy_id=policy_id,
        permitted_principal_ids={_PRINCIPAL_ID},
        permitted_commands={"RegisterActor"},
        conduit_id=conduit_id,
        occurred_at=_NOW,
    )

    # 3. Wire TrustAuthorize with the verdicts store + a fresh
    #    id-generator (separate from the one used for define_conduit
    #    so we get deterministic entry ids).
    authorize = TrustAuthorize(
        event_store,
        policy_id=policy_id,
        verdict_store=verdict_store,
        clock=FakeClock(_NOW),
        id_generator=FixedIdGenerator([allow_entry_id, deny_entry_id]),
    )

    # 4. One Allow, one Deny against the Conduit.
    allow_result = await authorize.authorize(_PRINCIPAL_ID, "RegisterActor", conduit_id)
    assert isinstance(allow_result, Allow)
    deny_result = await authorize.authorize(_DENIED_PRINCIPAL, "RegisterActor", conduit_id)
    assert isinstance(deny_result, Deny)

    # 5. Read back from the entries table.
    rows = await _read_traversals(db_pool, conduit_id)
    assert len(rows) == 2

    allow_row = next(r for r in rows if r["event_id"] == allow_entry_id)
    deny_row = next(r for r in rows if r["event_id"] == deny_entry_id)

    assert allow_row["conduit_id"] == conduit_id
    assert allow_row["logbook_id"] == verdict_logbook_id
    assert allow_row["actor_id"] == _PRINCIPAL_ID
    assert allow_row["command_name"] == "RegisterActor"
    assert allow_row["decision"] == "Allow"
    assert allow_row["reason"] is None
    assert allow_row["occurred_at"] == _NOW

    assert deny_row["conduit_id"] == conduit_id
    assert deny_row["logbook_id"] == verdict_logbook_id
    assert deny_row["actor_id"] == _DENIED_PRINCIPAL
    assert deny_row["decision"] == "Deny"
    assert deny_row["reason"] is not None
    assert "principal" in deny_row["reason"].lower()


@pytest.mark.integration
async def test_postgres_traversal_store_dedups_on_event_id(
    db_pool: asyncpg.Pool,
) -> None:
    """ON CONFLICT (event_id) DO NOTHING — producer retry is a no-op."""
    store = PostgresVerdictStore(db_pool)
    event_id = UUID("01900000-0000-7000-8000-000000068a01")
    conduit_id = UUID("01900000-0000-7000-8000-000000068a02")
    logbook_id = UUID("01900000-0000-7000-8000-000000068a03")

    first = Verdict(
        event_id=event_id,
        conduit_id=conduit_id,
        logbook_id=logbook_id,
        actor_id=uuid_for("01900000-0000-7000-8000-000000068a04"),
        command_name="StartRun",
        decision="Allow",
        reason=None,
        correlation_id=uuid_for("01900000-0000-7000-8000-000000068a05"),
        causation_id=None,
        occurred_at=_NOW,
    )
    # Different content, same event_id — must be dropped.
    second = Verdict(
        event_id=event_id,
        conduit_id=conduit_id,
        logbook_id=logbook_id,
        actor_id=uuid_for("01900000-0000-7000-8000-000000068a06"),
        command_name="DefinePolicy",
        decision="Deny",
        reason="other",
        correlation_id=uuid_for("01900000-0000-7000-8000-000000068a07"),
        causation_id=None,
        occurred_at=_NOW,
    )

    await store.append([first])
    await store.append([second])

    rows = await _read_traversals(db_pool, conduit_id)
    assert len(rows) == 1
    assert rows[0]["command_name"] == "StartRun"
    assert rows[0]["decision"] == "Allow"


def uuid_for(s: str) -> UUID:
    return UUID(s)
