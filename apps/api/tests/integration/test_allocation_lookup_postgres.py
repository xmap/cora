"""Integration tests for `PostgresAllocationLookup` over `proj_budget_allocation_summary`.

Seeds projection rows by direct INSERT (the read model has no store
abstraction; the projection worker is the only production writer) and
verifies the Active-only contract: the lookup answers with the single
Active envelope, ignoring Granted and terminal rows, and resolves an
anomalous Active overlap to the newest-activated row.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.budget.adapters import PostgresAllocationLookup

_GRANTED_AT = datetime(2026, 7, 10, tzinfo=UTC)
_T1 = datetime(2026, 7, 11, tzinfo=UTC)
_T2 = datetime(2026, 7, 12, tzinfo=UTC)

_INSERT_SQL = """
INSERT INTO proj_budget_allocation_summary
    (allocation_id, ceiling_usd, campaign_id, note, status,
     granted_at, activated_at, created_at)
VALUES ($1, $2, $3, 'FY26 imaging award', $4, $5, $6, $5)
"""


async def _insert_row(
    pool: asyncpg.Pool,
    *,
    allocation_id: UUID,
    status: str,
    activated_at: datetime | None = None,
    ceiling_usd: float = 25000.0,
    campaign_id: UUID | None = None,
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            _INSERT_SQL,
            allocation_id,
            ceiling_usd,
            campaign_id,
            status,
            _GRANTED_AT,
            activated_at,
        )


@pytest.mark.integration
async def test_active_envelope_wins_over_granted_and_sealed_siblings(
    db_pool: asyncpg.Pool,
) -> None:
    """A dormant grant and a sealed predecessor never shadow the one
    open window: only the Active row arms the gate."""
    active_id = uuid4()
    campaign_id = uuid4()
    await _insert_row(db_pool, allocation_id=uuid4(), status="Granted")
    await _insert_row(db_pool, allocation_id=uuid4(), status="Sealed", activated_at=_T1)
    await _insert_row(
        db_pool,
        allocation_id=active_id,
        status="Active",
        activated_at=_T2,
        ceiling_usd=12000.0,
        campaign_id=campaign_id,
    )

    result = await PostgresAllocationLookup(db_pool).find_active()

    assert result is not None
    assert result.allocation_id == active_id
    assert result.ceiling_usd == 12000.0
    assert result.activated_at == _T2
    assert result.campaign_id == campaign_id


@pytest.mark.integration
async def test_newest_activated_wins_on_anomalous_active_overlap(
    db_pool: asyncpg.Pool,
) -> None:
    """At-most-one-Active is best-effort at grant/activate; if two
    rows are ever Active the most recently opened window is the
    operator's current intent."""
    newer_id = uuid4()
    await _insert_row(db_pool, allocation_id=uuid4(), status="Active", activated_at=_T1)
    await _insert_row(db_pool, allocation_id=newer_id, status="Active", activated_at=_T2)

    result = await PostgresAllocationLookup(db_pool).find_active()

    assert result is not None
    assert result.allocation_id == newer_id


@pytest.mark.integration
async def test_no_active_envelope_returns_none(db_pool: asyncpg.Pool) -> None:
    """Granted-only and terminal rows leave the envelope check
    disarmed: None means no constraint."""
    await _insert_row(db_pool, allocation_id=uuid4(), status="Granted")
    await _insert_row(db_pool, allocation_id=uuid4(), status="Voided")

    result = await PostgresAllocationLookup(db_pool).find_active()

    assert result is None


@pytest.mark.integration
async def test_empty_table_returns_none(db_pool: asyncpg.Pool) -> None:
    result = await PostgresAllocationLookup(db_pool).find_active()

    assert result is None
