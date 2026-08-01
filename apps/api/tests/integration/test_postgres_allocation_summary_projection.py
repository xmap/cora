"""End-to-end: `proj_budget_allocation_summary` against real Postgres.

Exercises every AllocationSummaryProjection arm against the real
projection table, so the column names, the status CHECK, the
`ceiling_usd > 0` CHECK, and the ON CONFLICT idempotency are validated
against the schema rather than an AsyncMock:

  - AllocationGranted        -> INSERT row status=Granted, nullable
                                campaign_id, ceiling + note
  - AllocationGranted (again) -> ON CONFLICT DO NOTHING (no duplicate,
                                 no second row)
  - AllocationActivated      -> UPDATE status=Active, activated_at
  - AllocationCeilingUpdated -> UPDATE ceiling_usd (PUT semantics)
  - AllocationSealed         -> UPDATE status=Sealed, sealed_at,
                                spent_usd_at_seal
  - AllocationVoided (own row) -> UPDATE status=Voided
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.budget.projections.allocation import AllocationSummaryProjection
from cora.infrastructure.ports.event_store import StoredEvent

_NOW = datetime(2026, 7, 13, 12, 0, 0, tzinfo=UTC)
_LATER = datetime(2026, 7, 13, 18, 0, 0, tzinfo=UTC)


def _event(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Allocation",
        stream_id=UUID(payload["allocation_id"]),
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=datetime.fromisoformat(payload["occurred_at"]),
        recorded_at=datetime.fromisoformat(payload["occurred_at"]),
    )


async def _fetch(conn: Any, allocation_id: UUID) -> Any:
    return await conn.fetchrow(
        "SELECT * FROM proj_budget_allocation_summary WHERE allocation_id = $1",
        allocation_id,
    )


@pytest.mark.integration
async def test_lifecycle_arms_land_in_the_summary_table(db_pool: asyncpg.Pool) -> None:
    proj = AllocationSummaryProjection()
    allocation_id = uuid4()
    aid = str(allocation_id)
    campaign_id = uuid4()

    async with db_pool.acquire() as conn:
        await proj.apply(
            _event(
                "AllocationGranted",
                {
                    "allocation_id": aid,
                    "ceiling_usd": 500.0,
                    "campaign_id": str(campaign_id),
                    "note": "APS 2-BM award 2026-2",
                    "occurred_at": _NOW.isoformat(),
                },
            ),
            conn,
        )
        # A re-delivered genesis must not duplicate or overwrite.
        await proj.apply(
            _event(
                "AllocationGranted",
                {
                    "allocation_id": aid,
                    "ceiling_usd": 999.0,
                    "campaign_id": None,
                    "note": "should be ignored",
                    "occurred_at": _NOW.isoformat(),
                },
            ),
            conn,
        )
        row = await _fetch(conn, allocation_id)
        assert row["status"] == "Granted"
        assert float(row["ceiling_usd"]) == 500.0
        assert row["campaign_id"] == campaign_id
        assert row["note"] == "APS 2-BM award 2026-2"
        count = await conn.fetchval(
            "SELECT count(*) FROM proj_budget_allocation_summary WHERE allocation_id = $1",
            allocation_id,
        )
        assert count == 1

        await proj.apply(
            _event(
                "AllocationActivated",
                {"allocation_id": aid, "occurred_at": _NOW.isoformat()},
            ),
            conn,
        )
        await proj.apply(
            _event(
                "AllocationCeilingUpdated",
                {"allocation_id": aid, "ceiling_usd": 300.0, "occurred_at": _NOW.isoformat()},
            ),
            conn,
        )
        await proj.apply(
            _event(
                "AllocationSealed",
                {"allocation_id": aid, "spent_usd": 275.5, "occurred_at": _LATER.isoformat()},
            ),
            conn,
        )
        row = await _fetch(conn, allocation_id)
        assert row["status"] == "Sealed"
        assert float(row["ceiling_usd"]) == 300.0  # the update won
        assert row["activated_at"] is not None
        assert row["sealed_at"] == _LATER
        assert float(row["spent_usd_at_seal"]) == 275.5

        # clean up so a re-run of the suite starts fresh
        await conn.execute(
            "DELETE FROM proj_budget_allocation_summary WHERE allocation_id = $1",
            allocation_id,
        )


@pytest.mark.integration
async def test_voided_arm_updates_status(db_pool: asyncpg.Pool) -> None:
    proj = AllocationSummaryProjection()
    allocation_id = uuid4()
    aid = str(allocation_id)

    async with db_pool.acquire() as conn:
        await proj.apply(
            _event(
                "AllocationGranted",
                {
                    "allocation_id": aid,
                    "ceiling_usd": 100.0,
                    "campaign_id": None,
                    "note": "mistaken grant",
                    "occurred_at": _NOW.isoformat(),
                },
            ),
            conn,
        )
        await proj.apply(
            _event(
                "AllocationVoided",
                {"allocation_id": aid, "occurred_at": _NOW.isoformat()},
            ),
            conn,
        )
        row = await _fetch(conn, allocation_id)
        assert row["status"] == "Voided"
        await conn.execute(
            "DELETE FROM proj_budget_allocation_summary WHERE allocation_id = $1",
            allocation_id,
        )
