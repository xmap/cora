"""Integration test: the slice-E.1 migration adds the lifecycle date
and reserved persistent_id columns to `proj_equipment_asset_summary`.

Pins the column shape declared in
`20260603130000_add_asset_summary_persistent_id.sql`:

  - commissioned_at TIMESTAMPTZ NULL
  - decommissioned_at TIMESTAMPTZ NULL
  - persistent_id JSONB NULL

The migration runs in the testcontainer's template DB (see
`tests/conftest.py`), so the per-test `db_pool` already has every
migration applied. The tests below assert column presence + type
against that live schema.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import asyncpg
import pytest

_COLUMN_SHAPES = (
    ("commissioned_at", "timestamp with time zone", "YES"),
    ("decommissioned_at", "timestamp with time zone", "YES"),
    ("persistent_id", "jsonb", "YES"),
)


@pytest.mark.integration
@pytest.mark.parametrize(
    ("column_name", "expected_type", "expected_nullable"),
    _COLUMN_SHAPES,
)
async def test_proj_equipment_asset_summary_carries_pidinst_columns(
    db_pool: asyncpg.Pool,
    column_name: str,
    expected_type: str,
    expected_nullable: str,
) -> None:
    """Each of the three columns exists with the expected type and is
    nullable (slice E.1 ships them as additive; persistent_id stays
    NULL until slice F's assign mutation writes it)."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'proj_equipment_asset_summary'
              AND column_name = $1
            """,
            column_name,
        )
    assert row is not None, f"proj_equipment_asset_summary is missing the {column_name!r} column"
    assert row["data_type"] == expected_type
    assert row["is_nullable"] == expected_nullable


@pytest.mark.integration
async def test_pidinst_columns_default_to_null_for_freshly_inserted_row(
    db_pool: asyncpg.Pool,
) -> None:
    """A bare INSERT against the table leaves persistent_id NULL and
    decommissioned_at NULL by default. commissioned_at depends on the
    projection writer (which passes the AssetRegistered.occurred_at);
    this test omits it from the INSERT to assert the default-NULL
    behavior."""
    from uuid import uuid4

    asset_id = uuid4()
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO proj_equipment_asset_summary
                (asset_id, name, tier, lifecycle, condition, parent_id, created_at)
            VALUES ($1, 'X', 'Unit', 'Commissioned', 'Nominal', NULL, now())
            """,
            asset_id,
        )
        row = await conn.fetchrow(
            """
            SELECT commissioned_at, decommissioned_at, persistent_id
            FROM proj_equipment_asset_summary
            WHERE asset_id = $1
            """,
            asset_id,
        )
    assert row is not None
    assert row["commissioned_at"] is None
    assert row["decommissioned_at"] is None
    assert row["persistent_id"] is None
