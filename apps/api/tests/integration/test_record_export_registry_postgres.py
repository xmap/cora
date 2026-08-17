"""Integration test: the entries-tier registry against a live schema.

AST enumeration can prove a `*LogbookOpened` class exists; it cannot
prove the table or columns the registry names for it are real, because
renames defeat it. Three of these nine tables have already been
renamed (see `project_record_is_two_tier.md`), so this test queries
`information_schema` directly against the fully-migrated template
database and fails if `_registry.py` still points at a name from before
a rename.

Also exercises the reader end to end: for a table with zero rows scoped
to a random id, the reader returns an empty list rather than raising,
which is the shape the exporter needs to distinguish "this stream opened
a logbook with no entries yet" (Conduit's eager-open pattern) from a
registry or SQL error.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.record_export import EntriesTableSpec, all_specs


async def _columns(conn: asyncpg.Connection, table: str) -> set[str]:
    rows = await conn.fetch(
        "SELECT column_name FROM information_schema.columns WHERE table_name = $1",
        table,
    )
    return {row["column_name"] for row in rows}


@pytest.mark.integration
@pytest.mark.parametrize("spec", all_specs(), ids=lambda spec: spec.kind)
async def test_registered_table_exists_with_its_declared_columns(
    db_pool: asyncpg.Pool, spec: EntriesTableSpec
) -> None:
    async with db_pool.acquire() as conn:
        # PoolConnectionProxy and Connection expose the same runtime API;
        # narrowed here to match the `_columns` / EntriesReader signature,
        # per the postgres_profile_store.py convention.
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        exists = await pg_conn.fetchval(
            "SELECT count(*) FROM information_schema.tables WHERE table_name = $1",
            spec.table,
        )
        assert exists == 1, (
            f"kind={spec.kind!r} names table {spec.table!r}, which does not "
            "exist in the live schema. A migration rename that forgot to "
            "update _registry.py is exactly the failure mode this test "
            "exists to catch."
        )

        columns = await _columns(pg_conn, spec.table)
        needed = {spec.scope_column, *spec.order_by}
        missing = needed - columns
        assert not missing, (
            f"kind={spec.kind!r}: {spec.table!r} is missing column(s) "
            f"{sorted(missing)} that _registry.py's scope_column/order_by "
            "declare for it."
        )


@pytest.mark.integration
@pytest.mark.parametrize("spec", all_specs(), ids=lambda spec: spec.kind)
async def test_reader_returns_empty_list_for_an_unscoped_id(
    db_pool: asyncpg.Pool, spec: EntriesTableSpec
) -> None:
    """Self-classifying on `spec.scope_type`: a bare `uuid4()` bound
    against a TEXT scope column (`capture_probe`'s `capture_code`) is a
    type mismatch at the wire, so the dummy value's TYPE must match what
    the spec itself declares rather than assuming every spec is
    UUID-scoped."""
    dummy_scope_id: UUID | str = uuid4() if spec.scope_type is UUID else "no-such-capture-code"
    async with db_pool.acquire() as conn:
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        rows = await spec.reader(pg_conn, dummy_scope_id)
    assert rows == []
