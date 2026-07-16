"""Integration tests for `PostgresLanguageModelLookup` over `proj_agent_language_model_summary`.

Seeds projection rows by direct INSERT (the read model has no store
abstraction; the projection worker is the only production writer) and
verifies the approved-only contract: the lookup answers with the
newest APPROVED entry for an identity, so an unapproved newer entry
can never shadow an older Approved one into refusing agent
registration.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.agent.adapters import PostgresLanguageModelLookup

_PROVIDER = "anthropic"
_MODEL = "claude-sonnet-4-5"

_T1 = datetime(2026, 7, 10, tzinfo=UTC)
_T2 = datetime(2026, 7, 11, tzinfo=UTC)

_INSERT_SQL = """
INSERT INTO proj_agent_language_model_summary
    (language_model_id, name, provider, model, snapshot_pin, served_via,
     data_tier, archivability, status, created_at)
VALUES ($1, $2, $3, $4, $5, 'Direct', 'Internal', 'Alias', $6, $7)
"""


async def _insert_entry(
    pool: asyncpg.Pool,
    *,
    language_model_id: UUID,
    status: str,
    created_at: datetime,
    provider: str = _PROVIDER,
    model: str = _MODEL,
    snapshot_pin: str | None = None,
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            _INSERT_SQL,
            language_model_id,
            "Claude Sonnet 4.5",
            provider,
            model,
            snapshot_pin,
            status,
            created_at,
        )


@pytest.mark.integration
async def test_unapproved_newer_entry_does_not_shadow_older_approved(
    db_pool: asyncpg.Pool,
) -> None:
    """The shadow fix pinned: with an older Approved entry and a newer
    Defined one for the same identity, the lookup returns the Approved
    entry, so the gate keeps admitting the identity."""
    approved_id = uuid4()
    await _insert_entry(db_pool, language_model_id=approved_id, status="Approved", created_at=_T1)
    await _insert_entry(db_pool, language_model_id=uuid4(), status="Defined", created_at=_T2)

    result = await PostgresLanguageModelLookup(db_pool).find_by_model(
        provider=_PROVIDER,
        model=_MODEL,
    )

    assert result is not None
    assert result.language_model_id == approved_id
    assert result.status == "Approved"


@pytest.mark.integration
async def test_newest_approved_entry_wins_among_approved_siblings(
    db_pool: asyncpg.Pool,
) -> None:
    """Two Approved entries for one identity: the newer one is the
    current governance posture and its tiers are the answer."""
    newer_approved_id = uuid4()
    await _insert_entry(db_pool, language_model_id=uuid4(), status="Approved", created_at=_T1)
    await _insert_entry(
        db_pool, language_model_id=newer_approved_id, status="Approved", created_at=_T2
    )

    result = await PostgresLanguageModelLookup(db_pool).find_by_model(
        provider=_PROVIDER,
        model=_MODEL,
    )

    assert result is not None
    assert result.language_model_id == newer_approved_id


@pytest.mark.integration
async def test_identity_with_only_a_defined_entry_returns_none(db_pool: asyncpg.Pool) -> None:
    """None means "nothing currently approved for this identity": a
    Defined-only identity is cataloged but not yet usable by the gate."""
    await _insert_entry(db_pool, language_model_id=uuid4(), status="Defined", created_at=_T1)

    result = await PostgresLanguageModelLookup(db_pool).find_by_model(
        provider=_PROVIDER,
        model=_MODEL,
    )

    assert result is None


@pytest.mark.integration
async def test_unknown_identity_returns_none(db_pool: asyncpg.Pool) -> None:
    result = await PostgresLanguageModelLookup(db_pool).find_by_model(
        provider=_PROVIDER,
        model="claude-opus-4-1",
    )

    assert result is None
