"""Every `entries_*` / `events` table created in migrations carries a
matching GRANT on cora_app.

Sibling of `test_projection_grants.py` (proj_* tables) and
`test_migration_revokes.py` (the REVOKE half of the same append-only
tables this file checks). `entries_*` migration headers have
historically claimed cora_app "gets SELECT + INSERT via ALTER DEFAULT
PRIVILEGES" (see e.g. `20260621040000_init_entries_run_feed_heartbeats.sql`);
that claim is FALSE for tables (the role-init migration's
`ALTER DEFAULT PRIVILEGES` covers sequences only, per
`20260512230000_init_role_cora_app.sql`). Five tables created this way
carried no working grant at all; `20260810120000_grant_cora_app_entries_table_access.sql`
closed the gap with a purely additive GRANT-only migration, so
`_GRANDFATHERED` is empty again. This test's job is to make sure the
mistake stops recurring: every entries_*/events table must carry an
explicit GRANT.
"""

from __future__ import annotations

import re

import pytest

from tests.architecture.conftest import append_only_table_lineage, tracked_migration_files

# Closed: the five tables that relied on the false ALTER DEFAULT
# PRIVILEGES claim all got an explicit GRANT in
# 20260810120000_grant_cora_app_entries_table_access.sql. Do not add to
# this list going forward: a new table belongs in a migration with its
# own explicit GRANT, per the assertion message below.
_GRANDFATHERED: frozenset[str] = frozenset()


def _all_migration_text() -> str:
    return "\n".join(f.read_text() for f in tracked_migration_files())


@pytest.mark.architecture
def test_every_new_entries_table_has_cora_app_grant() -> None:
    """Pattern accepted: `GRANT ... ON [TABLE] <name> ... TO cora_app`,
    where `<name>` is any name in the table's rename lineage (see
    `append_only_table_lineage`), not just its current one. Tables on
    `_GRANDFATHERED` are skipped: they predate this test and fixing them
    is a separate production migration, not a test change.
    """
    haystack = _all_migration_text()
    lineages = append_only_table_lineage()
    tables = set(lineages) - _GRANDFATHERED
    assert tables, (
        "No non-grandfathered append-only tables found; either the schema "
        "is empty, table-name detection is wrong, or _GRANDFATHERED has "
        "swallowed every table (check it against tracked_migration_files())."
    )

    missing: list[str] = []
    for table in sorted(tables):
        if not any(
            re.search(
                rf"GRANT\b[^;]*\bON\s+(?:TABLE\s+)?{re.escape(name)}\b[^;]*\bTO\s+[^;]*cora_app\b",
                haystack,
                re.IGNORECASE | re.DOTALL,
            )
            for name in lineages[table]
        ):
            missing.append(table)

    assert not missing, (
        "entries_* / events tables missing a GRANT on cora_app:\n"
        + "\n".join(f"  - {t}" for t in missing)
        + "\n\nAdd a `GRANT SELECT, INSERT ON <table> TO cora_app;` statement "
        "to the migration that creates the table. Do NOT add the table to "
        "_GRANDFATHERED instead: that list is closed to the tables already "
        "affected by the ALTER DEFAULT PRIVILEGES mistake this test exists "
        "to stop repeating."
    )
