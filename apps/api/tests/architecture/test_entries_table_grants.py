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

from tests.architecture.conftest import tracked_migration_files

_CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z_][a-zA-Z0-9_]*)",
    re.IGNORECASE,
)
_RENAME_TABLE_RE = re.compile(
    r"ALTER\s+TABLE\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+RENAME\s+TO\s+([a-zA-Z_][a-zA-Z0-9_]*)",
    re.IGNORECASE,
)

# Closed: the five tables that relied on the false ALTER DEFAULT
# PRIVILEGES claim all got an explicit GRANT in
# 20260810120000_grant_cora_app_entries_table_access.sql. Do not add to
# this list going forward: a new table belongs in a migration with its
# own explicit GRANT, per the assertion message below.
_GRANDFATHERED: frozenset[str] = frozenset()


def _all_migration_text() -> str:
    return "\n".join(f.read_text() for f in tracked_migration_files())


def _append_only_tables_created() -> dict[str, frozenset[str]]:
    """Every CURRENTLY append-only table, keyed by its CURRENT identifier
    and mapped to every name it has ever held.

    Follows `ALTER TABLE ... RENAME TO ...` across ALL tables' migration
    history, not just tables already matching `entries_`/`events`, then
    filters to that prefix only on the final (current) name. A table can
    enter the append-only family through a rename whose OLD name never
    matched the prefix: `entries_conduit_verdicts` was created as
    `observations_conduit_traversals`, renamed to
    `entries_conduit_traversals`, then renamed again to its current name.
    Gating the rename-follow on "old name already tracked as entries_/
    events" would silently drop that chain the moment the origin name
    fell outside the prefix, exactly the same blind spot this function
    exists to close for the `entries_run_readings` case (see below), just
    one hop earlier.

    The same walk gives the full lineage, not just the current name,
    which matters for the GRANT search: a privilege attaches to the
    table's OID, not its name, so a GRANT issued under an OLD name (e.g.
    `entries_decision_reasonings`, before it became
    `entries_decision_inferences`) remains valid forever and a rename
    never needs it re-issued under the new name. And the current-name
    requirement matters for correctness in the other direction: a GRANT
    written TODAY must target the table's current name (e.g.
    `entries_run_observations`, not the dead `entries_run_readings`), the
    only name that actually exists in the database by the time a later
    migration runs.
    """
    lineage: dict[str, set[str]] = {}
    for path in tracked_migration_files():
        text = path.read_text()
        for match in _CREATE_TABLE_RE.finditer(text):
            name = match.group(1)
            lineage.setdefault(name, {name})
        for match in _RENAME_TABLE_RE.finditer(text):
            old_name, new_name = match.group(1), match.group(2)
            if old_name in lineage:
                names = lineage.pop(old_name)
                names.add(new_name)
                lineage[new_name] = names
    return {
        name: frozenset(names)
        for name, names in lineage.items()
        if name == "events" or name.startswith("entries_")
    }


@pytest.mark.architecture
def test_every_new_entries_table_has_cora_app_grant() -> None:
    """Pattern accepted: `GRANT ... ON [TABLE] <name> ... TO cora_app`,
    where `<name>` is any name in the table's rename lineage (see
    `_append_only_tables_created`), not just its current one. Tables on
    `_GRANDFATHERED` are skipped: they predate this test and fixing them
    is a separate production migration, not a test change.
    """
    haystack = _all_migration_text()
    lineages = _append_only_tables_created()
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
