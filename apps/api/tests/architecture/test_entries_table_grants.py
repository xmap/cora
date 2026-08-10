"""Every `entries_*` / `events` table created in migrations carries a
matching GRANT on cora_app.

Sibling of `test_projection_grants.py` (proj_* tables) and
`test_migration_revokes.py` (the REVOKE half of the same append-only
tables this file checks). `entries_*` migration headers have
historically claimed cora_app "gets SELECT + INSERT via ALTER DEFAULT
PRIVILEGES" (see e.g. `20260621040000_init_entries_run_feed_heartbeats.sql`);
that claim is FALSE for tables (the role-init migration's
`ALTER DEFAULT PRIVILEGES` covers sequences only, per
`20260512230000_init_role_cora_app.sql`), so several tables created
this way carry no working grant at all. `_GRANDFATHERED` lists the
tables already affected; fixing them is a separate, already-tracked
follow-up (a GRANT-only migration against a live production database),
not something to silently paper over here. This test's job is to make
sure the mistake stops recurring: every table NOT on that list must
carry an explicit GRANT.
"""

from __future__ import annotations

import re

import pytest

from tests.architecture.conftest import tracked_migration_files

_CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z_][a-zA-Z0-9_]*)",
    re.IGNORECASE,
)

# Tables confirmed (2026-08-10, alongside the enclosure permit probe
# trail's own migration review) to rely on the false ALTER DEFAULT
# PRIVILEGES claim and carry no working GRANT today. Do not add to this
# list going forward: a new table belongs in a migration with its own
# explicit GRANT, per the assertion message below.
_GRANDFATHERED = frozenset(
    {
        "entries_run_readings",
        "entries_operation_procedure_steps",
        "entries_run_feed_heartbeats",
        "entries_operation_procedure_diagnostics",
        "entries_operation_procedure_outcomes",
    }
)


def _all_migration_text() -> str:
    return "\n".join(f.read_text() for f in tracked_migration_files())


def _append_only_tables_created() -> set[str]:
    out: set[str] = set()
    for path in tracked_migration_files():
        for match in _CREATE_TABLE_RE.finditer(path.read_text()):
            name = match.group(1)
            if name == "events" or name.startswith("entries_"):
                out.add(name)
    return out


@pytest.mark.architecture
def test_every_new_entries_table_has_cora_app_grant() -> None:
    """Pattern accepted: `GRANT ... ON [TABLE] <table> ... TO cora_app`.

    Tables on `_GRANDFATHERED` are skipped: they predate this test and
    fixing them is a separate production migration, not a test change.
    A table that is renamed off the grandfathered list (its CREATE TABLE
    name changes) is NOT exempt under its new name; only the exact
    grandfathered identifiers are excused.
    """
    haystack = _all_migration_text()
    tables = _append_only_tables_created() - _GRANDFATHERED
    assert tables, (
        "No non-grandfathered append-only tables found; either the schema "
        "is empty, table-name detection is wrong, or _GRANDFATHERED has "
        "swallowed every table (check it against tracked_migration_files())."
    )

    missing: list[str] = []
    for table in sorted(tables):
        pattern = re.compile(
            rf"GRANT\b[^;]*\bON\s+(?:TABLE\s+)?{re.escape(table)}\b[^;]*\bTO\s+[^;]*cora_app\b",
            re.IGNORECASE | re.DOTALL,
        )
        if not pattern.search(haystack):
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
